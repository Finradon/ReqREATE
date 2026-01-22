"""Cypher serialization for DPO rules (create-only prototype)."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

from reqre.rules import DpoRule, RuleGraph

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class RuleSerializationError(ValueError):
    """Raised when a rule cannot be serialized under current constraints."""


@dataclass(frozen=True)
class CypherQuery:
    query: str
    params: dict[str, Any]


@dataclass(frozen=True)
class _EdgeRecord:
    source: Any
    target: Any
    key: Any
    data: Mapping[str, Any]


@dataclass(frozen=True)
class _RulePlan:
    created_nodes: list[Any]
    created_edges: list[_EdgeRecord]


class _ParamBuilder:
    def __init__(self) -> None:
        self.params: dict[str, Any] = {}

    def add(self, scope: str, key: str, value: Any) -> str:
        scope_clean = _sanitize_identifier(scope)
        key_clean = _sanitize_identifier(key)
        base = "_".join(part for part in (scope_clean, key_clean) if part)
        if not base:
            base = "p"
        name = base
        counter = 1
        while name in self.params:
            name = f"{base}_{counter}"
            counter += 1
        self.params[name] = value
        return f"${name}"


def rule_to_cypher(rule: DpoRule) -> CypherQuery:
    """Serialize a create-only DPO rule into Cypher."""
    plan = _build_plan(rule)

    used_vars: set[str] = set()
    node_vars: dict[Any, str] = {}
    for node_id in _sorted_nodes(rule.left):
        node_vars[node_id] = _make_node_var(node_id, used_vars)
    for node_id in plan.created_nodes:
        node_vars[node_id] = _make_node_var(node_id, used_vars)

    params = _ParamBuilder()
    match_patterns = _build_match_patterns(rule.left, node_vars, params)
    create_node_patterns = _build_create_nodes(
        rule.right, plan.created_nodes, node_vars, params
    )
    create_edge_patterns = _build_create_edges(plan.created_edges, node_vars, params)

    clauses: list[str] = []
    if match_patterns:
        clauses.append("MATCH " + ", ".join(match_patterns))
    if create_node_patterns:
        clauses.append("CREATE " + ", ".join(create_node_patterns))
    if create_edge_patterns:
        clauses.append("CREATE " + ", ".join(create_edge_patterns))

    return CypherQuery(query="\n".join(clauses), params=params.params)


def _build_plan(rule: DpoRule) -> _RulePlan:
    _validate_graphs(rule)

    left_nodes = set(rule.left.nodes)
    interface_nodes = set(rule.interface.nodes)
    right_nodes = set(rule.right.nodes)

    if interface_nodes != left_nodes:
        missing = left_nodes - interface_nodes
        if missing:
            raise RuleSerializationError(
                "Create-only rules do not support node deletion. "
                f"Nodes missing from interface: {sorted(missing, key=str)}"
            )
        extra = interface_nodes - left_nodes
        raise RuleSerializationError(
            "Interface must be a subgraph of left. "
            f"Extra interface nodes: {sorted(extra, key=str)}"
        )

    if not interface_nodes.issubset(right_nodes):
        extra = interface_nodes - right_nodes
        raise RuleSerializationError(
            "Interface nodes must exist in right graph. "
            f"Missing from right: {sorted(extra, key=str)}"
        )

    left_edges = _edge_multiset(rule.left, context="left")
    interface_edges = _edge_multiset(rule.interface, context="interface")
    if left_edges != interface_edges:
        raise RuleSerializationError(
            "Create-only rules require left and interface edges to match."
        )

    right_edges = _edge_multiset(rule.right, context="right")
    if not _multiset_is_subset(interface_edges, right_edges):
        raise RuleSerializationError(
            "Interface edges must be preserved in right graph."
        )

    created_nodes = sorted(right_nodes - interface_nodes, key=str)
    created_edges = _edge_difference(rule.right, interface_edges)

    return _RulePlan(created_nodes=created_nodes, created_edges=created_edges)


def _validate_graphs(rule: DpoRule) -> None:
    for name, graph in (
        ("left", rule.left),
        ("interface", rule.interface),
        ("right", rule.right),
    ):
        if not isinstance(graph, RuleGraph):
            raise RuleSerializationError(f"{name} must be a networkx.MultiDiGraph")


def _build_match_patterns(
    graph: RuleGraph, node_vars: Mapping[Any, str], params: _ParamBuilder
) -> list[str]:
    patterns: list[str] = []

    for node_id in _sorted_nodes(graph):
        data = graph.nodes[node_id]
        patterns.append(_node_pattern(node_id, data, node_vars, params, "left"))

    edges = _sorted_edges(graph)
    for index, edge in enumerate(edges):
        patterns.append(
            _match_edge_pattern(edge, node_vars, params, index, context="left")
        )

    return patterns


def _build_create_nodes(
    graph: RuleGraph,
    created_nodes: Sequence[Any],
    node_vars: Mapping[Any, str],
    params: _ParamBuilder,
) -> list[str]:
    patterns: list[str] = []
    for node_id in created_nodes:
        data = graph.nodes[node_id]
        patterns.append(_node_pattern(node_id, data, node_vars, params, "right"))
    return patterns


def _build_create_edges(
    created_edges: Sequence[_EdgeRecord],
    node_vars: Mapping[Any, str],
    params: _ParamBuilder,
) -> list[str]:
    patterns: list[str] = []
    for index, edge in enumerate(created_edges):
        patterns.append(
            _create_edge_pattern(edge, node_vars, params, index, context="right")
        )
    return patterns


def _node_pattern(
    node_id: Any,
    data: Mapping[str, Any],
    node_vars: Mapping[Any, str],
    params: _ParamBuilder,
    context: str,
) -> str:
    var = node_vars[node_id]
    node_context = f"{context} node {node_id}"
    labels = _labels_fragment(data.get("label"), context=node_context)
    props = _props_fragment(data.get("props"), params, var, context=node_context)
    return f"({var}{labels}{props})"


def _match_edge_pattern(
    edge: _EdgeRecord,
    node_vars: Mapping[Any, str],
    params: _ParamBuilder,
    index: int,
    context: str,
) -> str:
    return _edge_pattern(
        edge,
        node_vars=node_vars,
        params=params,
        index=index,
        context=context,
        require_type=False,
        allow_anonymous=True,
    )


def _create_edge_pattern(
    edge: _EdgeRecord,
    node_vars: Mapping[Any, str],
    params: _ParamBuilder,
    index: int,
    context: str,
) -> str:
    return _edge_pattern(
        edge,
        node_vars=node_vars,
        params=params,
        index=index,
        context=context,
        require_type=True,
        allow_anonymous=False,
    )


def _edge_pattern(
    edge: _EdgeRecord,
    *,
    node_vars: Mapping[Any, str],
    params: _ParamBuilder,
    index: int,
    context: str,
    require_type: bool,
    allow_anonymous: bool,
) -> str:
    source_var = node_vars[edge.source]
    target_var = node_vars[edge.target]
    edge_context = f"{context} edge {edge.source}->{edge.target}"
    rel_type = _normalize_rel_type(
        edge.data.get("type"), required=require_type, context=edge_context
    )
    rel_props = _normalize_props(edge.data.get("props"), context=edge_context)
    rel_scope = f"r{index}"
    rel_props_fragment = _props_fragment(
        rel_props, params, rel_scope, context=edge_context
    )

    rel_var = ""
    if not rel_type and rel_props and allow_anonymous:
        rel_var = rel_scope

    rel_type_fragment = f":{rel_type}" if rel_type else ""
    rel_body = f"{rel_var}{rel_type_fragment}{rel_props_fragment}"
    return f"({source_var})-[{rel_body}]->({target_var})"


def _labels_fragment(label_value: Any, *, context: str) -> str:
    labels = _normalize_labels(label_value, context=context)
    if not labels:
        return ""
    return ":" + ":".join(labels)


def _props_fragment(
    props: Mapping[str, Any],
    params: _ParamBuilder,
    scope: str,
    *,
    context: str,
) -> str:
    if not props:
        return ""
    entries = []
    for key in sorted(props.keys()):
        if not isinstance(key, str):
            raise RuleSerializationError(f"{context} property keys must be strings.")
        _validate_identifier("property key", key, context=context)
        param = params.add(scope, key, props[key])
        entries.append(f"{key}: {param}")
    return " {" + ", ".join(entries) + "}"


def _normalize_labels(value: Any, *, context: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        labels = [value]
    elif isinstance(value, (list, tuple, set)):
        labels = list(value)
    else:
        raise RuleSerializationError(f"{context} labels must be strings or sequences.")

    cleaned: list[str] = []
    for label in labels:
        if not isinstance(label, str):
            raise RuleSerializationError(f"{context} labels must be strings.")
        _validate_identifier("label", label, context=context)
        cleaned.append(label)
    return cleaned


def _normalize_rel_type(value: Any, *, required: bool, context: str) -> Optional[str]:
    if value is None:
        if required:
            raise RuleSerializationError(
                f"{context} relationships must define a type for creation."
            )
        return None
    if not isinstance(value, str):
        raise RuleSerializationError(f"{context} relationship types must be strings.")
    _validate_identifier("relationship type", value, context=context)
    return value


def _normalize_props(value: Any, *, context: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise RuleSerializationError(f"{context} props must be a mapping.")
    props: dict[str, Any] = {}
    for key, val in value.items():
        if not isinstance(key, str):
            raise RuleSerializationError(f"{context} prop keys must be strings.")
        _validate_identifier("property key", key, context=context)
        props[key] = val
    return props


def _validate_identifier(kind: str, value: str, *, context: str) -> None:
    if not _IDENTIFIER_RE.match(value):
        raise RuleSerializationError(
            f"{context} {kind} '{value}' is not a valid Cypher identifier."
        )


def _sanitize_identifier(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", value)
    return cleaned.strip("_").lower()


def _make_node_var(node_id: Any, used: set[str]) -> str:
    base = f"n_{_sanitize_identifier(str(node_id))}" or "n"
    if base == "n_":
        base = "n"
    name = base
    counter = 1
    while name in used or not name:
        name = f"{base}_{counter}"
        counter += 1
    used.add(name)
    return name


def _sorted_nodes(graph: RuleGraph) -> list[Any]:
    return sorted(graph.nodes, key=lambda item: str(item))


def _sorted_edges(graph: RuleGraph) -> list[_EdgeRecord]:
    edges = [
        _EdgeRecord(source=u, target=v, key=k, data=data)
        for u, v, k, data in graph.edges(keys=True, data=True)
    ]
    return sorted(edges, key=_edge_sort_key)


def _edge_sort_key(edge: _EdgeRecord) -> tuple[str, str, str, str, str]:
    rel_type = edge.data.get("type") or ""
    props = edge.data.get("props") or {}
    props_key = repr(_freeze_value(props))
    return (
        str(edge.source),
        str(edge.target),
        str(edge.key),
        str(rel_type),
        props_key,
    )


def _edge_descriptor(
    edge: _EdgeRecord, *, context: str
) -> tuple[Any, Any, Optional[str], tuple]:
    rel_type = _normalize_rel_type(
        edge.data.get("type"), required=False, context=context
    )
    props = _normalize_props(edge.data.get("props"), context=f"{context} edge")
    frozen_props = tuple(
        sorted((key, _freeze_value(val)) for key, val in props.items())
    )
    return (edge.source, edge.target, rel_type, frozen_props)


def _edge_multiset(graph: RuleGraph, *, context: str) -> Counter:
    counter: Counter = Counter()
    for edge in _sorted_edges(graph):
        counter[_edge_descriptor(edge, context=context)] += 1
    return counter


def _edge_difference(graph: RuleGraph, preserved_edges: Counter) -> list[_EdgeRecord]:
    remaining = Counter(preserved_edges)
    created: list[_EdgeRecord] = []
    for edge in _sorted_edges(graph):
        descriptor = _edge_descriptor(edge, context="right")
        if remaining[descriptor] > 0:
            remaining[descriptor] -= 1
        else:
            created.append(edge)
    return created


def _multiset_is_subset(left: Counter, right: Counter) -> bool:
    for key, count in left.items():
        if right.get(key, 0) < count:
            return False
    return True


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return tuple(sorted((key, _freeze_value(val)) for key, val in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(val) for val in value)
    if isinstance(value, set):
        return tuple(sorted(_freeze_value(val) for val in value))
    try:
        hash(value)
    except TypeError:
        return repr(value)
    return value
