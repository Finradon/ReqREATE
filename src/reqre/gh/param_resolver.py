"""Resolve and persist cross-element GH parameters from graph constraints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from reqre.neo4j import Neo4jClient

from .assembly import AssemblyConfig

_D1_PAIR_QUERY = """
MATCH (a:BuildingElement:AbutmentElement)-[r:INTERFACES]->(g:BuildingElement:GirderElement)
WHERE a.detail_level = 'D1'
  AND g.detail_level = 'D1'
  AND a.gh_file = 'gh_samples/abutment_d1.gh'
  AND g.gh_file IN ['gh_samples/Girder.gh', 'gh_samples/girder_D1.gh']
RETURN DISTINCT
  elementId(a) AS abutment_id,
  elementId(g) AS girder_id,
  properties(a) AS abutment_props,
  properties(g) AS girder_props,
  r.dst_interface AS dst_interface
ORDER BY abutment_id, girder_id, dst_interface
"""

_D1_BOUND_PARAM_QUERY = """
MATCH (n:BuildingElement)-[u:USES_PARAM]->(p:Parameter)
WHERE elementId(n) IN [$abutment_id, $girder_id]
RETURN elementId(n) AS node_id, u.input AS input, p.value AS value
ORDER BY node_id, input
"""

_D1_UPSERT_QUERY = """
MATCH (a:BuildingElement) WHERE elementId(a) = $abutment_id
MATCH (g:BuildingElement) WHERE elementId(g) = $girder_id
SET a += $abutment_param_props
SET g += $girder_param_props
MERGE (pw:Parameter:D1Constraint {pair_key: $pair_key, key: 'ABT_width_EQ_GRD_width'})
SET pw.value = $width,
    pw.unit = 'mm',
    pw.kind = 'equality',
    pw.updated_at = datetime()
MERGE (a)-[:USES_PARAM {input: 'ABT_width'}]->(pw)
MERGE (g)-[:USES_PARAM {input: 'GRD_width'}]->(pw)
MERGE (ph:Parameter:D1Constraint {pair_key: $pair_key, key: 'ABT_ledgeheight_EQ_GRD_height'})
SET ph.value = $ledge_height,
    ph.unit = 'mm',
    ph.kind = 'equality',
    ph.updated_at = datetime()
MERGE (a)-[:USES_PARAM {input: 'ABT_ledgeheight'}]->(ph)
MERGE (g)-[:USES_PARAM {input: 'GRD_height'}]->(ph)
MERGE (po:Parameter:D1Constraint {pair_key: $pair_key, key: 'ABT_offset_EQ_GRD_offset2'})
SET po.value = $offset,
    po.unit = 'mm',
    po.kind = 'equality',
    po.updated_at = datetime()
MERGE (a)-[:USES_PARAM {input: 'ABT_offset'}]->(po)
MERGE (g)-[:USES_PARAM {input: 'GRD_offset2'}]->(po)
"""

_D1_SYNC_BOUND_PARAM_VALUES_QUERY = """
MATCH (n:BuildingElement)-[u:USES_PARAM]->(p:Parameter)
WHERE elementId(n) IN [$abutment_id, $girder_id]
WITH n, u, p,
CASE
  WHEN elementId(n) = $abutment_id AND u.input = 'ABT_width' THEN $ABT_width
  WHEN elementId(n) = $girder_id AND u.input = 'GRD_width' THEN $GRD_width
  WHEN elementId(n) = $abutment_id AND u.input = 'ABT_ledgeheight' THEN $ABT_ledgeheight
  WHEN elementId(n) = $girder_id AND u.input = 'GRD_height' THEN $GRD_height
  WHEN elementId(n) = $abutment_id AND u.input = 'ABT_ledgewidth' THEN $ABT_ledgewidth
  WHEN elementId(n) = $girder_id AND u.input = 'GRD_offset1' THEN $GRD_offset1
  WHEN elementId(n) = $abutment_id AND u.input = 'ABT_offset' THEN $ABT_offset
  WHEN elementId(n) = $girder_id AND u.input = 'GRD_offset2' THEN $GRD_offset2
  ELSE null
END AS resolved_value
WHERE resolved_value IS NOT NULL
SET p.value = resolved_value,
    p.unit = coalesce(p.unit, 'mm'),
    p.updated_at = datetime()
