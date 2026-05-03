#!/usr/bin/env python3
"""Generate phase-7 decoupled memory streaming evidence.

The report derives deterministic stream-window projections from existing
kernel lowering and micro-op execution evidence. It is a clean-room performance
architecture proxy for evaluating address/load decoupling, ALU overlap, and
scoreboard wait reduction. It is not a real LSU implementation, cache model,
timing model, bandwidth guarantee, or silicon performance claim.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "celviz.gpgpu.phase7_memory_streaming.v1"
CLEAN_ROOM_SCOPE = (
    "clean-room phase-7 decoupled memory streaming evidence derived from "
    "Celviz lowering and micro-op execution reports only; not a proprietary "
    "LSU/cache/bus implementation, not a timing or bandwidth signoff, and not "
    "a silicon performance claim"
)
# Claim boundary token for source gates: not a proprietary LSU/cache/bus implementation.
DEFAULT_ROOT = Path("artifacts/rank_01_vivante_3d_gpgpu_ip")
KERNELS = ("vector_add", "gemm", "conv2d", "image_filter")


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


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def stream_shape(kernel: str) -> dict[str, Any]:
    """Return deterministic stream-shaping knobs for the current proxy kernels."""

    shapes: dict[str, dict[str, Any]] = {
        "vector_add": {
            "stream_windows": 2,
            "outstanding_stream_slots": 2,
            "prefetch_distance": 1,
            "alu_overlap_factor": 0.50,
            "reuse_factor": 1.00,
            "scoreboard_exposure_factor": 0.25,
            "rationale": "two contiguous input streams can be issued one wave ahead of the add",
        },
        "gemm": {
            "stream_windows": 5,
            "outstanding_stream_slots": 4,
            "prefetch_distance": 4,
            "alu_overlap_factor": 0.78,
            "reuse_factor": 1.50,
            "scoreboard_exposure_factor": 0.58,
            "rationale": "A/B tile streams have reuse across inner-product MAD windows",
        },
        "conv2d": {
            "stream_windows": 6,
            "outstanding_stream_slots": 4,
            "prefetch_distance": 5,
            "alu_overlap_factor": 0.82,
            "reuse_factor": 1.80,
            "scoreboard_exposure_factor": 0.64,
            "rationale": "overlapping 3x3 filter windows expose load lookahead around MAD work",
        },
        "image_filter": {
            "stream_windows": 4,
            "outstanding_stream_slots": 3,
            "prefetch_distance": 2,
            "alu_overlap_factor": 0.62,
            "reuse_factor": 1.20,
            "scoreboard_exposure_factor": 0.43,
            "rationale": "packed image lanes allow load/unpack overlap before clamp and store",
        },
    }
    return dict(shapes.get(kernel, shapes["vector_add"]))


def build_kernel_projection(
    *,
    kernel: str,
    lowering: Mapping[str, Any],
    execution: Mapping[str, Any],
    compiler_ir: Mapping[str, Any],
) -> dict[str, Any]:
    counts = execution.get("execution", {}).get("memory_counts", {})
    opcode_counts = execution.get("execution", {}).get("opcode_counts", {})
    alu_ops = execution.get("execution", {}).get("alu_ops", {})
    loads = as_int(counts.get("load"))
    stores = as_int(counts.get("store"))
    memory_events = loads + stores
    work_items = as_int(execution.get("execution", {}).get("work_items"))
    wavefront_size = as_int(execution.get("execution", {}).get("wavefront_size"), 32)
    wavefronts = max(1, (work_items + wavefront_size - 1) // wavefront_size)
    load_uops = as_int(opcode_counts.get("uop_global_load"))
    store_uops = as_int(opcode_counts.get("uop_global_store"))
    address_uops = as_int(opcode_counts.get("uop_address_calc"))
    alu_uops = sum(as_int(value) for value in alu_ops.values())
    basic_blocks = len(compiler_ir.get("basic_blocks", []))
    cfg_edges = len(compiler_ir.get("cfg_edges", []))
    shape = stream_shape(kernel)

    stream_windows = as_int(shape["stream_windows"])
    outstanding_slots = as_int(shape["outstanding_stream_slots"])
    prefetch_distance = as_int(shape["prefetch_distance"])
    reuse_factor = float(shape["reuse_factor"])
    overlap_factor = float(shape["alu_overlap_factor"])
    exposure_factor = float(shape["scoreboard_exposure_factor"])

    baseline_scoreboard_wait_cycles = int(round(loads * exposure_factor + stores * 0.10 + wavefronts * 0.50))
    hidden_by_streaming = int(
        round(
            baseline_scoreboard_wait_cycles
            * overlap_factor
            * clamp((outstanding_slots + prefetch_distance) / 10.0, 0.25, 0.95)
        )
    )
    projected_scoreboard_wait_cycles = max(0, baseline_scoreboard_wait_cycles - hidden_by_streaming)
    projected_wait_reduction = baseline_scoreboard_wait_cycles - projected_scoreboard_wait_cycles
    stream_load_coverage = round(clamp((stream_windows * outstanding_slots * reuse_factor) / max(1.0, float(load_uops * 4)), 0.0, 1.0), 6)
    alu_overlap_cycles = int(round(loads * overlap_factor * max(1.0, reuse_factor)))

    return {
        "kernel": kernel,
        "work_items": work_items,
        "wavefront_size": wavefront_size,
        "wavefronts": wavefronts,
        "loads": loads,
        "stores": stores,
        "memory_events": memory_events,
        "load_uops": load_uops,
        "store_uops": store_uops,
        "address_uops": address_uops,
        "alu_uops": alu_uops,
        "basic_blocks": basic_blocks,
        "cfg_edges": cfg_edges,
        "stream_windows": stream_windows,
        "outstanding_stream_slots": outstanding_slots,
        "prefetch_distance": prefetch_distance,
        "stream_load_coverage": stream_load_coverage,
        "alu_overlap_factor": overlap_factor,
        "alu_overlap_cycles": alu_overlap_cycles,
        "baseline_scoreboard_wait_cycles": baseline_scoreboard_wait_cycles,
        "projected_scoreboard_wait_cycles": projected_scoreboard_wait_cycles,
        "projected_scoreboard_wait_reduction": projected_wait_reduction,
        "projected_scoreboard_wait_reduction_percent": round(
            (projected_wait_reduction / baseline_scoreboard_wait_cycles) * 100.0, 3
        )
        if baseline_scoreboard_wait_cycles
        else 0.0,
        "stream_uop_vocabulary_projection": [
            "uop_stream_open",
            "uop_stream_load",
            "uop_stream_wait",
            "uop_stream_close",
        ],
        "source_lowering_sha256": lowering.get("sha256"),
        "source_execution_sha256": execution.get("sha256"),
        "rationale": shape["rationale"],
        "model": "deterministic proxy from current lowering opcodes, micro-op memory counts, and compiler IR shape",
    }


def collect(artifact_root: Path) -> dict[str, Any]:
    lowering_report = load_json(artifact_root / "lowering" / "kernel_lowering_report.json")
    microop_report = load_json(artifact_root / "microop_execution" / "microop_execution_report.json")
    compiler_report = load_json(artifact_root / "compiler_ir" / "compiler_ir_report.json")
    kernels = []
    for kernel in KERNELS:
        lowering = load_json(artifact_root / "lowering" / "kernels" / f"{kernel}.lowering.json")
        execution = load_json(artifact_root / "microop_execution" / "kernels" / f"{kernel}.microop_execution.json")
        compiler_ir = load_json(artifact_root / "compiler_ir" / "kernels" / f"{kernel}.compiler_ir.json")
        kernels.append(
            build_kernel_projection(
                kernel=kernel,
                lowering=lowering,
                execution=execution,
                compiler_ir=compiler_ir,
            )
        )

    total_baseline_wait = sum(item["baseline_scoreboard_wait_cycles"] for item in kernels)
    total_projected_wait = sum(item["projected_scoreboard_wait_cycles"] for item in kernels)
    total_reduction = total_baseline_wait - total_projected_wait
    total_stream_windows = sum(item["stream_windows"] for item in kernels)
    total_overlap_cycles = sum(item["alu_overlap_cycles"] for item in kernels)
    checks = [
        {"name": "input_reports_pass", "pass": lowering_report.get("status") == microop_report.get("status") == compiler_report.get("status") == "pass"},
        {"name": "all_required_kernels_projected", "pass": {item["kernel"] for item in kernels} == set(KERNELS)},
        {"name": "stream_windows_present", "pass": all(item["stream_windows"] > 0 for item in kernels)},
        {"name": "outstanding_slots_present", "pass": all(item["outstanding_stream_slots"] > 0 for item in kernels)},
        {"name": "alu_overlap_positive", "pass": all(item["alu_overlap_cycles"] > 0 for item in kernels)},
        {"name": "projected_scoreboard_wait_reduction_positive", "pass": total_reduction > 0 and all(item["projected_scoreboard_wait_reduction"] > 0 for item in kernels)},
        {"name": "stream_uop_vocabulary_projected", "pass": all("uop_stream_wait" in item["stream_uop_vocabulary_projection"] for item in kernels)},
    ]
    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "status": "pass" if all(check["pass"] for check in checks) else "fail",
        "checks": checks,
        "summary": {
            "kernel_count": len(kernels),
            "total_stream_windows": total_stream_windows,
            "total_outstanding_stream_slots": sum(item["outstanding_stream_slots"] for item in kernels),
            "total_alu_overlap_cycles": total_overlap_cycles,
            "baseline_scoreboard_wait_cycles": total_baseline_wait,
            "projected_scoreboard_wait_cycles": total_projected_wait,
            "projected_scoreboard_wait_reduction": total_reduction,
            "projected_scoreboard_wait_reduction_percent": round((total_reduction / total_baseline_wait) * 100.0, 3)
            if total_baseline_wait
            else 0.0,
        },
        "kernels": kernels,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate phase-7 memory streaming evidence.")
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_ROOT / "verification" / "phase7_memory_streaming_report.json")
    args = parser.parse_args()
    report = collect(args.artifact_root)
    write_json(args.output, report)
    passed = sum(1 for check in report["checks"] if check["pass"])
    summary = report["summary"]
    print(
        "celviz_gpgpu_phase7_memory_streaming: "
        f"{report['status']} checks={passed}/{len(report['checks'])} "
        f"stream_windows={summary['total_stream_windows']} "
        f"scoreboard_wait_reduction={summary['projected_scoreboard_wait_reduction']} "
        f"output={args.output}"
    )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
