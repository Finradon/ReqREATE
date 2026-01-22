from pathlib import Path

import networkx as nx
import pytest

from reqre.graphml import (
    RuleGraphMLFormatError,
    export_rule_graphml,
    import_rule_graphml,
)
from reqre.rules import DpoRule, add_edge, add_node


def _assert_graph_equal(left: nx.MultiDiGraph, right: nx.MultiDiGraph) -> None:
    assert set(left.nodes) == set(right.nodes)
    for node_id in left.nodes:
        assert left.nodes[node_id] == right.nodes[node_id]

    assert set(left.edges(keys=True)) == set(right.edges(keys=True))
    for source, target, key, data in left.edges(keys=True, data=True):
        assert right.edges[source, target, key] == data


def test_graphml_round_trip(tmp_path: Path) -> None:
    left = nx.MultiDiGraph()
    interface = nx.MultiDiGraph()
    right = nx.MultiDiGraph()

    add_node(left, "req1", label="Requirement", props={"id": "REQ-1"})
    add_node(interface, "req1", label="Requirement", props={"id": "REQ-1"})
    add_node(right, "req1", label="Requirement", props={"id": "REQ-1"})
    add_node(right, "comp1", label="Component", props={"name": "Beam"})
    add_edge(right, "req1", "comp1", rel_type="SATISFIES", props={"strength": 10})

    rule = DpoRule(left=left, interface=interface, right=right)
    path = tmp_path / "rule.graphml"

    export_rule_graphml(rule, path)
    loaded = import_rule_graphml(path)

    _assert_graph_equal(rule.left, loaded.left)
    _assert_graph_equal(rule.interface, loaded.interface)
    _assert_graph_equal(rule.right, loaded.right)


def test_graphml_export_rejects_non_json_props(tmp_path: Path) -> None:
    left = nx.MultiDiGraph()
    interface = nx.MultiDiGraph()
    right = nx.MultiDiGraph()

    add_node(left, "req1", label="Requirement", props={"tags": {"a"}})
    add_node(interface, "req1", label="Requirement", props={"tags": {"a"}})
    add_node(right, "req1", label="Requirement", props={"tags": {"a"}})

    rule = DpoRule(left=left, interface=interface, right=right)

    with pytest.raises(RuleGraphMLFormatError):
        export_rule_graphml(rule, tmp_path / "rule.graphml")


def test_graphml_import_requires_roles(tmp_path: Path) -> None:
    graph = nx.MultiDiGraph()
    graph.add_node("req1", label="Requirement")
    path = tmp_path / "missing_roles.graphml"

    nx.write_graphml(graph, path)

    with pytest.raises(RuleGraphMLFormatError):
        import_rule_graphml(path)
