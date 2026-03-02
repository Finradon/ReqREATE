#!/usr/bin/env python3
"""Minimal Grasshopper evaluation example that writes an STL."""

from __future__ import annotations

from pathlib import Path

from reqre.gh import (
    DEFAULT_COMPUTE_URL,
    GhEvaluationConfig,
    build_default_registry,
    evaluate_definition,
    resolve_gh_path,
    util,
)

GH_FILE = "gh_samples/Girder.gh"
GH_ROOT = Path("gh_samples")

PARAMS = {
    "GRD_length": 10000.0,
    "GRD_width": 5000.0,
    "GRD_height": 500.0,
    "GRD_offset1": 500.0,
    "GRD_offset2": 500.0,
}

OUT_PATH = Path("out/girder.stl")


def main() -> None:
    registry = build_default_registry()
    definition = registry.require(GH_FILE)
    config = GhEvaluationConfig(compute_url=DEFAULT_COMPUTE_URL, gh_root=GH_ROOT)

    gh_path = Path(resolve_gh_path(definition.gh_file, config.gh_root))
    if gh_path.suffix.lower() == ".gh":
        try:
            head = gh_path.read_text(encoding="utf-8", errors="ignore")[:200]
        except FileNotFoundError as exc:
            raise RuntimeError(f"Grasshopper file not found: {gh_path}") from exc
        if "<" not in head:
            raise RuntimeError(
                "Grasshopper file appears to be binary (.gh). "
                "Rhino Compute expects XML-based .ghx. "
                "Resave the definition as .ghx and update GH_FILE."
            )

    result = evaluate_definition(definition, PARAMS, config=config)

    breps = []
    if result.brep is not None:
        breps = [result.brep]
    elif definition.brep_output and definition.brep_output in result.outputs:
        breps = result.outputs.get(definition.brep_output, [])

    if not breps:
        raise RuntimeError("No breps returned by the definition output.")

    util.write_stl(str(OUT_PATH), breps)
    print(f"Wrote STL to {OUT_PATH}")


if __name__ == "__main__":
    main()
