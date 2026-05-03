#!/usr/bin/env python3
"""Celviz reusable functional/acceptance coverage aggregation template.

This template is for acceptance bins only. Keep RTL structural line, branch,
toggle, timing, power, and physical-signoff metrics in separate observations.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "celviz.functional_acceptance_coverage.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def add_bin(bins: list[dict[str, Any]], group: str, name: str, hit: bool, evidence: dict[str, Any] | None = None) -> None:
    bins.append({"group": group, "name": name, "hit": bool(hit), "evidence": evidence or {}})


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate Celviz functional/acceptance bins.")
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-100", action="store_true")
    args = parser.parse_args()

    matrix_path = args.artifact_root / "verification" / "acceptance_matrix.json"
    matrix = load_json(matrix_path)
    bins: list[dict[str, Any]] = []
    add_bin(bins, "matrix", "schema_present", bool(matrix.get("schema")), {"path": str(matrix_path)})
    for gate in matrix.get("gates", []):
        add_bin(
            bins,
            "matrix_gates",
            str(gate.get("id", "<unnamed>")),
            bool(gate.get("pass_condition") and gate.get("required_evidence")),
            gate,
        )

    total = len(bins)
    hit = sum(1 for item in bins if item["hit"])
    coverage = round((hit / total) * 100.0, 3) if total else 0.0
    report = {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "coverage_kind": "functional_acceptance_bins",
        "status": "pass" if coverage == 100.0 else "fail",
        "coverage_percent": coverage,
        "hit_bins": hit,
        "total_bins": total,
        "missed_bins": [f"{item['group']}.{item['name']}" for item in bins if not item["hit"]],
        "bins": bins,
        "rtl_structural_coverage_observation": "reported separately; not converted into functional 100 percent",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"celviz_functional_acceptance_coverage: {report['status']} coverage={coverage:.3f}% output={args.output}")
    return 0 if report["status"] == "pass" or not args.require_100 else 1


if __name__ == "__main__":
    raise SystemExit(main())
