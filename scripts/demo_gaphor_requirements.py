"""Demo: import SysML requirements from a Gaphor file into Neo4j."""

from __future__ import annotations

import json
from pathlib import Path

from reqre.cypher import rule_to_cypher
from reqre.gaphor_requirements import (
    load_requirement_relationships_from_file,
    load_requirements_from_file,
    push_requirement_relationships_to_neo4j,
    push_requirements_to_neo4j,
)
from reqre.neo4j import Neo4jClient
from reqre.rules import DpoRule


def _load_rule(path: Path) -> DpoRule:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return DpoRule.from_json(payload, validate=True)


def _pause(message: str) -> None:
    input(message)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    gaphor_path = repo_root / "gaphor_files" / "Sample1.gaphor"
    rule_paths = [
        repo_root / "json_rules" / "requirements" / "satisfy_d1_1_bridge.json",
        repo_root / "json_rules" / "requirements" / "satisfy_d2_1_girder.json",
    ]

    requirements = load_requirements_from_file(gaphor_path)
    relationships = load_requirement_relationships_from_file(gaphor_path)
    if not requirements:
        print("No requirements found in", gaphor_path)
        return

    with Neo4jClient() as client:
        client.execute("MATCH (n) DETACH DELETE n")
        total = push_requirements_to_neo4j(client, requirements)
        rel_total = push_requirement_relationships_to_neo4j(client, relationships)
        print(f"Pushed {total} requirements from {gaphor_path}")
        print(f"Pushed {rel_total} requirement relationships from {gaphor_path}")
        _pause("Requirements pushed. Press Enter to apply rules...")

        for rule_path in rule_paths:
            rule = _load_rule(rule_path)
            cypher = rule_to_cypher(rule)
            client.execute(cypher.query, cypher.params)
            print(f"Applied {rule_path.name}.")
            _pause("Press Enter to continue...")


if __name__ == "__main__":
    main()
