# Repository Guidelines

## Quick Orientation
- This project is ReqRE: a Python graph-rewriting engine for SysML requirements, Neo4j host graphs, and Rhino Compute/Grasshopper bridge assembly.
- Current primary workflow is `scripts/demo.py`; it imports Gaphor requirements, applies staged DPO JSON rules, resolves GH parameters, assembles geometry, and writes staged `3dm` snapshots.
- Core source lives in `src/reqre/`; treat scripts as demos/orchestration unless the requested change is explicitly script behavior.
- Rule source-of-truth files live in `json_rules/`; GraphML examples live in `graphml_rules/`; GH definitions live in `gh_samples/`; sample SysML models live in `gaphor_files/`.
- Ignore generated/local artifacts such as `__pycache__/`, `.pytest_cache/`, `.env/`, `.venv/`, `src/reqre.egg-info/`, and `out/` unless the task explicitly targets them.

## Source Map
- `src/reqre/rules.py`: DPO rule data model, NetworkX `MultiDiGraph` helpers, JSON payload loading, NAC loading.
- `src/reqre/cypher.py`: DPO validation and Cypher serialization. Common-node/common-edge DPO invariants are enforced here.
- `src/reqre/schema.py` and `src/reqre/schemas/dpo_rule.schema.json`: JSON schema loading and validation for rule files.
- `src/reqre/graphml.py`: DPO GraphML import/export with reserved `reqre_*` metadata keys.
- `src/reqre/gaphor_requirements.py`: Gaphor SysML requirement and requirement-relationship import.
- `src/reqre/neo4j.py`: environment-driven Neo4j config and thin query client.
- `src/reqre/gh/registry.py`: GH definition/input models, path normalization, missing-definition errors.
- `src/reqre/gh/definitions.py`: registered GH files, required inputs, aliases, brep/interface output names.
- `src/reqre/gh/evaluate.py`: Rhino Compute health checks, GH evaluation, output decoding, D2/D3 output-name fallbacks.
- `src/reqre/gh/graph.py`: Neo4j discovery of `BuildingElement` nodes and relationships.
- `src/reqre/gh/assembly.py`: frontier-based component assembly, interface selection, default GH params.
- `src/reqre/gh/param_resolver.py`: graph-derived GH parameter synchronization and D2 module-count planning.

## Setup Commands
- `python -m venv .venv` then `source .venv/bin/activate`: create and activate a local virtual environment.
- Install Gaphor system dependencies before installing Python packages when `.gaphor` import is needed:
- Debian/Ubuntu: `sudo apt install libcairo2-dev pkg-config python3-dev libgirepository1.0-dev libgtk-4-dev gir1.2-pango-1.0 libgtksourceview-5-dev gir1.2-adw-1`
- Fedora: `sudo dnf install cairo-devel pkgconf-pkg-config python3-devel gobject-introspection-devel gtk4-devel pango-devel gtksourceview5-devel libadwaita-devel`
- Arch: `sudo pacman -S --needed cairo pkgconf python gobject-introspection gtk4 pango gtksourceview5 libadwaita`
- `pip install -e . -r requirements.txt pytest`: install package dependencies, runtime/demo dependencies, and test runner. `pyproject.toml` provides editable-package deps such as `gaphor`; `requirements.txt` provides Neo4j/Rhino/manim runtime deps.
- `gaphor install-schemas`: run once after installing Gaphor if loading `.gaphor` files.
- There is currently no checked-in pre-commit config. Do not claim `pre-commit run --all-files` is available unless a config is added.

## Environment Variables
- Required for Neo4j auth: `NEO4J_USER`, `NEO4J_PASSWORD`.
- Optional Neo4j settings: `NEO4J_URI` defaults to `bolt://localhost:7687`; `NEO4J_DATABASE` selects a database.
- Optional Rhino Compute override: `REQRE_COMPUTE_URL` defaults to `http://localhost:6500/`.
- Optional demo config override: `REQRE_DEMO_CONFIG` defaults to `scripts/demo.config.json`.
- Keep credentials in environment variables or ignored local files. Do not commit secrets or machine-specific paths.

