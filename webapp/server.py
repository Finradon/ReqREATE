#!/usr/bin/env python3
"""Small ReqRE web app server.

The backend deliberately uses the Python standard library for HTTP serving. It
keeps the web app isolated in this directory while calling the same ReqRE
workflow primitives used by ``scripts/demo.py``.
"""

from __future__ import annotations

import json
import mimetypes
import os
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
STATIC_ROOT = Path(__file__).resolve().parent / "static"
MODELS_ROOT = STATIC_ROOT / "models"

for search_path in (str(SRC_ROOT), str(REPO_ROOT)):
    if search_path not in sys.path:
        sys.path.insert(0, search_path)

from reqre.cypher import rule_to_cypher  # noqa: E402
from reqre.gaphor_requirements import (  # noqa: E402
    load_requirement_relationships_from_file,
    load_requirements_from_file,
    push_requirement_relationships_to_neo4j,
    push_requirements_to_neo4j,
)
from reqre.gh import (  # noqa: E402
    AssemblyConfig,
    BridgeParameters,
    assemble_from_graph,
    build_default_registry,
    resolve_d1_parameters,
    resolve_d2_module_plan,
    write_assembly_glb,
)
from reqre.neo4j import Neo4jClient  # noqa: E402
from scripts import demo as demo_workflow  # noqa: E402


DEMO_ACTIONS = [
    {
        "id": "run_d1_stage",
        "label": "Run D1 Stage",
        "description": "Apply the D1 demo rules and resolve D1 parameters.",
    },
    {
        "id": "run_d2_stage",
        "label": "Run D2 Stage",
        "description": "Apply D2 decomposition rules and grow girder modules.",
    },
    {
        "id": "resolve_d1_parameters",
        "label": "Resolve D1 Parameters",
        "description": "Synchronize D1 abutment/girder parameters from requirements.",
    },
    {
        "id": "grow_d2_modules",
        "label": "Grow D2 Modules",
        "description": "Use D2 girder length to add the required D3 girder modules.",
    },
    {
        "id": "run_kappe_per_module",
        "label": "Add Kappe",
        "description": "Apply the configured Kappe rules once per girder module.",
    },
    {
        "id": "run_expansion",
        "label": "Add Expansion",
        "description": "Apply the expansion joint rules from the demo config.",
    },
    {
        "id": "run_foundation",
        "label": "Add Foundations",
        "description": "Apply the configured foundation rules and repeat counts.",
    },
    {
        "id": "run_fahrbahn",
        "label": "Add Fahrbahn",
        "description": "Apply the Fahrbahn rule from the demo config.",
    },
]


