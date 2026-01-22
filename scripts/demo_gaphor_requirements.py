"""Demo: import SysML requirements from a Gaphor file into Neo4j."""

from __future__ import annotations

from pathlib import Path

from reqre.gaphor_requirements import (
    load_requirement_relationships_from_file,
    load_requirements_from_file,
    push_requirement_relationships_to_neo4j,
    push_requirements_to_neo4j,
)
from reqre.neo4j import Neo4jClient


def main() -> None:
    gaphor_path = (
        Path(__file__).resolve().parents[1]
        / "gaphor_files"
        / "ArchBridgeRequirements.gaphor"
    )

    requirements = load_requirements_from_file(gaphor_path)
    relationships = load_requirement_relationships_from_file(gaphor_path)
    if not requirements:
        print("No requirements found in", gaphor_path)
        return

    with Neo4jClient() as client:
        total = push_requirements_to_neo4j(client, requirements)
        rel_total = push_requirement_relationships_to_neo4j(client, relationships)

    print(f"Pushed {total} requirements from {gaphor_path}")
    print(f"Pushed {rel_total} requirement relationships from {gaphor_path}")


if __name__ == "__main__":
    main()
