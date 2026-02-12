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
