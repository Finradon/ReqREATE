#!/usr/bin/env python3
"""Demo: assemble BuildingElements from Neo4j using GH definitions."""

from __future__ import annotations

import math
import subprocess
from pathlib import Path

import rhino3dm as r3d

from reqre.gh import (
    DEFAULT_COMPUTE_URL,
    AssemblyConfig,
    assemble_from_graph,
    build_default_registry,
    resolve_d1_parameters,
    util,
)
from reqre.neo4j import Neo4jClient

CONFIG = {
    "detail_level": "D2",
    "relationship_types": ("INTERFACES",),
    "allowed_definitions": ("Abutment", "Girder"),
    "run_d1_param_resolver": True,
    "write_shared_parameter_nodes": False,
    "compute_url": DEFAULT_COMPUTE_URL,
    "gh_root": "gh_samples",
    "out_stl": "out/assembly.stl",
    "out_3dm": "smb://nas.ads.mwn.de/ga27guz/TUM/assembly.3dm",
    "out_obj": "out/assembly.obj",
    "show_interface_axes_3dm": True,
    "interface_axis_length": 400.0,
    "start_name": None,  # example: "AbutmentElement1"
    "start_id": None,  # example: "4:7f38d0f5-...:123"
    "allow_interface_reuse": False,
    "flip_normals": True,
    "definition_colors": {
        "Abutment": (210, 90, 90, 255),
        "Girder": (90, 120, 210, 255),
        "AbutmentSideD2": (210, 90, 90, 255),
        "AbutmentMiddleD2": (210, 140, 80, 255),
        "TGirderD2": (90, 120, 210, 255),
        "TGirderModule3": (90, 120, 210, 255),
    },
}


def _allowed_definitions_for_detail(detail_level: str) -> tuple[str, ...]:
    if detail_level == "D2":
        return (
            "AbutmentSideD2",
            "AbutmentMiddleD2",
            "AbutmentTopD2",
            "TGirderModule3",
        )
    if detail_level == "D1":
        return ("Abutment", "Girder")
    return ()


def _attrs(name: str, color: tuple[int, int, int, int]) -> r3d.ObjectAttributes:
    attrs = r3d.ObjectAttributes()
    attrs.Name = name
    attrs.ColorSource = r3d.ObjectColorSource.ColorFromObject
    attrs.ObjectColor = color
    return attrs


def _scale_vec(axis: r3d.Vector3d, length: float) -> r3d.Vector3d | None:
    mag = math.sqrt(axis.X * axis.X + axis.Y * axis.Y + axis.Z * axis.Z)
    if mag <= 1e-12:
        return None
    scale = length / mag
    return r3d.Vector3d(axis.X * scale, axis.Y * scale, axis.Z * scale)


def _point_plus_vec(point: r3d.Point3d, vec: r3d.Vector3d) -> r3d.Point3d:
    return r3d.Point3d(point.X + vec.X, point.Y + vec.Y, point.Z + vec.Z)


def _add_interface_visuals(
    model: r3d.File3dm,
    components: dict[int, dict[str, object]],
    *,
    axis_length: float,
) -> None:
    if axis_length <= 0:
        return

    for node_id, comp in sorted(components.items()):
        iface_list = comp.get("iface_list")
        if not isinstance(iface_list, list):
            continue
        for idx, iface in enumerate(iface_list, start=1):
            if iface is None:
                continue
            if not isinstance(iface, r3d.Plane):
                continue

            origin_name = f"BE_{node_id}_iface_{idx}_origin"
            model.Objects.AddPoint(
                iface.Origin, _attrs(origin_name, (255, 220, 0, 255))
            )

            x_axis = _scale_vec(iface.XAxis, axis_length)
            y_axis = _scale_vec(iface.YAxis, axis_length)
            z_raw = r3d.Vector3d.CrossProduct(iface.XAxis, iface.YAxis)
            z_axis = _scale_vec(z_raw, axis_length)

            if x_axis is not None:
                model.Objects.AddLine(
                    iface.Origin,
                    _point_plus_vec(iface.Origin, x_axis),
                    _attrs(f"BE_{node_id}_iface_{idx}_x", (255, 0, 0, 255)),
                )
            if y_axis is not None:
                model.Objects.AddLine(
                    iface.Origin,
                    _point_plus_vec(iface.Origin, y_axis),
                    _attrs(f"BE_{node_id}_iface_{idx}_y", (0, 200, 0, 255)),
                )
            if z_axis is not None:
                model.Objects.AddLine(
                    iface.Origin,
                    _point_plus_vec(iface.Origin, z_axis),
                    _attrs(f"BE_{node_id}_iface_{idx}_z", (0, 120, 255, 255)),
                )


