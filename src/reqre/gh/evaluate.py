"""Evaluate Grasshopper definitions via Rhino Compute."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

from .registry import (
    MISSING,
    GhDefinition,
    GhInput,
    GhRegistry,
    MissingGhParameters,
    normalize_gh_path,
)

DEFAULT_COMPUTE_URL = os.environ.get("REQRE_COMPUTE_URL", "http://localhost:6500/")


@dataclass(frozen=True)
class GhEvaluationConfig:
    compute_url: str = DEFAULT_COMPUTE_URL
    gh_root: Path = Path("gh_samples")


@dataclass
class GhEvaluationResult:
    definition: GhDefinition
    params: dict[str, Any]
    raw: dict[str, Any]
    brep: Any | None = None
    iface_list: list[Any] = field(default_factory=list)
    outputs: dict[str, list[Any]] = field(default_factory=dict)


def _load_util_module():
    try:
        from . import util  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on env setup
        raise ImportError(
            "util.py is required for Grasshopper output decoding. "
            "Ensure it is available at src/reqre/gh/util.py."
        ) from exc
    return util


def _load_compute_modules():
    try:
        import compute_rhino3d.Grasshopper as gh  # type: ignore
        import compute_rhino3d.Util as compute_util  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on env setup
        raise ImportError(
            "compute-rhino3d is required to evaluate Grasshopper definitions."
        ) from exc
    return compute_util, gh


def _check_compute_health(compute_url: str) -> None:
    base = compute_url.rstrip("/")
    health_url = f"{base}/healthcheck"
    try:
        response = requests.get(health_url, timeout=5)
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Rhino Compute health check failed at {health_url}: {exc}"
        ) from exc
    if response.status_code != 200:
        raise RuntimeError(
            "Rhino Compute health check returned "
            f"{response.status_code} from {health_url}."
        )
    if "Healthy" not in response.text:
        raise RuntimeError(
            "Rhino Compute health check did not return 'Healthy' " f"from {health_url}."
        )


def _resolve_param_value(raw_params: dict[str, Any], spec: GhInput) -> Any:
    for key in (spec.name, *spec.aliases):
        if key in raw_params:
            return raw_params[key]
    return MISSING


def resolve_params(
    definition: GhDefinition, raw_params: dict[str, Any]
) -> dict[str, Any]:
    if not definition.inputs:
        return dict(raw_params)

    missing: list[str] = []
    resolved: dict[str, Any] = {}
    for spec in definition.inputs:
        value = _resolve_param_value(raw_params, spec)
        if value is MISSING:
            if spec.default is not MISSING:
                value = spec.default
            elif spec.required:
                missing.append(spec.name)
        if value is not MISSING:
            resolved[spec.name] = value
    if missing:
        raise MissingGhParameters(definition.name, missing)
    return resolved


def _coerce_tree_values(value: Any) -> list[Any]:
    if isinstance(value, (list, tuple)) and not isinstance(value, (str, bytes)):
        return list(value)
    return [value]


def resolve_gh_path(gh_file: str, gh_root: Path | None) -> str:
    normalized = normalize_gh_path(gh_file)
    path = Path(normalized)
    if path.is_absolute():
        return str(path)
    if gh_root is None:
        return normalized
    relative = normalized
    if relative.startswith("gh_samples/"):
        relative = relative[len("gh_samples/") :]
    return str(Path(gh_root) / relative)


def _alternate_output_names(name: str) -> tuple[str, ...]:
    candidates: list[str] = []
    if "D3_" in name:
        candidates.append(name.replace("D3_", "D2_"))
    if "D2_" in name:
        candidates.append(name.replace("D2_", "D3_"))
    # Also support lowercase variants in case outputs were renamed manually.
    if "d3_" in name:
        candidates.append(name.replace("d3_", "d2_"))
    if "d2_" in name:
        candidates.append(name.replace("d2_", "d3_"))
    deduped: list[str] = []
    for candidate in candidates:
        if candidate != name and candidate not in deduped:
            deduped.append(candidate)
    return tuple(deduped)


def _first_brep_from_any_output(values: list[dict[str, Any]], util) -> Any | None:
    for entry in values:
        param_name = entry.get("ParamName")
        if not isinstance(param_name, str):
            continue
        if "brep" not in param_name.lower():
            continue
        inner_tree = entry.get("InnerTree")
        if not isinstance(inner_tree, dict):
            continue
        decoded = util.decode_inner_tree(inner_tree)
        for obj in decoded:
            if obj.__class__.__name__.lower() == "brep":
                return obj
    return None


def evaluate_definition(
    definition: GhDefinition,
    params: dict[str, Any],
    *,
    config: GhEvaluationConfig | None = None,
) -> GhEvaluationResult:
    config = config or GhEvaluationConfig()
    resolved_params = resolve_params(definition, params)
    expanded_params = dict(resolved_params)
    # Send alias trees too; GH files can still use legacy D2-style parameter names.
    for spec in definition.inputs:
        if spec.name not in resolved_params:
            continue
        value = resolved_params[spec.name]
        for alias in spec.aliases:
            expanded_params.setdefault(alias, value)

    _check_compute_health(config.compute_url)

    compute_util, gh = _load_compute_modules()
    compute_util.url = config.compute_url

    trees = []
    for name, value in expanded_params.items():
        tree = gh.DataTree(name)
        tree.Append([0], _coerce_tree_values(value))
        trees.append(tree)

    gh_path = resolve_gh_path(definition.gh_file, config.gh_root)
    out = gh.EvaluateDefinition(gh_path, trees)

    util = _load_util_module()
    result = GhEvaluationResult(definition=definition, params=resolved_params, raw=out)

    values = out.get("values", [])
    if definition.brep_output:
        breps = util.get_output_by_name(values, definition.brep_output)
        if not breps:
            for alt_name in _alternate_output_names(definition.brep_output):
                breps = util.get_output_by_name(values, alt_name)
                if breps:
                    break
        result.outputs[definition.brep_output] = breps
        result.brep = breps[0] if breps else None
        if result.brep is None:
            result.brep = _first_brep_from_any_output(values, util)

    if definition.interface_outputs:
        iface_list: list[Any] = []
        for name in definition.interface_outputs:
            plane = util.extract_plane(values, name)
            if plane is None:
                for alt_name in _alternate_output_names(name):
                    plane = util.extract_plane(values, alt_name)
                    if plane is not None:
                        break
            iface_list.append(plane)
        result.iface_list = iface_list

    for name in definition.extra_outputs:
        result.outputs[name] = util.get_output_by_name(values, name)

    return result


def evaluate_element(
    element_props: dict[str, Any],
    registry: GhRegistry,
    *,
    config: GhEvaluationConfig | None = None,
) -> GhEvaluationResult:
    gh_file = element_props.get("gh_file")
    if not gh_file:
        raise ValueError("BuildingElement is missing gh_file property.")

    definition = registry.require(gh_file)
    raw_params = element_props.get("gh_params") or element_props.get("params") or {}
    if isinstance(raw_params, str):
        import json

        raw_params = json.loads(raw_params)
    if definition.param_builder is not None:
        raw_params = definition.param_builder(dict(raw_params), dict(element_props))

    if not isinstance(raw_params, dict):
        raise TypeError("Grasshopper params must be a dict-like mapping.")

    return evaluate_definition(definition, raw_params, config=config)
