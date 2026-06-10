#!/usr/bin/env python3
"""Demo: evaluate Girder.gh and export a 3DM with interface axis visuals."""

from __future__ import annotations

import math
import subprocess
from pathlib import Path
from typing import Any

import rhino3dm as r3d

from reqre.gh import (
    DEFAULT_COMPUTE_URL,
    AssemblyConfig,
    GhEvaluationConfig,
    build_default_registry,
    evaluate_definition,
)

RHINO_3DM_VERSION = 8

CONFIG = {
    "detail_level_for_defaults": "D1",
    "compute_url": DEFAULT_COMPUTE_URL,
    "gh_root": "gh_samples",
    "out_3dm": "smb://nas.ads.mwn.de/ga27guz/TUM/girder.3dm",
    "show_interface_axes_3dm": True,
    "interface_axis_length": 400.0,
    "params_override": {},  # example: {"GRD_length": 15000.0}
}


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
    model: r3d.File3dm, iface_list: list[Any], *, axis_length: float
) -> None:
    if axis_length <= 0:
        return

    for idx, iface in enumerate(iface_list, start=1):
        if iface is None or not isinstance(iface, r3d.Plane):
            continue

        model.Objects.AddPoint(
            iface.Origin, _attrs(f"Girder_iface_{idx}_origin", (255, 220, 0, 255))
        )

        x_axis = _scale_vec(iface.XAxis, axis_length)
        y_axis = _scale_vec(iface.YAxis, axis_length)
        z_raw = r3d.Vector3d.CrossProduct(iface.XAxis, iface.YAxis)
        z_axis = _scale_vec(z_raw, axis_length)

        if x_axis is not None:
            model.Objects.AddLine(
                iface.Origin,
                _point_plus_vec(iface.Origin, x_axis),
                _attrs(f"Girder_iface_{idx}_x", (255, 0, 0, 255)),
            )
        if y_axis is not None:
            model.Objects.AddLine(
                iface.Origin,
                _point_plus_vec(iface.Origin, y_axis),
                _attrs(f"Girder_iface_{idx}_y", (0, 200, 0, 255)),
            )
        if z_axis is not None:
            model.Objects.AddLine(
                iface.Origin,
                _point_plus_vec(iface.Origin, z_axis),
                _attrs(f"Girder_iface_{idx}_z", (0, 120, 255, 255)),
            )


def _write_3dm(path: str, brep: r3d.Brep, iface_list: list[Any]) -> None:
    model = r3d.File3dm()
    model.Objects.AddBrep(brep, _attrs("Girder", (220, 220, 220, 255)))

    if CONFIG["show_interface_axes_3dm"]:
        _add_interface_visuals(
            model,
            iface_list,
            axis_length=float(CONFIG["interface_axis_length"]),
        )

    if path.startswith("smb://"):
        tmp_path = Path("out/girder_with_interfaces.3dm")
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        if not model.Write(str(tmp_path), RHINO_3DM_VERSION):
            raise RuntimeError(f"Failed to write temporary 3DM: {tmp_path}")
        try:
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
    if not model.Write(str(out_3dm), RHINO_3DM_VERSION):
        raise RuntimeError(f"Failed to write 3DM: {out_3dm}")


def _girder_default_params() -> dict[str, Any]:
    assembly_defaults = AssemblyConfig(
        detail_level=CONFIG["detail_level_for_defaults"]
    ).default_params
    params = dict(assembly_defaults.get("Girder", {}))
    if not params:
        raise RuntimeError("No default Girder parameters found in AssemblyConfig.")
    overrides = CONFIG.get("params_override", {})
    if not isinstance(overrides, dict):
        raise TypeError("CONFIG['params_override'] must be a dict.")
    params.update(overrides)
    return params


def main() -> None:
    registry = build_default_registry()
    definition = registry.require("gh_samples/Girder.gh")

    params = _girder_default_params()
    result = evaluate_definition(
        definition,
        params,
        config=GhEvaluationConfig(
            compute_url=CONFIG["compute_url"],
            gh_root=Path(CONFIG["gh_root"]),
        ),
    )

    if result.brep is None:
        raise RuntimeError("Girder.gh evaluation did not return a brep.")

    out_3dm = str(CONFIG["out_3dm"])
    _write_3dm(out_3dm, result.brep, list(result.iface_list))
    print(f"Wrote 3DM to {out_3dm}")
    print("Params:", result.params)


if __name__ == "__main__":
    main()
