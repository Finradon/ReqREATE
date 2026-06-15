#!/usr/bin/env python3
"""Minimal Manim demo for applying a DPO rule to a host graph."""

from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import networkx as nx
import numpy as np
from manim import (
    BLUE_D,
    DOWN,
    GRAY_C,
    GREEN_D,
    ORIGIN,
    RED_D,
    TEAL_D,
    UP,
    WHITE,
    YELLOW,
    Arrow,
    Circle,
    Create,
    DiGraph,
    FadeIn,
    FadeOut,
    Indicate,
    Line,
    Scene,
    Text,
    TransformFromCopy,
    VGroup,
    Write,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
RULE_PATH = REPO_ROOT / "json_rules" / "requirements" / "satisfy_d1_1_bridge.json"

try:
    from reqre.rules import DpoRule, RuleGraph, add_edge, add_node
except ModuleNotFoundError:
    src_root = REPO_ROOT / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))
    from reqre.rules import DpoRule, RuleGraph, add_edge, add_node

EdgeSignature = tuple[str, str, str | None, str]


@dataclass(frozen=True)
class RenderedGraph:
    group: VGroup
    graph: DiGraph
    edge_labels: VGroup
    edge_label_map: dict[tuple[str, str], Text]


@dataclass(frozen=True)
class RulePanel:
    group: VGroup
    lhs: RenderedGraph
    rhs: RenderedGraph


@dataclass(frozen=True)
class LoadedRule:
    rule: DpoRule
    rule_id: str


def _load_rule(path: Path) -> LoadedRule:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rule = DpoRule.from_json(payload, validate=True)
    raw_rule_id = payload.get("rule_id")
    rule_id = str(raw_rule_id) if raw_rule_id else path.stem
    return LoadedRule(rule=rule, rule_id=rule_id)


def _build_mock_host_graph() -> RuleGraph:
    host = nx.MultiDiGraph()
    add_node(
        host,
        "req_d1_1",
        label="Requirement",
        props={"external_id": "D1.1"},
    )
    add_node(
        host,
        "req_context",
        label="Requirement",
        props={"external_id": "CTX.1"},
    )
    add_node(
        host,
        "fe_context",
        label="FunctionalElement",
        props={"name": "ContextSubsystem"},
    )
    add_edge(host, "req_context", "fe_context", rel_type="SATISFIES")
    return host


