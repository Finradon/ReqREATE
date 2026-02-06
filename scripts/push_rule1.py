#!/usr/bin/env python3
"""Load rule1 JSON, serialize to Cypher, and push to Neo4j."""

from __future__ import annotations

import json
from pathlib import Path

from reqre.cypher import rule_to_cypher
from reqre.neo4j import Neo4jClient
from reqre.rules import DpoRule


def _load_rule(path: Path) -> DpoRule:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return DpoRule.from_json(payload, validate=True)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    rule_path = repo_root / "json_rules" / "rule1.json"

    rule = _load_rule(rule_path)
    cypher = rule_to_cypher(rule)

    print(cypher)
    with Neo4jClient() as client:
        client.execute(cypher.query, cypher.params)

    print("Applied rule1 to Neo4j.")


if __name__ == "__main__":
    main()
