#!/usr/bin/env python3
"""Manual demo for executing Cypher against a local Neo4j instance."""

from __future__ import annotations

import argparse
import sys
from typing import Optional

from reqre.neo4j import Neo4jClient, Neo4jConfigError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a Cypher query against a local Neo4j instance."
    )
    parser.add_argument(
        "--query",
        default="MATCH (n) RETURN count(n) AS total",
        help="Cypher query to execute.",
    )
    parser.add_argument("--uri", default=None, help="Neo4j bolt URI.")
    parser.add_argument("--user", default=None, help="Neo4j username.")
    parser.add_argument("--password", default=None, help="Neo4j password.")
    parser.add_argument("--database", default=None, help="Neo4j database name.")
    return parser.parse_args()


def run_query(
    *,
    query: str,
    uri: Optional[str],
    user: Optional[str],
    password: Optional[str],
    database: Optional[str],
) -> int:
    try:
        with Neo4jClient(
            uri=uri, user=user, password=password, database=database
        ) as client:
            rows = client.execute(query, database=database)
    except Neo4jConfigError as exc:
        print(f"Neo4j config error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Neo4j query error: {exc}", file=sys.stderr)
        return 1

    print("Query:")
    print(query)
    print("Rows:")
    if rows:
        for row in rows:
            print(f"  {row}")
    else:
        print("  <no rows>")
    return 0


def main() -> None:
    args = parse_args()
    raise SystemExit(
        run_query(
            query=args.query,
            uri=args.uri,
            user=args.user,
            password=args.password,
            database=args.database,
        )
    )


if __name__ == "__main__":
    main()
