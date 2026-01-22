"""Neo4j connection helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from neo4j import GraphDatabase


class Neo4jConfigError(ValueError):
    """Raised when required Neo4j configuration is missing."""


@dataclass(frozen=True)
class Neo4jConfig:
    uri: str
    user: str
    password: str
    database: Optional[str] = None

    @classmethod
    def from_env(
        cls,
        *,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
    ) -> "Neo4jConfig":
        resolved_uri = uri or os.getenv("NEO4J_URI") or "bolt://localhost:7687"
        resolved_user = user or os.getenv("NEO4J_USER")
        resolved_password = password or os.getenv("NEO4J_PASSWORD")
        resolved_database = database or os.getenv("NEO4J_DATABASE")

        missing = [
            name
            for name, value in (
                ("NEO4J_USER", resolved_user),
                ("NEO4J_PASSWORD", resolved_password),
            )
            if not value
        ]
        if missing:
            raise Neo4jConfigError(
                "Missing Neo4j credentials. "
                "Set NEO4J_USER and NEO4J_PASSWORD or pass them explicitly."
            )

        return cls(
            uri=resolved_uri,
            user=resolved_user,
            password=resolved_password,
            database=resolved_database,
        )


class Neo4jClient:
    """Simple Neo4j client for executing Cypher queries."""

    def __init__(
        self,
        *,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
    ) -> None:
        self._config = Neo4jConfig.from_env(
            uri=uri, user=user, password=password, database=database
        )
        self._driver = GraphDatabase.driver(
            self._config.uri, auth=(self._config.user, self._config.password)
        )

    def close(self) -> None:
        self._driver.close()

    def __enter__(self) -> "Neo4jClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def execute(
        self,
        query: str,
        params: Optional[Mapping[str, Any]] = None,
        *,
        database: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        if not query or not query.strip():
            raise ValueError("Cypher query must be a non-empty string.")

        with self._driver.session(
            database=database or self._config.database
        ) as session:
            result = session.run(query, params or {})
            return [record.data() for record in result]
