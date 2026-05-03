#!/usr/bin/env python3
"""Celviz reusable phase-gate report verifier template."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REQUIRED_FIELDS = ("schema", "generated_at", "clean_room_scope", "status", "checks", "summary")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify one Celviz phase-gate report.")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--expected-schema-prefix", default="celviz.")
    args = parser.parse_args()

    if not args.report.exists():
        print(f"celviz_phase_gate: fail missing={args.report}", file=sys.stderr)
        return 1

    report = json.loads(args.report.read_text(encoding="utf-8"))
    errors: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in report:
            errors.append(f"missing required field: {field}")
    if not str(report.get("schema", "")).startswith(args.expected_schema_prefix):
        errors.append("schema prefix mismatch")
    if report.get("status") != "pass":
        errors.append(f"status is not pass: {report.get('status')}")
    for check in report.get("checks", []):
        if check.get("pass") is not True:
            errors.append(f"failed check: {check.get('name', '<unnamed>')}")

    if errors:
        print("celviz_phase_gate: fail", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print(f"celviz_phase_gate: pass report={args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
