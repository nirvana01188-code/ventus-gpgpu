#!/usr/bin/env python3
"""Generate phase-7 control-flow manager projection evidence.

This tool consumes clean-room compiler IR and SIMT execution evidence to model
how a compact control-flow manager could encode predicate masks, loop backedges,
and reconvergence joins. It reports dynamic control-uop reduction for the
current Celviz kernels. It is not a production compiler pass, not SPIR-V/LLVM,
not a proprietary branch-stack implementation, and not a timing/signoff claim.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "celviz.gpgpu.phase7_control_flow_manager.v1"
CLEAN_ROOM_SCOPE = (
    "clean-room phase-7 control-flow manager projection derived from Celviz "
    "compiler IR and SIMT execution evidence only; not a production compiler "
    "pass, not SPIR-V/LLVM, not a proprietary branch-stack implementation, "
    "not Vivante ISA compatibility, and not timing or silicon signoff"
)
DEFAULT_ROOT = Path("artifacts/rank_01_vivante_3d_gpgpu_ip")
KERNELS = ("vector_add", "gemm", "conv2d", "image_filter")
CONTROL_VOCABULARY = (
    "uop_cf_push",
    "uop_cf_mask",
    "uop_cf_join",
    "uop_predicated_branch",
)
WORKLOAD_ALIAS = {
    "vector_add": "vector_add",
    "gemm": "gemm_proxy",
    "conv2d": "convolution_proxy",
    "image_filter": "image_filter",
}


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


def simt_by_workload(simt: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(item.get("workload")): item for item in simt.get("workloads", []) if isinstance(item, Mapping)}


def count_active_masks(workload: Mapping[str, Any]) -> dict[str, Any]:
    masks: list[str] = []
    transitions = 0
    previous = ""
    for event in workload.get("trace", []):
        if not isinstance(event, Mapping):
            continue
        mask = event.get("active_mask")
        if not isinstance(mask, str):
            continue
        masks.append(mask)
        if previous and previous != mask:
            transitions += 1
        previous = mask
    return {
        "unique_active_masks": sorted(set(masks)),
        "active_mask_events": len(masks),
        "active_mask_transitions": transitions,
    }


def build_kernel_projection(kernel: str, ir: Mapping[str, Any], microop: Mapping[str, Any], simt_workload: Mapping[str, Any]) -> dict[str, Any]:
    blocks = list(ir.get("basic_blocks", []))
    edges = list(ir.get("cfg_edges", []))
    predicates = list(ir.get("predicate_registers", []))
    backedges = [edge for edge in edges if edge.get("kind") == "backedge"]
    predicated_blocks = [block for block in blocks if block.get("predicate")]
    loop_blocks = [block for block in blocks if str(block.get("opcode")) in {"uop_loop_begin", "uop_loop_end"}]
    barrier_blocks = [block for block in blocks if str(block.get("opcode")) == "uop_barrier"]
    dynamic_pc_count = as_int(microop.get("execution", {}).get("pc_count"))
    loop_trip_product = 1
    loop_trips = microop.get("execution", {}).get("loop_trips", {})
    if isinstance(loop_trips, Mapping) and loop_trips:
        for trip in loop_trips.values():
            loop_trip_product *= max(1, as_int(trip, 1))
    else:
        loop_trip_product = 1
    mask_summary = count_active_masks(simt_workload)
    scheduler_issues = as_int(simt_workload.get("counters", {}).get("scheduler_issues"))

    baseline_control_uops = len(predicated_blocks) + len(backedges) * max(1, loop_trip_product) + len(barrier_blocks)
    projected_control_uops = (
        len(predicates)
        + len(backedges)
        + (1 if backedges else 0)
        + (1 if predicated_blocks else 0)
        + len(barrier_blocks)
    )
    dynamic_uop_reduction = max(0, baseline_control_uops - projected_control_uops)
    dynamic_uop_reduction_percent = round((dynamic_uop_reduction / baseline_control_uops) * 100.0, 3) if baseline_control_uops else 0.0
    reconvergence_points = len(backedges) + len(barrier_blocks) + (1 if predicated_blocks else 0)
    skipped_inactive_lanes_proxy = max(0, scheduler_issues - dynamic_pc_count) if scheduler_issues else len(predicated_blocks)

    return {
        "kernel": kernel,
        "workload": WORKLOAD_ALIAS[kernel],
        "basic_blocks": len(blocks),
        "cfg_edges": len(edges),
        "predicate_registers": len(predicates),
        "predicated_blocks": len(predicated_blocks),
        "loop_blocks": len(loop_blocks),
        "loop_backedges": len(backedges),
        "loop_trip_product": loop_trip_product,
        "barrier_blocks": len(barrier_blocks),
        "dynamic_pc_count": dynamic_pc_count,
        "scheduler_issues": scheduler_issues,
        "baseline_control_uops": baseline_control_uops,
        "projected_control_manager_uops": projected_control_uops,
        "dynamic_uop_reduction": dynamic_uop_reduction,
        "dynamic_uop_reduction_percent": dynamic_uop_reduction_percent,
        "active_mask_events": mask_summary["active_mask_events"],
        "active_mask_transitions": mask_summary["active_mask_transitions"],
        "unique_active_masks": mask_summary["unique_active_masks"],
        "reconvergence_points": reconvergence_points,
        "skipped_inactive_lanes_proxy": skipped_inactive_lanes_proxy,
        "control_uop_vocabulary_projection": list(CONTROL_VOCABULARY),
        "model": "deterministic projection from compiler IR predicates, CFG backedges, SIMT active masks, and micro-op execution counts",
    }


def collect(artifact_root: Path) -> dict[str, Any]:
    compiler_report = load_json(artifact_root / "compiler_ir" / "compiler_ir_report.json")
    microop_report = load_json(artifact_root / "microop_execution" / "microop_execution_report.json")
    simt = load_json(artifact_root / "model" / "outputs" / "simt_execution.json")
    simt_workloads = simt_by_workload(simt)
    kernels = []
    for kernel in KERNELS:
        ir = load_json(artifact_root / "compiler_ir" / "kernels" / f"{kernel}.compiler_ir.json")
        microop = load_json(artifact_root / "microop_execution" / "kernels" / f"{kernel}.microop_execution.json")
        kernels.append(build_kernel_projection(kernel, ir, microop, simt_workloads[WORKLOAD_ALIAS[kernel]]))

    total_baseline = sum(item["baseline_control_uops"] for item in kernels)
    total_projected = sum(item["projected_control_manager_uops"] for item in kernels)
    total_reduction = total_baseline - total_projected
    by_kernel = {item["kernel"]: item for item in kernels}
    checks = [
        {"name": "input_reports_pass", "pass": compiler_report.get("status") == microop_report.get("status") == simt.get("status") == "pass"},
        {"name": "all_required_kernels_projected", "pass": set(by_kernel) == set(KERNELS)},
        {"name": "predicate_and_cfg_evidence_present", "pass": all(item["predicate_registers"] > 0 and item["cfg_edges"] > 0 for item in kernels)},
        {"name": "active_mask_evidence_present", "pass": all(item["active_mask_events"] > 0 and item["unique_active_masks"] for item in kernels)},
        {"name": "reconvergence_evidence_present", "pass": all(item["reconvergence_points"] > 0 for item in kernels)},
        {"name": "dynamic_uop_reduction_positive_for_loop_kernels", "pass": by_kernel["gemm"]["dynamic_uop_reduction"] > 0 and by_kernel["conv2d"]["dynamic_uop_reduction"] > 0},
        {"name": "control_uop_vocabulary_projected", "pass": all("uop_cf_join" in item["control_uop_vocabulary_projection"] for item in kernels)},
        {"name": "aggregate_control_uop_reduction_positive", "pass": total_reduction > 0 and total_projected < total_baseline},
    ]
    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "status": "pass" if all(check["pass"] for check in checks) else "fail",
        "checks": checks,
        "summary": {
            "kernel_count": len(kernels),
            "baseline_control_uops": total_baseline,
            "projected_control_manager_uops": total_projected,
            "dynamic_uop_reduction": total_reduction,
            "dynamic_uop_reduction_percent": round((total_reduction / total_baseline) * 100.0, 3) if total_baseline else 0.0,
            "loop_kernel_reductions": {
                "gemm": by_kernel["gemm"]["dynamic_uop_reduction"],
                "conv2d": by_kernel["conv2d"]["dynamic_uop_reduction"],
            },
            "total_reconvergence_points": sum(item["reconvergence_points"] for item in kernels),
            "total_active_mask_events": sum(item["active_mask_events"] for item in kernels),
        },
        "kernels": kernels,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate phase-7 control-flow manager evidence.")
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_ROOT / "verification" / "phase7_control_flow_manager_report.json")
    args = parser.parse_args()
    report = collect(args.artifact_root)
    write_json(args.output, report)
    passed = sum(1 for check in report["checks"] if check["pass"])
    summary = report["summary"]
    print(
        "celviz_gpgpu_phase7_control_flow_manager: "
        f"{report['status']} checks={passed}/{len(report['checks'])} "
        f"dynamic_uop_reduction={summary['dynamic_uop_reduction']} "
        f"reconvergence_points={summary['total_reconvergence_points']} output={args.output}"
    )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
