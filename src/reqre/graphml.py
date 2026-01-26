"""GraphML serialization for DPO rules."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

import networkx as nx

from reqre.rules import DpoRule, RuleGraph

_ROLE_ATTR = "reqre_roles"
_PROPS_ATTR = "reqre_props"
_LABELS_ATTR = "reqre_labels"
_EDGE_KEY_ATTR = "reqre_edge_key"
_FORMAT_ATTR = "reqre_format"
_VERSION_ATTR = "reqre_version"
_FORMAT_NAME = "reqre_dpo_rule"
_FORMAT_VERSION = "1"
_ROLE_NAMES = ("left", "interface", "right")


class RuleGraphMLFormatError(ValueError):
    """Raised when GraphML input/output is invalid for DPO rules."""


def export_rule_graphml(rule: DpoRule, path: str | Path) -> None:
    """Export a DPO rule to a single GraphML file."""
    combined = nx.MultiDiGraph()
    combined.graph[_FORMAT_ATTR] = _FORMAT_NAME
    combined.graph[_VERSION_ATTR] = _FORMAT_VERSION
    combined.graph[_ROLE_ATTR] = ",".join(_ROLE_NAMES)

    for role, graph in (
        ("left", rule.left),
        ("interface", rule.interface),
        ("right", rule.right),
    ):
        _merge_graph(role, graph, combined)

    nx.write_graphml(combined, Path(path))


def import_rule_graphml(path: str | Path) -> DpoRule:
    """Load a DPO rule from a GraphML file."""
    graph = nx.read_graphml(Path(path))
    if not isinstance(graph, nx.MultiDiGraph):
        graph = nx.MultiDiGraph(graph)
    _validate_graph_metadata(graph)

    left = nx.MultiDiGraph()
    interface = nx.MultiDiGraph()
    right = nx.MultiDiGraph()
    role_map = {"left": left, "interface": interface, "right": right}

    for node_id, data in graph.nodes(data=True):
        roles = _parse_roles(data.get(_ROLE_ATTR), f"node {node_id}")
        node_attrs = _deserialize_attrs(data, context=f"node {node_id}")
        for role in roles:
            role_map[role].add_node(node_id, **node_attrs)

    for source, target, key, data in graph.edges(keys=True, data=True):
        roles = _parse_roles(data.get(_ROLE_ATTR), f"edge {source}->{target}")
        edge_attrs = _deserialize_attrs(data, context=f"edge {source}->{target}")
        edge_key = _read_edge_key(data, key, context=f"edge {source}->{target}")
        for role in roles:
            role_map[role].add_edge(source, target, key=edge_key, **edge_attrs)

    return DpoRule(left=left, interface=interface, right=right)


def _validate_graph_metadata(graph: RuleGraph) -> None:
    format_value = graph.graph.get(_FORMAT_ATTR)
    if format_value is not None and format_value != _FORMAT_NAME:
        raise RuleGraphMLFormatError(
            f"GraphML format '{format_value}' is not supported."
        )
    version_value = graph.graph.get(_VERSION_ATTR)
    if version_value is not None and str(version_value) != _FORMAT_VERSION:
        raise RuleGraphMLFormatError(
            f"GraphML format version '{version_value}' is not supported."
        )


def _merge_graph(role: str, graph: RuleGraph, combined: RuleGraph) -> None:
    if role not in _ROLE_NAMES:
        raise RuleGraphMLFormatError(f"Unknown role '{role}'")

    for node_id, data in graph.nodes(data=True):
        _merge_node(role, node_id, data, combined)

    for source, target, key, data in graph.edges(keys=True, data=True):
        _merge_edge(role, source, target, key, data, combined)


def _merge_node(
    role: str, node_id: Any, data: Mapping[str, Any], combined: RuleGraph
) -> None:
    if _ROLE_ATTR in data or _PROPS_ATTR in data or _LABELS_ATTR in data:
        raise RuleGraphMLFormatError(
            f"Node {node_id} uses reserved GraphML metadata keys."
        )

    if combined.has_node(node_id):
        existing = _deserialize_attrs(
            combined.nodes[node_id], context=f"node {node_id}"
        )
        incoming = _deserialize_attrs(data, context=f"node {node_id}")
        if existing != incoming:
            raise RuleGraphMLFormatError(
                f"Node {node_id} attributes conflict across rule graphs."
            )
        combined.nodes[node_id][_ROLE_ATTR] = _merge_roles_value(
            combined.nodes[node_id].get(_ROLE_ATTR), role
        )
        return

    node_attrs = _serialize_attrs(data, context=f"node {node_id}")
    node_attrs[_ROLE_ATTR] = role
    combined.add_node(node_id, **node_attrs)


def _merge_edge(
    role: str,
    source: Any,
    target: Any,
    key: Any,
    data: Mapping[str, Any],
    combined: RuleGraph,
) -> None:
    if _ROLE_ATTR in data or _PROPS_ATTR in data or _EDGE_KEY_ATTR in data:
        raise RuleGraphMLFormatError(
            f"Edge {source}->{target} uses reserved GraphML metadata keys."
        )

    if combined.has_edge(source, target, key=key):
        existing = _deserialize_attrs(
            combined.edges[source, target, key], context=f"edge {source}->{target}"
        )
        incoming = _deserialize_attrs(data, context=f"edge {source}->{target}")
        if existing != incoming:
            raise RuleGraphMLFormatError(
                f"Edge {source}->{target} attributes conflict across rule graphs."
            )
        combined.edges[source, target, key][_ROLE_ATTR] = _merge_roles_value(
            combined.edges[source, target, key].get(_ROLE_ATTR), role
        )
        return

    edge_attrs = _serialize_attrs(data, context=f"edge {source}->{target}")
    edge_attrs[_EDGE_KEY_ATTR] = _serialize_edge_key(
        key, context=f"edge {source}->{target}"
    )
    edge_attrs[_ROLE_ATTR] = role
    combined.add_edge(source, target, key=key, **edge_attrs)


def _merge_roles_value(value: Any, role: str) -> str:
    roles = set(_parse_roles(value, "existing roles"))
    roles.add(role)
    return ",".join(sorted(roles))


def _serialize_attrs(data: Mapping[str, Any], context: str) -> dict[str, Any]:
    result = dict(data)
    labels = result.pop("label", None)
    props = result.pop("props", None)
    if labels is not None:
        if isinstance(labels, str):
            result["label"] = labels
        else:
            label_list = _validate_labels(labels, context)
            result[_LABELS_ATTR] = json.dumps(label_list)
    if props is None:
        return result

    props_dict = _validate_props(props, context)
    result[_PROPS_ATTR] = json.dumps(props_dict, sort_keys=True)
    return result


def _deserialize_attrs(data: Mapping[str, Any], context: str) -> dict[str, Any]:
    result = dict(data)
    result.pop(_ROLE_ATTR, None)
    result.pop(_EDGE_KEY_ATTR, None)
    labels_value = result.pop(_LABELS_ATTR, None)
    if context.startswith("edge "):
        result.pop("id", None)

    if labels_value is not None:
        result["label"] = _parse_labels(labels_value, context)
    elif "label" in result:
        label_value = result["label"]
        if not isinstance(label_value, str):
            result["label"] = _parse_labels(label_value, context)

    if _PROPS_ATTR in result:
        props_value = result.pop(_PROPS_ATTR)
        result["props"] = _parse_props(props_value, context)
        return result

    if "props" in result:
        props_value = result["props"]
        if isinstance(props_value, Mapping):
            result["props"] = _validate_props(props_value, context)
        else:
            result["props"] = _parse_props(props_value, context)
    return result


def _serialize_edge_key(key: Any, context: str) -> str:
    try:
        return json.dumps(key)
    except TypeError as exc:
        raise RuleGraphMLFormatError(
            f"{context} edge key must be JSON-serializable."
        ) from exc


def _read_edge_key(value: Mapping[str, Any], fallback: Any, context: str) -> Any:
    if _EDGE_KEY_ATTR not in value:
        return fallback
    raw_key = value[_EDGE_KEY_ATTR]
    if not isinstance(raw_key, str):
        raise RuleGraphMLFormatError(f"{context} edge key must be a JSON string.")
    try:
        decoded = json.loads(raw_key)
    except json.JSONDecodeError as exc:
        raise RuleGraphMLFormatError(f"{context} edge key must be valid JSON.") from exc
    return fallback if decoded is None else decoded


def _validate_props(props: Any, context: str) -> dict[str, Any]:
    if not isinstance(props, Mapping):
        raise RuleGraphMLFormatError(f"{context} props must be a mapping.")
    if not all(isinstance(key, str) for key in props.keys()):
        raise RuleGraphMLFormatError(f"{context} props keys must be strings.")
    try:
        json.dumps(props)
    except TypeError as exc:
        raise RuleGraphMLFormatError(
            f"{context} props must be JSON-serializable."
        ) from exc
    return dict(props)


def _validate_labels(labels: Any, context: str) -> list[str]:
    if isinstance(labels, str):
        return [labels]
    if not isinstance(labels, (list, tuple, set)):
        raise RuleGraphMLFormatError(f"{context} labels must be strings or sequences.")
    cleaned: list[str] = []
    for label in labels:
        if not isinstance(label, str):
            raise RuleGraphMLFormatError(f"{context} labels must be strings.")
        cleaned.append(label)
    return cleaned


def _parse_labels(value: Any, context: str) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return _validate_labels(value, context)
    if not isinstance(value, str):
        raise RuleGraphMLFormatError(f"{context} labels must be a JSON string.")
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as exc:
        raise RuleGraphMLFormatError(f"{context} labels must be valid JSON.") from exc
    return _validate_labels(decoded, context)


def _parse_props(value: Any, context: str) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return _validate_props(value, context)
    if not isinstance(value, str):
        raise RuleGraphMLFormatError(f"{context} props must be a JSON string.")
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as exc:
        raise RuleGraphMLFormatError(f"{context} props must be valid JSON.") from exc
    return _validate_props(decoded, context)


def _parse_roles(value: Any, context: str) -> set[str]:
    if value is None:
        raise RuleGraphMLFormatError(
            f"{context} is missing required '{_ROLE_ATTR}' metadata."
        )

    if isinstance(value, str):
        roles = {role.strip() for role in value.split(",") if role.strip()}
    elif isinstance(value, Iterable):
        roles = {str(role).strip() for role in value if str(role).strip()}
    else:
        raise RuleGraphMLFormatError(
            f"{context} '{_ROLE_ATTR}' metadata must be a string."
        )

    invalid = sorted(role for role in roles if role not in _ROLE_NAMES)
    if invalid:
        raise RuleGraphMLFormatError(
            f"{context} has unknown roles: {', '.join(invalid)}"
        )
    if not roles:
        raise RuleGraphMLFormatError(f"{context} has no roles assigned.")
    return roles