## Verification
- `pytest`: run the full unit test suite. Most tests are pure Python and do not require live Neo4j or Rhino Compute.
- `pytest tests/test_cypher.py tests/test_rules.py tests/test_schema.py`: fast DPO/rule serialization checks after rule-model or schema changes.
- `pytest tests/test_gh_assembly.py tests/test_gh_param_resolver.py tests/test_gh_util.py`: GH assembly/parameter utility checks after GH path changes.
- `python scripts/validate_rules.py json_rules`: validate all JSON rules against the schema and `DpoRule.from_json`.
- `python scripts/demo.py`: integration/demo workflow only. It resets Neo4j demo state, requires Neo4j credentials, Gaphor schemas, Rhino Compute for assembly, and may write snapshots to configured local/SMB paths.

## Coding Style
- Use Python 3.9+ compatible syntax, 4-space indentation, PEP 8 names (`snake_case` functions/variables, `PascalCase` classes).
- Keep graph-rewriting behavior in `src/reqre/`; keep orchestration in `scripts/`.
- Prefer small, explicit dataclasses and pure helpers where practical; tests in this repo commonly construct minimal NetworkX or GH fixture objects directly.
- When adding dependencies, update `pyproject.toml` for package/import requirements and `requirements.txt` for demo/runtime extras if needed.
- Do not rewrite notebooks or generated outputs for ordinary source changes.

## Testing Guidelines
- Use `pytest`; name new test files `test_*.py`.
- Prefer deterministic, minimal graph fixtures. Keep each test focused on one rule, serializer, schema, GH assembly, or parameter-resolution behavior.
- For Cypher changes, assert both query text and params where possible; existing tests use exact expected Cypher strings.
- For JSON rule changes, run `python scripts/validate_rules.py` on the touched file or `json_rules/`.
- For GH assembly changes, mock Rhino Compute unless the task is explicitly an integration/demo run.

## DPO Rule JSON Rules
- JSON rules are validated against `src/reqre/schemas/dpo_rule.schema.json`.
- A rule object must include `left`, `interface`, and `right`. Optional top-level fields are `schema_version`, `rule_id`, `name`, `description`, `metadata`, and `nac`.
- `nac` is a list of negative application condition graphs. Use NACs for idempotency and guard conditions, for example to block creation when a `SATISFIES` edge already exists.
- Each graph contains `nodes` and `edges` arrays; both default to empty arrays when omitted.
- Nodes require non-empty string `id`. `label` may be a string or array of strings. `props` may contain JSON-compatible values.
- Edges require non-empty string `source` and `target`. Optional fields are `key`, `type`, and `props`.
- `additionalProperties` is `false` for rule objects, graphs, nodes, and edges; put custom data inside `metadata` or `props`.
- DPO invariants enforced by `rule_to_cypher`: `interface` must be a subgraph of both `left` and `right`; nodes or edges present in both `left` and `right` must be in `interface`; preserved node labels/props must stay identical.
- Nodes labeled `BuildingElement` must include `props.gh_file` and `props.detail_level`; supported detail levels are `D1`, `D2`, and `D3`.

## GraphML Rules
- GraphML export/import stores all DPO roles in one combined graph with reserved metadata keys such as `reqre_roles`, `reqre_props`, `reqre_labels`, and `reqre_edge_key`.
- Do not add user-level attributes beginning with `reqre_` to rule nodes/edges intended for GraphML export.
- `.gitignore` ignores `*.graphml` globally except under `graphml_rules/`; put checked-in GraphML rule fixtures there.

