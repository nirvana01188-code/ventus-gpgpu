#!/usr/bin/env python3
"""Proxy performance model for the Rank 1 Celviz GPGPU IP package.

This tool is intentionally standard-library-only and evidence-oriented. It
turns existing S1 compute-model metrics into S5/S6-style proxy estimates for
cycles, throughput, bandwidth pressure, and a relative power index. The output
is not silicon PPA, not tapeout evidence, and not Vivante-equivalent data.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_METRICS = REPO_ROOT / "artifacts/rank_01_vivante_3d_gpgpu_ip/model/metrics.json"
DEFAULT_OUTPUT_JSON = (
    REPO_ROOT
    / "artifacts/rank_01_vivante_3d_gpgpu_ip/integration/perf_model_metrics.json"
)
DEFAULT_OUTPUT_LOG = (
    REPO_ROOT
    / "artifacts/rank_01_vivante_3d_gpgpu_ip/integration/perf_model_run.log"
)


PUBLIC_TIER_FALLBACK = [
    {"tier": "CC8000L", "shader_units_vec1": 16, "fp32_ops_per_cycle": 32, "fp16_ops_per_cycle": 64},
    {"tier": "CC8000", "shader_units_vec1": 32, "fp32_ops_per_cycle": 64, "fp16_ops_per_cycle": 128},
    {"tier": "CC8200", "shader_units_vec1": 128, "fp32_ops_per_cycle": 128, "fp16_ops_per_cycle": 256},
    {"tier": "CC8400", "shader_units_vec1": 256, "fp32_ops_per_cycle": 512, "fp16_ops_per_cycle": 1024},
    {"tier": "CC8400-MP2", "shader_units_vec1": 512, "fp32_ops_per_cycle": 1024, "fp16_ops_per_cycle": 2048},
    {"tier": "CC8400-MP4", "shader_units_vec1": 1024, "fp32_ops_per_cycle": 2048, "fp16_ops_per_cycle": 4096},
    {"tier": "CC8800", "shader_units_vec1": 512, "fp32_ops_per_cycle": 1024, "fp16_ops_per_cycle": 2048},
    {"tier": "CC8800-MP2", "shader_units_vec1": 1024, "fp32_ops_per_cycle": 2048, "fp16_ops_per_cycle": 4096},
    {"tier": "CC8800-MP4", "shader_units_vec1": 2048, "fp32_ops_per_cycle": 4096, "fp16_ops_per_cycle": 8192},
]


ASSUMPTIONS = {
    "claim_boundary": (
        "clean-room proxy model only; not measured RTL, not silicon PPA, "
        "not Vivante-equivalent performance, and not API conformance"
    ),
    "model_version": "celviz-gpgpu-proxy-perf-v1",
    "clock_model": "cycle-domain only; no frequency, voltage, capacitance, or timing closure assumed",
    "compute_utilization": 0.60,
    "memory_bus_bytes_per_cycle": 32,
    "memory_efficiency": 0.70,
    "launch_overhead_cycles": 64,
    "completion_overhead_cycles": 16,
    "axi_lite_setup_writes": 8,
    "axi_lite_status_reads": 4,
    "axi_lite_clear_writes": 1,
    "axi_lite_register_bytes": 4,
    "activity_weights": {
        "fp32_op": 1.0,
        "integer_op": 0.5,
        "read_byte": 0.20,
        "write_byte": 0.25,
        "axi_lite_transaction": 8.0,
        "cycle": 0.03,
    },
}

MONOTONIC_EVIDENCE_TIERS = ("CC8000L", "CC8000", "CC8400")


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"expected object in {path}, got {type(data).__name__}")
    return data


def _extract_workloads(metrics: dict[str, Any] | None) -> tuple[list[dict[str, Any]], str]:
    if metrics and isinstance(metrics.get("workloads"), list):
        workloads = []
        for item in metrics["workloads"]:
            if isinstance(item, dict) and "workload" in item:
                workloads.append(
                    {
                        "workload": str(item.get("workload")),
                        "alias": item.get("alias"),
                        "precision_path": item.get("precision_path", "unknown"),
                        "fp32_ops": int(item.get("fp32_ops", 0) or 0),
                        "integer_ops": int(item.get("integer_ops", 0) or 0),
                        "fp16_proxy_ops": int(
                            item.get("fp16_proxy", {}).get("fp16_ops", 0)
                            if isinstance(item.get("fp16_proxy"), dict)
                            else 0
                        ),
                        "bytes_read": int(item.get("bytes_read", 0) or 0),
                        "bytes_written": int(item.get("bytes_written", 0) or 0),
                        "result_sha256": item.get("result_sha256"),
                        "tolerance_pass": item.get("tolerance", {}).get("pass")
                        if isinstance(item.get("tolerance"), dict)
                        else None,
                        "source_status": "from_model_metrics",
                    }
                )
        if workloads:
            return workloads, "artifacts/rank_01_vivante_3d_gpgpu_ip/model/metrics.json"

    return [
        {
            "workload": "vector_add",
            "alias": None,
            "precision_path": "FP32",
            "fp32_ops": 32,
            "integer_ops": 0,
            "fp16_proxy_ops": 32,
            "bytes_read": 256,
            "bytes_written": 128,
            "result_sha256": None,
            "tolerance_pass": None,
            "source_status": "fallback",
        },
        {
            "workload": "gemm_proxy",
            "alias": None,
            "precision_path": "FP32",
            "fp32_ops": 240,
            "integer_ops": 0,
            "fp16_proxy_ops": 240,
            "bytes_read": 216,
            "bytes_written": 80,
            "result_sha256": None,
            "tolerance_pass": None,
            "source_status": "fallback",
        },
        {
            "workload": "convolution_proxy",
            "alias": "image_filter",
            "precision_path": "FP32",
            "fp32_ops": 450,
            "integer_ops": 0,
            "fp16_proxy_ops": 450,
            "bytes_read": 232,
            "bytes_written": 100,
            "result_sha256": None,
            "tolerance_pass": None,
            "source_status": "fallback",
        },
        {
            "workload": "image_filter",
            "alias": None,
            "precision_path": "u8",
            "fp32_ops": 0,
            "integer_ops": 576,
            "fp16_proxy_ops": 0,
            "bytes_read": 64,
            "bytes_written": 64,
            "result_sha256": None,
            "tolerance_pass": None,
            "source_status": "fallback",
        },
        {
            "workload": "memory_copy",
            "alias": None,
            "precision_path": "byte",
            "fp32_ops": 0,
            "integer_ops": 0,
            "fp16_proxy_ops": 0,
            "bytes_read": 256,
            "bytes_written": 256,
            "result_sha256": None,
            "tolerance_pass": None,
            "source_status": "fallback",
        },
    ], "built_in_fallback"


def _extract_tiers(metrics: dict[str, Any] | None) -> tuple[list[dict[str, Any]], str]:
    if metrics:
        public_scaling = metrics.get("public_shader_unit_scaling")
        if isinstance(public_scaling, dict) and isinstance(public_scaling.get("tiers"), list):
            tiers = []
            for item in public_scaling["tiers"]:
                if isinstance(item, dict) and "tier" in item:
                    tiers.append(
                        {
                            "tier": str(item.get("tier")),
                            "shader_units_vec1": int(item.get("shader_units_vec1", 0) or 0),
                            "fp32_ops_per_cycle": int(item.get("fp32_ops_per_cycle", 0) or 0),
                            "fp16_ops_per_cycle": int(item.get("fp16_ops_per_cycle", 0) or 0),
                        }
                    )
            if tiers:
                return tiers, "model_metrics_public_shader_unit_scaling"

    return [dict(item) for item in PUBLIC_TIER_FALLBACK], "built_in_public_tier_fallback"


def _estimate_workload_for_tier(workload: dict[str, Any], tier: dict[str, Any]) -> dict[str, Any]:
    fp32_ops = int(workload["fp32_ops"])
    integer_ops = int(workload.get("integer_ops", 0))
    fp16_proxy_ops = int(workload.get("fp16_proxy_ops", 0))
    bytes_read = int(workload["bytes_read"])
    bytes_written = int(workload["bytes_written"])
    payload_bytes = bytes_read + bytes_written
    axi_lite_transactions = (
        ASSUMPTIONS["axi_lite_setup_writes"]
        + ASSUMPTIONS["axi_lite_status_reads"]
        + ASSUMPTIONS["axi_lite_clear_writes"]
    )
    control_bytes = int(axi_lite_transactions * ASSUMPTIONS["axi_lite_register_bytes"])

    usable_fp32_ops_per_cycle = max(
        float(tier["fp32_ops_per_cycle"]) * float(ASSUMPTIONS["compute_utilization"]),
        1.0,
    )
    usable_fp16_ops_per_cycle = max(
        float(tier["fp16_ops_per_cycle"]) * float(ASSUMPTIONS["compute_utilization"]),
        1.0,
    )
    usable_memory_bytes_per_cycle = max(
        float(ASSUMPTIONS["memory_bus_bytes_per_cycle"]) * float(ASSUMPTIONS["memory_efficiency"]),
        1.0,
    )

    compute_work_units = fp32_ops + integer_ops
    compute_cycles = int(math.ceil(compute_work_units / usable_fp32_ops_per_cycle)) if compute_work_units else 0
    fp16_compute_cycles = (
        int(math.ceil(fp16_proxy_ops / usable_fp16_ops_per_cycle)) if fp16_proxy_ops else 0
    )
    memory_cycles = int(math.ceil(payload_bytes / usable_memory_bytes_per_cycle))
    kernel_body_cycles = max(compute_cycles, memory_cycles)
    kernel_cycles = int(
        ASSUMPTIONS["launch_overhead_cycles"]
        + kernel_body_cycles
        + ASSUMPTIONS["completion_overhead_cycles"]
    )

    weights = ASSUMPTIONS["activity_weights"]
    activity_index = (
        fp32_ops * float(weights["fp32_op"])
        + integer_ops * float(weights["integer_op"])
        + bytes_read * float(weights["read_byte"])
        + bytes_written * float(weights["write_byte"])
        + axi_lite_transactions * float(weights["axi_lite_transaction"])
        + kernel_cycles * float(weights["cycle"])
    )
    power_index = activity_index / max(kernel_cycles, 1)
    bandwidth_bytes_per_cycle = payload_bytes / max(kernel_cycles, 1)
    compute_ops_per_cycle_proxy = fp32_ops / max(kernel_cycles, 1)
    memory_pressure_ratio = memory_cycles / max(kernel_body_cycles, 1)
    compute_pressure_ratio = compute_cycles / max(kernel_body_cycles, 1)
    bottleneck = "memory" if memory_cycles >= compute_cycles else "compute"

    return {
        "tier": tier["tier"],
        "workload": workload["workload"],
        "alias": workload.get("alias"),
        "precision_path": workload.get("precision_path", "unknown"),
        "shader_units_vec1": tier["shader_units_vec1"],
        "public_fp32_ops_per_cycle": tier["fp32_ops_per_cycle"],
        "public_fp16_ops_per_cycle": tier["fp16_ops_per_cycle"],
        "input_fp32_ops": fp32_ops,
        "input_integer_ops": integer_ops,
        "input_fp16_proxy_ops": fp16_proxy_ops,
        "input_bytes_read": bytes_read,
        "input_bytes_written": bytes_written,
        "input_result_sha256": workload.get("result_sha256"),
        "input_tolerance_pass": workload.get("tolerance_pass"),
        "payload_bytes": payload_bytes,
        "axi_lite_transactions_proxy": axi_lite_transactions,
        "control_bytes_proxy": control_bytes,
        "compute_cycles_proxy": compute_cycles,
        "fp16_compute_cycles_proxy": fp16_compute_cycles,
        "memory_cycles_proxy": memory_cycles,
        "kernel_body_cycles_proxy": kernel_body_cycles,
        "kernel_cycles_proxy": kernel_cycles,
        "compute_ops_per_cycle_proxy": round(compute_ops_per_cycle_proxy, 6),
        "integer_ops_per_cycle_proxy": round(integer_ops / max(kernel_cycles, 1), 6),
        "fp16_proxy_ops_per_cycle_proxy": round(fp16_proxy_ops / max(kernel_cycles, 1), 6),
        "bandwidth_bytes_per_cycle_proxy": round(bandwidth_bytes_per_cycle, 6),
        "memory_pressure_ratio": round(memory_pressure_ratio, 6),
        "compute_pressure_ratio": round(compute_pressure_ratio, 6),
        "control_to_payload_ratio": round(control_bytes / max(payload_bytes, 1), 6),
        "activity_index_proxy": round(activity_index, 6),
        "power_index_proxy": round(power_index, 6),
        "bottleneck_proxy": bottleneck,
        "claim_boundary": "proxy estimate only",
    }


def _summarize_by_tier(estimates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_tier: dict[str, list[dict[str, Any]]] = {}
    for item in estimates:
        by_tier.setdefault(item["tier"], []).append(item)

    summary = []
    for tier_name, rows in by_tier.items():
        total_cycles = sum(int(row["kernel_cycles_proxy"]) for row in rows)
        total_payload = sum(int(row["payload_bytes"]) for row in rows)
        total_fp32_ops = sum(int(row["input_fp32_ops"]) for row in rows)
        total_integer_ops = sum(int(row.get("input_integer_ops", 0)) for row in rows)
        total_fp16_proxy_ops = sum(int(row.get("input_fp16_proxy_ops", 0)) for row in rows)
        total_compute_ops = total_fp32_ops + total_integer_ops
        total_activity = sum(float(row["activity_index_proxy"]) for row in rows)
        total_control_bytes = sum(int(row["control_bytes_proxy"]) for row in rows)
        total_axi_lite_transactions = sum(int(row["axi_lite_transactions_proxy"]) for row in rows)
        memory_bound = sum(1 for row in rows if row["bottleneck_proxy"] == "memory")
        compute_bound = sum(1 for row in rows if row["bottleneck_proxy"] == "compute")
        first = rows[0]
        summary.append(
            {
                "tier": tier_name,
                "shader_units_vec1": first["shader_units_vec1"],
                "public_fp32_ops_per_cycle": first["public_fp32_ops_per_cycle"],
                "public_fp16_ops_per_cycle": first["public_fp16_ops_per_cycle"],
                "workload_count": len(rows),
                "total_kernel_cycles_proxy": total_cycles,
                "latency_proxy_cycles": total_cycles,
                "total_payload_bytes": total_payload,
                "total_control_bytes_proxy": total_control_bytes,
                "total_axi_lite_transactions_proxy": total_axi_lite_transactions,
                "total_axi_pressure_bytes_proxy": total_payload + total_control_bytes,
                "total_fp32_ops": total_fp32_ops,
                "total_integer_ops": total_integer_ops,
                "total_compute_ops_proxy": total_compute_ops,
                "total_fp16_proxy_ops": total_fp16_proxy_ops,
                "aggregate_ops_per_cycle_proxy": round(total_fp32_ops / max(total_cycles, 1), 6),
                "aggregate_compute_ops_per_cycle_proxy": round(total_compute_ops / max(total_cycles, 1), 6),
                "aggregate_bandwidth_bytes_per_cycle_proxy": round(total_payload / max(total_cycles, 1), 6),
                "aggregate_axi_pressure_bytes_per_cycle_proxy": round(
                    (total_payload + total_control_bytes) / max(total_cycles, 1),
                    6,
                ),
                "aggregate_control_to_payload_ratio_proxy": round(
                    total_control_bytes / max(total_payload, 1),
                    6,
                ),
                "total_activity_index_proxy": round(total_activity, 6),
                "aggregate_power_index_proxy": round(total_activity / max(total_cycles, 1), 6),
                "memory_bound_workloads": memory_bound,
                "compute_bound_workloads": compute_bound,
            }
        )

    return summary


def _metric_values(rows: list[dict[str, Any]], metric: str) -> list[float]:
    return [float(row[metric]) for row in rows]


def _is_non_decreasing(values: list[float]) -> bool:
    return all(right >= left for left, right in zip(values, values[1:]))


def _is_strictly_increasing(values: list[float]) -> bool:
    return all(right > left for left, right in zip(values, values[1:]))


def _is_strictly_decreasing(values: list[float]) -> bool:
    return all(right < left for left, right in zip(values, values[1:]))


def _build_check(
    name: str,
    rows: list[dict[str, Any]],
    metric: str,
    direction: str,
    claim: str,
) -> dict[str, Any]:
    values = _metric_values(rows, metric)
    if direction == "strictly_increasing":
        passed = _is_strictly_increasing(values)
    elif direction == "strictly_decreasing":
        passed = _is_strictly_decreasing(values)
    elif direction == "non_decreasing":
        passed = _is_non_decreasing(values)
    else:
        raise ValueError(f"unknown direction: {direction}")

    return {
        "name": name,
        "claim": claim,
        "metric": metric,
        "direction": direction,
        "tiers": [str(row["tier"]) for row in rows],
        "values": values,
        "pass": passed,
    }


def _build_presence_check(rows: list[dict[str, Any]]) -> dict[str, Any]:
    fields = [
        "total_payload_bytes",
        "total_control_bytes_proxy",
        "total_axi_lite_transactions_proxy",
        "total_axi_pressure_bytes_proxy",
        "aggregate_axi_pressure_bytes_per_cycle_proxy",
        "aggregate_control_to_payload_ratio_proxy",
    ]
    missing = [
        {"tier": str(row["tier"]), "field": field}
        for row in rows
        for field in fields
        if field not in row
    ]
    nonpositive = [
        {"tier": str(row["tier"]), "field": field, "value": row.get(field)}
        for row in rows
        for field in fields
        if field in row and float(row[field]) <= 0.0
    ]
    return {
        "name": "axi_byte_pressure_fields_present",
        "claim": "Selected tiers carry payload, control, and aggregate AXI byte-pressure fields.",
        "fields": fields,
        "tiers": [str(row["tier"]) for row in rows],
        "missing": missing,
        "nonpositive": nonpositive,
        "pass": not missing and not nonpositive,
    }


def _build_tier_validation(
    tier_summary: list[dict[str, Any]],
    selected_tiers: tuple[str, ...] = MONOTONIC_EVIDENCE_TIERS,
) -> dict[str, Any]:
    by_tier = {str(row["tier"]): row for row in tier_summary}
    missing_tiers = [tier for tier in selected_tiers if tier not in by_tier]
    rows = [by_tier[tier] for tier in selected_tiers if tier in by_tier]
    enough_tiers = len(rows) >= 3

    checks: list[dict[str, Any]] = [
        {
            "name": "minimum_three_tiers_selected",
            "claim": "Validation covers at least three public-style tiers.",
            "minimum_tier_count": 3,
            "selected_tier_count": len(rows),
            "missing_tiers": missing_tiers,
            "pass": enough_tiers and not missing_tiers,
        }
    ]

    if enough_tiers and not missing_tiers:
        checks.extend(
            [
                _build_check(
                    "tier_throughput_monotonic",
                    rows,
                    "aggregate_compute_ops_per_cycle_proxy",
                    "strictly_increasing",
                    "Aggregate compute throughput proxy increases across the selected tier ladder.",
                ),
                _build_presence_check(rows),
                _build_check(
                    "axi_byte_pressure_monotonic",
                    rows,
                    "aggregate_axi_pressure_bytes_per_cycle_proxy",
                    "strictly_increasing",
                    "Payload plus AXI4-Lite control byte pressure per proxy cycle increases as latency falls.",
                ),
                _build_check(
                    "latency_proxy_monotonic",
                    rows,
                    "latency_proxy_cycles",
                    "strictly_decreasing",
                    "Aggregate proxy latency cycles decrease across the selected tier ladder.",
                ),
                _build_check(
                    "power_proxy_monotonic",
                    rows,
                    "aggregate_power_index_proxy",
                    "strictly_increasing",
                    "Relative power proxy rises with higher modeled activity per cycle.",
                ),
            ]
        )

    status = "pass" if all(bool(check["pass"]) for check in checks) else "fail"
    return {
        "schema": "celviz.gpgpu.proxy_perf_model.tier_validation.v1",
        "claim_boundary": ASSUMPTIONS["claim_boundary"],
        "selected_tiers": list(selected_tiers),
        "selected_tier_rows": rows,
        "checks": checks,
        "status": status,
    }


def build_report(model_metrics_path: Path) -> dict[str, Any]:
    metrics = _load_json(model_metrics_path)
    workloads, workload_source = _extract_workloads(metrics)
    tiers, tier_source = _extract_tiers(metrics)

    estimates = []
    for tier in tiers:
        for workload in workloads:
            estimates.append(_estimate_workload_for_tier(workload, tier))

    generated_at = _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()
    tier_summary = _summarize_by_tier(estimates)
    tier_validation = _build_tier_validation(tier_summary)
    return {
        "schema": "celviz.gpgpu.proxy_perf_model.v1",
        "generated_at_utc": generated_at,
        "ip_name": "Celviz GPGPU IP",
        "public_reference_ip": "Vivante 3D GPGPU IP",
        "orientation": "GPGPU compute workloads, not 3D graphics workloads",
        "source_model_metrics": str(model_metrics_path.relative_to(REPO_ROOT))
        if model_metrics_path.exists()
        else str(model_metrics_path),
        "workload_source": workload_source,
        "tier_source": tier_source,
        "assumptions": ASSUMPTIONS,
        "workloads": workloads,
        "tiers": tiers,
        "estimates": estimates,
        "tier_summary": tier_summary,
        "tier_validation": tier_validation,
        "limitations": [
            "This is a clean-room proxy model, not measured RTL or silicon PPA.",
            "Public CC8000/CC8X00 tier rows are metadata, not local performance measurements.",
            "Cycle estimates use fixed utilization, memory-efficiency, and launch/completion overhead assumptions.",
            "Power index is relative activity weighting only; it has no watt, joule, voltage, or frequency meaning.",
            "FP16 cycle rows use compute-model binary16 proxy operation counts when present; they are not ISA timing.",
            "AXI traffic is estimated from workload bytes and proxy MMIO counts until RTL/control-plane monitors exist.",
        ],
        "status": "pass" if tier_validation["status"] == "pass" else "fail",
    }


def write_outputs(report: dict[str, Any], output_json: Path, output_log: Path) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_log.parent.mkdir(parents=True, exist_ok=True)

    with output_json.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
        fh.write("\n")

    tier_summary = report["tier_summary"]
    fastest = min(tier_summary, key=lambda row: row["total_kernel_cycles_proxy"])
    slowest = max(tier_summary, key=lambda row: row["total_kernel_cycles_proxy"])
    with output_log.open("w", encoding="utf-8") as fh:
        fh.write("Celviz GPGPU IP proxy performance model run\n")
        fh.write(f"schema={report['schema']}\n")
        fh.write(f"generated_at_utc={report['generated_at_utc']}\n")
        fh.write(f"orientation={report['orientation']}\n")
        fh.write(f"source_model_metrics={report['source_model_metrics']}\n")
        fh.write(f"workload_source={report['workload_source']}\n")
        fh.write(f"tier_source={report['tier_source']}\n")
        fh.write(f"workload_count={len(report['workloads'])}\n")
        fh.write(f"tier_count={len(report['tiers'])}\n")
        fh.write(f"estimate_count={len(report['estimates'])}\n")
        fh.write(f"tier_validation_status={report['tier_validation']['status']}\n")
        fh.write(
            "tier_validation_selected_tiers="
            + ",".join(report["tier_validation"]["selected_tiers"])
            + "\n"
        )
        fh.write(f"fastest_tier_by_proxy_cycles={fastest['tier']} cycles={fastest['total_kernel_cycles_proxy']}\n")
        fh.write(f"slowest_tier_by_proxy_cycles={slowest['tier']} cycles={slowest['total_kernel_cycles_proxy']}\n")
        fh.write("assumption_claim_boundary=" + report["assumptions"]["claim_boundary"] + "\n")
        fh.write("assumption_compute_utilization=" + str(report["assumptions"]["compute_utilization"]) + "\n")
        fh.write(
            "assumption_memory_bus_bytes_per_cycle="
            + str(report["assumptions"]["memory_bus_bytes_per_cycle"])
            + "\n"
        )
        fh.write("assumption_memory_efficiency=" + str(report["assumptions"]["memory_efficiency"]) + "\n")
        for row in tier_summary:
            fh.write(
                "tier_summary"
                f" tier={row['tier']}"
                f" shader_units_vec1={row['shader_units_vec1']}"
                f" cycles={row['total_kernel_cycles_proxy']}"
                f" ops_per_cycle={row['aggregate_ops_per_cycle_proxy']}"
                f" compute_ops_per_cycle={row['aggregate_compute_ops_per_cycle_proxy']}"
                f" bandwidth_bytes_per_cycle={row['aggregate_bandwidth_bytes_per_cycle_proxy']}"
                f" axi_pressure_bytes_per_cycle={row['aggregate_axi_pressure_bytes_per_cycle_proxy']}"
                f" power_index={row['aggregate_power_index_proxy']}"
                f" memory_bound_workloads={row['memory_bound_workloads']}"
                f" compute_bound_workloads={row['compute_bound_workloads']}"
                "\n"
            )
        for check in report["tier_validation"]["checks"]:
            fh.write(
                "tier_validation_check"
                f" name={check['name']}"
                f" pass={str(check['pass']).lower()}"
                + (f" metric={check['metric']}" if "metric" in check else "")
                + (f" direction={check['direction']}" if "direction" in check else "")
                + "\n"
            )
        fh.write(f"metrics={output_json.relative_to(REPO_ROOT)}\n")
        fh.write(f"status={report['status']}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-metrics", type=Path, default=DEFAULT_MODEL_METRICS)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-log", type=Path, default=DEFAULT_OUTPUT_LOG)
    parser.add_argument("--print-summary", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args.model_metrics)
    write_outputs(report, args.output_json, args.output_log)

    if args.print_summary:
        print(json.dumps(report["tier_summary"], indent=2, sort_keys=True))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
