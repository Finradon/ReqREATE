from pathlib import Path
from typing import Any

from reqre.gh import assembly
from reqre.gh.graph import BuildingElement, BuildingElementEdge
from reqre.gh.registry import GhDefinition, GhRegistry


def _make_registry() -> GhRegistry:
    registry = GhRegistry()
    registry.register(
        GhDefinition(
            name="Abutment",
            gh_file="gh_samples/abutment_d1.gh",
            interface_outputs=(
                "ABT_interface1",
                "ABT_interface2",
                "ABT_interface3",
            ),
        )
    )
    registry.register(
        GhDefinition(
            name="Girder",
            gh_file="gh_samples/Girder.gh",
            interface_outputs=(
                "GRD_interface1",
                "GRD_interface2",
            ),
        )
    )
    return registry


def test_edge_interface_hints_support_role_specific_property_names() -> None:
    abutment = GhDefinition(
        name="Abutment",
        gh_file="gh_samples/abutment_d1.gh",
        interface_outputs=("ABT_interface1", "ABT_interface2", "ABT_interface3"),
    )
    girder = GhDefinition(
        name="Girder",
        gh_file="gh_samples/Girder.gh",
        interface_outputs=(
            "GRD_interface1",
            "GRD_interface2",
        ),
    )
    edge = BuildingElementEdge(
        src_id=11,
        dst_id=22,
        rel_type="SUPPORTS",
        props={
            "abutmentinterface": "ABT_interface2",
            "grderInterface": "GRD_interface1",
        },
    )

    src_hint, dst_hint = assembly._edge_interface_hints(
        edge=edge,
        current_id=11,
        interface_map={},
        current_def=abutment,
        neighbor_def=girder,
    )
    assert (src_hint, dst_hint) == ("ABT_interface2", "GRD_interface1")

    src_hint, dst_hint = assembly._edge_interface_hints(
        edge=edge,
        current_id=22,
        interface_map={},
        current_def=girder,
        neighbor_def=abutment,
    )
    assert (src_hint, dst_hint) == ("GRD_interface1", "ABT_interface2")


def test_assemble_elements_uses_per_edge_interface_mapping(monkeypatch) -> None:
    registry = _make_registry()
    elements = [
        BuildingElement(
            neo4j_id=101,
            gh_file="gh_samples/abutment_d1.gh",
            name="AbutmentElement1",
            detail_level="D1",
            params={},
            props={},
        ),
        BuildingElement(
            neo4j_id=102,
            gh_file="gh_samples/abutment_d1.gh",
            name="AbutmentElement2",
            detail_level="D1",
            params={},
            props={},
        ),
        BuildingElement(
            neo4j_id=201,
            gh_file="gh_samples/Girder.gh",
            name="GirderElement",
            detail_level="D1",
            params={},
            props={},
        ),
    ]
    edges = [
        BuildingElementEdge(
            src_id=101,
            dst_id=201,
            rel_type="SUPPORTS",
            props={
                "src_interface": "ABT_interface2",
                "dst_interface": "GRD_interface1",
            },
        ),
        BuildingElementEdge(
            src_id=102,
            dst_id=201,
            rel_type="SUPPORTS",
            props={
                "src_interface": "ABT_interface2",
                "dst_interface": "GRD_interface2",
            },
        ),
    ]
    align_calls: list[tuple[str, Any, Any]] = []

    def fake_evaluate_component(element, definition, eval_config, default_params):
        iface_list = [f"{element.name}-{name}" for name in definition.interface_outputs]
        return {
            "element": element,
            "definition": definition,
            "params": {},
            "brep": object(),
            "iface_list": iface_list,
        }

    def fake_align_component(component, source_plane, target_plane):
        align_calls.append((component["element"].name, source_plane, target_plane))
        return component

    monkeypatch.setattr(assembly, "_evaluate_component", fake_evaluate_component)
    monkeypatch.setattr(assembly.util, "align_component", fake_align_component)

    outcome = assembly.assemble_elements(
        elements,
        edges,
        registry,
        config=assembly.AssemblyConfig(
            detail_level="D1",
            gh_root=Path("gh_samples"),
            start_element_name="AbutmentElement1",
            flip_normals=False,
        ),
    )

    assert outcome.connected is True
    assert outcome.order == [101, 201, 102]
    assert align_calls == [
        (
            "GirderElement",
            "GirderElement-GRD_interface1",
            "AbutmentElement1-ABT_interface2",
        ),
        (
            "AbutmentElement2",
            "AbutmentElement2-ABT_interface2",
            "GirderElement-GRD_interface2",
        ),
    ]
