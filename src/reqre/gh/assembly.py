"""Assembly helpers for building GH components from Neo4j graphs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import rhino3dm as r3d

from . import util
from .evaluate import DEFAULT_COMPUTE_URL, GhEvaluationConfig, evaluate_definition
from .graph import (
    BuildingElement,
    BuildingElementEdge,
    fetch_building_element_edges,
    fetch_building_elements,
)
from .registry import GhDefinition, GhRegistry, normalize_gh_path

SOURCE_IFACE_KEYS = (
    "src_interface",
    "src_iface",
    "source_interface",
    "source_iface",
    "from_interface",
    "from_iface",
    "interface_src",
    "iface_src",
)
TARGET_IFACE_KEYS = (
    "dst_interface",
    "dst_iface",
    "target_interface",
    "target_iface",
    "to_interface",
    "to_iface",
    "interface_dst",
    "iface_dst",
)


def _default_interface_priority() -> dict[str, tuple[int, ...]]:
    return {
        "Abutment": (0, 1, 2),
        "Girder": (0, 1, 2, 3, 4, 5),
    }


def _default_params() -> dict[str, dict[str, Any]]:
    return {
        "Abutment": {
            "ABT_height": 2000.0,
            "ABT_width": 5000.0,
            "ABT_ledgewidth": 1000.0,
            "ABT_ledgeheight": 500.0,
            "ABT_offset": 500.0,
        },
        "Girder": {
            "GRD_length": 10000.0,
            "GRD_width": 5000.0,
            "GRD_height": 500.0,
            "GRD_offset1": 500.0,
            "GRD_offset2": 500.0,
        },
    }


def _default_interface_map() -> dict[tuple[str, str, str], tuple[Any, Any]]:
    return {
        ("Abutment", "SUPPORTS", "Girder"): ("ABT_interface2", "GRD_interface5"),
    }


@dataclass(frozen=True)
class AssemblyConfig:
    detail_level: str
    compute_url: str = DEFAULT_COMPUTE_URL
    gh_root: Path = Path("gh_samples")
    relationship_types: tuple[str, ...] = ("SUPPORTS",)
    allowed_definitions: tuple[str, ...] = ("Abutment", "Girder")
    interface_priority: dict[str, tuple[int, ...]] = field(
        default_factory=_default_interface_priority
    )
    default_params: dict[str, dict[str, Any]] = field(default_factory=_default_params)
    interface_map: dict[tuple[str, str, str], tuple[Any, Any]] = field(
        default_factory=_default_interface_map
    )
    start_element_id: int | None = None
    start_element_name: str | None = None
    allow_interface_reuse: bool = False
    flip_normals: bool = True


@dataclass
class AssemblyOutcome:
    connected: bool
    reason: str | None = None
    root_id: int | None = None
    order: list[int] = field(default_factory=list)
    components: dict[int, dict[str, Any]] = field(default_factory=dict)
    elements: dict[int, BuildingElement] = field(default_factory=dict)
    edges: list[BuildingElementEdge] = field(default_factory=list)
    missing_definitions: list[str] = field(default_factory=list)

    def breps(self) -> list[Any]:
        return [
            self.components[node_id]["brep"]
            for node_id in self.order
            if node_id in self.components
        ]


def assemble_from_graph(
    client,
    registry: GhRegistry,
    *,
    config: AssemblyConfig,
) -> AssemblyOutcome:
    elements = fetch_building_elements(client, detail_level=config.detail_level)
    edges = fetch_building_element_edges(
        client,
        detail_level=config.detail_level,
        relationship_types=config.relationship_types,
    )
    return assemble_elements(elements, edges, registry, config=config)


def assemble_elements(
    elements: Iterable[BuildingElement],
    edges: Iterable[BuildingElementEdge],
    registry: GhRegistry,
    *,
    config: AssemblyConfig,
) -> AssemblyOutcome:
    elements_by_id: dict[int, BuildingElement] = {}
    definitions: dict[int, GhDefinition] = {}
    missing_definitions: list[str] = []
    allowed = {name.lower() for name in config.allowed_definitions}

    for element in elements:
        if element.neo4j_id is None:
            continue
        definition = _resolve_definition(element, registry)
        if definition is None:
            missing_definitions.append(normalize_gh_path(element.gh_file))
            continue
        if allowed and definition.name.lower() not in allowed:
            continue
        elements_by_id[element.neo4j_id] = element
        definitions[element.neo4j_id] = definition

    filtered_edges = [
        edge
        for edge in edges
        if edge.src_id in elements_by_id and edge.dst_id in elements_by_id
    ]

    outcome = AssemblyOutcome(
        connected=False,
        elements=elements_by_id,
        edges=filtered_edges,
        missing_definitions=sorted(set(missing_definitions)),
    )

    if not elements_by_id:
        outcome.reason = "No matching BuildingElement nodes found."
        return outcome

    if not _is_fully_connected(elements_by_id.keys(), filtered_edges):
        outcome.reason = "BuildingElement graph is not fully connected."
        return outcome

    root_id = _choose_root(elements_by_id, definitions, config)
    outcome.root_id = root_id

    placed: dict[int, dict[str, Any]] = {}
    used_ifaces: dict[int, set[int]] = {}
    order: list[int] = []

    eval_config = GhEvaluationConfig(
        compute_url=config.compute_url, gh_root=config.gh_root
    )

    root_comp = _evaluate_component(
        elements_by_id[root_id],
        definitions[root_id],
        eval_config,
        config.default_params,
    )
    placed[root_id] = root_comp
    used_ifaces[root_id] = set()
    order.append(root_id)

    edges_by_node = _edges_by_node(elements_by_id.keys(), filtered_edges)

    pending = [root_id]
    while pending:
        current_id = pending.pop(0)
        current_comp = placed[current_id]
        current_def = current_comp["definition"]
        current_used = used_ifaces.setdefault(current_id, set())

        neighbors = sorted(
            edges_by_node.get(current_id, []),
            key=lambda edge: _neighbor_sort_key(edge, current_id, elements_by_id),
        )
        for edge in neighbors:
            neighbor_id = edge.other(current_id)
            if neighbor_id in placed:
                continue

            neighbor_def = definitions[neighbor_id]
            neighbor_comp = _evaluate_component(
                elements_by_id[neighbor_id],
                neighbor_def,
                eval_config,
                config.default_params,
            )
            neighbor_used = used_ifaces.setdefault(neighbor_id, set())

            src_hint, dst_hint = _edge_interface_hints(
                edge, current_id, config.interface_map, current_def, neighbor_def
            )

            src_idx = _pick_interface_index(
                current_def,
                current_comp["iface_list"],
                current_used,
                config.interface_priority.get(current_def.name, ()),
                src_hint,
                allow_reuse=config.allow_interface_reuse,
            )
            dst_idx = _pick_interface_index(
                neighbor_def,
                neighbor_comp["iface_list"],
                neighbor_used,
                config.interface_priority.get(neighbor_def.name, ()),
                dst_hint,
                allow_reuse=config.allow_interface_reuse,
            )

            target_plane = current_comp["iface_list"][src_idx]
            source_plane = neighbor_comp["iface_list"][dst_idx]
            if target_plane is None or source_plane is None:
                raise RuntimeError(
                    "Missing interface plane while assembling components "
                    f"(src={current_def.name}:{src_idx}, dst={neighbor_def.name}:{dst_idx})."
                )

            # if config.flip_normals:
            #     target_plane = _flip_plane(target_plane)
            #     source_plane = _flip_plane(source_plane)

            util.align_component(neighbor_comp, source_plane, target_plane)

            placed[neighbor_id] = neighbor_comp
            current_used.add(src_idx)
            neighbor_used.add(dst_idx)
            order.append(neighbor_id)
            pending.append(neighbor_id)

    outcome.connected = True
    outcome.components = placed
    outcome.order = order
    return outcome


def _resolve_definition(
    element: BuildingElement, registry: GhRegistry
) -> GhDefinition | None:
    definition = registry.get(element.gh_file)
    if definition is not None:
        return definition

    normalized = normalize_gh_path(element.gh_file).lower()
    for candidate in registry.all():
        if candidate.normalized_gh_file.lower() == normalized:
            return candidate

    if "abutment" in normalized:
        return _definition_by_name(registry, "Abutment")
    if "girder" in normalized:
        return _definition_by_name(registry, "Girder")
    return None


def _definition_by_name(registry: GhRegistry, name: str) -> GhDefinition | None:
    for definition in registry.all():
        if definition.name.lower() == name.lower():
            return definition
    return None


def _choose_root(
    elements: dict[int, BuildingElement],
    definitions: dict[int, GhDefinition],
    config: AssemblyConfig,
) -> int:
    if config.start_element_id is not None and config.start_element_id in elements:
        return config.start_element_id
    if config.start_element_name:
        for element_id, element in elements.items():
            if (element.name or "").lower() == config.start_element_name.lower():
                return element_id

    candidates = sorted(
        elements.items(),
        key=lambda item: ((item[1].name or "").lower(), item[0]),
    )
    for element_id, _ in candidates:
        definition = definitions.get(element_id)
        if definition and definition.name.lower() == "abutment":
            return element_id
    return candidates[0][0]


def _evaluate_component(
    element: BuildingElement,
    definition: GhDefinition,
    eval_config: GhEvaluationConfig,
    default_params: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    params.update(default_params.get(definition.name, {}))
    params.update(element.params)
    if definition.param_builder is not None:
        params = definition.param_builder(dict(params), dict(element.props))

    result = evaluate_definition(definition, params, config=eval_config)
    brep = result.brep
    if brep is None and definition.brep_output:
        breps = result.outputs.get(definition.brep_output, [])
        brep = breps[0] if breps else None
    if brep is None:
        raise RuntimeError(
            f"No brep returned for {definition.name} ({definition.gh_file})."
        )

    return {
        "element": element,
        "definition": definition,
        "params": params,
        "brep": brep,
        "iface_list": list(result.iface_list),
    }


def _edges_by_node(
    node_ids: Iterable[int],
    edges: Iterable[BuildingElementEdge],
) -> dict[int, list[BuildingElementEdge]]:
    adj: dict[int, list[BuildingElementEdge]] = {node_id: [] for node_id in node_ids}
    for edge in edges:
        if edge.src_id in adj:
            adj[edge.src_id].append(edge)
        if edge.dst_id in adj:
            adj[edge.dst_id].append(edge)
    return adj


def _is_fully_connected(
    node_ids: Iterable[int], edges: Iterable[BuildingElementEdge]
) -> bool:
    node_list = list(node_ids)
    if not node_list:
        return False
    if len(node_list) == 1:
        return True

    adjacency = {node_id: set() for node_id in node_list}
    for edge in edges:
        if edge.src_id in adjacency and edge.dst_id in adjacency:
            adjacency[edge.src_id].add(edge.dst_id)
            adjacency[edge.dst_id].add(edge.src_id)

    start = node_list[0]
    visited = set([start])
    queue = [start]
    while queue:
        current = queue.pop(0)
        for neighbor in adjacency[current]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    return len(visited) == len(node_list)


def _edge_interface_hints(
    edge: BuildingElementEdge,
    current_id: int,
    interface_map: dict[tuple[str, str, str], tuple[Any, Any]],
    current_def: GhDefinition,
    neighbor_def: GhDefinition,
) -> tuple[Any | None, Any | None]:
    mapping = _lookup_interface_map(
        interface_map, current_def.name, edge.rel_type, neighbor_def.name
    )
    if mapping is not None:
        return mapping
    reverse = _lookup_interface_map(
        interface_map, neighbor_def.name, edge.rel_type, current_def.name
    )
    if reverse is not None:
        return reverse[1], reverse[0]

    if current_id == edge.src_id:
        src_hint = _first_prop(edge.props, SOURCE_IFACE_KEYS)
        dst_hint = _first_prop(edge.props, TARGET_IFACE_KEYS)
    else:
        src_hint = _first_prop(edge.props, TARGET_IFACE_KEYS)
        dst_hint = _first_prop(edge.props, SOURCE_IFACE_KEYS)
    return src_hint, dst_hint


def _lookup_interface_map(
    interface_map: dict[tuple[str, str, str], tuple[Any, Any]],
    src_name: str,
    rel_type: str,
    dst_name: str,
) -> tuple[Any, Any] | None:
    for (src, rel, dst), pair in interface_map.items():
        if (
            src.lower() == src_name.lower()
            and rel.upper() == rel_type.upper()
            and dst.lower() == dst_name.lower()
        ):
            return pair
    return None


def _first_prop(props: dict[str, Any], keys: Iterable[str]) -> Any | None:
    for key in keys:
        if key in props:
            return props[key]
    return None


def _pick_interface_index(
    definition: GhDefinition,
    iface_list: list[Any],
    used: set[int],
    priority: Iterable[int],
    hint: Any | None,
    *,
    allow_reuse: bool,
) -> int:
    def _available(idx: int) -> bool:
        if idx < 0 or idx >= len(iface_list):
            return False
        if iface_list[idx] is None:
            return False
        if not allow_reuse and idx in used:
            return False
        return True

    if hint is not None:
        resolved = _resolve_interface_index(definition, hint)
        if resolved is None:
            raise RuntimeError(
                f"Could not resolve interface hint {hint!r} for {definition.name}."
            )
        if not _available(resolved):
            raise RuntimeError(
                f"Interface {resolved} not available for {definition.name}."
            )
        return resolved

    for idx in priority:
        if _available(idx):
            return idx
    for idx in range(len(iface_list)):
        if _available(idx):
            return idx

    raise RuntimeError(f"No available interface for {definition.name}.")


def _resolve_interface_index(definition: GhDefinition, hint: Any) -> int | None:
    if isinstance(hint, str):
        lowered = hint.lower()
        for idx, name in enumerate(definition.interface_outputs):
            if name.lower() == lowered:
                return idx
        digits = "".join(ch for ch in lowered if ch.isdigit())
        if digits:
            return _coerce_interface_index(
                int(digits),
                len(definition.interface_outputs),
                prefer_one_based=True,
            )
        return None
    if isinstance(hint, (int, float)):
        return _coerce_interface_index(
            int(hint),
            len(definition.interface_outputs),
            prefer_one_based=True,
        )
    return None


def _coerce_interface_index(
    value: int, count: int, *, prefer_one_based: bool
) -> int | None:
    if count <= 0:
        return None
    if prefer_one_based:
        if value == 0 and count > 0:
            return 0
        if 1 <= value <= count:
            return value - 1
        if 0 <= value < count:
            return value
    else:
        if 0 <= value < count:
            return value
        if 1 <= value <= count:
            return value - 1
    return None


def _neighbor_sort_key(
    edge: BuildingElementEdge,
    current_id: int,
    elements: dict[int, BuildingElement],
) -> tuple[str, int]:
    other_id = edge.other(current_id)
    element = elements.get(other_id)
    name = (element.name or "").lower() if element else ""
    return name, other_id


def _plane_normal(pl: r3d.Plane) -> r3d.Vector3d:
    return r3d.Vector3d.CrossProduct(pl.XAxis, pl.YAxis)


def _dot(a: r3d.Vector3d, b: r3d.Vector3d) -> float:
    return a.X * b.X + a.Y * b.Y + a.Z * b.Z


def _flip_plane(pl: r3d.Plane) -> r3d.Plane:
    x_axis = r3d.Vector3d(-pl.XAxis.X, -pl.XAxis.Y, -pl.XAxis.Z)
    return r3d.Plane(pl.Origin, x_axis, pl.YAxis)
