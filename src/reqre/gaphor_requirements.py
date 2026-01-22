"""Import SysML requirements from Gaphor models and push to Neo4j."""

from __future__ import annotations

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
        "Install it with `pip install gaphor`."
    ) from exc


@dataclass(frozen=True)
class RequirementRecord:
    gaphor_id: str
    external_id: Optional[str]
    name: Optional[str]
    text: Optional[str]
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


def load_requirements_from_directory(path: str | Path) -> list[RequirementRecord]:
    """Load SysML requirements from all .gaphor files in a directory."""
    root = Path(path)
    if not root.is_dir():
        raise ValueError(f"{root} is not a directory.")

    records: list[RequirementRecord] = []
    for file_path in sorted(root.glob("*.gaphor")):
        records.extend(load_requirements_from_file(file_path))
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


def push_requirements_from_directory(
    client: Neo4jClient,
    path: str | Path,
) -> int:
    """Load requirements from a directory and push them to Neo4j."""
    requirements = load_requirements_from_directory(path)
    return push_requirements_to_neo4j(client, requirements)


def _record_to_params(record: RequirementRecord) -> dict[str, Any]:
    return {
        "gaphor_id": record.gaphor_id,
        "external_id": record.external_id,
        "name": record.name,
        "text": record.text,
        "source_file": record.source_file,
    }


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
