"""Demo for GraphML import/export of DPO rules."""

from __future__ import annotations

import networkx as nx

from reqre.graphml import export_rule_graphml, import_rule_graphml
from reqre.rules import DpoRule, add_edge, add_node


def build_rule() -> DpoRule:
    left = nx.MultiDiGraph()
    interface = nx.MultiDiGraph()
    right = nx.MultiDiGraph()

    add_node(left, "req1", label="Requirement", props={"id": "REQ-1"})
    add_node(interface, "req1", label="Requirement", props={"id": "REQ-1"})
    add_node(right, "req1", label="Requirement", props={"id": "REQ-1"})
    add_node(right, "comp1", label="Component", props={"name": "Beam"})
    add_edge(
        right,
        "req1",
        "comp1",
        key="satisfies",
        rel_type="SATISFIES",
        props={"strength": 10},
    )

    return DpoRule(left=left, interface=interface, right=right)


def main() -> None:
    rule = build_rule()
    path = "rule.graphml"

    export_rule_graphml(rule, path)
    loaded = import_rule_graphml(path)

    print("Wrote GraphML to", path)
    print("Original summary:", rule.summary())
    print("Loaded summary:  ", loaded.summary())


if __name__ == "__main__":
    main()
