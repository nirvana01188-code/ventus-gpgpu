#!/usr/bin/env python3
"""Report clean-room synthesis/PPA readiness evidence."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


SCHEMA = "celviz.gpgpu.synthesis_readiness.v1"
CLEAN_ROOM_SCOPE = (
    "clean-room synthesis readiness and PPA proxy evidence only; not logic "
    "synthesis through a target library, not STA, not power signoff, not DFT, "
    "not physical implementation, and not silicon readiness"
)
DEFAULT_ROOT = Path("artifacts/rank_01_vivante_3d_gpgpu_ip")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def iter_files(root: Path, suffixes: Iterable[str]) -> list[Path]:
    suffix_set = set(suffixes)
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix in suffix_set)


def count_token(files: list[Path], token: str) -> int:
    total = 0
    for path in files:
        try:
            total += path.read_text(encoding="utf-8", errors="replace").count(token)
        except OSError:
            pass
    return total


def collect(repo_root: Path, artifact_root: Path) -> dict[str, Any]:
    scala_files = iter_files(repo_root / "ventus" / "src", {".scala"})
    sim_files = iter_files(repo_root / "sim-verilator", {".cpp", ".cc", ".c", ".h", ".hpp"})
    tool_status = {name: shutil.which(name) for name in ("yosys", "verilator", "sbt", "make")}
    ppa_path = artifact_root / "ppa" / "ppa_proxy_report.json"
    ppa = json.loads(ppa_path.read_text(encoding="utf-8")) if ppa_path.exists() else {}
    dont_touch = count_token(scala_files, "dontTouch")
    debug_hooks = count_token(scala_files + sim_files, "celviz")
    blackbox_hints = count_token(scala_files, "BlackBox") + count_token(scala_files, "ExtModule")
    checks = [
        {"name": "rtl_source_scope_present", "pass": len(scala_files) >= 10, "evidence": {"scala_files": len(scala_files)}},
        {"name": "verilator_runtime_scope_present", "pass": len(sim_files) >= 5, "evidence": {"sim_files": len(sim_files)}},
        {"name": "debug_observability_hooks_present", "pass": debug_hooks > 0 and dont_touch > 0, "evidence": {"celviz_tokens": debug_hooks, "dontTouch": dont_touch}},
        {"name": "ppa_proxy_present", "pass": ppa.get("status") == "pass", "evidence": {"ppa_status": ppa.get("status")}},
        {"name": "build_tooling_detected", "pass": bool(tool_status.get("make") or tool_status.get("sbt") or tool_status.get("verilator")), "evidence": tool_status},
        {"name": "yosys_status_recorded", "pass": "yosys" in tool_status, "evidence": {"yosys": tool_status.get("yosys") or "tool_unavailable"}},
        {"name": "no_signoff_overclaim", "pass": "not logic synthesis" in json.dumps(ppa) or ppa.get("clean_room_scope") is not None},
    ]
    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "status": "pass" if all(c["pass"] for c in checks) else "fail",
        "checks": checks,
        "tool_availability": {k: (v or "tool_unavailable") for k, v in tool_status.items()},
        "source_scope": {
            "scala_files": len(scala_files),
            "sim_verilator_files": len(sim_files),
            "celviz_debug_hook_tokens": debug_hooks,
            "dont_touch_tokens": dont_touch,
            "blackbox_or_extmodule_hints": blackbox_hints,
        },
        "ppa_proxy": {
            "path": str(ppa_path),
            "status": ppa.get("status"),
            "area_proxy_units": ppa.get("area_proxy_units"),
            "frequency_proxy_index": ppa.get("frequency_proxy_index"),
        },
        "non_goals": [
            "target-library logic synthesis",
            "static timing analysis",
            "power signoff",
            "DFT or scan insertion",
            "physical implementation",
            "silicon readiness",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Celviz synthesis readiness evidence.")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_ROOT / "synthesis")
    args = parser.parse_args()
    report = collect(args.repo_root, args.artifact_root)
    output = args.output_dir / "synthesis_readiness_report.json"
    write_json(output, report)
    passed = sum(1 for c in report["checks"] if c["pass"])
    print(f"celviz_gpgpu_synthesis_readiness: {report['status']} checks={passed}/{len(report['checks'])} output={output}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
