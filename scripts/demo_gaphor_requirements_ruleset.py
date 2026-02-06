"""Demo: import SysML requirements from Gaphor, then apply JSON rules."""

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

CONFIG = {
    "gaphor_files": [
        "Sample1.gaphor",
    ],
    "json_rules": [
        "ReqD1-1.json",
        "ReqD2-1.json",
    ],
}


def _load_rule(path: Path) -> DpoRule:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return DpoRule.from_json(payload, validate=True)


def _pause(message: str) -> None:
    input(message)


def _describe_rule(rule: DpoRule, fallback: str) -> str:
    return getattr(rule, "name", None) or fallback


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    gaphor_root = repo_root / "gaphor_files"
    rules_root = repo_root / "json_rules"

    gaphor_paths = [gaphor_root / name for name in CONFIG["gaphor_files"]]
    rule_paths = [rules_root / name for name in CONFIG["json_rules"]]

    requirements: list[object] = []
    relationships: list[object] = []
    for gaphor_path in gaphor_paths:
        requirements.extend(load_requirements_from_file(gaphor_path))
        relationships.extend(load_requirement_relationships_from_file(gaphor_path))

    if not requirements:
        print("No requirements found in:", ", ".join(p.name for p in gaphor_paths))
        return

    rules = [_load_rule(path) for path in rule_paths]

    with Neo4jClient() as client:
        client.execute("MATCH (n) DETACH DELETE n")
        total = push_requirements_to_neo4j(client, requirements)
        rel_total = push_requirement_relationships_to_neo4j(client, relationships)

        print(
            f"Pushed {total} requirements and {rel_total} relationships "
            f"from {len(gaphor_paths)} Gaphor file(s)."
        )

        if rules:
            next_name = _describe_rule(rules[0], rule_paths[0].name)
            _pause(f"Next rule: {next_name}. Press Enter to apply...")

        for index, (rule, rule_path) in enumerate(zip(rules, rule_paths)):
            cypher = rule_to_cypher(rule)
            client.execute(cypher.query, cypher.params)
            print(f"Applied {rule_path.name}.")

            next_index = index + 1
            if next_index < len(rules):
                next_rule = rules[next_index]
                next_name = _describe_rule(next_rule, rule_paths[next_index].name)
                _pause(f"Next rule: {next_name}. Press Enter to continue...")


if __name__ == "__main__":
    main()
