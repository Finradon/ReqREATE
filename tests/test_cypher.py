import networkx as nx
import pytest

from reqre.cypher import RuleSerializationError, rule_to_cypher
from reqre.rules import DpoRule, add_edge, add_node


def test_rule_to_cypher_create_only() -> None:
    left = nx.MultiDiGraph()
    interface = nx.MultiDiGraph()
    right = nx.MultiDiGraph()

    add_node(left, "req1", label="Requirement", props={"id": "REQ-1"})
    add_node(interface, "req1", label="Requirement", props={"id": "REQ-1"})
    add_node(right, "req1", label="Requirement", props={"id": "REQ-1"})
    add_node(right, "comp1", label="Component", props={"name": "Beam"})

    add_edge(right, "req1", "comp1", rel_type="SATISFIES")

    rule = DpoRule(left=left, interface=interface, right=right)
    cypher = rule_to_cypher(rule)

    assert cypher.query == (
        "MATCH (n_req1:Requirement {id: $n_req1_id})\n"
        "CREATE (n_comp1:Component {name: $n_comp1_name})\n"
        "CREATE (n_req1)-[:SATISFIES]->(n_comp1)"
    )
    assert cypher.params == {
        "n_req1_id": "REQ-1",
        "n_comp1_name": "Beam",
    }


def test_rule_to_cypher_rejects_deletions() -> None:
    left = nx.MultiDiGraph()
    interface = nx.MultiDiGraph()
    right = nx.MultiDiGraph()

    add_node(left, "req1", label="Requirement", props={"id": "REQ-1"})
    add_node(right, "req1", label="Requirement", props={"id": "REQ-1"})

    rule = DpoRule(left=left, interface=interface, right=right)

    with pytest.raises(RuleSerializationError, match="do not support node deletion"):
        rule_to_cypher(rule)
