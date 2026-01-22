# Repository Guidelines

## Project Structure & Module Organization
This repository is currently minimal and focused on the core concept in `README.md` plus Python dependencies in `requirements.txt`. As code is added, place Python modules in a top-level package directory (for example, `reqre/`) and keep scripts in `scripts/`. If tests are introduced, use a `tests/` directory alongside the package.

## Build, Test, and Development Commands
- `python -m venv .venv` then `source .venv/bin/activate`: create and activate a local virtual environment.
- `pip install -r requirements.txt`: install runtime and test dependencies (`networkx`, `neo4j`, `pytest`).
- `pytest`: run the test suite once tests exist.

## Coding Style & Naming Conventions
- Use Python 3 style with 4-space indentation and PEP 8 naming (`snake_case` for functions/variables, `PascalCase` for classes).
- Keep graph rewriting logic isolated in well-named modules (for example, `rules.py`, `matching.py`, `cypher.py`) to mirror the LHS/RHS workflow described in `README.md`.
- No formatter or linter is configured yet; if you add one, document it here and pin it in `requirements.txt`.

## Testing Guidelines
- Use `pytest` for unit tests and name files `test_*.py`.
- Prefer small, deterministic graph fixtures; keep test graphs minimal and focused on one rule behavior at a time.
- If coverage goals are introduced, document the threshold and how it is enforced.

## Commit & Pull Request Guidelines
- There is no commit history yet, so no established commit message convention. If you introduce one, keep it consistent and document it here (for example, `feat:`, `fix:`, `docs:` prefixes).
- PRs should describe the rule change or behavior added, mention any new dependencies, and include tests where applicable.

## Notes for Contributors
- This project targets rule-based graph rewriting for SysML requirements; keep the LHS/RHS mental model visible in naming and module boundaries.
- If you add configuration or credentials for Neo4j, use environment variables and avoid committing secrets.