"""

_D1_UPSERT_ONLY_GH_PARAMS_QUERY = """
MATCH (a:BuildingElement) WHERE elementId(a) = $abutment_id
MATCH (g:BuildingElement) WHERE elementId(g) = $girder_id
SET a += $abutment_param_props
SET g += $girder_param_props
"""


@dataclass(frozen=True)
class D1ResolvedPair:
    abutment_id: str
    girder_id: str
    pair_key: str
    dst_interface: str | None
    abutment_updates: dict[str, float]
    girder_updates: dict[str, float]

    @property
    def width(self) -> float:
        return self.abutment_updates["ABT_width"]

    @property
    def ledge_height(self) -> float:
        return self.abutment_updates["ABT_ledgeheight"]

    @property
    def offset(self) -> float:
        return self.abutment_updates["ABT_offset"]


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


def _extract_param_map(props: Mapping[str, Any]) -> dict[str, Any]:
    params: dict[str, Any] = {}
    params.update(_coerce_param_map(props.get("gh_params")))
    params.update(_coerce_param_map(props.get("params")))
    for key, value in props.items():
        if key.startswith("param_") and len(key) > len("param_"):
            params[key[len("param_") :]] = value
    return params


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _pick_float(*values: Any) -> float | None:
    for value in values:
        resolved = _as_float(value)
        if resolved is not None:
            return resolved
    return None


def _resolve_d1_pair_values(
    abutment_props: Mapping[str, Any],
    girder_props: Mapping[str, Any],
    abutment_bound: Mapping[str, float],
    girder_bound: Mapping[str, float],
    abutment_defaults: Mapping[str, Any],
    girder_defaults: Mapping[str, Any],
) -> tuple[dict[str, float], dict[str, float]]:
    abutment_params = _extract_param_map(abutment_props)
    girder_params = _extract_param_map(girder_props)

    width = _pick_float(
        abutment_bound.get("ABT_width"),
        girder_bound.get("GRD_width"),
        abutment_params.get("ABT_width"),
        girder_params.get("GRD_width"),
        abutment_defaults.get("ABT_width"),
        girder_defaults.get("GRD_width"),
    )
    ledge_height = _pick_float(
        abutment_bound.get("ABT_ledgeheight"),
        girder_bound.get("GRD_height"),
        abutment_params.get("ABT_ledgeheight"),
        girder_params.get("GRD_height"),
        abutment_defaults.get("ABT_ledgeheight"),
        girder_defaults.get("GRD_height"),
    )
    ledge_width = _pick_float(
        abutment_bound.get("ABT_ledgewidth"),
        abutment_params.get("ABT_ledgewidth"),
        abutment_defaults.get("ABT_ledgewidth"),
    )
    if ledge_width is None:
        existing_offset1 = _pick_float(
            girder_bound.get("GRD_offset1"),
            girder_params.get("GRD_offset1"),
            girder_defaults.get("GRD_offset1"),
        )
        if existing_offset1 is not None:
            ledge_width = existing_offset1 * 2.0

    offset = _pick_float(
        abutment_bound.get("ABT_offset"),
        girder_bound.get("GRD_offset2"),
        abutment_params.get("ABT_offset"),
        girder_params.get("GRD_offset2"),
        abutment_defaults.get("ABT_offset"),
        girder_defaults.get("GRD_offset2"),
    )

    missing: list[str] = []
    if width is None:
        missing.append("ABT_width/GRD_width")
    if ledge_height is None:
        missing.append("ABT_ledgeheight/GRD_height")
    if ledge_width is None:
        missing.append("ABT_ledgewidth")
    if offset is None:
        missing.append("ABT_offset/GRD_offset2")
    if missing:
        raise RuntimeError(
            "Could not resolve D1 abutment/girder parameters. Missing: "
            + ", ".join(missing)
        )

    girder_offset1 = ledge_width / 2.0
    abutment_updates = {
        "ABT_width": width,
        "ABT_ledgeheight": ledge_height,
        "ABT_ledgewidth": ledge_width,
        "ABT_offset": offset,
    }
    girder_updates = {
        "GRD_width": width,
        "GRD_height": ledge_height,
        "GRD_offset1": girder_offset1,
        "GRD_offset2": offset,
    }
    return abutment_updates, girder_updates


def _assert_compatible(
    seen_girder_updates: dict[str, dict[str, float]],
    girder_id: str,
    updates: Mapping[str, float],
) -> None:
    existing = seen_girder_updates.get(girder_id)
    if existing is None:
        seen_girder_updates[girder_id] = dict(updates)
        return
    for key, value in updates.items():
        previous = existing.get(key)
        if previous is None:
            existing[key] = value
            continue
        if abs(previous - value) > 1e-9:
            raise RuntimeError(
                "Conflicting resolved value for Girder "
                f"{girder_id} parameter {key}: {previous} vs {value}"
            )


def _bound_params_for_pair(
    client: Neo4jClient, *, abutment_id: str, girder_id: str
) -> tuple[dict[str, float], dict[str, float]]:
    rows = client.execute(
        _D1_BOUND_PARAM_QUERY,
        {"abutment_id": abutment_id, "girder_id": girder_id},
    )
    abutment_bound: dict[str, float] = {}
    girder_bound: dict[str, float] = {}
    for row in rows:
        node_id = row.get("node_id")
        input_name = row.get("input")
        value = _as_float(row.get("value"))
        if node_id is None or not isinstance(input_name, str) or value is None:
            continue
        if node_id == abutment_id:
            abutment_bound[input_name] = value
        elif node_id == girder_id:
            girder_bound[input_name] = value
    return abutment_bound, girder_bound


def resolve_d1_parameters(
    client: Neo4jClient,
    *,
    write_shared_parameter_nodes: bool = True,
) -> list[D1ResolvedPair]:
    """Resolve D1 cross-element constraints and persist gh_params.

    This establishes the D1 constraint examples:
    - ABT_width == GRD_width
    - ABT_ledgeheight == GRD_height
    - GRD_offset1 == ABT_ledgewidth / 2
    - ABT_offset == GRD_offset2
    """

    defaults = AssemblyConfig(detail_level="D1").default_params
    abutment_defaults = defaults.get("Abutment", {})
    girder_defaults = defaults.get("Girder", {})

    rows = client.execute(_D1_PAIR_QUERY)
    seen_girder_updates: dict[str, dict[str, float]] = {}
    resolved: list[D1ResolvedPair] = []

    for row in rows:
        abutment_id = row.get("abutment_id")
        girder_id = row.get("girder_id")
        if not abutment_id or not girder_id:
            continue

        abutment_bound, girder_bound = _bound_params_for_pair(
            client, abutment_id=abutment_id, girder_id=girder_id
        )
        abutment_updates, girder_updates = _resolve_d1_pair_values(
            row.get("abutment_props") or {},
            row.get("girder_props") or {},
            abutment_bound,
            girder_bound,
            abutment_defaults,
            girder_defaults,
        )
        _assert_compatible(seen_girder_updates, girder_id, girder_updates)

        dst_interface = row.get("dst_interface")
        pair_key = f"{abutment_id}|{girder_id}|{dst_interface or ''}"
        abutment_param_props = {
            f"param_{key}": value for key, value in abutment_updates.items()
        }
        girder_param_props = {
            f"param_{key}": value for key, value in girder_updates.items()
        }
        abutment_param_props["param_resolver_d1_pair_key"] = pair_key
        girder_param_props["param_resolver_d1_pair_key"] = pair_key

        payload = {
            "abutment_id": abutment_id,
            "girder_id": girder_id,
            "pair_key": pair_key,
            "abutment_updates": abutment_updates,
            "girder_updates": girder_updates,
            "abutment_param_props": abutment_param_props,
            "girder_param_props": girder_param_props,
            "width": abutment_updates["ABT_width"],
            "ledge_height": abutment_updates["ABT_ledgeheight"],
            "offset": abutment_updates["ABT_offset"],
            "ABT_width": abutment_updates["ABT_width"],
            "GRD_width": girder_updates["GRD_width"],
            "ABT_ledgeheight": abutment_updates["ABT_ledgeheight"],
            "GRD_height": girder_updates["GRD_height"],
            "ABT_ledgewidth": abutment_updates["ABT_ledgewidth"],
            "GRD_offset1": girder_updates["GRD_offset1"],
            "ABT_offset": abutment_updates["ABT_offset"],
            "GRD_offset2": girder_updates["GRD_offset2"],
        }

        client.execute(_D1_SYNC_BOUND_PARAM_VALUES_QUERY, payload)

        if write_shared_parameter_nodes:
            client.execute(_D1_UPSERT_QUERY, payload)
        else:
            client.execute(_D1_UPSERT_ONLY_GH_PARAMS_QUERY, payload)

        resolved.append(
            D1ResolvedPair(
                abutment_id=abutment_id,
                girder_id=girder_id,
                pair_key=pair_key,
                dst_interface=dst_interface,
                abutment_updates=abutment_updates,
                girder_updates=girder_updates,
            )
        )

    return resolved
