#!/usr/bin/env python3
"""Validate DPO rule JSON files against the ReqRE schema."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from reqre.rules import DpoRule
from reqre.schema import iter_dpo_rule_errors, validate_dpo_rule_payload


def _iter_json_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(sorted(path.rglob("*.json")))
        else:
            files.append(path)
    return files


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate DPO rule JSON files against the ReqRE schema."
    )
    parser.add_argument("paths", nargs="+", help="JSON files or directories")
    args = parser.parse_args()

    input_paths = [Path(item) for item in args.paths]
    files = _iter_json_files(input_paths)
    if not files:
        print("No JSON files found.")
        return 1

    failures: list[str] = []
    for file_path in files:
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"{file_path}: invalid JSON ({exc})")
            continue
        except OSError as exc:
            failures.append(f"{file_path}: {exc}")
            continue

        errors = iter_dpo_rule_errors(payload)
        if errors:
            failures.append(f"{file_path}: {', '.join(errors)}")
            continue

        try:
            validate_dpo_rule_payload(payload)
            DpoRule.from_json(payload)
        except Exception as exc:  # pragma: no cover - defensive
            failures.append(f"{file_path}: {exc}")

    if failures:
        for item in failures:
            print(item)
        return 1

    print(f"Validated {len(files)} file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