def _labels_to_set(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return {value}
    if isinstance(value, (list, tuple, set)):
        return {str(item) for item in value}
    return {str(value)}


def _node_matches(pattern: Mapping[str, Any], candidate: Mapping[str, Any]) -> bool:
    pattern_labels = _labels_to_set(pattern.get("label"))
    candidate_labels = _labels_to_set(candidate.get("label"))
    if pattern_labels and not pattern_labels.issubset(candidate_labels):
        return False

    pattern_props = pattern.get("props") or {}
    candidate_props = candidate.get("props") or {}
    if not isinstance(pattern_props, Mapping) or not isinstance(
        candidate_props, Mapping
    ):
        return False
    return all(
        candidate_props.get(key) == value for key, value in pattern_props.items()
    )


def _edge_matches(pattern: Mapping[str, Any], candidate: Mapping[str, Any]) -> bool:
    pattern_type = pattern.get("type")
    if pattern_type is not None and candidate.get("type") != pattern_type:
        return False

    pattern_props = pattern.get("props") or {}
    candidate_props = candidate.get("props") or {}
    if not isinstance(pattern_props, Mapping) or not isinstance(
        candidate_props, Mapping
    ):
        return False
    return all(
        candidate_props.get(key) == value for key, value in pattern_props.items()
    )


def _edge_sort_key(
    edge: tuple[str, str, Any, Mapping[str, Any]],
) -> tuple[str, str, str, str]:
    source, target, _, data = edge
    return (
        str(source),
        str(target),
        str(data.get("type", "")),
        json.dumps(data.get("props", {}), sort_keys=True),
    )


def _edges_match(
    pattern_graph: RuleGraph,
    host_graph: RuleGraph,
    node_mapping: Mapping[str, str],
) -> bool:
    used_host_edges: set[tuple[str, str, Any]] = set()
    for source, target, _, edge_data in sorted(
        pattern_graph.edges(keys=True, data=True),
        key=_edge_sort_key,
    ):
        mapped_source = node_mapping[source]
        mapped_target = node_mapping[target]
        candidates = host_graph.get_edge_data(mapped_source, mapped_target, default={})
        chosen_key = None
        for host_key, host_data in candidates.items():
            token = (mapped_source, mapped_target, host_key)
            if token in used_host_edges:
                continue
            if _edge_matches(edge_data, host_data):
                chosen_key = host_key
                break
        if chosen_key is None:
            return False
        used_host_edges.add((mapped_source, mapped_target, chosen_key))
    return True


def _find_graph_match(
    pattern_graph: RuleGraph,
    host_graph: RuleGraph,
    *,
    fixed_mapping: Mapping[str, str] | None = None,
) -> dict[str, str] | None:
    node_order = sorted(pattern_graph.nodes, key=str)
    mapping: dict[str, str] = dict(fixed_mapping or {})
    used_hosts: set[str] = set(mapping.values())

    for node_id, host_id in mapping.items():
        if node_id not in pattern_graph.nodes or host_id not in host_graph.nodes:
            return None
        if not _node_matches(pattern_graph.nodes[node_id], host_graph.nodes[host_id]):
            return None

    candidates: dict[str, list[str]] = {}
    for node_id in node_order:
        if node_id in mapping:
            continue
        options = [
            host_id
            for host_id, host_attrs in host_graph.nodes(data=True)
            if host_id not in used_hosts
            and _node_matches(pattern_graph.nodes[node_id], host_attrs)
        ]
        if not options:
            return None
        candidates[node_id] = sorted(options, key=str)

    def backtrack(index: int) -> dict[str, str] | None:
        if index >= len(node_order):
            if _edges_match(pattern_graph, host_graph, mapping):
                return dict(mapping)
            return None

        node_id = node_order[index]
        if node_id in mapping:
            return backtrack(index + 1)

        for host_id in candidates[node_id]:
            if host_id in used_hosts:
                continue
            mapping[node_id] = host_id
            used_hosts.add(host_id)
            found = backtrack(index + 1)
            if found is not None:
                return found
            used_hosts.remove(host_id)
            del mapping[node_id]
        return None

    return backtrack(0)


def _nac_blocks(
    rule: DpoRule, host_graph: RuleGraph, left_match: Mapping[str, str]
) -> bool:
    for nac in rule.nacs:
        fixed = {
            node_id: left_match[node_id]
            for node_id in nac.nodes
            if node_id in left_match
        }
        if _find_graph_match(nac, host_graph, fixed_mapping=fixed) is not None:
            return True
    return False


def _edge_signature(source: str, target: str, data: Mapping[str, Any]) -> EdgeSignature:
    edge_type = data.get("type")
    edge_type_text = str(edge_type) if edge_type is not None else None
    props_key = json.dumps(data.get("props", {}), sort_keys=True, separators=(",", ":"))
    return (str(source), str(target), edge_type_text, props_key)


def _edge_multiset(graph: RuleGraph) -> Counter[EdgeSignature]:
    counts: Counter[EdgeSignature] = Counter()
    for source, target, _, data in graph.edges(keys=True, data=True):
        counts[_edge_signature(source, target, data)] += 1
    return counts


def _fresh_node_id(graph: RuleGraph, base: str) -> str:
    if base not in graph.nodes:
        return base
    index = 1
    while True:
        candidate = f"{base}_{index}"
        if candidate not in graph.nodes:
            return candidate
        index += 1


def _remove_one_edge(
    graph: RuleGraph,
    source: str,
    target: str,
    edge_type: str | None,
    props_key: str,
) -> bool:
    data = graph.get_edge_data(source, target, default={})
    for key, attrs in data.items():
        candidate_sig = _edge_signature(source, target, attrs)
        if candidate_sig[2] == edge_type and candidate_sig[3] == props_key:
            graph.remove_edge(source, target, key=key)
            return True
    return False


def _copy_node_attrs(attrs: Mapping[str, Any]) -> dict[str, Any]:
    copied: dict[str, Any] = {}
    if "label" in attrs:
        copied["label"] = attrs["label"]
    if "props" in attrs:
        copied["props"] = json.loads(json.dumps(attrs["props"]))
    return copied


def _apply_rule_once(
    rule: DpoRule,
    host_graph: RuleGraph,
    left_match: Mapping[str, str],
) -> RuleGraph:
    updated = host_graph.copy()

    left_nodes = set(rule.left.nodes)
    interface_nodes = set(rule.interface.nodes)
    right_nodes = set(rule.right.nodes)

    deleted_nodes = sorted(left_nodes - interface_nodes, key=str)
    created_nodes = sorted(right_nodes - interface_nodes, key=str)

    deleted_edges = _edge_multiset(rule.left) - _edge_multiset(rule.interface)
    created_edges = _edge_multiset(rule.right) - _edge_multiset(rule.interface)

    for (source, target, edge_type, props_key), count in deleted_edges.items():
        mapped_source = left_match[source]
        mapped_target = left_match[target]
        for _ in range(count):
            removed = _remove_one_edge(
                updated,
                mapped_source,
                mapped_target,
                edge_type=edge_type,
                props_key=props_key,
            )
            if not removed:
                raise RuntimeError("Could not remove an expected edge from host graph.")

    for node_id in deleted_nodes:
        updated.remove_node(left_match[node_id])

    right_to_host: dict[str, str] = dict(left_match)
    for node_id in created_nodes:
        host_id = _fresh_node_id(updated, node_id)
        right_to_host[node_id] = host_id
        updated.add_node(host_id, **_copy_node_attrs(rule.right.nodes[node_id]))

    for (source, target, edge_type, props_key), count in created_edges.items():
        mapped_source = right_to_host[source]
        mapped_target = right_to_host[target]
        props = json.loads(props_key)
        edge_attrs: dict[str, Any] = {}
        if edge_type is not None:
            edge_attrs["type"] = edge_type
        if props:
            edge_attrs["props"] = props
        for _ in range(count):
            updated.add_edge(mapped_source, mapped_target, **edge_attrs)

    return updated


def _graph_layout(before: RuleGraph, after: RuleGraph) -> dict[str, np.ndarray]:
    union = nx.DiGraph()
    union.add_nodes_from(before.nodes)
    union.add_nodes_from(after.nodes)
    union.add_edges_from((source, target) for source, target in before.edges())
    union.add_edges_from((source, target) for source, target in after.edges())

    layout = nx.spring_layout(union, seed=13, k=1.3)
    return {
        node_id: np.array([float(pos[0]) * 4.4, float(pos[1]) * 2.6, 0.0])
        for node_id, pos in layout.items()
    }


def _single_graph_layout(
    graph: RuleGraph,
    *,
    seed: int,
    scale_x: float,
    scale_y: float,
) -> dict[str, np.ndarray]:
    simple = nx.DiGraph()
    simple.add_nodes_from(graph.nodes)
    simple.add_edges_from((source, target) for source, target in graph.edges())
    if simple.number_of_nodes() == 0:
        return {}
    if simple.number_of_nodes() == 1:
        only_node = next(iter(simple.nodes))
        return {str(only_node): ORIGIN.copy()}

    layout = nx.spring_layout(simple, seed=seed, k=1.15)
    return {
        str(node_id): np.array([float(pos[0]) * scale_x, float(pos[1]) * scale_y, 0.0])
        for node_id, pos in layout.items()
    }


def _node_text(node_id: str, attrs: Mapping[str, Any]) -> str:
    del node_id
    labels = _labels_to_set(attrs.get("label"))
    if "Requirement" not in labels:
        return ""
    props = attrs.get("props") or {}
    if isinstance(props, Mapping) and "external_id" in props:
        return str(props["external_id"])
    return "Requirement"


def _node_color(attrs: Mapping[str, Any], *, is_added: bool) -> str:
    if is_added:
        return GREEN_D
    labels = _labels_to_set(attrs.get("label"))
    if "Requirement" in labels:
        return BLUE_D
    if "FunctionalElement" in labels:
        return TEAL_D
    return GRAY_C


def _edge_type_labels(graph: RuleGraph) -> dict[tuple[str, str], str]:
    labels: dict[tuple[str, str], set[str]] = {}
    for source, target, _, data in graph.edges(keys=True, data=True):
        edge_type = data.get("type")
        if edge_type is None:
            continue
        pair = (str(source), str(target))
        labels.setdefault(pair, set()).add(str(edge_type))
    return {pair: "/".join(sorted(types)) for pair, types in labels.items()}


def _edge_pair_multiset(graph: RuleGraph) -> Counter[tuple[str, str]]:
    counts: Counter[tuple[str, str]] = Counter()
    for source, target, _, _ in graph.edges(keys=True, data=True):
        counts[(str(source), str(target))] += 1
    return counts


def _added_edge_pairs(before: RuleGraph, after: RuleGraph) -> set[tuple[str, str]]:
    additions = _edge_pair_multiset(after) - _edge_pair_multiset(before)
    return {pair for pair, count in additions.items() if count > 0}


def _edge_label_offset(start: np.ndarray, end: np.ndarray) -> np.ndarray:
    direction = end - start
    orthogonal = np.array([-direction[1], direction[0], 0.0])
    norm = np.linalg.norm(orthogonal)
    if norm < 1e-6:
        return np.array([0.0, 0.0, 0.0])
    return (orthogonal / norm) * 0.2


def _render_graph(
    graph: RuleGraph,
    layout: Mapping[str, np.ndarray],
    *,
    added_nodes: set[str] | None = None,
    added_edges: set[tuple[str, str]] | None = None,
) -> RenderedGraph:
    added_nodes = added_nodes or set()
    added_edges = added_edges or set()
    nodes = sorted((str(node_id) for node_id in graph.nodes), key=str)

    edge_pairs = sorted(
        {
            (str(source), str(target))
            for source, target, _, _ in graph.edges(keys=True, data=True)
        },
        key=lambda pair: (pair[0], pair[1]),
    )

    labels = {
        node_id: Text(
            _node_text(node_id, graph.nodes[node_id]), font_size=18, color=WHITE
        )
        for node_id in nodes
    }
    vertex_config = {
        node_id: {
            "fill_color": _node_color(
                graph.nodes[node_id], is_added=node_id in added_nodes
            ),
            "fill_opacity": 1.0,
            "stroke_color": WHITE,
            "stroke_width": 2.0,
            "radius": 0.24,
        }
        for node_id in nodes
    }
    edge_config = {
        pair: {
            "stroke_color": GREEN_D if pair in added_edges else GRAY_C,
            "stroke_width": 2.0,
        }
        for pair in edge_pairs
    }

    digraph = DiGraph(
        vertices=nodes,
        edges=edge_pairs,
        labels=labels,
        layout={node_id: layout[node_id] for node_id in nodes},
        vertex_config=vertex_config,
        edge_config=edge_config,
    )

    edge_type_map = _edge_type_labels(graph)
    edge_label_group = VGroup()
    edge_label_map: dict[tuple[str, str], Text] = {}
    for pair, edge_type in edge_type_map.items():
        if pair not in digraph.edges:
            continue
        start = digraph.vertices[pair[0]].get_center()
        end = digraph.vertices[pair[1]].get_center()
        midpoint = (start + end) / 2
        label = Text(
            edge_type,
            font_size=16,
            color=GREEN_D if pair in added_edges else WHITE,
        )
        label.move_to(midpoint + _edge_label_offset(start, end))
        edge_label_group.add(label)
        edge_label_map[pair] = label

    return RenderedGraph(
        group=VGroup(digraph, edge_label_group),
        graph=digraph,
        edge_labels=edge_label_group,
        edge_label_map=edge_label_map,
    )


def _edge_pairs(graph: RuleGraph) -> set[tuple[str, str]]:
    return {
        (str(source), str(target))
        for source, target, _, _ in graph.edges(keys=True, data=True)
    }


def _mapped_edge_pairs(
    pattern_graph: RuleGraph,
    node_mapping: Mapping[str, str],
) -> set[tuple[str, str]]:
    return {
        (str(node_mapping[source]), str(node_mapping[target]))
        for source, target, _, _ in pattern_graph.edges(keys=True, data=True)
    }


def _highlight_graph_elements(
    rendered: RenderedGraph,
    *,
    node_ids: set[str],
    edge_pairs: set[tuple[str, str]],
    color: str = YELLOW,
) -> VGroup:
    overlay = VGroup()
    for node_id in sorted(node_ids, key=str):
        if node_id not in rendered.graph.vertices:
            continue
        vertex = rendered.graph.vertices[node_id]
        ring = Circle(
            radius=(vertex.width * 0.72),
            color=color,
            stroke_width=4.0,
        )
        ring.move_to(vertex.get_center())
        overlay.add(ring)

    for pair in sorted(edge_pairs, key=lambda item: (item[0], item[1])):
        if pair not in rendered.graph.edges:
            continue
        edge_overlay = rendered.graph.edges[pair].copy()
        edge_overlay.set_color(color)
        edge_overlay.set_stroke(width=4.0)
        overlay.add(edge_overlay)
        label = rendered.edge_label_map.get(pair)
        if label is not None:
            label_overlay = label.copy()
            label_overlay.set_color(color)
            overlay.add(label_overlay)
    return overlay


def _collect_graph_elements(
    rendered: RenderedGraph,
    *,
    node_ids: set[str],
    edge_pairs: set[tuple[str, str]],
) -> VGroup:
    elements = VGroup()
    for node_id in sorted(node_ids, key=str):
        vertex = rendered.graph.vertices.get(node_id)
        if vertex is not None:
            elements.add(vertex)
    for pair in sorted(edge_pairs, key=lambda item: (item[0], item[1])):
        edge = rendered.graph.edges.get(pair)
        if edge is not None:
            elements.add(edge)
        label = rendered.edge_label_map.get(pair)
        if label is not None:
            elements.add(label)
    return elements


def _build_rule_panel(rule: DpoRule) -> RulePanel:
    lhs_layout = _single_graph_layout(rule.left, seed=19, scale_x=1.2, scale_y=0.9)
    rhs_layout = _single_graph_layout(rule.right, seed=23, scale_x=1.6, scale_y=1.15)
    created_nodes = {
        str(node_id) for node_id in set(rule.right.nodes) - set(rule.interface.nodes)
    }
    created_edges = _added_edge_pairs(rule.interface, rule.right)

    lhs = _render_graph(rule.left, lhs_layout)
    rhs = _render_graph(
        rule.right,
        rhs_layout,
        added_nodes=created_nodes,
        added_edges=created_edges,
    )

    lhs.group.shift(np.array([-1.95, -0.05, 0.0]))
    rhs.group.shift(np.array([1.95, -0.05, 0.0]))
    divider = Line(
        np.array([0.0, -2.1, 0.0]),
        np.array([0.0, 2.1, 0.0]),
        color=GRAY_C,
        stroke_width=1.4,
    )
    lhs_label = Text("LHS", font_size=20, color=WHITE).next_to(lhs.group, UP, buff=0.15)
    rhs_label = Text("RHS", font_size=20, color=WHITE).next_to(rhs.group, UP, buff=0.15)
    top_label = Text("LHS | RHS", font_size=24, color=WHITE).next_to(
        VGroup(lhs.group, rhs.group, divider), UP, buff=0.28
    )

    panel = VGroup(lhs.group, rhs.group, divider, lhs_label, rhs_label, top_label)
    return RulePanel(group=panel, lhs=lhs, rhs=rhs)


class HostRuleRewriteScene(Scene):
    """Apply satisfy_d1_1_bridge to a mock host graph and animate before/after."""

    def construct(self) -> None:
        loaded = _load_rule(RULE_PATH)
        rule = loaded.rule
        host_before = _build_mock_host_graph()

        left_match = _find_graph_match(rule.left, host_before)
        if left_match is None:
            raise RuntimeError("No valid LHS match found in mock host graph.")
        if _nac_blocks(rule, host_before, left_match):
            raise RuntimeError("NAC blocked the match in mock host graph.")

        host_after = _apply_rule_once(rule, host_before, left_match)

        added_nodes = {
            str(node_id) for node_id in set(host_after.nodes) - set(host_before.nodes)
        }
        added_edges = _added_edge_pairs(host_before, host_after)
        created_rule_nodes = {
            str(node_id)
            for node_id in set(rule.right.nodes) - set(rule.interface.nodes)
        }
        created_rule_edges = _added_edge_pairs(rule.interface, rule.right)

        host_layout = _graph_layout(host_before, host_after)
        host_center = _render_graph(host_before, host_layout)
        host_center_label = Text("Host graph", font_size=24).next_to(
            host_center.group, direction=DOWN
        )

        host_right_before = _render_graph(host_before, host_layout)
        host_right_before.group.shift(np.array([4.65, 0.0, 0.0]))
        host_right_before_label = Text("Copied host", font_size=24).next_to(
            host_right_before.group, direction=DOWN
        )

        host_right_after = _render_graph(
            host_after,
            host_layout,
            added_nodes=added_nodes,
            added_edges=added_edges,
        )
        host_right_after.group.shift(np.array([4.65, 0.0, 0.0]))
        host_right_after_label = Text("Transformed host", font_size=24).next_to(
            host_right_after.group, direction=DOWN
        )

        rule_panel = _build_rule_panel(rule)
        rule_panel.group.move_to(ORIGIN)
        rule_label = Text(f"Rule {loaded.rule_id}", font_size=26).next_to(
            rule_panel.group, direction=UP, buff=0.35
        )

        title = Text("Host-Graph Rule Application", font_size=32).to_edge(UP)

        self.play(Write(title))
        self.play(FadeIn(host_center.group), Write(host_center_label))

        self.play(
            host_center.group.animate.shift(np.array([-4.65, 0.0, 0.0])),
            host_center_label.animate.shift(np.array([-4.65, 0.0, 0.0])),
            run_time=1.0,
        )
        self.play(FadeIn(rule_panel.group), Write(rule_label))

        matched_host_nodes = {str(left_match[node_id]) for node_id in rule.left.nodes}
        matched_host_edges = _mapped_edge_pairs(rule.left, left_match)
        host_match_overlay = _highlight_graph_elements(
            host_center,
            node_ids=matched_host_nodes,
            edge_pairs=matched_host_edges,
            color=YELLOW,
        )
        lhs_match_overlay = _highlight_graph_elements(
            rule_panel.lhs,
            node_ids={str(node_id) for node_id in rule.left.nodes},
            edge_pairs=_edge_pairs(rule.left),
            color=YELLOW,
        )
        self.play(Create(host_match_overlay), Create(lhs_match_overlay))

        self.play(
            TransformFromCopy(host_center.group, host_right_before.group),
            Write(host_right_before_label),
            run_time=1.0,
        )

        rhs_overlay = _highlight_graph_elements(
            rule_panel.rhs,
            node_ids={str(node_id) for node_id in rule.right.nodes},
            edge_pairs=_edge_pairs(rule.right),
            color=GREEN_D,
        )
        self.play(Create(rhs_overlay))

        rewrite_arrow = Arrow(
            start=np.array([1.9, 0.0, 0.0]),
            end=np.array([3.2, 0.0, 0.0]),
            buff=0.08,
            stroke_width=2.2,
            max_tip_length_to_length_ratio=0.12,
            color=RED_D,
        )
        self.play(Create(rewrite_arrow), run_time=0.6)

        self.play(
            FadeOut(host_right_before.group, shift=np.array([0.4, 0.0, 0.0])),
            FadeOut(host_right_before_label, shift=np.array([0.4, 0.0, 0.0])),
            FadeIn(host_right_after.group, shift=np.array([0.4, 0.0, 0.0])),
            FadeIn(host_right_after_label, shift=np.array([0.4, 0.0, 0.0])),
            run_time=1.1,
        )

        rhs_created_source = _collect_graph_elements(
            rule_panel.rhs,
            node_ids=created_rule_nodes,
            edge_pairs=created_rule_edges,
        )
        transformed_targets = _collect_graph_elements(
            host_right_after,
            node_ids=added_nodes,
            edge_pairs=added_edges,
        )
        if (
            len(rhs_created_source.submobjects) > 0
            and len(transformed_targets.submobjects) > 0
        ):
            self.play(
                TransformFromCopy(rhs_created_source, transformed_targets),
                run_time=1.0,
            )
            self.play(Indicate(transformed_targets, color=GREEN_D), run_time=0.7)

        self.play(
            host_match_overlay.animate.set_stroke(width=2.0).set_opacity(0.45),
            lhs_match_overlay.animate.set_stroke(width=2.0).set_opacity(0.45),
            rhs_overlay.animate.set_stroke(width=2.0).set_opacity(0.45),
            rewrite_arrow.animate.set_stroke(width=1.8).set_opacity(0.7),
            run_time=0.7,
        )
        self.wait(1.5)
