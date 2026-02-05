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
- A rule object must include `left`, `interface`, and `right`. Optional top-level fields are `schema_version`, `rule_id`, `name`, `description`, and `metadata`.
- Each graph (`left`, `interface`, `right`) contains `nodes` and `edges` arrays; both default to empty arrays when omitted.
- Nodes require a non-empty string `id`. `label` may be a string or array of strings. `props` may contain any JSON-compatible values.
- Edges require `source` and `target` (non-empty strings). Optional fields: `key` (string or number), `type` (string), `props` (any JSON values).
- `additionalProperties` is `false` for rule objects, graphs, nodes, and edges, so unknown fields will fail validation. Keep custom data inside `metadata` or `props`.
