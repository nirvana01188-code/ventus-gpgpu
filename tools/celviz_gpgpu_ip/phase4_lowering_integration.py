#!/usr/bin/env python3
"""Phase-4 integration for kernel lowering evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "celviz.gpgpu.phase4_lowering_integration.v1"
CLEAN_ROOM_SCOPE = (
    "clean-room phase-4 kernel lowering integration evidence; not a production "
    "compiler backend, not an ISA compatibility claim, not SPIR-V/LLVM, not "
    "Vivante command stream compatibility, and not timing/PPA signoff"
)


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
    lowering_path = artifact_root / "lowering" / "kernel_lowering_report.json"
    phase3_path = artifact_root / "verification" / "phase3_cross_layer_report.json"
    simt_path = artifact_root / "model" / "outputs" / "simt_execution.json"
    memory_path = artifact_root / "memory" / "memory_system_phase1_evidence.json"
    runtime_path = artifact_root / "demo" / "opencl_subset" / "runtime_commands.json"
    lowering = load_json(lowering_path)
    phase3 = load_json(phase3_path)
    simt = load_json(simt_path)
    memory = load_json(memory_path)
    runtime = load_json(runtime_path)

    kernel_names = {item["kernel"] for item in lowering.get("kernels", [])}
    runtime_kernels = {cmd.get("kernel") for cmd in runtime.get("commands", []) if cmd.get("opcode") == "kernel_dispatch"}
    simt_names = set(simt.get("workload_names", []))
    simt_from_lowering = {item["simt_workload"] for item in lowering.get("kernels", [])}
    categories = set(lowering.get("uop_categories", []))
    memory_ops = memory.get("summary", {}).get("operations", {})
    checks = [
        {
            "name": "lowering_report_pass",
            "pass": lowering.get("status") == "pass" and lowering.get("schema") == "celviz.gpgpu.kernel_lowering.v1",
        },
        {
            "name": "lowering_matches_runtime_dispatch_set",
            "pass": kernel_names == runtime_kernels,
            "evidence": {"lowered": sorted(kernel_names), "runtime": sorted(runtime_kernels)},
        },
        {
            "name": "lowering_matches_simt_workloads",
            "pass": simt_from_lowering.issubset(simt_names),
            "evidence": {"lowering_simt": sorted(simt_from_lowering), "simt": sorted(simt_names)},
        },
        {
            "name": "lowering_covers_memory_ops",
            "pass": {"uop_global_load", "uop_global_store", "uop_address_calc"}.issubset(categories)
            and as_int(memory_ops.get("load")) > 0
            and as_int(memory_ops.get("store")) > 0
            and as_int(memory_ops.get("copy")) > 0,
            "evidence": {"uop_categories": sorted(categories), "memory_ops": memory_ops},
        },
        {
            "name": "lowering_covers_control_ops",
            "pass": {"uop_predicate_bounds", "uop_write_completion"}.issubset(categories)
            and any("uop_loop_begin" in item.get("uop_categories", []) for item in lowering.get("kernels", [])),
            "evidence": {"uop_categories": sorted(categories)},
        },
        {
            "name": "phase3_dependency_pass",
            "pass": phase3.get("status") == "pass",
            "evidence": {"phase3_status": phase3.get("status")},
        },
    ]
    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "status": "pass" if all(check["pass"] for check in checks) else "fail",
        "checks": checks,
        "lowering_summary": {
            "kernel_count": lowering.get("kernel_count"),
            "total_uops": lowering.get("total_uops"),
            "uop_categories": lowering.get("uop_categories"),
        },
        "artifacts": {
            "lowering": str(lowering_path),
            "phase3": str(phase3_path),
            "simt": str(simt_path),
            "memory": str(memory_path),
            "runtime": str(runtime_path),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify phase-4 kernel lowering integration.")
    parser.add_argument(
        "--artifact-root",
        type=Path,
        default=Path("artifacts/rank_01_vivante_3d_gpgpu_ip"),
        help="Rank 1 artifact root",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/rank_01_vivante_3d_gpgpu_ip/verification/phase4_lowering_integration_report.json"),
        help="Output report path",
    )
    args = parser.parse_args()
    report = collect(args.artifact_root)
    write_json(args.output, report)
    passed = sum(1 for check in report["checks"] if check["pass"])
    total = len(report["checks"])
    print(f"celviz_gpgpu_phase4_lowering: {report['status']} checks={passed}/{total} output={args.output}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
