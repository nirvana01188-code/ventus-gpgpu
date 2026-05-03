#!/usr/bin/env python3
"""Phase-5 integration gate for executable micro-op evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "celviz.gpgpu.phase5_microop_integration.v1"
CLEAN_ROOM_SCOPE = (
    "clean-room phase-5 executable micro-op integration evidence; not a "
    "production ISA simulator, not a compiler backend, not SPIR-V/LLVM, not "
    "Vivante ISA or command-stream compatibility, not official OpenCL "
    "conformance, and not timing/PPA signoff"
)
REQUIRED_KERNELS = {"vector_add", "gemm", "conv2d", "image_filter"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def as_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def collect(artifact_root: Path) -> dict[str, Any]:
    phase4_path = artifact_root / "verification" / "phase4_lowering_integration_report.json"
    lowering_path = artifact_root / "lowering" / "kernel_lowering_report.json"
    microop_path = artifact_root / "microop_execution" / "microop_execution_report.json"
    memory_path = artifact_root / "memory" / "memory_system_phase1_evidence.json"
    simt_path = artifact_root / "model" / "outputs" / "simt_execution.json"
    runtime_path = artifact_root / "demo" / "opencl_subset" / "runtime_commands.json"

    phase4 = load_json(phase4_path)
    lowering = load_json(lowering_path)
    microop = load_json(microop_path)
    memory = load_json(memory_path)
    simt = load_json(simt_path)
    runtime = load_json(runtime_path)

    lowered_kernels = {str(item.get("kernel")) for item in lowering.get("kernels", [])}
    executed_kernels = {str(item.get("kernel")) for item in microop.get("kernels", [])}
    runtime_kernels = {
        str(command.get("kernel"))
        for command in runtime.get("commands", [])
        if command.get("opcode") == "kernel_dispatch"
    }
    simt_workloads = set(simt.get("workload_names", []))
    oracle_workloads = {str(item.get("oracle_workload")) for item in microop.get("kernels", [])}
    memory_ops = memory.get("summary", {}).get("operations", {})
    uop_categories = set(microop.get("uop_categories_executed", []))
    checks = [
        {
            "name": "microop_execution_report_pass",
            "pass": microop.get("status") == "pass" and microop.get("schema") == "celviz.gpgpu.microop_interpreter.v1",
            "evidence": {"status": microop.get("status"), "schema": microop.get("schema")},
        },
        {
            "name": "phase4_dependency_pass",
            "pass": phase4.get("status") == "pass",
            "evidence": {"phase4_status": phase4.get("status")},
        },
        {
            "name": "executed_kernel_set_matches_lowering_and_runtime",
            "pass": executed_kernels == lowered_kernels == runtime_kernels == REQUIRED_KERNELS,
            "evidence": {
                "executed": sorted(executed_kernels),
                "lowered": sorted(lowered_kernels),
                "runtime": sorted(runtime_kernels),
            },
        },
        {
            "name": "oracle_workloads_match_simt_workloads",
            "pass": oracle_workloads.issubset(simt_workloads),
            "evidence": {"oracle_workloads": sorted(oracle_workloads), "simt_workloads": sorted(simt_workloads)},
        },
        {
            "name": "microop_memory_trace_links_memory_model",
            "pass": as_int(microop.get("total_memory_events")) > 0
            and as_int(memory_ops.get("load")) > 0
            and as_int(memory_ops.get("store")) > 0,
            "evidence": {
                "microop_memory_events": microop.get("total_memory_events"),
                "memory_model_ops": memory_ops,
            },
        },
        {
            "name": "control_data_memory_uops_executed",
            "pass": {
                "uop_kernel_prologue",
                "uop_read_workitem_id",
                "uop_predicate_bounds",
                "uop_global_load",
                "uop_global_store",
                "uop_write_completion",
            }.issubset(uop_categories),
            "evidence": {"uop_categories_executed": sorted(uop_categories)},
        },
    ]
    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "status": "pass" if all(check["pass"] for check in checks) else "fail",
        "checks": checks,
        "microop_summary": {
            "kernel_count": microop.get("kernel_count"),
            "total_uops_executed": microop.get("total_uops_executed"),
            "total_memory_events": microop.get("total_memory_events"),
            "uop_categories_executed": microop.get("uop_categories_executed"),
        },
        "artifacts": {
            "phase4": str(phase4_path),
            "lowering": str(lowering_path),
            "microop_execution": str(microop_path),
            "memory": str(memory_path),
            "simt": str(simt_path),
            "runtime": str(runtime_path),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify phase-5 executable micro-op integration.")
    parser.add_argument(
        "--artifact-root",
        type=Path,
        default=Path("artifacts/rank_01_vivante_3d_gpgpu_ip"),
        help="Rank 1 artifact root",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/rank_01_vivante_3d_gpgpu_ip/verification/phase5_microop_integration_report.json"),
        help="Output report path",
    )
    args = parser.parse_args(argv)
    report = collect(args.artifact_root)
    write_json(args.output, report)
    passed = sum(1 for check in report["checks"] if check["pass"])
    total = len(report["checks"])
    print(f"celviz_gpgpu_phase5_microop: {report['status']} checks={passed}/{total} output={args.output}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
