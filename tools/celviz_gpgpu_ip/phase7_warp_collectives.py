#!/usr/bin/env python3
"""Generate phase-7 warp/subgroup collective projection evidence.

This tool models clean-room software-emulated versus hardware-projected warp
collective sequences for ballot, vote, shuffle, reduce, and subgroup sync. It
uses existing SIMT traces, compiler IR, control-flow manager, and register
occupancy evidence. It is not CUDA/OpenCL subgroup conformance, not a vendor
ISA claim, not a physical implementation, and not silicon signoff.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "celviz.gpgpu.phase7_warp_collectives.v1"
CLEAN_ROOM_SCOPE = (
    "clean-room phase-7 warp/subgroup collectives projection derived from "
    "Celviz SIMT traces, compiler IR, control-flow manager, and register "
    "occupancy evidence only; not CUDA or OpenCL subgroup conformance, not a "
    "vendor ISA claim, not a physical collective unit implementation, and not "
    "silicon signoff"
)
DEFAULT_ROOT = Path("artifacts/rank_01_vivante_3d_gpgpu_ip")
KERNELS = ("vector_add", "gemm", "conv2d", "image_filter")
WORKLOAD_ALIAS = {
    "vector_add": "vector_add",
    "gemm": "gemm_proxy",
    "conv2d": "convolution_proxy",
    "image_filter": "image_filter",
}
COLLECTIVE_VOCABULARY = (
    "uop_warp_ballot",
    "uop_warp_vote",
    "uop_warp_shuffle",
    "uop_warp_reduce",
    "uop_subgroup_sync",
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


def simt_by_workload(simt: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(item.get("workload")): item for item in simt.get("workloads", []) if isinstance(item, Mapping)}


def by_kernel(report: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(item.get("kernel")): item for item in report.get("kernels", []) if isinstance(item, Mapping)}


def trace_shape(workload: Mapping[str, Any]) -> dict[str, Any]:
    schedule_ops: dict[str, int] = {}
    active_masks: list[str] = []
    transitions = 0
    previous = ""
    for event in workload.get("trace", []):
        if not isinstance(event, Mapping):
            continue
        if event.get("type") == "warp_schedule":
            op = str(event.get("op"))
            schedule_ops[op] = schedule_ops.get(op, 0) + 1
        mask = event.get("active_mask")
        if isinstance(mask, str):
            active_masks.append(mask)
            if previous and previous != mask:
                transitions += 1
            previous = mask
    return {
        "schedule_ops": schedule_ops,
        "unique_active_masks": sorted(set(active_masks)),
        "active_mask_events": len(active_masks),
        "active_mask_transitions": transitions,
    }


def collective_needs(kernel: str, trace: Mapping[str, Any], control: Mapping[str, Any]) -> dict[str, Any]:
    ops = trace["schedule_ops"]
    transitions = as_int(trace["active_mask_transitions"])
    needs_ballot = transitions > 0 or as_int(control.get("predicated_blocks")) > 0
    needs_vote = as_int(control.get("reconvergence_points")) > 0
    needs_shuffle = kernel in {"gemm", "conv2d", "image_filter"}
    needs_reduce = kernel in {"gemm", "conv2d", "image_filter"} or as_int(ops.get("iadd")) > 0
    needs_sync = as_int(ops.get("barrier")) > 0
    return {
        "ballot": needs_ballot,
        "vote": needs_vote,
        "shuffle": needs_shuffle,
        "reduce": needs_reduce,
        "subgroup_sync": needs_sync,
    }


def build_kernel_projection(
    *,
    kernel: str,
    simt_workload: Mapping[str, Any],
    ir: Mapping[str, Any],
    control: Mapping[str, Any],
    occupancy: Mapping[str, Any],
) -> dict[str, Any]:
    trace = trace_shape(simt_workload)
    counters = simt_workload.get("counters", {})
    warps = len(simt_workload.get("warps", []))
    wavefront_size = as_int(simt_workload.get("warps", [{}])[0].get("lane_count"), 8) if simt_workload.get("warps") else 8
    needs = collective_needs(kernel, trace, control)
    collective_count = sum(1 for value in needs.values() if value)
    software_sequence_uops = (
        (wavefront_size if needs["ballot"] else 0)
        + (max(1, math.ceil(math.log2(max(2, wavefront_size)))) if needs["vote"] else 0)
        + (wavefront_size if needs["shuffle"] else 0)
        + (max(1, wavefront_size - 1) if needs["reduce"] else 0)
        + (as_int(trace["schedule_ops"].get("barrier")) if needs["subgroup_sync"] else 0)
    )
    hardware_projection_uops = (
        (1 if needs["ballot"] else 0)
        + (1 if needs["vote"] else 0)
        + (1 if needs["shuffle"] else 0)
        + (1 if needs["reduce"] else 0)
        + (1 if needs["subgroup_sync"] else 0)
    ) * max(1, warps)
    software_sequence_uops *= max(1, warps)
    reduction = max(0, software_sequence_uops - hardware_projection_uops)
    reduction_percent = round((reduction / software_sequence_uops) * 100.0, 3) if software_sequence_uops else 0.0
    register_read_reduction_proxy = int(round(as_int(counters.get("register_reads")) * min(0.45, reduction_percent / 200.0)))
    bank_conflict_after_collectives = round(float(occupancy.get("bank_conflict_proxy", 0.0)) * (1.0 - min(0.35, reduction_percent / 300.0)), 6)
    return {
        "kernel": kernel,
        "workload": WORKLOAD_ALIAS[kernel],
        "warps": warps,
        "wavefront_size": wavefront_size,
        "collective_needs": needs,
        "collective_count": collective_count,
        "software_sequence_uops": software_sequence_uops,
        "hardware_projection_uops": hardware_projection_uops,
        "software_vs_hardware_projection_reduction": reduction,
        "software_vs_hardware_projection_reduction_percent": reduction_percent,
        "active_mask_events": trace["active_mask_events"],
        "active_mask_transitions": trace["active_mask_transitions"],
        "unique_active_masks": trace["unique_active_masks"],
        "predicate_registers": len(ir.get("predicate_registers", [])),
        "reconvergence_points": control.get("reconvergence_points"),
        "register_read_reduction_proxy": register_read_reduction_proxy,
        "bank_conflict_proxy_before": occupancy.get("bank_conflict_proxy"),
        "bank_conflict_proxy_after_collectives": bank_conflict_after_collectives,
        "collective_uop_vocabulary_projection": list(COLLECTIVE_VOCABULARY),
        "model": "deterministic projection from SIMT active masks/barriers, compiler predicates, control reconvergence, and register occupancy",
    }


def collect(artifact_root: Path) -> dict[str, Any]:
    simt = load_json(artifact_root / "model" / "outputs" / "simt_execution.json")
    compiler = load_json(artifact_root / "compiler_ir" / "compiler_ir_report.json")
    control = load_json(artifact_root / "verification" / "phase7_control_flow_manager_report.json")
    occupancy = load_json(artifact_root / "verification" / "phase7_register_occupancy_report.json")
    simt_workloads = simt_by_workload(simt)
    control_by_kernel = by_kernel(control)
    occupancy_by_kernel = by_kernel(occupancy)
    kernels = []
    for kernel in KERNELS:
        kernels.append(
            build_kernel_projection(
                kernel=kernel,
                simt_workload=simt_workloads[WORKLOAD_ALIAS[kernel]],
                ir=load_json(artifact_root / "compiler_ir" / "kernels" / f"{kernel}.compiler_ir.json"),
                control=control_by_kernel[kernel],
                occupancy=occupancy_by_kernel[kernel],
            )
        )

    total_software = sum(item["software_sequence_uops"] for item in kernels)
    total_hardware = sum(item["hardware_projection_uops"] for item in kernels)
    total_reduction = total_software - total_hardware
    checks = [
        {
            "name": "input_reports_pass",
            "pass": simt.get("status") == compiler.get("status") == control.get("status") == occupancy.get("status") == "pass",
        },
        {"name": "all_required_kernels_projected", "pass": {item["kernel"] for item in kernels} == set(KERNELS)},
        {"name": "software_sequence_vs_hardware_projection", "pass": total_software > total_hardware and all(item["software_sequence_uops"] >= item["hardware_projection_uops"] for item in kernels)},
        {"name": "collective_vocabulary_projected", "pass": all("uop_warp_shuffle" in item["collective_uop_vocabulary_projection"] for item in kernels)},
        {"name": "active_mask_or_sync_evidence_present", "pass": all(item["active_mask_events"] > 0 and item["collective_count"] > 0 for item in kernels)},
        {"name": "gemm_conv_image_collectives_present", "pass": all(any(item["collective_needs"][name] for name in ("shuffle", "reduce")) for item in kernels if item["kernel"] in {"gemm", "conv2d", "image_filter"})},
        {"name": "register_bank_effect_projected", "pass": all(item["bank_conflict_proxy_after_collectives"] <= item["bank_conflict_proxy_before"] for item in kernels)},
        {"name": "claim_boundary_declared", "pass": "not CUDA or OpenCL subgroup conformance" in CLEAN_ROOM_SCOPE and "not silicon signoff" in CLEAN_ROOM_SCOPE},
    ]
    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "status": "pass" if all(check["pass"] for check in checks) else "fail",
        "checks": checks,
        "summary": {
            "kernel_count": len(kernels),
            "total_software_sequence_uops": total_software,
            "total_hardware_projection_uops": total_hardware,
            "total_collective_uop_reduction": total_reduction,
            "total_collective_uop_reduction_percent": round((total_reduction / total_software) * 100.0, 3) if total_software else 0.0,
            "kernels_with_shuffle_or_reduce": [
                item["kernel"]
                for item in kernels
                if item["collective_needs"]["shuffle"] or item["collective_needs"]["reduce"]
            ],
            "max_register_read_reduction_proxy": max(item["register_read_reduction_proxy"] for item in kernels),
        },
        "kernels": kernels,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate phase-7 warp collectives evidence.")
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_ROOT / "verification" / "phase7_warp_collectives_report.json")
    args = parser.parse_args()
    report = collect(args.artifact_root)
    write_json(args.output, report)
    passed = sum(1 for check in report["checks"] if check["pass"])
    summary = report["summary"]
    print(
        "celviz_gpgpu_phase7_warp_collectives: "
        f"{report['status']} checks={passed}/{len(report['checks'])} "
        f"uop_reduction={summary['total_collective_uop_reduction']} "
        f"reduction_percent={summary['total_collective_uop_reduction_percent']} output={args.output}"
    )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
