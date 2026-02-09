"""CLI entrypoint to discover Grasshopper definitions from Neo4j."""

from __future__ import annotations

import argparse
from pathlib import Path

from reqre.neo4j import Neo4jClient

from .definitions import build_default_registry, register_directory_definitions
from .graph import load_requirements_from_graph


def _format_summary(requirements) -> str:
    lines = []
    for gh_file, elements in sorted(requirements.elements_by_file.items()):
        lines.append(f"{gh_file}: {len(elements)} element(s)")
    if not lines:
        lines.append("No BuildingElement nodes with gh_file found.")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="List Grasshopper definitions needed by BuildingElement nodes."
    )
    parser.add_argument(
        "--gh-root",
        default="gh_samples",
        help="Directory that contains Grasshopper definitions.",
    )
    parser.add_argument(
        "--include-placeholders",
        action="store_true",
        help="Register placeholder definitions for any .gh files in gh-root.",
    )
    args = parser.parse_args()

    registry = build_default_registry()
    if args.include_placeholders:
        register_directory_definitions(registry, Path(args.gh_root))

    with Neo4jClient() as client:
        requirements = load_requirements_from_graph(client, registry)

    print(_format_summary(requirements))

    if requirements.missing_files:
        print("\nMissing definitions:")
        for missing in requirements.missing_files:
            print(f"- {missing}")


if __name__ == "__main__":
    main()
