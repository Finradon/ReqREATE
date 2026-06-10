"""Import SysML requirements from Gaphor models and push to Neo4j."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

from reqre.neo4j import Neo4jClient

try:
    from gaphor.core.modeling import ElementFactory
    from gaphor.services.modelinglanguage import ModelingLanguageService
    from gaphor.storage.storage import load
    from gaphor.SysML.sysml import Requirement
except ImportError as exc:  # pragma: no cover - depends on optional runtime package
    raise ImportError(
        "gaphor is required to load .gaphor files. "
        "Install project dependencies with `uv sync`."
    ) from exc


@dataclass(frozen=True)
class RequirementRecord:
    gaphor_id: str
    external_id: Optional[str]
    name: Optional[str]
    text: Optional[str]
    source_file: str


@dataclass(frozen=True)
class RequirementRelationship:
    source_id: str
    target_id: str
    rel_type: str
    gaphor_id: str
    pair_index: int
    source_file: str


def load_requirements_from_file(path: str | Path) -> list[RequirementRecord]:
    """Load SysML requirements from a single .gaphor file."""
    source = str(Path(path))
    element_factory = ElementFactory()
    modeling_language = ModelingLanguageService()
    with open(source, "r", encoding="utf-8") as file_obj:
        load(file_obj, element_factory, modeling_language)

    requirements: list[RequirementRecord] = []
    for requirement in element_factory.select(Requirement):
        gaphor_id = _string_or_none(getattr(requirement, "id", None))
        if not gaphor_id:
            continue
        requirements.append(
            RequirementRecord(
                gaphor_id=gaphor_id,
                external_id=_string_or_none(
                    _get_attr(requirement, "externalId", "external_id")
                ),
                name=_string_or_none(_get_attr(requirement, "name")),
                text=_string_or_none(_get_attr(requirement, "text")),
                source_file=source,
            )
        )
    return requirements


def load_requirement_relationships_from_file(
    path: str | Path,
) -> list[RequirementRelationship]:
    """Load requirement-to-requirement relationships from a .gaphor file."""
    source = str(Path(path))
    element_factory = ElementFactory()
    modeling_language = ModelingLanguageService()
    with open(source, "r", encoding="utf-8") as file_obj:
        load(file_obj, element_factory, modeling_language)

    relationships: list[RequirementRelationship] = []
    for element in element_factory.lselect():
        if isinstance(element, Requirement):
            continue
        if element.__class__.__name__.endswith("Item"):
            continue
        rel_pairs = _extract_requirement_relations(element)
        if not rel_pairs:
            continue
        gaphor_id = _string_or_none(getattr(element, "id", None))
        if not gaphor_id:
            continue
        rel_type = _relation_type(element.__class__.__name__)
        if rel_type == "REFINE":
            rel_pairs = [(target, source) for source, target in rel_pairs]
        for index, (source_req, target_req) in enumerate(rel_pairs):
            relationships.append(
                RequirementRelationship(
                    source_id=_string_or_none(getattr(source_req, "id", None)) or "",
                    target_id=_string_or_none(getattr(target_req, "id", None)) or "",
                    rel_type=rel_type,
                    gaphor_id=gaphor_id,
                    pair_index=index,
                    source_file=source,
                )
            )
    return [
        rel
        for rel in relationships
        if rel.source_id and rel.target_id and rel.source_id != rel.target_id
    ]


def load_requirements_from_directory(path: str | Path) -> list[RequirementRecord]:
    """Load SysML requirements from all .gaphor files in a directory."""
    root = Path(path)
    if not root.is_dir():
        raise ValueError(f"{root} is not a directory.")

    records: list[RequirementRecord] = []
    for file_path in sorted(root.glob("*.gaphor")):
        records.extend(load_requirements_from_file(file_path))
    return records


def load_requirement_relationships_from_directory(
    path: str | Path,
) -> list[RequirementRelationship]:
    """Load requirement relationships from all .gaphor files in a directory."""
    root = Path(path)
    if not root.is_dir():
        raise ValueError(f"{root} is not a directory.")

    records: list[RequirementRelationship] = []
    for file_path in sorted(root.glob("*.gaphor")):
        records.extend(load_requirement_relationships_from_file(file_path))
    return records


def push_requirements_to_neo4j(
    client: Neo4jClient,
    requirements: Sequence[RequirementRecord],
) -> int:
    """Push requirements to Neo4j, keyed by Gaphor element id."""
    if not requirements:
        return 0

    query = """
    UNWIND $rows AS row
    MERGE (req:Requirement {gaphor_id: row.gaphor_id})
    SET req.external_id = row.external_id,
        req.name = row.name,
        req.text = row.text,
        req.source_file = row.source_file
    RETURN count(req) AS total
    """
    params = {"rows": [_record_to_params(record) for record in requirements]}
    rows = client.execute(query, params)
    if not rows:
        return 0
    return int(rows[0].get("total", 0))


def push_requirement_relationships_to_neo4j(
    client: Neo4jClient,
    relationships: Sequence[RequirementRelationship],
) -> int:
    """Push requirement relationships to Neo4j."""
    if not relationships:
        return 0

    grouped: dict[str, list[RequirementRelationship]] = {}
    for rel in relationships:
        grouped.setdefault(rel.rel_type, []).append(rel)

    total = 0
    for rel_type, rels in grouped.items():
        query = f"""
        UNWIND $rows AS row
        MATCH (src:Requirement {{gaphor_id: row.source_id}})
        MATCH (tgt:Requirement {{gaphor_id: row.target_id}})
        MERGE (src)-[rel:{rel_type} {{gaphor_id: row.gaphor_id, pair_index: row.pair_index}}]->(tgt)
        SET rel.source_file = row.source_file
        RETURN count(rel) AS total
        """
        params = {
            "rows": [
                {
                    "source_id": rel.source_id,
                    "target_id": rel.target_id,
                    "gaphor_id": rel.gaphor_id,
                    "pair_index": rel.pair_index,
                    "source_file": rel.source_file,
                }
                for rel in rels
            ]
        }
        rows = client.execute(query, params)
        if rows:
            total += int(rows[0].get("total", 0))
    return total


def push_requirements_from_directory(
    client: Neo4jClient,
    path: str | Path,
) -> int:
    """Load requirements from a directory and push them to Neo4j."""
    requirements = load_requirements_from_directory(path)
    return push_requirements_to_neo4j(client, requirements)


def push_requirement_relationships_from_directory(
    client: Neo4jClient,
    path: str | Path,
) -> int:
    """Load requirement relationships from a directory and push them to Neo4j."""
    relationships = load_requirement_relationships_from_directory(path)
    return push_requirement_relationships_to_neo4j(client, relationships)


def _record_to_params(record: RequirementRecord) -> dict[str, Any]:
    return {
        "gaphor_id": record.gaphor_id,
        "external_id": record.external_id,
        "name": record.name,
        "text": record.text,
        "source_file": record.source_file,
    }


def _extract_requirement_relations(element: Any) -> list[tuple[Any, Any]]:
    pairs: list[tuple[Any, Any]] = []
    for source_attr, target_attr in (
        ("sourceContext", "targetContext"),
        ("source", "target"),
        ("client", "supplier"),
    ):
        if not hasattr(element, source_attr) and not hasattr(element, target_attr):
            continue
        sources = _collect_requirements(getattr(element, source_attr, None))
        targets = _collect_requirements(getattr(element, target_attr, None))
        if not sources or not targets:
            continue
        for source in sources:
            for target in targets:
                pairs.append((source, target))
    return pairs


def _collect_requirements(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, Requirement):
        return [value]
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return [item for item in value if isinstance(item, Requirement)]
    return []


def _relation_type(name: str) -> str:
    cleaned = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", cleaned)
    return cleaned.upper()


def _get_attr(obj: Any, *names: str) -> Any:
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    return None


def _string_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
