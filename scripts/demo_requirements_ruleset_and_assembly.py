#!/usr/bin/env python3
"""Demo: import SysML requirements from Gaphor, apply JSON rules, assemble GH."""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

import rhino3dm as r3d

from reqre.cypher import rule_to_cypher
from reqre.gaphor_requirements import (
    load_requirement_relationships_from_file,
    load_requirements_from_file,
    push_requirement_relationships_to_neo4j,
    push_requirements_to_neo4j,
)
from reqre.gh import (
    DEFAULT_COMPUTE_URL,
    AssemblyConfig,
    assemble_from_graph,
    build_default_registry,
    resolve_d1_parameters,
    resolve_d2_module_plan,
    util,
)
from reqre.neo4j import Neo4jClient
from reqre.rules import DpoRule

RHINO_3DM_VERSION = 8

CONFIG = {
    "gaphor_files": [
        "Sample1.gaphor",
    ],
    "json_rules": [
        "ReqD1-1.json",
        "SubstructureDecompD1.json",
        "ReqD2-1.json",
        "ReqD2-1-1.json",
        "SubstructureDecomp2.json",
        "SubstructureDecomp3.json",
        "girder_module_d3.json",
    ],
    # Rule execution phases:
    # 1) json_rules in listed order
    # 2) module_decomp_rule repeated by length resolver
    # 3) module_count_rules repeated for each D3 module
    # 4) single_run_rules once each
    # 5) fixed_run_rules exactly `times`
    "module_decomp_rule": "girder_module_decomp_d3.json",
    "module_count_rules": [
        "kappe_module_d3_iface5.json",
        "kappe_module_d3_iface6.json",
    ],
    "single_run_rules": [
        "expansion_module_d3_from_if2.json",
        "fahrbahn_module_d3_from_if2.json",
        "expansion_module_d3_from_if1.json",
    ],
    "fixed_run_rules": [
        {"file": "foundation_module_d2.json", "times": 2},
    ],
    "run_d2_module_length_resolver": True,
    "d2_length_param": "D2_GRD_length",
    "module_length": 1000.0,
    "detail_level": "D2",
    "relationship_types": ("INTERFACES",),
    "allowed_definitions": ("Abutment", "Girder"),
    "run_d1_param_resolver": True,
    "write_shared_parameter_nodes": False,
    "compute_url": DEFAULT_COMPUTE_URL,
    "gh_root": "gh_samples",
    "out_stl": None,
    "out_3dm": "smb://nas.ads.mwn.de/ga27guz/TUM/assembly.3dm",
    "out_obj": None,
    "show_interface_axes_3dm": False,
    "interface_axis_length": 400.0,
    "start_name": None,
    "start_id": None,
    "allow_interface_reuse": False,
    "flip_normals": True,
    "definition_colors": {
        "Abutment": (120, 120, 120, 255),
        "Girder": (180, 180, 180, 255),
        "AbutmentSideD2": (120, 120, 120, 255),
        "AbutmentMiddleD2": (120, 120, 120, 255),
        "AbutmentTopD2": (120, 120, 120, 255),
        "TGirderD2": (180, 180, 180, 255),
        "TGirderModule3": (180, 180, 180, 255),
        "KappeD3": (170, 170, 170, 255),
        "ExpansionD3": (110, 110, 110, 255),
        "FahrbahnD3": (95, 95, 95, 255),
        "FoundationD2": (145, 145, 145, 255),
    },
}


def _load_rule(path: Path) -> DpoRule:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return DpoRule.from_json(payload, validate=True)


def _allowed_definitions_for_detail(detail_level: str) -> tuple[str, ...]:
    if detail_level == "D2":
        return (
            "AbutmentSideD2",
            "AbutmentMiddleD2",
            "AbutmentTopD2",
            "TGirderModule3",
            "KappeD3",
            "ExpansionD3",
            "FahrbahnD3",
            "FoundationD2",
        )
    if detail_level == "D1":
        return ("Abutment", "Girder")
    return ()


