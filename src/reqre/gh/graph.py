"""Neo4j helpers for Grasshopper evaluation discovery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from reqre.neo4j import Neo4jClient

from .registry import GhDefinition, GhRegistry, normalize_gh_path


@dataclass(frozen=True)
class BuildingElement:
    neo4j_id: int
    gh_file: str
    name: str | None
    detail_level: str | None
    params: dict[str, Any]
    props: dict[str, Any]


@dataclass(frozen=True)
class GhGraphRequirements:
    elements: list[BuildingElement]
    elements_by_file: dict[str, list[BuildingElement]]
    definitions: dict[str, GhDefinition]
    missing_files: list[str]


def _coerce_param_map(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        import json

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _extract_params(props: dict[str, Any]) -> dict[str, Any]:
    params: dict[str, Any] = {}
    params.update(_coerce_param_map(props.get("gh_params")))
    params.update(_coerce_param_map(props.get("params")))

    for key, value in props.items():
        if key.startswith("param_") and len(key) > len("param_"):
            params[key[len("param_") :]] = value
    return params


def fetch_building_elements(client: Neo4jClient) -> list[BuildingElement]:
    query = (
        "MATCH (n:BuildingElement) "
        "WHERE exists(n.gh_file) "
        "RETURN id(n) AS neo4j_id, n.name AS name, n.gh_file AS gh_file, "
        "n.detail_level AS detail_level, properties(n) AS props"
    )
    rows = client.execute(query)
    elements: list[BuildingElement] = []

    for row in rows:
        props = row.get("props") or {}
        gh_file = props.get("gh_file") or row.get("gh_file")
        if not gh_file:
            continue
        elements.append(
            BuildingElement(
                neo4j_id=row.get("neo4j_id"),
                gh_file=gh_file,
                name=row.get("name"),
                detail_level=row.get("detail_level"),
                params=_extract_params(props),
                props=props,
            )
        )
    return elements


def resolve_requirements(
    elements: list[BuildingElement], registry: GhRegistry
) -> GhGraphRequirements:
    elements_by_file: dict[str, list[BuildingElement]] = {}
    definitions: dict[str, GhDefinition] = {}
    missing_files: list[str] = []

    for element in elements:
        key = normalize_gh_path(element.gh_file)
        elements_by_file.setdefault(key, []).append(element)
        if key in definitions:
            continue
        definition = registry.get(key)
        if definition is None:
            missing_files.append(key)
        else:
            definitions[key] = definition

    return GhGraphRequirements(
        elements=elements,
        elements_by_file=elements_by_file,
        definitions=definitions,
        missing_files=sorted(set(missing_files)),
    )


def load_requirements_from_graph(
    client: Neo4jClient, registry: GhRegistry
) -> GhGraphRequirements:
    elements = fetch_building_elements(client)
    return resolve_requirements(elements, registry)
