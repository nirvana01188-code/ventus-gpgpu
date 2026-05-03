#!/usr/bin/env python3
"""Aggregate phase-2 Celviz GPGPU advancement evidence.

Phase 2 covers the six next-hardening lanes requested after the baseline
functional acceptance closed: SIMT compute path, OpenCL subset ABI, memory
system, Linux userspace/DRM-like runtime, supplemental RTL verification, and
PPA proxy evidence.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "celviz.gpgpu.phase2_integration.v1"
CLEAN_ROOM_SCOPE = (
    "clean-room phase-2 hardening evidence for the Ventus-based Celviz GPGPU IP; "
    "not Vivante compatibility, not OpenCL conformance, not a Linux kernel driver, "
    "not RTL structural coverage closure, not synthesis/PPA signoff, and not "
    "silicon/tapeout readiness"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_command(command: list[str], cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return {
        "command": command,
        "exit_code": completed.returncode,
        "output_tail": completed.stdout.splitlines()[-20:],
        "pass": completed.returncode == 0,
    }


def artifact(path: Path) -> dict[str, Any]:
    exists = path.exists()
    size = path.stat().st_size if exists else None
    return {
        "path": str(path),
        "exists": exists,
        "size_bytes": size,
        "non_empty": bool(exists and size and size > 0),
    }


def as_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def simt_workload_names(simt: Mapping[str, Any]) -> set[str]:
    names = {str(name) for name in simt.get("workload_names", [])}
    for item in simt.get("workloads", []):
        if isinstance(item, Mapping):
            name = item.get("workload") or item.get("name") or item.get("kernel")
            if name is not None:
                names.add(str(name))
        elif item is not None:
            names.add(str(item))
    return names


def collect(artifact_root: Path) -> dict[str, Any]:
    paths = {
        "simt": artifact_root / "model" / "outputs" / "simt_execution.json",
        "opencl": artifact_root / "demo" / "opencl_subset" / "opencl_subset_evidence.json",
        "memory": artifact_root / "memory" / "memory_system_phase1_evidence.json",
        "linux_runtime": artifact_root / "os_runtime" / "linux_runtime_evidence.json",
        "rtl_supplemental": artifact_root / "verification" / "verilator_supplemental_phase1" / "phase1_supplemental_evidence.json",
        "ppa": artifact_root / "ppa" / "ppa_proxy_report.json",
    }
    artifacts = {name: artifact(path) for name, path in paths.items()}
    simt = load_json(paths["simt"])
    opencl = load_json(paths["opencl"])
    memory = load_json(paths["memory"])
    linux_runtime = load_json(paths["linux_runtime"])
    rtl_supp = load_json(paths["rtl_supplemental"])
    ppa = load_json(paths["ppa"])
    simt_names = simt_workload_names(simt)
    linux_counters = linux_runtime.get("counters", {})

    checks = [
        {
            "name": "simt_compute_core_path",
            "pass": simt.get("status") == "pass"
            and {"vector_add", "gemm_proxy", "convolution_proxy", "image_filter"}.issubset(simt_names)
            and as_int(simt.get("totals", {}).get("scheduler_issues")) > 0
            and as_int(simt.get("totals", {}).get("register_writes")) > 0
            and as_int(simt.get("totals", {}).get("alu_ops")) > 0
            and as_int(simt.get("totals", {}).get("lsu_loads")) > 0
            and as_int(simt.get("totals", {}).get("scoreboard_hazard_events")) > 0
            and as_int(simt.get("totals", {}).get("barrier_events")) > 0,
            "evidence": {"workloads": sorted(simt_names), "totals": simt.get("totals")},
        },
        {
            "name": "opencl_subset_runtime_abi",
            "pass": opencl.get("status") == "pass"
            and opencl.get("schema") == "celviz.gpgpu.opencl_subset.evidence.v1"
            and len(opencl.get("kernels", [])) >= 4
            and opencl.get("runtime_proxy", {}).get("summary", {}).get("commands_failed") == 0,
            "evidence": {
                "kernel_count": len(opencl.get("kernels", [])),
                "runtime_summary": opencl.get("runtime_proxy", {}).get("summary", {}),
            },
        },
        {
            "name": "memory_system_phase1",
            "pass": memory.get("summary", {}).get("status") == "pass"
            and all(item.get("pass") is True for item in memory.get("checks", []))
            and as_int(memory.get("summary", {}).get("categories", {}).get("dma")) >= 3
            and as_int(memory.get("summary", {}).get("categories", {}).get("kernel")) > 0
            and as_int(memory.get("summary", {}).get("categories", {}).get("negative")) >= 5,
            "evidence": memory.get("summary", {}),
        },
        {
            "name": "linux_userspace_runtime_proxy",
            "pass": linux_runtime.get("status") == "pass"
            and linux_runtime.get("boundary", {}).get("kernel_driver_claim") is False
            and as_int(linux_counters.get("submits")) >= 2
            and as_int(linux_counters.get("submit_success")) >= 1
            and as_int(linux_counters.get("submit_errors")) >= 1
            and as_int(linux_counters.get("events_polled")) >= 1,
            "evidence": linux_counters,
        },
        {
            "name": "rtl_verilator_supplemental_phase1",
            "pass": rtl_supp.get("status") == "pass"
            and rtl_supp.get("failures") == []
            and rtl_supp.get("observed_metrics", {}).get("structural_target_percent") == 100.0,
            "evidence": {
                "structural_targets": rtl_supp.get("structural_targets"),
                "observed_metrics": rtl_supp.get("observed_metrics"),
            },
        },
        {
            "name": "ppa_proxy_phase1",
            "pass": ppa.get("status") == "pass"
            and ppa.get("schema") == "celviz.gpgpu.ppa_proxy.v1"
            and {"CC8000L", "CC8000"}.issubset({item.get("tier") for item in ppa.get("public_baseline_tiers", [])})
            and as_int(ppa.get("source_summary", {}).get("marker_hit_count")) > 0,
            "evidence": {
                "source_summary": ppa.get("source_summary"),
                "proxy_metrics": ppa.get("proxy_metrics"),
            },
        },
    ]
    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "status": "pass" if all(item["pass"] for item in checks) else "fail",
        "checks": checks,
        "artifacts": artifacts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Celviz GPGPU phase-2 integration evidence.")
    parser.add_argument("--repo-root", type=Path, default=Path("."), help="Repository root")
    parser.add_argument(
        "--artifact-root",
        type=Path,
        default=Path("artifacts/rank_01_vivante_3d_gpgpu_ip"),
        help="Rank 1 artifact root",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/rank_01_vivante_3d_gpgpu_ip/verification/phase2_integration_report.json"),
        help="Output JSON report path",
    )
    parser.add_argument("--run-focused", action="store_true", help="Run focused phase-2 generators before aggregation")
    args = parser.parse_args()

    root = args.repo_root.resolve()
    focused_results: list[dict[str, Any]] = []
    if args.run_focused:
        commands = [
            ["python3", "tools/celviz_gpgpu_ip/simt_execution_model.py", "--check"],
            ["python3", "tools/celviz_gpgpu_ip/opencl_subset.py", "--output-dir", "artifacts/rank_01_vivante_3d_gpgpu_ip/demo/opencl_subset", "verify"],
            ["python3", "tools/celviz_gpgpu_ip/memory_model.py", "--verify"],
            ["python3", "tools/celviz_gpgpu_ip/verify_linux_runtime_proxy.py", "--reuse-existing"],
            ["bash", "scripts/tools/artifacts/run_celviz_gpgpu_verilator_supplemental_phase1.sh"],
            ["bash", "scripts/verify_celviz_gpgpu_ppa_proxy.sh"],
        ]
        for command in commands:
            result = run_command(command, root)
            focused_results.append(result)
            if not result["pass"]:
                report = {
                    "schema": SCHEMA,
                    "generated_at": utc_now(),
                    "clean_room_scope": CLEAN_ROOM_SCOPE,
                    "status": "fail",
                    "focused_results": focused_results,
                    "checks": [],
                }
                write_json(args.output, report)
                print(f"celviz_gpgpu_phase2_integration: fail command={command}")
                return 1

    report = collect(args.artifact_root)
    report["focused_results"] = focused_results
    write_json(args.output, report)
    passed = sum(1 for item in report["checks"] if item["pass"])
    total = len(report["checks"])
    print(f"celviz_gpgpu_phase2_integration: {report['status']} checks={passed}/{total} output={args.output}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
