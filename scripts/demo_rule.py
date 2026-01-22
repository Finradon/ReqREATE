#!/usr/bin/env python3
"""Manual demo of the current DPO rule representation."""

from __future__ import annotations

import networkx as nx

from reqre.rules import DpoRule, add_edge, add_node


def build_demo_rule() -> DpoRule:
    left = nx.MultiDiGraph()
    interface = nx.MultiDiGraph()
    right = nx.MultiDiGraph()

    add_node(left, "l1", label="Requirement", props={"id": "REQ-1"})
    add_node(interface, "k1", label="Requirement", props={"id": "REQ-1"})
    add_node(right, "r1", label="Requirement", props={"id": "REQ-1"})
    add_node(right, "r2", label="Component", props={"name": "Beam"})

    add_edge(right, "r1", "r2", rel_type="SATISFIES")

    return DpoRule(left=left, interface=interface, right=right)


def describe_graph(name: str, graph: nx.MultiDiGraph) -> None:
    print(f"{name} nodes:")
    for node_id, attrs in graph.nodes(data=True):
        print(f"  - {node_id}: {attrs}")

    print(f"{name} edges:")
    for source, target, key, attrs in graph.edges(keys=True, data=True):
        print(f"  - {source} -> {target} ({key}): {attrs}")


def main() -> None:
    rule = build_demo_rule()
    print("DPO rule summary:", rule.summary())
    print("")

    describe_graph("L", rule.left)
    print("")
    describe_graph("K", rule.interface)
    print("")
    describe_graph("R", rule.right)


if __name__ == "__main__":
    main()