## GH Assembly Guidelines
- Register new GH definitions in `src/reqre/gh/definitions.py`; keep `gh_file`, required inputs, aliases, `brep_output`, and `interface_outputs` aligned with the actual `.gh` file.
- Add or update default parameter values in `AssemblyConfig.default_params` in `src/reqre/gh/assembly.py` when a definition must assemble without explicit graph params.
- GH file paths are normalized by `normalize_gh_path`; `gh/` maps to `gh_samples/`, backslashes are converted, and leading `./` is stripped.
- BuildingElement parameter extraction accepts `gh_params`, `params`, and `param_<input>` node properties. Preserve that compatibility when changing graph import/export.
- Store interface pairing on each `BuildingElement` relationship using edge `props`; prefer `src_interface` and `dst_interface`, where `src`/`dst` follow relationship direction.
- Assembly also accepts aliases such as `source_interface`/`target_interface`, `from_interface`/`to_interface`, and role-specific keys like `abutmentinterface` or `girderinterface`.
- For repeated relationships to the same component, set interface props per edge so each connection can use different interface indices.
- `AssemblyConfig.relationship_types` defaults to `("SUPPORTS",)`, while the main demo uses `("INTERFACES",)`. Match the graph data for the workflow you are changing.
- Root selection order is `start_element_id`, then `start_element_name`, then first `Abutment`, otherwise lexicographic fallback.
- Placement is frontier-based: each step picks one unplaced node adjacent to the placed set and aligns only the new component toward the already assembled component.
- If an edge has no interface hints, assembly falls back to `AssemblyConfig.interface_priority` and optional `interface_map` entries.

## D3 Girder Module Workflow Hints
- Keep the modular girder flow at `detail_level: D2` for now, even though modules come from `t_girder_module_d3.gh`.
- `json_rules/girder_module_d3.json` is the initial replacement rule: it preserves the canonical `t_girder_d2` node, introduces one `t_girder_module_d3` node, and moves abutment-middle-wall interfaces from the monolithic D2 girder to the new module.
- `json_rules/girder_module_decomp_d3.json` is repeatable and must add exactly one module per application.
- Growth is always from one fixed tail side, not alternating sides.
- Module-to-module mapping is `D3_GRD_interface4 -> D3_GRD_interface3`.
- In the current rule version, the tail abutment-middle-wall/module connection uses `D3_GRD_interface1` on the module side.
- Length preservation is driven by the D2 girder length: read `D2_GRD_length`, use module standard length `1000`, compute `target_modules = ceil(D2_GRD_length / 1000)`, then apply decomposition `target_modules - current_modules` times.
- When touching GH definitions for module parts, preserve D2/D3 parameter and output-name compatibility through aliases/fallbacks because some GH files expose mixed naming.

## Demo Workflow Notes
- `scripts/demo.py` loads `scripts/demo.config.json` when present and merges it over the built-in config.
- Stage order is requirements import, D1 model, D2 decomposition/module growth, Kappe, expansion, foundation, and Fahrbahn.
- The demo intentionally pauses after snapshots and may use `gio` for SMB destinations. Treat snapshot path changes as environment/config changes, not core engine changes.
- The demo applies grouped rules for girder modules and Kappe modules; do not add per-module snapshots unless explicitly requested.

## Issues, Commits, And PRs
- Use `glab` to update, create, or close issues in the GitLab instance when asked.
- Issue titles should be verb-first, concise, and scoped, for example `Support in-place label updates`.
- Issue descriptions should include a brief problem/motivation statement, an `Acceptance` checklist, and testing notes if applicable.
- Include at least one area label such as `Serialization`, `Feature`, or `SysML`.
- Some CLI tools render literal `\n`; prefer heredocs or true multiline input for issue descriptions.
- Follow existing commit style when visible. If unsure, use conventional prefixes such as `feat:`, `fix:`, `docs:`, `test:`, or `chore:`.
- PRs should describe the rule or behavior change, mention dependency/config impacts, and list tests or validation commands run.
