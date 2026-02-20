# ReqREATE

![](ReqREATE.png)

Requirements Rewriting and Transformation Engine for SysML-driven graph rewriting in Neo4j, with Grasshopper-based geometry assembly.

## What It Does
- Imports `SysML:Requirement` objects and requirement relationships from `.gaphor` files.
- Applies DPO-style rule JSONs (`left` / `interface` / `right`, optional `nac`) to a Neo4j host graph.
- Builds bridge assemblies via Rhino Compute + Grasshopper definitions from `BuildingElement` nodes and `INTERFACES` edges.
- Supports requirement-aware rewriting (`SATISFIES` edges) so rule application can depend on requirement IDs (for example `D2.2`).

## Current Recommended Entry Point
- Start with `scripts/demo.py`.
- It is the current orchestrated, stepwise demo and snapshot workflow.

## Stepwise Demo Pipeline (`scripts/demo.py`)
The script resets Neo4j, imports requirements, applies staged rule groups, and writes a `3dm` snapshot after each stage.

Stage order:
1. D1 model: two D1 abutments + one D1 girder.
2. D2 decomposition: abutment decomposition + D2-to-D3 module decomposition.
3. Kappe stage.
4. Expansion stage.
5. Foundation stage.
6. Fahrbahn stage.

Notes:
- Girder-module expansion is handled as one grouped strategy (not snapshot per inserted module).
- Kappe expansion is grouped (not snapshot per module).
- The script pauses after each snapshot so you can capture the Neo4j graph state.
- Snapshot output supports SMB paths (for example `smb://...`) using `gio`.

## Requirements and Environment
Install system deps for Gaphor first.

Debian/Ubuntu:
```bash
sudo apt install libcairo2-dev pkg-config python3-dev libgirepository1.0-dev libgtk-4-dev gir1.2-pango-1.0 libgtksourceview-5-dev gir1.2-adw-1
```

Fedora:
```bash
sudo dnf install cairo-devel pkgconf-pkg-config python3-devel gobject-introspection-devel gtk4-devel pango-devel gtksourceview5-devel libadwaita-devel
```

Arch:
```bash
sudo pacman -S --needed cairo pkgconf python gobject-introspection gtk4 pango gtksourceview5 libadwaita
```

Python setup:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
gaphor install-schemas
pip install -e .
```

Neo4j env vars:
```bash
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=neo4jneo4j
```

## Run
Stepwise orchestration + snapshots:
```bash
python scripts/demo.py
```

Rule schema validation:
```bash
python scripts/validate_rules.py json_rules/<rule>.json
```

Tests:
```bash
pytest
```

## Rule Format
- JSON rules are validated against `src/reqre/schemas/dpo_rule.schema.json`.
- Required top-level keys: `left`, `interface`, `right`.
- Optional keys: `rule_id`, `name`, `description`, `metadata`, `nac`.
- Nodes and edges support `props`.
- `nac` blocks matches for idempotency/guard conditions.

## Geometry Assembly Notes
- GH definitions are registered in `src/reqre/gh/definitions.py`.
- Default fallback GH parameters are in `src/reqre/gh/assembly.py`.
- Interface pairing is read from edge props (preferred keys: `src_interface`, `dst_interface`).
- `scripts/demo.py` writes staged `3dm` snapshots and can color components per definition.

## Repository Structure
- Source code: `src/reqre/`
- Rules: `json_rules/`
- Demos/scripts: `scripts/`
- Tests: `tests/`
- Sample GH files: `gh_samples/`
- Sample Gaphor file: `gaphor_files/Sample1.gaphor`