def _apply_rule(client: Neo4jClient, rule_path: Path, rule: DpoRule) -> None:
    cypher = rule_to_cypher(rule)
    client.execute(cypher.query, cypher.params)
    print(f"Applied {rule_path.name}.")


def _run_d2_module_length_resolver(
    client: Neo4jClient,
    *,
    module_decomp_path: Path,
    module_decomp_rule: DpoRule,
) -> None:
    # Compute how many D3 modules should exist from current D2 girder length.
    plan = resolve_d2_module_plan(
        client,
        module_length=float(CONFIG["module_length"]),
        length_param=str(CONFIG["d2_length_param"]),
    )
    print(
        "D2 girder length "
        f"{plan.girder_length:.3f} mm -> "
        f"{plan.target_modules} module(s) at {plan.module_length:.3f} mm each. "
        f"Current modules: {plan.current_modules}."
    )

    if plan.current_modules == 0 and plan.target_modules > 0:
        raise RuntimeError(
            "No D3 modules found for the D2 girder. "
            "Apply girder_module_d3.json before module decomposition."
        )

    if plan.insertions_required <= 0:
        print("No additional module decomposition steps required.")
        return

    # Apply decomposition one step at a time and assert +1 module per step.
    cypher = rule_to_cypher(module_decomp_rule)
    for step in range(plan.insertions_required):
        before = resolve_d2_module_plan(
            client,
            module_length=float(CONFIG["module_length"]),
            length_param=str(CONFIG["d2_length_param"]),
        )
        client.execute(cypher.query, cypher.params)
        after = resolve_d2_module_plan(
            client,
            module_length=float(CONFIG["module_length"]),
            length_param=str(CONFIG["d2_length_param"]),
        )
        if after.current_modules != before.current_modules + 1:
            raise RuntimeError(
                "Module decomposition did not add exactly one module "
                f"at step {step + 1}: "
                f"before={before.current_modules}, after={after.current_modules}."
            )

    final_plan = resolve_d2_module_plan(
        client,
        module_length=float(CONFIG["module_length"]),
        length_param=str(CONFIG["d2_length_param"]),
    )
    print(
        f"Applied {module_decomp_path.name} "
        f"{plan.insertions_required} time(s). "
        f"Final modules: {final_plan.current_modules}."
    )


def _count_d2_modules(client: Neo4jClient) -> int:
    rows = client.execute(
        """
MATCH (m:BuildingElement:GirderElement)
WHERE m.detail_level = 'D2'
  AND m.gh_file = 'gh_samples/t_girder_module_d3.gh'
RETURN count(DISTINCT m) AS module_count
"""
    )
    if not rows:
        return 0
    raw = rows[0].get("module_count")
    if isinstance(raw, (int, float)):
        return int(raw)
    return 0


def _run_rules_per_module_count(
    client: Neo4jClient,
    *,
    rule_paths: list[Path],
    rules: list[DpoRule],
) -> None:
    # Run each rule once per currently present D3 module.
    module_count = _count_d2_modules(client)
    if module_count <= 0:
        print("No D3 girder modules found; skipping per-module rules.")
        return

    for rule_path, rule in zip(rule_paths, rules):
        cypher = rule_to_cypher(rule)
        for _ in range(module_count):
            client.execute(cypher.query, cypher.params)
        print(f"Applied {rule_path.name} {module_count} time(s).")


def _run_rules_once(
    client: Neo4jClient,
    *,
    rule_paths: list[Path],
    rules: list[DpoRule],
) -> None:
    # Run each rule exactly once, in list order.
    for rule_path, rule in zip(rule_paths, rules):
        _apply_rule(client, rule_path, rule)


