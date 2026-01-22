import networkx as nx

from reqre.rules import DpoRule, add_edge, add_node


def test_dpo_rule_summary_counts() -> None:
    left = nx.MultiDiGraph()
    interface = nx.MultiDiGraph()
    right = nx.MultiDiGraph()

    add_node(left, "l1", label="Requirement", props={"id": "REQ-1"})
    add_node(interface, "k1", label="Requirement", props={"id": "REQ-1"})
    add_node(right, "r1", label="Requirement", props={"id": "REQ-1"})
    add_node(right, "r2", label="Component", props={"name": "Beam"})

    add_edge(right, "r1", "r2", rel_type="SATISFIES")

    rule = DpoRule(left=left, interface=interface, right=right)

    assert rule.summary() == {
        "left_nodes": 1,
        "left_edges": 0,
        "interface_nodes": 1,
        "interface_edges": 0,
        "right_nodes": 2,
        "right_edges": 1,
    }
