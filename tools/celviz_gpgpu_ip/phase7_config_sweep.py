#!/usr/bin/env python3
"""Generate phase-7 configuration sweep evidence.

This tool sweeps clean-room proxy knobs for issue width, ALU/LSU/FPU lanes,
warp count, and register-file banks. It combines existing Phase 7 coalescing,
control-flow manager, memory-streaming, and SIMT evidence to estimate
area-normalized performance. It is not RTL synthesis, physical PPA, a timing
model, a vendor performance claim, or silicon signoff.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "celviz.gpgpu.phase7_config_sweep.v1"
CLEAN_ROOM_SCOPE = (
    "clean-room phase-7 configuration sweep evidence derived from Celviz "
    "SIMT/compiler/micro-op and Phase 7 proxy reports only; not RTL synthesis, "
    "not physical PPA, not timing closure, not a vendor performance claim, and "
    "not silicon signoff"
)
DEFAULT_ROOT = Path("artifacts/rank_01_vivante_3d_gpgpu_ip")
KERNELS = ("vector_add", "gemm", "conv2d", "image_filter")
WORKLOAD_ALIAS = {
    "vector_add": "vector_add",
    "gemm": "gemm_proxy",
    "conv2d": "convolution_proxy",
    "image_filter": "image_filter",
}
SWEEP_CONFIGS = (
    {
        "config_id": "tiny_balanced",
        "issue_width": 1,
        "alu_lanes": 8,
        "fpu_lanes": 8,
        "lsu_lanes": 1,
        "warp_count": 4,
        "register_file_banks": 4,
    },
    {
        "config_id": "balanced_16",
        "issue_width": 1,
        "alu_lanes": 16,
        "fpu_lanes": 16,
        "lsu_lanes": 2,
        "warp_count": 8,
        "register_file_banks": 8,
    },
    {
        "config_id": "memory_heavy_16",
        "issue_width": 1,
        "alu_lanes": 16,
        "fpu_lanes": 16,
        "lsu_lanes": 4,
        "warp_count": 8,
        "register_file_banks": 8,
    },
    {
        "config_id": "wide_issue_32",
        "issue_width": 2,
        "alu_lanes": 32,
        "fpu_lanes": 32,
        "lsu_lanes": 4,
        "warp_count": 12,
        "register_file_banks": 16,
    },
    {
        "config_id": "latency_hiding_32",
        "issue_width": 2,
        "alu_lanes": 32,
        "fpu_lanes": 32,
        "lsu_lanes": 6,
        "warp_count": 16,
        "register_file_banks": 16,
    },
    {
        "config_id": "max_proxy_64",
        "issue_width": 4,
        "alu_lanes": 64,
        "fpu_lanes": 64,
        "lsu_lanes": 8,
        "warp_count": 24,
        "register_file_banks": 32,
    },
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


def by_kernel(report: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(item.get("kernel")): item for item in report.get("kernels", []) if isinstance(item, Mapping)}


def simt_by_workload(simt: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(item.get("workload")): item for item in simt.get("workloads", []) if isinstance(item, Mapping)}


def area_proxy(config: Mapping[str, Any]) -> float:
    issue_width = as_int(config["issue_width"])
    alu_lanes = as_int(config["alu_lanes"])
    fpu_lanes = as_int(config["fpu_lanes"])
    lsu_lanes = as_int(config["lsu_lanes"])
    warp_count = as_int(config["warp_count"])
    rf_banks = as_int(config["register_file_banks"])
    return round(
        100.0
        + issue_width * 18.0
        + alu_lanes * 1.45
        + fpu_lanes * 2.10
        + lsu_lanes * 8.5
        + warp_count * 4.0
        + rf_banks * 2.6,
        3,
    )


def frequency_proxy(config: Mapping[str, Any]) -> float:
    width_pressure = (
        as_int(config["issue_width"]) * 0.08
        + as_int(config["alu_lanes"]) / 512.0
        + as_int(config["lsu_lanes"]) / 96.0
        + as_int(config["register_file_banks"]) / 384.0
    )
    return round(max(0.55, 1.0 - width_pressure), 6)


def estimate_kernel_config(
    *,
    kernel: str,
    config: Mapping[str, Any],
    simt_workload: Mapping[str, Any],
    coalescing: Mapping[str, Any],
    control_flow: Mapping[str, Any],
    memory_streaming: Mapping[str, Any],
) -> dict[str, Any]:
    counters = simt_workload.get("counters", {})
    alu_ops = as_int(counters.get("alu_ops"))
    scheduler_issues = as_int(counters.get("scheduler_issues"))
    coalesced_transactions = as_int(coalescing.get("coalesced_transactions"))
    projected_control_uops = as_int(control_flow.get("projected_control_manager_uops"))
    projected_scoreboard_wait = as_int(memory_streaming.get("projected_scoreboard_wait_cycles"))
    issue_width = max(1, as_int(config["issue_width"]))
    alu_lanes = max(1, as_int(config["alu_lanes"]))
    fpu_lanes = max(1, as_int(config["fpu_lanes"]))
    lsu_lanes = max(1, as_int(config["lsu_lanes"]))
    warp_count = max(1, as_int(config["warp_count"]))
    rf_banks = max(1, as_int(config["register_file_banks"]))

    compute_parallelism = max(1.0, float(issue_width * min(alu_lanes, fpu_lanes)) / 8.0)
    memory_parallelism = max(1.0, float(lsu_lanes) * (1.0 + math.log2(max(1, warp_count)) * 0.08))
    control_parallelism = max(1.0, float(issue_width) * (1.0 + rf_banks / 64.0))
    latency_hiding = max(1.0, math.sqrt(float(warp_count)) / 2.0)

    compute_cycles = int(math.ceil(alu_ops / compute_parallelism)) if alu_ops else 0
    memory_cycles = int(math.ceil(coalesced_transactions / memory_parallelism)) if coalesced_transactions else 0
    control_cycles = int(math.ceil(projected_control_uops / control_parallelism)) if projected_control_uops else 0
    scoreboard_cycles = int(math.ceil(projected_scoreboard_wait / latency_hiding)) if projected_scoreboard_wait else 0
    fixed_cycles = 18
    projected_cycles = fixed_cycles + max(compute_cycles, memory_cycles) + control_cycles + scoreboard_cycles
    throughput_proxy = round(float(alu_ops + scheduler_issues) / max(1, projected_cycles), 6)
    area = area_proxy(config)
    freq = frequency_proxy(config)
    area_normalized_perf_proxy = round((throughput_proxy * freq) / area, 9)
    bottleneck = "compute" if compute_cycles >= memory_cycles else "memory"
    if scoreboard_cycles > max(compute_cycles, memory_cycles):
        bottleneck = "scoreboard"
    return {
        "kernel": kernel,
        "config_id": config["config_id"],
        "compute_cycles_proxy": compute_cycles,
        "memory_cycles_proxy": memory_cycles,
        "control_cycles_proxy": control_cycles,
        "scoreboard_cycles_proxy": scoreboard_cycles,
        "projected_cycles_proxy": projected_cycles,
        "throughput_proxy": throughput_proxy,
        "frequency_proxy_index": freq,
        "area_proxy_units": area,
        "area_normalized_perf_proxy": area_normalized_perf_proxy,
        "bottleneck_proxy": bottleneck,
    }


def collect(artifact_root: Path) -> dict[str, Any]:
    simt = load_json(artifact_root / "model" / "outputs" / "simt_execution.json")
    coalescing = load_json(artifact_root / "verification" / "phase7_coalescing_score_report.json")
    control_flow = load_json(artifact_root / "verification" / "phase7_control_flow_manager_report.json")
    memory_streaming = load_json(artifact_root / "verification" / "phase7_memory_streaming_report.json")
    synthesis = load_json(artifact_root / "synthesis" / "synthesis_readiness_report.json")
    simt_workloads = simt_by_workload(simt)
    coalescing_by_kernel = by_kernel(coalescing)
    control_by_kernel = by_kernel(control_flow)
    streaming_by_kernel = by_kernel(memory_streaming)

    config_rows = []
    for config in SWEEP_CONFIGS:
        kernel_estimates = []
        for kernel in KERNELS:
            kernel_estimates.append(
                estimate_kernel_config(
                    kernel=kernel,
                    config=config,
                    simt_workload=simt_workloads[WORKLOAD_ALIAS[kernel]],
                    coalescing=coalescing_by_kernel[kernel],
                    control_flow=control_by_kernel[kernel],
                    memory_streaming=streaming_by_kernel[kernel],
                )
            )
        config_rows.append(
            {
                **config,
                "area_proxy_units": area_proxy(config),
                "frequency_proxy_index": frequency_proxy(config),
                "kernel_estimates": kernel_estimates,
                "mean_throughput_proxy": round(
                    sum(item["throughput_proxy"] for item in kernel_estimates) / len(kernel_estimates),
                    6,
                ),
                "mean_area_normalized_perf_proxy": round(
                    sum(item["area_normalized_perf_proxy"] for item in kernel_estimates) / len(kernel_estimates),
                    9,
                ),
            }
        )

    best_config_by_kernel = {}
    for kernel in KERNELS:
        candidates = [
            estimate
            for row in config_rows
            for estimate in row["kernel_estimates"]
            if estimate["kernel"] == kernel
        ]
        best = max(candidates, key=lambda item: item["area_normalized_perf_proxy"])
        best_config_by_kernel[kernel] = {
            "config_id": best["config_id"],
            "area_normalized_perf_proxy": best["area_normalized_perf_proxy"],
            "throughput_proxy": best["throughput_proxy"],
            "projected_cycles_proxy": best["projected_cycles_proxy"],
            "bottleneck_proxy": best["bottleneck_proxy"],
        }
    global_best = max(config_rows, key=lambda row: row["mean_area_normalized_perf_proxy"])

    checks = [
        {
            "name": "input_phase7_reports_pass",
            "pass": simt.get("status") == coalescing.get("status") == control_flow.get("status") == memory_streaming.get("status") == "pass",
        },
        {"name": "synthesis_readiness_available", "pass": synthesis.get("status") == "pass"},
        {"name": "sweep_config_depth", "pass": len(config_rows) >= 5},
        {"name": "all_kernels_swept", "pass": set(best_config_by_kernel) == set(KERNELS)},
        {
            "name": "best_config_by_kernel_present",
            "pass": all(item["config_id"] for item in best_config_by_kernel.values()),
        },
        {
            "name": "area_normalized_perf_proxy_positive",
            "pass": all(
                estimate["area_normalized_perf_proxy"] > 0.0
                for row in config_rows
                for estimate in row["kernel_estimates"]
            ),
        },
        {
            "name": "global_best_config_present",
            "pass": bool(global_best.get("config_id")) and global_best["mean_area_normalized_perf_proxy"] > 0.0,
        },
        {
            "name": "claim_boundary_declared",
            "pass": "not RTL synthesis" in CLEAN_ROOM_SCOPE and "not silicon signoff" in CLEAN_ROOM_SCOPE,
        },
    ]
    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "status": "pass" if all(check["pass"] for check in checks) else "fail",
        "checks": checks,
        "summary": {
            "config_count": len(config_rows),
            "kernel_count": len(KERNELS),
            "global_best_config": global_best["config_id"],
            "global_best_mean_area_normalized_perf_proxy": global_best["mean_area_normalized_perf_proxy"],
            "best_config_by_kernel": best_config_by_kernel,
            "area_proxy_range": {
                "min": min(row["area_proxy_units"] for row in config_rows),
                "max": max(row["area_proxy_units"] for row in config_rows),
            },
            "frequency_proxy_range": {
                "min": min(row["frequency_proxy_index"] for row in config_rows),
                "max": max(row["frequency_proxy_index"] for row in config_rows),
            },
        },
        "sweep_configs": config_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate phase-7 config sweep evidence.")
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_ROOT / "verification" / "phase7_config_sweep_report.json")
    args = parser.parse_args()
    report = collect(args.artifact_root)
    write_json(args.output, report)
    passed = sum(1 for check in report["checks"] if check["pass"])
    summary = report["summary"]
    print(
        "celviz_gpgpu_phase7_config_sweep: "
        f"{report['status']} checks={passed}/{len(report['checks'])} "
        f"configs={summary['config_count']} global_best={summary['global_best_config']} "
        f"area_norm_perf={summary['global_best_mean_area_normalized_perf_proxy']} output={args.output}"
    )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
