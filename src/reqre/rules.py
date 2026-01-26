"""Rule structures for DPO graph rewriting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, MutableMapping, Optional, Sequence

import networkx as nx

# Shared type alias used across rule/matching/serialization modules.
RuleGraph = nx.MultiDiGraph


def add_node(
    graph: RuleGraph,
    node_id: str,
    *,
    label: Optional[str | Sequence[str]] = None,
    props: Optional[Mapping[str, Any]] = None,
) -> None:
    """Add a node with standard label/props attributes."""
    attributes: MutableMapping[str, Any] = {}
    # Keep a consistent attribute schema for serialization/matching.
    if label is not None:
        attributes["label"] = label
    if props:
        attributes["props"] = dict(props)
    graph.add_node(node_id, **attributes)


def add_edge(
    graph: RuleGraph,
    source: str,
    target: str,
    *,
    key: Optional[str] = None,
    rel_type: Optional[str] = None,
    props: Optional[Mapping[str, Any]] = None,
) -> None:
    """Add an edge with standard type/props attributes."""
    attributes: MutableMapping[str, Any] = {}
    # Relationship type and props are used by the Cypher serializer.
    if rel_type is not None:
        attributes["type"] = rel_type
    if props:
        attributes["props"] = dict(props)
    graph.add_edge(source, target, key=key, **attributes)


@dataclass(frozen=True)
class DpoRule:
    """DPO rule represented as (L, K, R) graphs.

    Preserved elements should keep the same node IDs across L/K/R.
    """

    left: RuleGraph
    interface: RuleGraph
    right: RuleGraph

    def __post_init__(self) -> None:
        self._validate_graph("left", self.left)
        self._validate_graph("interface", self.interface)
        self._validate_graph("right", self.right)

    @staticmethod
    def _validate_graph(name: str, graph: RuleGraph) -> None:
        if not isinstance(graph, nx.MultiDiGraph):
            raise TypeError(f"{name} must be a networkx.MultiDiGraph")

    @classmethod
    def from_graphs(
        cls, left: RuleGraph, interface: RuleGraph, right: RuleGraph
    ) -> "DpoRule":
        return cls(left=left, interface=interface, right=right)

    def summary(self) -> dict[str, int]:
        """Return basic counts for inspection/logging."""
        return {
            "left_nodes": self.left.number_of_nodes(),
            "left_edges": self.left.number_of_edges(),
            "interface_nodes": self.interface.number_of_nodes(),
            "interface_edges": self.interface.number_of_edges(),
            "right_nodes": self.right.number_of_nodes(),
            "right_edges": self.right.number_of_edges(),
        }