def _write_3dm(
    path: str,
    components: dict[int, dict[str, object]],
    *,
    show_interface_axes: bool,
    interface_axis_length: float,
) -> None:
    model = r3d.File3dm()
    color_map = CONFIG.get("definition_colors", {}) or {}
    for node_id, comp in sorted(components.items()):
        brep = comp.get("brep")
        if isinstance(brep, r3d.Brep):
            definition = comp.get("definition")
            def_name = getattr(definition, "name", None)
            color = color_map.get(def_name, (220, 220, 220, 255))
            model.Objects.AddBrep(brep, _attrs(f"BE_{node_id}", color))

    if show_interface_axes:
        _add_interface_visuals(model, components, axis_length=interface_axis_length)

    if path.startswith("smb://"):
        tmp_path = Path("out/assembly.3dm")
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        if not model.Write(str(tmp_path), 7):
            raise RuntimeError(f"Failed to write temporary 3DM: {tmp_path}")
        try:
            # Overwrite behavior in gio copy varies by version; remove first if present.
            subprocess.run(["gio", "remove", path], check=False)
            subprocess.run(
                ["gio", "copy", "--no-target-directory", str(tmp_path), path],
                check=True,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "`gio` is required to copy files to smb:// URIs."
            ) from exc
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"Failed to copy 3DM to SMB path: {path}") from exc
        return

    out_3dm = Path(path)
    out_3dm.parent.mkdir(parents=True, exist_ok=True)
    if not model.Write(str(out_3dm), 7):
        raise RuntimeError(f"Failed to write 3DM: {out_3dm}")


def main() -> None:
    registry = build_default_registry()
    allowed_definitions = _allowed_definitions_for_detail(CONFIG["detail_level"])
    config = AssemblyConfig(
        detail_level=CONFIG["detail_level"],
        relationship_types=tuple(CONFIG["relationship_types"]),
        allowed_definitions=allowed_definitions,
        compute_url=CONFIG["compute_url"],
        gh_root=Path(CONFIG["gh_root"]),
        start_element_id=CONFIG["start_id"],
        start_element_name=CONFIG["start_name"],
        allow_interface_reuse=CONFIG["allow_interface_reuse"],
        flip_normals=CONFIG["flip_normals"],
    )

    with Neo4jClient() as client:
        if CONFIG["detail_level"] == "D1" and CONFIG["run_d1_param_resolver"]:
            resolved = resolve_d1_parameters(
                client,
                write_shared_parameter_nodes=bool(
                    CONFIG["write_shared_parameter_nodes"]
                ),
            )
            print(
                f"Resolved D1 parameters for {len(resolved)} abutment/girder pair(s)."
            )
        outcome = assemble_from_graph(client, registry, config=config)

    if outcome.missing_definitions:
        print("Missing definitions:")
        for missing in outcome.missing_definitions:
            print(f"- {missing}")

    if not outcome.connected:
        print(outcome.reason or "Assembly aborted.")
        return

    if not outcome.components:
        print("No components assembled.")
        return

    out_stl = Path(CONFIG["out_stl"])
    util.write_stl(str(out_stl), outcome.breps())
    print(f"Wrote STL to {out_stl}")

    if CONFIG["out_3dm"]:
        out_3dm = str(CONFIG["out_3dm"])
        _write_3dm(
            out_3dm,
            outcome.components,
            show_interface_axes=bool(CONFIG["show_interface_axes_3dm"]),
            interface_axis_length=float(CONFIG["interface_axis_length"]),
        )
        print(f"Wrote 3DM to {out_3dm}")

    if CONFIG["out_obj"]:
        out_obj = Path(CONFIG["out_obj"])
        util.write_obj(str(out_obj), outcome.breps())
        print(f"Wrote OBJ to {out_obj}")

    if outcome.order:
        ordered = [str(node_id) for node_id in outcome.order]
        print("Assembly order:", ", ".join(ordered))


if __name__ == "__main__":
    main()