def _run_rules_fixed_count(
    client: Neo4jClient,
    *,
    rule_paths: list[Path],
    rules: list[DpoRule],
    counts: list[int],
) -> None:
    # Run each rule with an explicit count from CONFIG.
    for rule_path, rule, count in zip(rule_paths, rules, counts):
        run_count = max(0, int(count))
        if run_count == 0:
            print(f"Skipped {rule_path.name} (0 time(s)).")
            continue
        cypher = rule_to_cypher(rule)
        for _ in range(run_count):
            client.execute(cypher.query, cypher.params)
        print(f"Applied {rule_path.name} {run_count} time(s).")


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
    # Optional debug visualization of interface planes in the 3DM output.
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
    # Serialize assembled Breps to 3DM, with optional SMB copy via gio.
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


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    gaphor_root = repo_root / "gaphor_files"
    rules_root = repo_root / "json_rules"

    gaphor_paths = [gaphor_root / name for name in CONFIG["gaphor_files"]]
    rule_paths = [rules_root / name for name in CONFIG["json_rules"]]
    module_decomp_path = rules_root / str(CONFIG["module_decomp_rule"])
    module_count_rule_paths = [
        rules_root / name for name in CONFIG["module_count_rules"]
    ]
    single_run_rule_paths = [rules_root / name for name in CONFIG["single_run_rules"]]
    fixed_run_specs = list(CONFIG.get("fixed_run_rules", []))
    fixed_run_rule_paths = [rules_root / str(spec["file"]) for spec in fixed_run_specs]
    fixed_run_rule_counts = [int(spec["times"]) for spec in fixed_run_specs]

    # Load requirements + requirement relationships from all input Gaphor files.
    requirements: list[object] = []
    relationships: list[object] = []
    for gaphor_path in gaphor_paths:
        requirements.extend(load_requirements_from_file(gaphor_path))
        relationships.extend(load_requirement_relationships_from_file(gaphor_path))

    if not requirements:
        print("No requirements found in:", ", ".join(p.name for p in gaphor_paths))
        return

    # Load all rule groups up front so validation errors fail fast.
    rules = [_load_rule(path) for path in rule_paths]
    module_decomp_rule = _load_rule(module_decomp_path)
    module_count_rules = [_load_rule(path) for path in module_count_rule_paths]
    single_run_rules = [_load_rule(path) for path in single_run_rule_paths]
    fixed_run_rules = [_load_rule(path) for path in fixed_run_rule_paths]

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
        # Reset demo DB state, then import requirements graph.
        client.execute("MATCH (n) DETACH DELETE n")
        total = push_requirements_to_neo4j(client, requirements)
        rel_total = push_requirement_relationships_to_neo4j(client, relationships)

        print(
            f"Pushed {total} requirements and {rel_total} relationships "
            f"from {len(gaphor_paths)} Gaphor file(s)."
        )

        # Base decomposition / enrichment rules in configured order.
        for rule_path, rule in zip(rule_paths, rules):
            _apply_rule(client, rule_path, rule)

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

        if CONFIG["detail_level"] == "D2" and CONFIG["run_d2_module_length_resolver"]:
            # D2 modular flow: grow module chain, then add module-dependent parts.
            _run_d2_module_length_resolver(
                client,
                module_decomp_path=module_decomp_path,
                module_decomp_rule=module_decomp_rule,
            )
            _run_rules_per_module_count(
                client,
                rule_paths=module_count_rule_paths,
                rules=module_count_rules,
            )
            _run_rules_once(
                client,
                rule_paths=single_run_rule_paths,
                rules=single_run_rules,
            )
            _run_rules_fixed_count(
                client,
                rule_paths=fixed_run_rule_paths,
                rules=fixed_run_rules,
                counts=fixed_run_rule_counts,
            )

        # Build geometry from the resulting BuildingElement graph.
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

    if CONFIG["out_stl"]:
        out_stl = Path(str(CONFIG["out_stl"]))
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
        out_obj = Path(str(CONFIG["out_obj"]))
        util.write_obj(str(out_obj), outcome.breps())
        print(f"Wrote OBJ to {out_obj}")

    if outcome.order:
        ordered: list[str] = []
        for node_id in outcome.order:
            element = outcome.elements.get(node_id)
            element_name = (element.name or "").strip() if element is not None else ""
            ordered.append(element_name or str(node_id))
        print("Assembly order:", ", ".join(ordered))


if __name__ == "__main__":
    main()
