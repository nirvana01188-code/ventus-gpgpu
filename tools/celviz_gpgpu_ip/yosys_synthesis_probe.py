#!/usr/bin/env python3
"""Run a bounded Yosys synthesis probe for Celviz GPGPU evidence."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "celviz.gpgpu.yosys_synthesis_probe.v1"
CLEAN_ROOM_SCOPE = (
    "bounded clean-room Yosys synthesis probe evidence; records parse/synthesis "
    "tool behavior on available generated Verilog, but is not target-library "
    "logic synthesis, not STA, not power signoff, not DFT, not physical "
    "implementation, and not silicon readiness"
)
DEFAULT_ROOT = Path("artifacts/rank_01_vivante_3d_gpgpu_ip")
COVERAGE_PREFIX_RE = re.compile(r"^([ \t]*)(?:[%~]?\d{6}\s+)(.*)$")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_command(cmd: list[str], timeout_s: int) -> dict[str, Any]:
    start = time.time()
    try:
        completed = subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_s,
            check=False,
        )
        output = completed.stdout
        return {
            "status": "pass" if completed.returncode == 0 else "fail",
            "returncode": completed.returncode,
            "elapsed_s": round(time.time() - start, 3),
            "timed_out": False,
            "output_tail": output[-12000:],
            "error_summary": first_error(output),
        }
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        return {
            "status": "timeout",
            "returncode": None,
            "elapsed_s": round(time.time() - start, 3),
            "timed_out": True,
            "output_tail": output[-12000:],
            "error_summary": first_error(output) or f"timeout after {timeout_s}s",
        }


def first_error(output: str) -> str:
    for line in output.splitlines():
        if "ERROR:" in line:
            return line.strip()
    return ""


def sanitize_coverage_verilog(input_path: Path, output_path: Path) -> dict[str, Any]:
    lines = input_path.read_text(encoding="utf-8", errors="replace").splitlines()
    replaced = 0
    out_lines = []
    for line in lines:
        match = COVERAGE_PREFIX_RE.match(line)
        if match:
            replaced += 1
            out_lines.append(match.group(1) + match.group(2))
        else:
            out_lines.append(line)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    return {
        "input": str(input_path),
        "output": str(output_path),
        "line_count": len(lines),
        "coverage_prefixes_removed": replaced,
    }


def parse_stat(output: str) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for line in output.splitlines():
        stripped = line.strip()
        for key in ("Number of wires:", "Number of wire bits:", "Number of public wires:", "Number of public wire bits:", "Number of memories:", "Number of memory bits:", "Number of cells:"):
            if stripped.startswith(key):
                value = stripped.split(":", 1)[1].strip().split()[0]
                try:
                    metrics[key.rstrip(":").lower().replace(" ", "_")] = int(value)
                except ValueError:
                    metrics[key.rstrip(":").lower().replace(" ", "_")] = value
    return metrics


def collect(artifact_root: Path, output_dir: Path, timeout_s: int) -> dict[str, Any]:
    yosys = shutil.which("yosys")
    dut = artifact_root / "verification" / "verilator_coverage" / "report" / "dut.v"
    sanitized = output_dir / "dut.coverage_sanitized.v"
    top = "GPGPU_SimTop"
    raw_cmd = [
        yosys or "yosys",
        "-q",
        "-p",
        f"read_verilog -sv -DSYNTHESIS {dut}; hierarchy -top {top}; proc; opt; stat; check",
    ]
    raw = run_command(raw_cmd, timeout_s) if yosys and dut.exists() else {
        "status": "skip",
        "returncode": None,
        "elapsed_s": 0,
        "timed_out": False,
        "output_tail": "",
        "error_summary": "yosys or dut.v unavailable",
    }
    sanitize = sanitize_coverage_verilog(dut, sanitized) if dut.exists() else {}
    sanitized_cmd = [
        yosys or "yosys",
        "-q",
        "-p",
        f"read_verilog -sv -DSYNTHESIS {sanitized}; hierarchy -top {top}; proc; opt; stat; check",
    ]
    sanitized_run = run_command(sanitized_cmd, timeout_s) if yosys and sanitized.exists() else {
        "status": "skip",
        "returncode": None,
        "elapsed_s": 0,
        "timed_out": False,
        "output_tail": "",
        "error_summary": "yosys or sanitized dut unavailable",
    }
    stat_metrics = parse_stat(sanitized_run.get("output_tail", ""))
    blocker_recorded = raw["status"] != "pass" or sanitized_run["status"] != "pass"
    checks = [
        {"name": "yosys_available", "pass": bool(yosys), "evidence": {"yosys": yosys or "tool_unavailable"}},
        {"name": "dut_verilog_present", "pass": dut.exists() and dut.stat().st_size > 0, "evidence": {"dut": str(dut), "size_bytes": dut.stat().st_size if dut.exists() else 0}},
        {"name": "raw_probe_executed", "pass": raw["status"] in {"pass", "fail", "timeout"}, "evidence": {"status": raw["status"], "error": raw["error_summary"]}},
        {"name": "coverage_prefix_sanitizer_executed", "pass": bool(sanitize.get("coverage_prefixes_removed", 0) > 0), "evidence": sanitize},
        {"name": "sanitized_probe_executed", "pass": sanitized_run["status"] in {"pass", "fail", "timeout"}, "evidence": {"status": sanitized_run["status"], "error": sanitized_run["error_summary"]}},
        {"name": "blocker_or_stat_recorded", "pass": blocker_recorded or bool(stat_metrics), "evidence": {"blocker_recorded": blocker_recorded, "stat_metrics": stat_metrics}},
        {"name": "no_signoff_overclaim", "pass": "not target-library" in CLEAN_ROOM_SCOPE and "not silicon readiness" in CLEAN_ROOM_SCOPE},
    ]
    status = "pass" if all(item["pass"] for item in checks) else "fail"
    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "status": status,
        "top": top,
        "timeout_s": timeout_s,
        "checks": checks,
        "tool": {
            "yosys": yosys or "tool_unavailable",
            "version": run_command([yosys, "-V"], 10)["output_tail"].strip() if yosys else "tool_unavailable",
        },
        "inputs": {
            "raw_dut": str(dut),
            "sanitized_dut": str(sanitized),
        },
        "sanitize": sanitize,
        "raw_probe": raw,
        "sanitized_probe": sanitized_run,
        "stat_metrics": stat_metrics,
        "classification": (
            "synthesis_probe_blocked_by_generated_verilog"
            if sanitized_run["status"] != "pass"
            else "bounded_yosys_probe_pass"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run bounded Yosys synthesis probe.")
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_ROOT / "synthesis")
    parser.add_argument("--timeout-s", type=int, default=60)
    args = parser.parse_args()
    report = collect(args.artifact_root, args.output_dir, args.timeout_s)
    output = args.output_dir / "yosys_synthesis_probe_report.json"
    write_json(output, report)
    passed = sum(1 for c in report["checks"] if c["pass"])
    print(
        "celviz_gpgpu_yosys_synthesis_probe: "
        f"{report['status']} checks={passed}/{len(report['checks'])} "
        f"classification={report['classification']} output={output}"
    )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
