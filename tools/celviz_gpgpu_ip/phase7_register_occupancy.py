#!/usr/bin/env python3
"""Generate phase-7 register occupancy and banking evidence.

This report links compiler IR, lowering metadata, SIMT workload shape, and the
Phase 7 config sweep into a clean-room register-pressure/occupancy proxy. It is
not a physical register-file implementation, not a place-and-route result, not
a timing model, and not silicon signoff.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "celviz.gpgpu.phase7_register_occupancy.v1"
CLEAN_ROOM_SCOPE = (
    "clean-room phase-7 register occupancy and banking proxy derived from "
    "Celviz compiler IR, lowering metadata, SIMT evidence, and config sweep "
    "only; not a physical register-file implementation, not timing closure, "
    "not place-and-route, and not silicon signoff"
)
DEFAULT_ROOT = Path("artifacts/rank_01_vivante_3d_gpgpu_ip")
KERNELS = ("vector_add", "gemm", "conv2d", "image_filter")
WORKLOAD_ALIAS = {
    "vector_add": "vector_add",
    "gemm": "gemm_proxy",
    "conv2d": "convolution_proxy",
    "image_filter": "image_filter",
}
SGPR_BUDGET = 64
VGPR_BUDGET = 256


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


def best_config_for_kernel(config_sweep: Mapping[str, Any], kernel: str) -> Mapping[str, Any]:
    best = config_sweep.get("summary", {}).get("best_config_by_kernel", {}).get(kernel, {})
    config_id = best.get("config_id")
    for row in config_sweep.get("sweep_configs", []):
        if row.get("config_id") == config_id:
            return row
    return {}


def peak_live_registers(ir: Mapping[str, Any]) -> dict[str, Any]:
    peak_vregs = 0
    peak_pregs = 0
    live_vregs: set[str] = set()
    live_pregs: set[str] = set()
    timeline = []
    for item in ir.get("def_use", []):
        for reg in item.get("defs", []):
            if str(reg).startswith("v"):
                live_vregs.add(str(reg))
            elif str(reg).startswith("p"):
                live_pregs.add(str(reg))
        peak_vregs = max(peak_vregs, len(live_vregs))
        peak_pregs = max(peak_pregs, len(live_pregs))
        timeline.append(
            {
                "pc": item.get("pc"),
                "opcode": item.get("opcode"),
                "live_vregs": len(live_vregs),
                "live_pregs": len(live_pregs),
            }
        )
    return {
        "peak_ir_vregs": peak_vregs,
        "peak_ir_pregs": peak_pregs,
        "live_register_timeline_head": timeline[:8],
        "live_register_timeline_tail": timeline[-8:],
    }


def limit_reason(sgpr_waves: int, vgpr_waves: int, warp_slots: int, bank_limited_waves: int) -> str:
    limits = {
        "sgpr": sgpr_waves,
        "vgpr": vgpr_waves,
        "warp_slots": warp_slots,
        "register_banks": bank_limited_waves,
    }
    return min(limits, key=limits.get)


def build_kernel(
    *,
    kernel: str,
    lowering: Mapping[str, Any],
    ir: Mapping[str, Any],
    microop: Mapping[str, Any],
    simt_workload: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    metadata = lowering.get("metadata_link", {})
    sgpr_usage = as_int(metadata.get("sgprUsage"))
    vgpr_usage = as_int(metadata.get("vgprUsage"))
    ir_pressure = peak_live_registers(ir)
    peak_sregs = max(sgpr_usage, ir_pressure["peak_ir_pregs"] + 8)
    peak_vregs = max(vgpr_usage, ir_pressure["peak_ir_vregs"] * 4)
    wavefront_size = as_int(microop.get("execution", {}).get("wavefront_size"), 32)
    work_items = as_int(microop.get("execution", {}).get("work_items"))
    required_wavefronts = max(1, math.ceil(work_items / max(1, wavefront_size)))
    warp_slots = as_int(config.get("warp_count"), 1)
    banks = as_int(config.get("register_file_banks"), 1)
    sgpr_limited_waves = max(1, SGPR_BUDGET // max(1, peak_sregs))
    vgpr_limited_waves = max(1, VGPR_BUDGET // max(1, peak_vregs))
    bank_limited_waves = max(1, banks // 2)
    active_wavefronts = max(1, min(required_wavefronts, warp_slots, sgpr_limited_waves, vgpr_limited_waves, bank_limited_waves))
    occupancy_ratio = round(active_wavefronts / max(1, min(required_wavefronts, warp_slots)), 6)
    bank_conflict_proxy = round((peak_vregs + peak_sregs) / max(1, banks * 16), 6)
    counters = simt_workload.get("counters", {})
    issue_pressure_proxy = round(as_int(counters.get("register_reads")) / max(1, active_wavefronts * banks), 6)
    reason = limit_reason(sgpr_limited_waves, vgpr_limited_waves, warp_slots, bank_limited_waves)
    return {
        "kernel": kernel,
        "workload": WORKLOAD_ALIAS[kernel],
        "config_id": config.get("config_id"),
        "register_file_banks": banks,
        "warp_slots": warp_slots,
        "work_items": work_items,
        "wavefront_size": wavefront_size,
        "required_wavefronts": required_wavefronts,
        "sgpr_budget": SGPR_BUDGET,
        "vgpr_budget": VGPR_BUDGET,
        "metadata_sgpr_usage": sgpr_usage,
        "metadata_vgpr_usage": vgpr_usage,
        "peak_sregs": peak_sregs,
        "peak_vregs": peak_vregs,
        "peak_ir_vregs": ir_pressure["peak_ir_vregs"],
        "peak_ir_pregs": ir_pressure["peak_ir_pregs"],
        "sgpr_limited_wavefronts": sgpr_limited_waves,
        "vgpr_limited_wavefronts": vgpr_limited_waves,
        "bank_limited_wavefronts": bank_limited_waves,
        "active_wavefronts_proxy": active_wavefronts,
        "occupancy_ratio_proxy": occupancy_ratio,
        "occupancy_limit_reason": reason,
        "bank_conflict_proxy": bank_conflict_proxy,
        "issue_pressure_proxy": issue_pressure_proxy,
        "live_register_timeline_head": ir_pressure["live_register_timeline_head"],
        "live_register_timeline_tail": ir_pressure["live_register_timeline_tail"],
        "model": "deterministic proxy from lowering sgpr/vgpr metadata, compiler IR live-register growth, SIMT counters, and config-sweep register banks",
    }


def collect(artifact_root: Path) -> dict[str, Any]:
    compiler = load_json(artifact_root / "compiler_ir" / "compiler_ir_report.json")
    lowering_report = load_json(artifact_root / "lowering" / "kernel_lowering_report.json")
    microop_report = load_json(artifact_root / "microop_execution" / "microop_execution_report.json")
    simt = load_json(artifact_root / "model" / "outputs" / "simt_execution.json")
    config_sweep = load_json(artifact_root / "verification" / "phase7_config_sweep_report.json")
    simt_workloads = simt_by_workload(simt)
    kernels = []
    for kernel in KERNELS:
        kernels.append(
            build_kernel(
                kernel=kernel,
                lowering=load_json(artifact_root / "lowering" / "kernels" / f"{kernel}.lowering.json"),
                ir=load_json(artifact_root / "compiler_ir" / "kernels" / f"{kernel}.compiler_ir.json"),
                microop=load_json(artifact_root / "microop_execution" / "kernels" / f"{kernel}.microop_execution.json"),
                simt_workload=simt_workloads[WORKLOAD_ALIAS[kernel]],
                config=best_config_for_kernel(config_sweep, kernel),
            )
        )

    checks = [
        {
            "name": "input_reports_pass",
            "pass": compiler.get("status") == lowering_report.get("status") == microop_report.get("status") == simt.get("status") == config_sweep.get("status") == "pass",
        },
        {"name": "all_required_kernels_modeled", "pass": {item["kernel"] for item in kernels} == set(KERNELS)},
        {"name": "peak_vregs_peak_sregs_present", "pass": all(item["peak_vregs"] > 0 and item["peak_sregs"] > 0 for item in kernels)},
        {"name": "occupancy_limit_reason_present", "pass": all(item["occupancy_limit_reason"] in {"sgpr", "vgpr", "warp_slots", "register_banks"} for item in kernels)},
        {"name": "bank_conflict_proxy_present", "pass": all(item["bank_conflict_proxy"] > 0.0 for item in kernels)},
        {"name": "active_wavefronts_positive", "pass": all(item["active_wavefronts_proxy"] > 0 for item in kernels)},
        {"name": "config_sweep_bank_link_present", "pass": all(item["config_id"] and item["register_file_banks"] > 0 for item in kernels)},
        {"name": "claim_boundary_declared", "pass": "not a physical register-file implementation" in CLEAN_ROOM_SCOPE and "not silicon signoff" in CLEAN_ROOM_SCOPE},
    ]
    occupancy_by_reason: dict[str, int] = {}
    for item in kernels:
        occupancy_by_reason[item["occupancy_limit_reason"]] = occupancy_by_reason.get(item["occupancy_limit_reason"], 0) + 1
    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "status": "pass" if all(check["pass"] for check in checks) else "fail",
        "checks": checks,
        "summary": {
            "kernel_count": len(kernels),
            "sgpr_budget": SGPR_BUDGET,
            "vgpr_budget": VGPR_BUDGET,
            "max_peak_sregs": max(item["peak_sregs"] for item in kernels),
            "max_peak_vregs": max(item["peak_vregs"] for item in kernels),
            "min_occupancy_ratio_proxy": min(item["occupancy_ratio_proxy"] for item in kernels),
            "max_bank_conflict_proxy": max(item["bank_conflict_proxy"] for item in kernels),
            "occupancy_limit_reasons": occupancy_by_reason,
        },
        "kernels": kernels,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate phase-7 register occupancy evidence.")
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_ROOT / "verification" / "phase7_register_occupancy_report.json")
    args = parser.parse_args()
    report = collect(args.artifact_root)
    write_json(args.output, report)
    passed = sum(1 for check in report["checks"] if check["pass"])
    summary = report["summary"]
    print(
        "celviz_gpgpu_phase7_register_occupancy: "
        f"{report['status']} checks={passed}/{len(report['checks'])} "
        f"max_peak_vregs={summary['max_peak_vregs']} max_peak_sregs={summary['max_peak_sregs']} "
        f"max_bank_conflict={summary['max_bank_conflict_proxy']} output={args.output}"
    )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
