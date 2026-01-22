"""Demo: build an Arch Bridge rule from Gaphor requirements."""

from __future__ import annotations

from pathlib import Path

import networkx as nx

from reqre.cypher import rule_to_cypher
from reqre.gaphor_requirements import load_requirements_from_file
from reqre.neo4j import Neo4jClient
from reqre.rules import DpoRule, add_edge, add_node


def _find_requirement(requirements, external_id: str, name: str) -> object:
    for req in requirements:
        if req.external_id == external_id and req.name == name:
            return req
    for req in requirements:
        if req.external_id == external_id:
            return req
    raise ValueError(
        f"Requirement with external_id={external_id!r} not found. "
        f"Available: {[req.external_id for req in requirements]}"
    )


def _gh_path(root: Path, filename: str) -> str:
    path = root / filename
    if not path.exists():
        raise FileNotFoundError(f"Missing Grasshopper file: {path}")
    return str(Path("gh") / filename)


def _add_building_element(
    graph: nx.MultiDiGraph,
    node_id: str,
    *,
    name: str,
    gh_file: str,
    index: int | None = None,
) -> None:
    props = {"name": name, "gh_file": gh_file}
    if index is not None:
        props["index"] = index
    add_node(graph, node_id, label="BuildingElement", props=props)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    gaphor_path = repo_root / "gaphor_files" / "ArchBridgeRequirements.gaphor"
    gh_root = repo_root / "gh"

    requirements = load_requirements_from_file(gaphor_path)
    bridge_req = _find_requirement(requirements, "0", "Bridge")
    arch_req = _find_requirement(requirements, "1", "Arch Bridge")

    left = nx.MultiDiGraph()
    interface = nx.MultiDiGraph()
    right = nx.MultiDiGraph()

    for req in (bridge_req, arch_req):
        props = {
            "external_id": req.external_id,
            "name": req.name,
            "text": req.text,
        }
        add_node(left, req.gaphor_id, label="Requirement", props=props)
        add_node(interface, req.gaphor_id, label="Requirement", props=props)
        add_node(right, req.gaphor_id, label="Requirement", props=props)

    bridge_element_id = "bridge_element"
    arch_element_id = "arch_element"
    abutment_a_id = "abutment_a"
    abutment_b_id = "abutment_b"
    girder_id = "girder"

    _add_building_element(
        right,
        bridge_element_id,
        name="Bridge Element",
        gh_file=_gh_path(gh_root, "twisty.gh"),
    )
    _add_building_element(
        right,
        arch_element_id,
        name="Arch Element",
        gh_file=_gh_path(gh_root, "ArchSegment_Connector.gh"),
    )
    _add_building_element(
        right,
        abutment_a_id,
        name="Abutment A",
        gh_file=_gh_path(gh_root, "Curb.gh"),
    )
    _add_building_element(
        right,
        abutment_b_id,
        name="Abutment B",
        gh_file=_gh_path(gh_root, "Sidewalk.gh"),
    )
    _add_building_element(
        right,
        girder_id,
        name="Girder",
        gh_file=_gh_path(gh_root, "Girder.gh"),
    )

    for index in range(1, 6):
        _add_building_element(
            right,
            f"arch_segment_{index}",
            name="Arch Segment",
            gh_file=_gh_path(gh_root, "ArchSegment.gh"),
            index=index,
        )

    for index in range(1, 5):
        _add_building_element(
            right,
            f"spandrel_column_{index}",
            name="Spandrel Column",
            gh_file=_gh_path(gh_root, "Spandrel.gh"),
            index=index,
        )

    add_edge(right, bridge_req.gaphor_id, bridge_element_id, rel_type="SATISFIES")
    add_edge(right, arch_req.gaphor_id, arch_element_id, rel_type="SATISFIES")

    add_edge(right, bridge_element_id, arch_element_id, rel_type="DECOMPOSES")
    add_edge(right, bridge_element_id, abutment_a_id, rel_type="DECOMPOSES")
    add_edge(right, bridge_element_id, abutment_b_id, rel_type="DECOMPOSES")
    add_edge(right, bridge_element_id, girder_id, rel_type="DECOMPOSES")

    for index in range(1, 6):
        add_edge(
            right,
            arch_element_id,
            f"arch_segment_{index}",
            rel_type="DECOMPOSES",
        )

    for index in range(1, 5):
        add_edge(
            right,
            arch_element_id,
            f"spandrel_column_{index}",
            rel_type="DECOMPOSES",
        )

    rule = DpoRule(left=left, interface=interface, right=right)
    cypher = rule_to_cypher(rule)

    # print(rule.summary())
    # print(cypher.query)
    # print(cypher.params)

    with Neo4jClient() as client:
        client.execute(cypher.query, cypher.params)
    print("Cypher pushed to Neo4j.")


if __name__ == "__main__":
    main()
