"""Known Grasshopper definition specs."""

from __future__ import annotations

from pathlib import Path

from .registry import GhDefinition, GhInput, GhRegistry


def register_default_definitions(registry: GhRegistry) -> GhRegistry:
    registry.register(
        GhDefinition(
            name="ArchSegment",
            gh_file="gh_samples/ArchSegment.gh",
            inputs=(
                GhInput("AS_height"),
                GhInput("AS_width"),
                GhInput("AS_length"),
                GhInput("AS_angle", aliases=("ASC_angle",)),
            ),
            brep_output="AS_brep",
            interface_outputs=("AS_interface1", "AS_interface2"),
        )
    )
    registry.register(
        GhDefinition(
            name="ArchSegmentConnector",
            gh_file="gh_samples/ArchSegment_Connector.gh",
            inputs=(
                GhInput("ASC_height"),
                GhInput("ASC_width"),
                GhInput("ASC_length"),
                GhInput("ASC_station"),
                GhInput("ASC_nras"),
            ),
            brep_output="ASC_brep",
            interface_outputs=("ASC_interface1", "ASC_interface2", "ASC_interface3"),
        )
    )
    registry.register(
        GhDefinition(
            name="Spandrel",
            gh_file="gh_samples/Spandrel.gh",
            inputs=(
                GhInput("SP_height"),
                GhInput("SP_width"),
                GhInput("SP_length"),
            ),
            brep_output="SP_brep",
            interface_outputs=("SP_interface1", "SP_interface2"),
        )
    )
    registry.register(
        GhDefinition(
            name="Girder",
            gh_file="gh_samples/Girder.gh",
            inputs=(
                GhInput("GRD_height"),
                GhInput("GRD_width"),
                GhInput("GRD_length"),
                GhInput("GRD_offset1"),
                GhInput("GRD_offset2"),
            ),
            brep_output="GRD_brep",
            interface_outputs=(
                "GRD_interface1",
                "GRD_interface2",
            ),
        )
    )
    registry.register(
        GhDefinition(
            name="Sidewalk",
            gh_file="gh_samples/Sidewalk.gh",
            inputs=(
                GhInput("WLK_height"),
                GhInput("WLK_width"),
                GhInput("WLK_length"),
            ),
            brep_output="WLK_brep",
            interface_outputs=(
                "WLK_interface1",
                "WLK_interface2",
                "WLK_interface3",
                "WLK_interface4",
                "WLK_interface5",
                "WLK_interface6",
            ),
        )
    )
    registry.register(
        GhDefinition(
            name="Curb",
            gh_file="gh_samples/Curb.gh",
            inputs=(
                GhInput("CRB_height"),
                GhInput("CRB_width"),
                GhInput("CRB_length"),
            ),
            brep_output="CRB_brep",
            interface_outputs=("CRB_interface1", "CRB_interface2"),
        )
    )
    registry.register(
        GhDefinition(
            name="Abutment",
            gh_file="gh_samples/abutment_d1.gh",
            inputs=(
                GhInput("ABT_height"),
                GhInput("ABT_width"),
                GhInput("ABT_ledgewidth"),
                GhInput("ABT_ledgeheight"),
                GhInput("ABT_offset"),
            ),
            brep_output="ABT_brep",
            interface_outputs=("ABT_interface1", "ABT_interface2", "ABT_interface3"),
        )
    )
    registry.register(
        GhDefinition(
            name="AbutmentSideD2",
            gh_file="gh_samples/abutment_side_d2.gh",
            inputs=(
                GhInput("ABT_SD_height"),
                GhInput("ABT_SD_thickness"),
                GhInput("ABT_SD_length"),
                GhInput("ABT_SD_angle"),
                GhInput("ABT_SD_middleheight"),
            ),
            brep_output="ABT_SD_brep",
            interface_outputs=(
                "ABT_SD_interface1",
                "ABT_SD_interface2",
                "ABT_SD_interface3",
            ),
        )
    )
    registry.register(
        GhDefinition(
            name="AbutmentMiddleD2",
            gh_file="gh_samples/abutment_middle_d2.gh",
            inputs=(
                GhInput("ABT_MD_length"),
                GhInput("ABT_MD_thickness"),
                GhInput("ABT_MD_height"),
            ),
            brep_output="ABT_MD_brep",
            interface_outputs=(
                "ABT_MD_interface1",
                "ABT_MD_interface2",
                "ABT_MD_interface3",
                "ABT_MD_interface4",
            ),
        )
    )
    registry.register(
        GhDefinition(
            name="TGirderD2",
            gh_file="gh_samples/t_girder_d2.gh",
            inputs=(
                GhInput("D2_GRD_width"),
                GhInput("D2_GRD_length"),
                GhInput("D2_GRD_thickness"),
                GhInput("D2_GRD_t_offset"),
                GhInput("D2_GRD_t_height"),
                GhInput("D2_GRD_t_thickness"),
                GhInput("D2_GRD_nr_t"),
                GhInput("D2_GRD_iface_offset"),
            ),
            brep_output="D2_GRD_brep",
            interface_outputs=("D2_GRD_interface1", "D2_GRD_interface2"),
        )
    )
    registry.register(
        GhDefinition(
            name="TGirderModule3",
            gh_file="gh_samples/t_girder_module_d3.gh",
            inputs=(
                GhInput("D3_GRD_width", aliases=("D2_GRD_width",)),
                GhInput("D3_GRD_length", aliases=("D2_GRD_length",)),
                GhInput("D3_GRD_thickness", aliases=("D2_GRD_thickness",)),
                GhInput("D3_GRD_t_offset", aliases=("D2_GRD_t_offset",)),
                GhInput("D3_GRD_t_height", aliases=("D2_GRD_t_height",)),
                GhInput("D3_GRD_t_thickness", aliases=("D2_GRD_t_thickness",)),
                GhInput("D3_GRD_nr_t", aliases=("D2_GRD_nr_t",)),
                GhInput("D3_GRD_iface_offset", aliases=("D2_GRD_iface_offset",)),
            ),
            brep_output="D3_GRD_brep",
            interface_outputs=(
                "D3_GRD_interface1",
                "D3_GRD_interface2",
                "D3_GRD_interface3",
                "D3_GRD_interface4",
                "D3_GRD_interface5",
                "D3_GRD_interface6",
                "D3_GRD_interface7",
            ),
        )
    )
    registry.register(
        GhDefinition(
            name="AbutmentTopD2",
            gh_file="gh_samples/abutment_top_d2.gh",
            inputs=(
                GhInput("ABT_TOP_width"),
                GhInput("ABT_TOP_length"),
                GhInput("ABT_TOP_thickness"),
                GhInput("ABT_TOP_offset"),
            ),
            brep_output="ABT_TOP_brep",
            interface_outputs=(
                "ABT_TOP_interface1",
                "ABT_TOP_interface2",
                "ABT_TOP_interface3",
            ),
        )
    )
    registry.register(
        GhDefinition(
            name="KappeD3",
            gh_file="gh_samples/kappe_d3.gh",
            inputs=(GhInput("KP_length"),),
            brep_output="KP_brep",
            interface_outputs=(
                "KP_interface1",
                "KP_interface2",
                "KP_interface3",
            ),
        )
    )
    registry.register(
        GhDefinition(
            name="ExpansionD3",
            gh_file="gh_samples/expansion_d3.gh",
            inputs=(GhInput("EXP_length"),),
            brep_output="EXP_brep",
            interface_outputs=(
                "EXP_interface1",
                "EXP_interface2",
            ),
        )
    )
    registry.register(
        GhDefinition(
            name="FahrbahnD3",
            gh_file="gh_samples/fahrbahn_d3.gh",
            inputs=(
                GhInput("FB_width"),
                GhInput("FB_length"),
            ),
            brep_output="FB_brep",
            interface_outputs=("FB_interface1",),
        )
    )
    registry.register(
        GhDefinition(
            name="FoundationD2",
            gh_file="gh_samples/foundation_d2.gh",
            inputs=(
                GhInput("FND_length"),
                GhInput("FND_width"),
                GhInput("FND_thickness"),
                GhInput("FND_girth"),
            ),
            brep_output="FND_brep",
            interface_outputs=("FND_interface1",),
        )
    )
    return registry


def register_directory_definitions(
    registry: GhRegistry, gh_root: Path, *, prefix: str = "gh_samples"
) -> GhRegistry:
    """Register placeholder definitions for any .gh files in a directory."""
    root = Path(gh_root)
    if not root.exists():
        return registry

    for gh_path in sorted(root.glob("*.gh")):
        gh_file = (Path(prefix) / gh_path.name).as_posix()
        if registry.get(gh_file) is None:
            registry.register(
                GhDefinition(
                    name=gh_path.stem,
                    gh_file=gh_file,
                )
            )
    return registry


def build_default_registry(*, gh_root: Path | None = None) -> GhRegistry:
    registry = GhRegistry()
    register_default_definitions(registry)
    if gh_root is not None:
        register_directory_definitions(registry, gh_root)
    return registry
