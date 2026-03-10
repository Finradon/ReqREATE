# Repository Guidelines

## Project Structure & Module Organization
Python modules live under `src/reqre/`, scripts under `scripts/`, and tests in `tests/`. Keep new graph-rewriting logic in well-named modules (for example, `rules.py`, `matching.py`, `cypher.py`) to preserve the LHS/RHS workflow described in `README.md`.

## Build, Test, and Development Commands
- `python -m venv .venv` then `source .venv/bin/activate`: create and activate a local virtual environment.
- Install Gaphor system dependencies (for Gaphor import support):
  - Debian/Ubuntu: `sudo apt install libcairo2-dev pkg-config python3-dev libgirepository1.0-dev libgtk-4-dev gir1.2-pango-1.0 libgtksourceview-5-dev gir1.2-adw-1`
  - Fedora: `sudo dnf install cairo-devel pkgconf-pkg-config python3-devel gobject-introspection-devel gtk4-devel pango-devel gtksourceview5-devel libadwaita-devel`
  - Arch: `sudo pacman -S --needed cairo pkgconf python gobject-introspection gtk4 pango gtksourceview5 libadwaita`
- `pip install -r requirements.txt`: install runtime and test dependencies (`networkx`, `neo4j`, `pytest`, `gaphor`).
- `gaphor install-schemas`: run once after installing `requirements.txt`.
- `pytest`: run the test suite.
- `pre-commit install`: enable local git hooks.
- `pre-commit run --all-files`: run the full pre-commit suite.

Environment variables used by the repo:
- Required for Neo4j auth: `NEO4J_USER`, `NEO4J_PASSWORD`
- Optional Neo4j settings: `NEO4J_URI` (defaults to `bolt://localhost:7687`), `NEO4J_DATABASE`
- Optional Rhino Compute override: `REQRE_COMPUTE_URL` (defaults to `http://localhost:6500/`)
- Optional demo config override: `REQRE_DEMO_CONFIG` (defaults to `scripts/demo.config.json`)

## Coding Style & Naming Conventions
- Use Python 3 style with 4-space indentation and PEP 8 naming (`snake_case` for functions/variables, `PascalCase` for classes).
- Keep graph rewriting logic isolated in the `src/reqre/` package; avoid spreading rule logic into scripts or notebooks.
- Format and lint with `ruff` and `ruff-format` via pre-commit.

## Testing Guidelines
- Use `pytest` for unit tests and name files `test_*.py`.
- Prefer small, deterministic graph fixtures; keep test graphs minimal and focused on one rule behavior at a time.
- If coverage goals are introduced, document the threshold and how it is enforced.

## Commit & Pull Request Guidelines
- Follow the established commit message style in the repository history. If unsure, use conventional prefixes like `feat:`, `fix:`, `docs:`, `test:`, `chore:`.
- PRs should describe the rule change or behavior added, mention any new dependencies, and include tests where applicable.

## Issue Guidelines
- Use glab to update/create/close issues in the gitlab instance.
- Title format: verb-first, concise, and scoped (for example, "Support in-place label updates").
- Description format:
  - Brief problem statement and motivation.
  - "Acceptance" section with checklist/ticklist.
  - Testing notes if applicable.
- Labels: include at least one area label (for example, `Serialization`, `Feature`, `SysML`).
- Newline safety: some CLI tools treat literal `\n` as text and render it verbatim; prefer heredocs or multiline strings to preserve line breaks in issue descriptions.

## Notes for Contributors
- This project targets rule-based graph rewriting for SysML requirements; keep the LHS/RHS mental model visible in naming and module boundaries.
- If you add configuration or credentials for Neo4j, use environment variables and avoid committing secrets.

## DPO Rule JSON Import Hints
- The JSON rule format is validated against `src/reqre/schemas/dpo_rule.schema.json`.
- A rule object must include `left`, `interface`, and `right`. Optional top-level fields are `schema_version`, `rule_id`, `name`, `description`, `metadata`, and `nac`.
- `nac` is a list of negative application condition graphs. Each NAC graph follows the same shape as `left`/`interface`/`right` and is used to block rule application when the NAC pattern already exists.
- Each graph (`left`, `interface`, `right`, and each `nac` entry) contains `nodes` and `edges` arrays; both default to empty arrays when omitted.
- Nodes require a non-empty string `id`. `label` may be a string or array of strings. `props` may contain any JSON-compatible values.
- Edges require `source` and `target` (non-empty strings). Optional fields: `key` (string or number), `type` (string), `props` (any JSON values).
- `additionalProperties` is `false` for rule objects, graphs, nodes, and edges, so unknown fields will fail validation. Keep custom data inside `metadata` or `props`.
- When creating rules that should be idempotent, add a `nac` that blocks the rule if a target subgraph already exists (for example, a `SATISFIES` edge from the requirement).
- Nodes labeled `BuildingElement` must include `props.gh_file` and `props.detail_level` (allowed values: `D1`, `D2`, or `D3`).

## GH Assembly Hints
- Store interface pairing on `BuildingElement` relationships (for example `SUPPORTS`) using edge `props`; avoid relying on global type-to-interface defaults.
- Recommended edge property keys are `src_interface` and `dst_interface` where `src`/`dst` follow relationship direction.
- Assembly also accepts aliases such as `source_interface`/`target_interface`, `from_interface`/`to_interface`, and role-specific keys like `abutmentinterface` / `girderinterface`.
- For repeated relationships to the same component (for example two abutments supporting one girder), set interface props per edge so each connection can use different interface indices.
- Root selection order in GH assembly is: `start_element_id` override, then `start_element_name` override, then first `Abutment`, otherwise lexicographic fallback.
- Placement strategy is frontier-based: each step picks one unplaced node adjacent to the placed set and aligns only the new component toward the already assembled component.
- If an edge has no interface hints, assembly falls back to `AssemblyConfig.interface_priority` (and optional `interface_map` entries if provided).

## D3 Girder Module Workflow Hints
- Keep the modular girder flow at `detail_level: D2` for now, even though modules come from `t_girder_module_d3.gh`.
- `json_rules/girder_module_d3.json` is the initial replacement rule:
  - It preserves the canonical `t_girder_d2` node.
  - It introduces one `t_girder_module_d3` node.
  - It moves abutment-middle-wall interfaces from the monolithic D2 girder to the new module.
- `json_rules/girder_module_decomp_d3.json` is repeatable and must add exactly one module per application:
  - Growth is always from one fixed side (the selected tail side), not alternating sides.
  - Module-to-module mapping is `D3_GRD_interface4 -> D3_GRD_interface3`.
  - In the current rule version, the tail abutment-middle-wall/module connection uses `D3_GRD_interface1` on the module side.
- Length preservation is driven by the D2 girder length:
  - Read `D2_GRD_length` from the preserved `t_girder_d2` node.
  - Use module standard length `1000`.
  - Compute `target_modules = ceil(D2_GRD_length / 1000)`.
  - Apply decomposition rule `target_modules - current_modules` times (typically `target_modules - 1` right after initial replacement).
- When touching GH definitions for module parts, preserve D2/D3 parameter/output name compatibility (aliases/fallbacks) because some GH files may expose mixed naming.