class ReqREWebEngine:
    def __init__(self) -> None:
        self.config = demo_workflow.CONFIG
        self.registry = build_default_registry()
        self.operation_lock = threading.Lock()
        self.state_lock = threading.Lock()
        self.initialized = False
        self.step_index = 0
        self.history: list[dict[str, Any]] = []
        self.last_preview: dict[str, Any] | None = None
        self.last_message: str | None = None
        self.bridge_parameters = BridgeParameters(
            length=20000.0,
            width=10000.0,
            height=4000.0,
        )
        MODELS_ROOT.mkdir(parents=True, exist_ok=True)

    def status(self) -> dict[str, Any]:
        stats: dict[str, Any] | None = None
        stats_error: str | None = None
        if self.initialized:
            try:
                with Neo4jClient() as client:
                    stats = self._graph_stats(client)
            except Exception as exc:
                stats_error = str(exc)

        with self.state_lock:
            return {
                "ok": True,
                "initialized": self.initialized,
                "busy": self.operation_lock.locked(),
                "step_index": self.step_index,
                "history": list(self.history),
                "preview": self.last_preview,
                "message": self.last_message,
                "stats": stats,
                "stats_error": stats_error,
                "config": self._public_config(),
            }

    def rules(self) -> dict[str, Any]:
        grouped = self._rule_groups()
        rules: list[dict[str, Any]] = []
        rule_root = REPO_ROOT / "json_rules"
        for path in self._iter_rule_paths():
            rule_id = path.relative_to(rule_root).as_posix()
            payload = self._read_rule_metadata(path)
            rules.append(
                {
                    "id": rule_id,
                    "label": payload.get("name") or path.stem,
                    "description": payload.get("description") or "",
                    "group": grouped.get(rule_id, "Other Rules"),
                }
            )
        return {"ok": True, "rules": rules, "actions": DEMO_ACTIONS}

    def graph(
        self, *, node_limit: int = 500, relationship_limit: int = 900
    ) -> dict[str, Any]:
        node_limit = _coerce_positive_int(
            node_limit, field="node_limit", maximum=5000
        )
        relationship_limit = _coerce_positive_int(
            relationship_limit, field="relationship_limit", maximum=10000
        )
        with Neo4jClient() as client:
            node_rows = client.execute(
                """
MATCH (n)
RETURN elementId(n) AS id,
       labels(n) AS labels,
       properties(n) AS props
ORDER BY id
LIMIT $limit
""",
                {"limit": node_limit},
            )
            nodes = [
                {
                    "id": str(row.get("id")),
                    "labels": _json_safe(row.get("labels") or []),
                    "props": _json_safe(row.get("props") or {}),
                }
                for row in node_rows
                if row.get("id") is not None
            ]
            node_ids = [node["id"] for node in nodes]
            relationship_rows: list[dict[str, Any]] = []
            if node_ids:
                relationship_rows = client.execute(
                    """
MATCH (a)-[r]->(b)
WHERE elementId(a) IN $node_ids
  AND elementId(b) IN $node_ids
RETURN elementId(r) AS id,
       elementId(a) AS source,
       elementId(b) AS target,
       type(r) AS type,
       properties(r) AS props
ORDER BY id
LIMIT $limit
""",
                    {"node_ids": node_ids, "limit": relationship_limit},
                )
            relationships = [
                {
                    "id": str(row.get("id")),
                    "source": str(row.get("source")),
                    "target": str(row.get("target")),
                    "type": str(row.get("type")),
                    "props": _json_safe(row.get("props") or {}),
                }
                for row in relationship_rows
                if row.get("id") is not None
            ]
            stats = self._graph_stats(client)

        return {
            "ok": True,
            "nodes": nodes,
            "relationships": relationships,
            "counts": stats,
            "truncated": (
                len(nodes) >= node_limit
                or len(relationships) >= relationship_limit
            ),
        }

    def reset(
        self,
        preview_detail: str = "auto",
        bridge_parameters: BridgeParameters | None = None,
    ) -> dict[str, Any]:
        with self.operation_lock:
            self._update_bridge_parameters(bridge_parameters)
            requirements, relationships, gaphor_names = self._load_requirements()
            with Neo4jClient() as client:
                client.execute("MATCH (n) DETACH DELETE n")
                total = push_requirements_to_neo4j(client, requirements)
                rel_total = push_requirement_relationships_to_neo4j(
                    client, relationships
                )
                preview = self._export_preview(client, preview_detail)
                stats = self._graph_stats(client)

            message = (
                f"Imported {total} requirements and {rel_total} relationships "
                f"from {len(gaphor_names)} Gaphor file(s)."
            )
            self._record("Reset graph", message, preview)
            with self.state_lock:
                self.initialized = True
                self.step_index = 0
                self.history = [
                    {
                        "step": 0,
                        "label": "Reset graph",
                        "detail": message,
                        "time": _timestamp(),
                    }
                ]
                self.last_message = message
                self.last_preview = preview
            return self._operation_response(message, preview, stats)

    def apply_rule(
        self,
        rule_id: str,
        *,
        times: int = 1,
        preview_detail: str = "auto",
        bridge_parameters: BridgeParameters | None = None,
    ) -> dict[str, Any]:
        run_count = _coerce_positive_int(times, field="times", maximum=100)
        rule_path = self._rule_path(rule_id)

        with self.operation_lock:
            self._update_bridge_parameters(bridge_parameters)
            with Neo4jClient() as client:
                self._apply_rule_path(client, rule_path, run_count)
                preview = self._export_preview(client, preview_detail)
                stats = self._graph_stats(client)

            message = f"Applied {rule_path.name} {run_count} time(s)."
            self._record_next(rule_path.name, message, preview)
            return self._operation_response(message, preview, stats)

    def preview(
        self,
        preview_detail: str = "auto",
        bridge_parameters: BridgeParameters | None = None,
    ) -> dict[str, Any]:
        with self.operation_lock:
            self._update_bridge_parameters(bridge_parameters)
            with Neo4jClient() as client:
                preview = self._export_preview(client, preview_detail)
                stats = self._graph_stats(client)

            message = "Preview refreshed."
            with self.state_lock:
                self.last_message = message
                self.last_preview = preview
            return self._operation_response(message, preview, stats)

    def run_action(
        self,
        action_id: str,
        preview_detail: str = "auto",
        bridge_parameters: BridgeParameters | None = None,
    ) -> dict[str, Any]:
        with self.operation_lock:
            self._update_bridge_parameters(bridge_parameters)
            with Neo4jClient() as client:
                message = self._run_action(client, action_id)
                preview = self._export_preview(client, preview_detail)
                stats = self._graph_stats(client)

            label = self._action_label(action_id)
            self._record_next(label, message, preview)
            return self._operation_response(message, preview, stats)

    def _run_action(self, client: Neo4jClient, action_id: str) -> str:
        if action_id == "run_d1_stage":
            count = self._apply_rule_group(client, "d1_stage_rules")
            if self.config.get("run_d1_param_resolver"):
                resolved = resolve_d1_parameters(
                    client,
                    write_shared_parameter_nodes=bool(
                        self.config.get("write_shared_parameter_nodes")
                    ),
                )
                return (
                    f"Applied {count} D1 rule(s) and resolved "
                    f"{len(resolved)} D1 parameter pair(s)."
                )
            return f"Applied {count} D1 rule(s)."

        if action_id == "run_d2_stage":
            count = self._apply_rule_group(client, "d2_stage_rules")
            module_message = self._grow_d2_modules(client)
            return f"Applied {count} D2 rule(s). {module_message}"

        if action_id == "resolve_d1_parameters":
            resolved = resolve_d1_parameters(
                client,
                write_shared_parameter_nodes=bool(
                    self.config.get("write_shared_parameter_nodes")
                ),
            )
            return f"Resolved D1 parameters for {len(resolved)} pair(s)."

        if action_id == "grow_d2_modules":
            return self._grow_d2_modules(client)

        if action_id == "run_kappe_per_module":
            count, module_count = self._apply_rules_per_module_count(
                client, "kappe_rules"
            )
            return (
                f"Applied {count} Kappe rule execution(s) "
                f"for {module_count} module(s)."
            )

        if action_id == "run_expansion":
            count = self._apply_rule_group(client, "expansion_rules")
            return f"Applied {count} expansion rule(s)."

        if action_id == "run_foundation":
            count = self._apply_foundation_rules(client)
            return f"Applied {count} foundation rule execution(s)."

        if action_id == "run_fahrbahn":
            count = self._apply_rule_group(client, "fahrbahn_rules")
            return f"Applied {count} Fahrbahn rule(s)."

        raise ValueError(f"Unknown action: {action_id}")

    def _apply_rule_group(self, client: Neo4jClient, config_key: str) -> int:
        rule_names = [str(name) for name in self.config.get(config_key, [])]
        for rule_name in rule_names:
            self._apply_rule_path(client, self._rule_path(rule_name), 1)
        return len(rule_names)

    def _apply_foundation_rules(self, client: Neo4jClient) -> int:
        total = 0
        for spec in self.config.get("foundation_rules", []):
            rule_path = self._rule_path(str(spec["file"]))
            count = max(0, int(spec.get("times", 1)))
            if count:
                self._apply_rule_path(client, rule_path, count)
                total += count
        return total

    def _apply_rules_per_module_count(
        self, client: Neo4jClient, config_key: str
    ) -> tuple[int, int]:
        module_count = int(demo_workflow._count_d2_modules(client))
        if module_count <= 0:
            return (0, 0)

        total = 0
        for rule_name in self.config.get(config_key, []):
            self._apply_rule_path(client, self._rule_path(str(rule_name)), module_count)
            total += module_count
        return total, module_count

    def _grow_d2_modules(self, client: Neo4jClient) -> str:
        module_rule_name = str(self.config["module_decomp_rule"])
        module_rule_path = self._rule_path(module_rule_name)
        module_rule = demo_workflow._load_rule(module_rule_path)
        cypher = rule_to_cypher(module_rule)
        plan = resolve_d2_module_plan(
            client,
            module_length=float(self.config["module_length"]),
            length_param=str(self.config["d2_length_param"]),
            bridge_parameters=self.bridge_parameters,
        )
        if plan.current_modules == 0 and plan.target_modules > 0:
            raise RuntimeError(
                "No D3 modules found for the D2 girder. Apply "
                "the configured initial girder module rule before growing modules."
            )
        for _ in range(plan.insertions_required):
            before = resolve_d2_module_plan(
                client,
                module_length=float(self.config["module_length"]),
                length_param=str(self.config["d2_length_param"]),
                bridge_parameters=self.bridge_parameters,
            )
            client.execute(cypher.query, cypher.params)
            after = resolve_d2_module_plan(
                client,
                module_length=float(self.config["module_length"]),
                length_param=str(self.config["d2_length_param"]),
                bridge_parameters=self.bridge_parameters,
            )
            if after.current_modules != before.current_modules + 1:
                raise RuntimeError(
                    "Module decomposition did not add exactly one module: "
                    f"before={before.current_modules}, after={after.current_modules}."
                )
        final_plan = resolve_d2_module_plan(
            client,
            module_length=float(self.config["module_length"]),
            length_param=str(self.config["d2_length_param"]),
            bridge_parameters=self.bridge_parameters,
        )
        return (
            f"Target modules: {final_plan.target_modules}; "
            f"current modules: {final_plan.current_modules}; "
            f"inserted {plan.insertions_required}."
        )

    def _apply_rule_path(
        self, client: Neo4jClient, rule_path: Path, times: int
    ) -> None:
        rule = demo_workflow._load_rule(rule_path)
        cypher = rule_to_cypher(rule)
        for _ in range(times):
            client.execute(cypher.query, cypher.params)

    def _export_preview(
        self, client: Neo4jClient, preview_detail: str = "auto"
    ) -> dict[str, Any]:
        detail = str(preview_detail or "auto").upper()
        details = ("D2", "D1") if detail == "AUTO" else (detail,)
        attempts: list[dict[str, Any]] = []

        for detail_level in details:
            config = self._assembly_config(detail_level)
            try:
                outcome = assemble_from_graph(client, self.registry, config=config)
            except Exception as exc:
                attempts.append(
                    {
                        "detail_level": detail_level,
                        "connected": False,
                        "reason": str(exc),
                    }
                )
                continue

            if outcome.connected and outcome.components:
                filename = f"state_{int(time.time() * 1000)}.glb"
                model_path = MODELS_ROOT / filename
                write_assembly_glb(
                    model_path,
                    outcome.components,
                    definition_colors=self.config.get("definition_colors", {}),
                )
                return {
                    "connected": True,
                    "detail_level": detail_level,
                    "model_url": f"/models/{filename}",
                    "component_count": len(outcome.components),
                    "root_id": str(outcome.root_id),
                    "order": [str(node_id) for node_id in outcome.order],
                    "missing_definitions": outcome.missing_definitions,
                    "generated_at": _timestamp(),
                }

            attempts.append(
                {
                    "detail_level": detail_level,
                    "connected": False,
                    "reason": outcome.reason or "No assembled components.",
                    "missing_definitions": outcome.missing_definitions,
                }
            )

        return {
            "connected": False,
            "detail_level": detail,
            "model_url": None,
            "component_count": 0,
            "attempts": attempts,
            "reason": _preview_reason(attempts),
            "generated_at": _timestamp(),
        }

    def _assembly_config(self, detail_level: str) -> AssemblyConfig:
        return AssemblyConfig(
            detail_level=detail_level,
            relationship_types=tuple(self.config["relationship_types"]),
            allowed_definitions=demo_workflow._allowed_definitions_for_detail(
                detail_level
            ),
            compute_url=str(self.config["compute_url"]),
            gh_root=REPO_ROOT / str(self.config["gh_root"]),
            start_element_id=self.config.get("start_id"),
            start_element_name=self.config.get("start_name"),
            allow_interface_reuse=bool(self.config.get("allow_interface_reuse")),
            flip_normals=bool(self.config.get("flip_normals")),
            bridge_parameters=self.bridge_parameters,
        )

    def _load_requirements(self) -> tuple[list[Any], list[Any], list[str]]:
        requirements: list[Any] = []
        relationships: list[Any] = []
        names: list[str] = []
        for name in self.config.get("gaphor_files", []):
            path = REPO_ROOT / "gaphor_files" / str(name)
            if not path.exists():
                raise FileNotFoundError(f"Configured Gaphor file not found: {path}")
            names.append(path.name)
            requirements.extend(load_requirements_from_file(path))
            relationships.extend(load_requirement_relationships_from_file(path))
        if not requirements:
            raise RuntimeError("No requirements found in configured Gaphor files.")
        return requirements, relationships, names

    def _graph_stats(self, client: Neo4jClient) -> dict[str, int]:
        rows = client.execute(
            """
MATCH (n)
WITH count(n) AS nodes
OPTIONAL MATCH ()-[r]->()
WITH nodes, count(r) AS relationships
OPTIONAL MATCH (be:BuildingElement)
RETURN nodes, relationships, count(be) AS building_elements
"""
        )
        base = rows[0] if rows else {}
        return {
            "nodes": int(base.get("nodes", 0)),
            "relationships": int(base.get("relationships", 0)),
            "building_elements": int(base.get("building_elements", 0)),
            "d2_modules": int(demo_workflow._count_d2_modules(client)),
        }

    def _rule_path(self, rule_id: str) -> Path:
        rule_root = (REPO_ROOT / "json_rules").resolve()
        rel_path = Path(rule_id)
        if rel_path.is_absolute() or ".." in rel_path.parts:
            raise ValueError("Rule id must be a safe relative path.")
        if rel_path.parts[:1] == ("legacy",):
            raise ValueError("Legacy rules are not available in the web app.")
        path = (rule_root / rel_path).resolve()
        try:
            path.relative_to(rule_root)
        except ValueError as exc:
            raise ValueError("Rule id must stay within json_rules.") from exc
        if not path.exists() or path.suffix != ".json":
            raise FileNotFoundError(f"Rule not found: {rule_id}")
        return path

    def _record_next(
        self, label: str, detail: str, preview: dict[str, Any] | None
    ) -> None:
        with self.state_lock:
            self.initialized = True
            self.step_index += 1
            self.history.append(
                {
                    "step": self.step_index,
                    "label": label,
                    "detail": detail,
                    "time": _timestamp(),
                }
            )
            self.history = self.history[-30:]
            self.last_message = detail
            self.last_preview = preview

    def _record(
        self, label: str, detail: str, preview: dict[str, Any] | None
    ) -> None:
        with self.state_lock:
            self.last_message = detail
            self.last_preview = preview

    def _operation_response(
        self,
        message: str,
        preview: dict[str, Any],
        stats: dict[str, Any],
    ) -> dict[str, Any]:
        with self.state_lock:
            return {
                "ok": True,
                "message": message,
                "initialized": self.initialized,
                "step_index": self.step_index,
                "history": list(self.history),
                "preview": preview,
                "stats": stats,
                "config": self._public_config(),
            }

    def _public_config(self) -> dict[str, Any]:
        return {
            "gaphor_files": [str(name) for name in self.config.get("gaphor_files", [])],
            "compute_url": str(self.config.get("compute_url")),
            "neo4j_uri": os.getenv("NEO4J_URI") or "bolt://localhost:7687",
            "detail_level": str(self.config.get("detail_level", "D2")),
            "relationship_types": [
                str(value) for value in self.config.get("relationship_types", [])
            ],
            "bridge_parameters": {
                "length": self.bridge_parameters.length,
                "width": self.bridge_parameters.width,
                "height": self.bridge_parameters.height,
            },
        }

    def _update_bridge_parameters(
        self, bridge_parameters: BridgeParameters | None
    ) -> None:
        if bridge_parameters is None:
            return
        with self.state_lock:
            self.bridge_parameters = bridge_parameters

    def _rule_groups(self) -> dict[str, str]:
        groups: dict[str, str] = {}
        labels = {
            "d1_stage_rules": "Demo Stage: D1",
            "d2_stage_rules": "Demo Stage: D2",
            "kappe_rules": "Demo Stage: Kappe",
            "expansion_rules": "Demo Stage: Expansion",
            "fahrbahn_rules": "Demo Stage: Fahrbahn",
        }
        for key, label in labels.items():
            for rule_name in self.config.get(key, []):
                groups[str(rule_name)] = label
        for spec in self.config.get("foundation_rules", []):
            groups[str(spec["file"])] = "Demo Stage: Foundation"
        groups[str(self.config["module_decomp_rule"])] = "Demo Stage: D2"
        return groups

    def _iter_rule_paths(self) -> list[Path]:
        rule_root = REPO_ROOT / "json_rules"
        paths: list[Path] = []
        for path in sorted(rule_root.rglob("*.json")):
            rel_path = path.relative_to(rule_root)
            if rel_path.parts[:1] == ("legacy",):
                continue
            paths.append(path)
        return paths

    def _read_rule_metadata(self, path: Path) -> dict[str, Any]:
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _action_label(self, action_id: str) -> str:
        for action in DEMO_ACTIONS:
            if action["id"] == action_id:
                return action["label"]
        return action_id


