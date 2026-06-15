#!/usr/bin/env python3
"""Validate one DPO rule JSON file and append the result to documentation.csv."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reqre.rules import DpoRule
from reqre.schema import iter_dpo_rule_errors, validate_dpo_rule_payload

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOCUMENTATION_CSV = REPO_ROOT / "json_rules" / "fbi_rules" / "documentation.csv"
CSV_HEADERS = [
    "timestamp_utc",
    "rule_path",
    "rule_id",
    "schema_valid",
    "validation_message",
    "compare_path",
    "similarity_percentage",
    "manual_validation",
]
_MISSING = object()


#
# Usage in the rule-creation workflow:
# 1. Create the new rule JSON file.
# 2. Run this script with `uv` if available, otherwise fall back to
#    `~/.local/bin/uv`.
# 3. Pass `--compare-to` with the canonical reference rule under `json_rules/`.
#
# Example:
#   uv run python scripts/validate_and_document_rule.py \
#     json_rules/fbi_rules/requirements/satisfy_d1_1_bridge.json \
#     --compare-to json_rules/requirements/satisfy_d1_1_bridge.json
#
# Fallback example:
#   ~/.local/bin/uv run python scripts/validate_and_document_rule.py \
#     json_rules/fbi_rules/requirements/satisfy_d1_1_bridge.json \
#     --compare-to json_rules/requirements/satisfy_d1_1_bridge.json
#


def _append_row(csv_path: Path, row: dict[str, str]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    needs_header = not csv_path.exists() or csv_path.stat().st_size == 0
    with csv_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_HEADERS)
        if needs_header:
            writer.writeheader()
        writer.writerow(row)


def recommended_uv_command() -> str:
    uv_path = shutil.which("uv")
    if uv_path:
        return "uv"

    local_uv = Path.home() / ".local" / "bin" / "uv"
    if local_uv.exists() and os.access(local_uv, os.X_OK):
        return str(local_uv)

    return "uv"


def _canonicalize_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _canonicalize_json(value[key])
            for key in sorted(value)
        }
    if isinstance(value, list):
        items = [_canonicalize_json(item) for item in value]
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True))
    return value


def _similarity_score(left: Any, right: Any) -> float:
    if left is _MISSING or right is _MISSING:
        return 0.0

    if isinstance(left, dict) and isinstance(right, dict):
        keys = sorted(set(left) | set(right))
        if not keys:
            return 1.0
        return sum(
            _similarity_score(left.get(key, _MISSING), right.get(key, _MISSING))
            for key in keys
        ) / len(keys)

    if isinstance(left, list) and isinstance(right, list):
        max_len = max(len(left), len(right))
        if max_len == 0:
            return 1.0
        total = 0.0
        for index in range(max_len):
            left_item = left[index] if index < len(left) else _MISSING
            right_item = right[index] if index < len(right) else _MISSING
            total += _similarity_score(left_item, right_item)
        return total / max_len

    return 1.0 if left == right else 0.0


def _compare_rule_payloads(rule_path: Path, compare_path: Path) -> float:
    left_payload = json.loads(rule_path.read_text(encoding="utf-8"))
    right_payload = json.loads(compare_path.read_text(encoding="utf-8"))
    left_value = _canonicalize_json(left_payload)
    right_value = _canonicalize_json(right_payload)
    return _similarity_score(left_value, right_value) * 100.0


def _validate_rule(rule_path: Path) -> tuple[bool, str, str]:
    try:
        payload = json.loads(rule_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, "", f"invalid JSON ({exc})"
    except OSError as exc:
        return False, "", str(exc)

    raw_rule_id = payload.get("rule_id") if isinstance(payload, dict) else None
    rule_id = str(raw_rule_id) if raw_rule_id is not None else ""

    errors = iter_dpo_rule_errors(payload)
    if errors:
        return False, rule_id, "; ".join(errors)

    try:
        validate_dpo_rule_payload(payload)
        DpoRule.from_json(payload, validate=True)
    except Exception as exc:  # pragma: no cover - defensive
        return False, rule_id, str(exc)

    return True, rule_id, "valid"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate one DPO rule JSON file and append the result to "
            "documentation.csv."
        )
    )
    parser.add_argument("rule_path", help="Path to the JSON rule file")
    parser.add_argument(
        "--csv-path",
        default=str(DEFAULT_DOCUMENTATION_CSV),
        help="Path to the documentation CSV file",
    )
    parser.add_argument(
        "--compare-to",
        help="Optional path to a reference JSON rule for similarity comparison",
    )
    args = parser.parse_args()

    rule_path = Path(args.rule_path)
    if not rule_path.is_absolute():
        rule_path = (Path.cwd() / rule_path).resolve()
    csv_path = Path(args.csv_path)
    if not csv_path.is_absolute():
        csv_path = (Path.cwd() / csv_path).resolve()
    compare_path: Path | None = None
    if args.compare_to:
        compare_path = Path(args.compare_to)
        if not compare_path.is_absolute():
            compare_path = (Path.cwd() / compare_path).resolve()

    is_valid, rule_id, message = _validate_rule(rule_path)
    rel_rule_path = (
        str(rule_path.relative_to(REPO_ROOT))
        if rule_path.is_relative_to(REPO_ROOT)
        else str(rule_path)
    )
    compare_rel_path = ""
    similarity_percentage = ""
    if compare_path is not None:
        compare_rel_path = (
            str(compare_path.relative_to(REPO_ROOT))
            if compare_path.is_relative_to(REPO_ROOT)
            else str(compare_path)
        )
        try:
            similarity_percentage = f"{_compare_rule_payloads(rule_path, compare_path):.2f}"
        except Exception as exc:
            similarity_percentage = ""
            if is_valid:
                message = f"{message}; similarity comparison failed ({exc})"
            else:
                message = f"{message}; similarity comparison failed ({exc})"
    row = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rule_path": rel_rule_path,
        "rule_id": rule_id,
        "schema_valid": "true" if is_valid else "false",
        "validation_message": message,
        "compare_path": compare_rel_path,
        "similarity_percentage": similarity_percentage,
        "manual_validation": "",
    }
    _append_row(csv_path, row)

    if is_valid:
        summary = f"Validated {rel_rule_path} and appended result to {csv_path}."
        if similarity_percentage:
            summary += f" Similarity: {similarity_percentage}%."
        print(summary)
        return 0

    summary = (
        f"Validation failed for {rel_rule_path}; appended result to {csv_path}: "
        f"{message}"
    )
    if similarity_percentage:
        summary += f" Similarity: {similarity_percentage}%."
    print(summary)
    return 1


if __name__ == "__main__":
    sys.exit(main())