class ReqRERequestHandler(BaseHTTPRequestHandler):
    engine: ReqREWebEngine

    server_version = "ReqREWebApp/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/status":
                self._send_json(self.engine.status())
                return
            if parsed.path == "/api/rules":
                self._send_json(self.engine.rules())
                return
            if parsed.path == "/api/graph":
                params = parse_qs(parsed.query)
                node_limit = int((params.get("node_limit") or ["500"])[0])
                relationship_limit = int(
                    (params.get("relationship_limit") or ["900"])[0]
                )
                self._send_json(
                    self.engine.graph(
                        node_limit=node_limit,
                        relationship_limit=relationship_limit,
                    )
                )
                return
        except Exception as exc:
            self._send_json(
                {
                    "ok": False,
                    "error": str(exc),
                    "error_type": exc.__class__.__name__,
                },
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return
        self._serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            payload = self._read_json()
            if parsed.path == "/api/reset":
                response = self.engine.reset(
                    _preview_detail(payload),
                    bridge_parameters=_bridge_parameters(payload),
                )
            elif parsed.path == "/api/apply-rule":
                response = self.engine.apply_rule(
                    str(payload.get("rule_id", "")),
                    times=int(payload.get("times", 1)),
                    preview_detail=_preview_detail(payload),
                    bridge_parameters=_bridge_parameters(payload),
                )
            elif parsed.path == "/api/action":
                response = self.engine.run_action(
                    str(payload.get("action_id", "")),
                    preview_detail=_preview_detail(payload),
                    bridge_parameters=_bridge_parameters(payload),
                )
            elif parsed.path == "/api/preview":
                response = self.engine.preview(
                    _preview_detail(payload),
                    bridge_parameters=_bridge_parameters(payload),
                )
            else:
                self._send_json(
                    {"ok": False, "error": f"Unknown API route: {parsed.path}"},
                    HTTPStatus.NOT_FOUND,
                )
                return
            self._send_json(response)
        except Exception as exc:
            self._send_json(
                {
                    "ok": False,
                    "error": str(exc),
                    "error_type": exc.__class__.__name__,
                },
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def _serve_static(self, request_path: str) -> None:
        relative = unquote(request_path.lstrip("/")) or "index.html"
        target = (STATIC_ROOT / relative).resolve()
        static_root = STATIC_ROOT.resolve()
        try:
            target.relative_to(static_root)
        except ValueError:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if target.is_dir():
            target = target / "index.html"
        if not target.exists() or not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        content_type = mimetypes.guess_type(str(target))[0]
        if target.suffix == ".glb":
            content_type = "model/gltf-binary"
        content_type = content_type or "application/octet-stream"
        data = target.read_bytes()

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        if target.suffix == ".glb":
            self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("API payload must be a JSON object.")
        return payload

    def _send_json(
        self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK
    ) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write("[reqre-web] " + format % args + "\n")


def _preview_detail(payload: dict[str, Any]) -> str:
    detail = str(payload.get("preview_detail", "auto") or "auto").lower()
    if detail not in {"auto", "d1", "d2"}:
        raise ValueError("preview_detail must be one of: auto, d1, d2.")
    return detail


def _bridge_parameters(payload: dict[str, Any]) -> BridgeParameters | None:
    raw = payload.get("bridge_parameters")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("bridge_parameters must be a JSON object.")
    return BridgeParameters(
        length=_positive_optional_float(raw.get("length"), "length"),
        width=_positive_optional_float(raw.get("width"), "width"),
        height=_positive_optional_float(raw.get("height"), "height"),
    )


def _positive_optional_float(value: Any, field: str) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise ValueError(f"Bridge {field} must be a positive number.")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Bridge {field} must be a positive number.") from exc
    if numeric <= 0:
        raise ValueError(f"Bridge {field} must be a positive number.")
    return numeric


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return str(value)


def _preview_reason(attempts: list[dict[str, Any]]) -> str:
    if not attempts:
        return "No assembly attempt was made."
    return "; ".join(
        f"{attempt.get('detail_level')}: {attempt.get('reason')}"
        for attempt in attempts
    )


def _coerce_positive_int(value: int, *, field: str, maximum: int) -> int:
    try:
        result = int(value)
    except Exception as exc:
        raise ValueError(f"{field} must be an integer.") from exc
    if result <= 0 or result > maximum:
        raise ValueError(f"{field} must be between 1 and {maximum}.")
    return result


def _timestamp() -> str:
    return time.strftime("%H:%M:%S")


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    host = os.getenv("REQRE_WEB_HOST", "127.0.0.1")
    port = int(os.getenv("REQRE_WEB_PORT", "8080"))
    if argv:
        port = int(argv[0])

    engine = ReqREWebEngine()
    ReqRERequestHandler.engine = engine
    server = ThreadingHTTPServer((host, port), ReqRERequestHandler)
    url = f"http://{host}:{port}/"
    print(f"ReqRE web app listening at {url}")
    print("Use Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping ReqRE web app.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
