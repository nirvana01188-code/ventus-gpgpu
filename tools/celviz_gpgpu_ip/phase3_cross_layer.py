#!/usr/bin/env python3
"""Cross-layer phase-3 evidence for the Celviz GPGPU IP prototype.

Phase 2 made six lanes pass independently. Phase 3 checks that those lanes line
up as one clean-room stack: OpenCL-like kernel ABI -> runtime command ABI ->
SIMT execution -> memory events -> Linux userspace submission -> verification
and PPA evidence.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "celviz.gpgpu.phase3_cross_layer.v1"
CLEAN_ROOM_SCOPE = (
    "clean-room cross-layer evidence for the Ventus-based Celviz GPGPU IP "
    "prototype; this is not Vivante compatibility, official OpenCL conformance, "
    "a production Linux driver, full RTL structural coverage closure, synthesis "
    "signoff, or silicon readiness"
)
KERNEL_ALIASES = {
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


def phase_status(checks: list[dict[str, Any]]) -> str:
    return "pass" if checks and all(item.get("pass") is True for item in checks) else "fail"


def collect(artifact_root: Path) -> dict[str, Any]:
    opencl_dir = artifact_root / "demo" / "opencl_subset"
    paths = {
        "opencl_evidence": opencl_dir / "opencl_subset_evidence.json",
        "runtime_commands": opencl_dir / "runtime_commands.json",
        "simt_execution": artifact_root / "model" / "outputs" / "simt_execution.json",
        "memory_evidence": artifact_root / "memory" / "memory_system_phase1_evidence.json",
        "linux_runtime": artifact_root / "os_runtime" / "linux_runtime_evidence.json",
        "phase2": artifact_root / "verification" / "phase2_integration_report.json",
        "rtl_supplemental": artifact_root / "verification" / "verilator_supplemental_phase1" / "phase1_supplemental_evidence.json",
        "ppa": artifact_root / "ppa" / "ppa_proxy_report.json",
    }
    artifacts = {name: artifact(path) for name, path in paths.items()}
    opencl = load_json(paths["opencl_evidence"])
    runtime_commands = load_json(paths["runtime_commands"])
    simt = load_json(paths["simt_execution"])
    memory = load_json(paths["memory_evidence"])
    linux_runtime = load_json(paths["linux_runtime"])
    phase2 = load_json(paths["phase2"])
    rtl = load_json(paths["rtl_supplemental"])
    ppa = load_json(paths["ppa"])

    kernel_names = [str(item.get("name")) for item in opencl.get("kernels", [])]
    runtime_dispatch_kernels = [
        str(command.get("kernel"))
        for command in runtime_commands.get("commands", [])
        if command.get("opcode") == "kernel_dispatch"
    ]
    simt_names = {str(name) for name in simt.get("workload_names", [])}
    mapped_simt_names = {KERNEL_ALIASES.get(name, name) for name in kernel_names}
    abi_paths = [Path(item.get("abi", "")) for item in opencl.get("kernels", [])]
    abi_docs = [load_json(path) for path in abi_paths if path.exists()]
    abi_kernel_names = {str(item.get("kernel_name") or item.get("name")) for item in abi_docs}
    global_arg_kernels = {
        str(item.get("kernel_name") or item.get("name"))
        for item in abi_docs
        if any(arg.get("address_space") == "global" for arg in item.get("args", []))
    }
    metadata_complete = {
        str(item.get("kernel_name") or item.get("name"))
        for item in abi_docs
        if item.get("metadata")
    }
    memory_summary = memory.get("summary", {})
    linux_counters = linux_runtime.get("counters", {})
    rtl_metrics = rtl.get("observed_metrics", {})
    ppa_metrics = ppa.get("proxy_metrics", {})

    checks = [
        {
            "name": "kernel_set_opencl_runtime_simt_aligned",
            "pass": set(kernel_names) == set(runtime_dispatch_kernels)
            and mapped_simt_names.issubset(simt_names)
            and set(kernel_names).issubset(abi_kernel_names),
            "evidence": {
                "opencl_kernels": sorted(kernel_names),
                "runtime_dispatch_kernels": sorted(runtime_dispatch_kernels),
                "mapped_simt_names": sorted(mapped_simt_names),
                "simt_names": sorted(simt_names),
                "abi_kernel_names": sorted(abi_kernel_names),
            },
        },
        {
            "name": "kernel_abi_metadata_to_runtime_command",
            "pass": len(abi_docs) == len(kernel_names)
            and set(kernel_names).issubset(global_arg_kernels)
            and set(kernel_names).issubset(metadata_complete)
            and runtime_commands.get("schema") == "celviz.gpgpu.runtime_commands.v1",
            "evidence": {
                "abi_count": len(abi_docs),
                "global_arg_kernels": sorted(global_arg_kernels),
                "metadata_complete": sorted(metadata_complete),
            },
        },
        {
            "name": "simt_memory_semantics_aligned",
            "pass": simt.get("status") == "pass"
            and memory_summary.get("status") == "pass"
            and as_int(simt.get("totals", {}).get("lsu_loads")) > 0
            and as_int(simt.get("totals", {}).get("lsu_stores")) > 0
            and as_int(memory_summary.get("operations", {}).get("load")) > 0
            and as_int(memory_summary.get("operations", {}).get("store")) > 0
            and as_int(memory_summary.get("operations", {}).get("copy")) >= 3,
            "evidence": {
                "simt_totals": simt.get("totals"),
                "memory_summary": memory_summary,
            },
        },
        {
            "name": "runtime_os_submission_semantics_aligned",
            "pass": opencl.get("runtime_proxy", {}).get("summary", {}).get("commands_failed") == 0
            and as_int(opencl.get("runtime_proxy", {}).get("summary", {}).get("commands_submitted")) == len(kernel_names)
            and as_int(linux_counters.get("submits")) >= 2
            and as_int(linux_counters.get("fence_waits")) >= 1
            and as_int(linux_counters.get("events_polled")) >= 1,
            "evidence": {
                "runtime_proxy": opencl.get("runtime_proxy", {}).get("summary", {}),
                "linux_counters": linux_counters,
            },
        },
        {
            "name": "verification_targets_cover_cross_layer_paths",
            "pass": phase2.get("status") == "pass"
            and rtl_metrics.get("structural_target_percent") == 100.0
            and as_int(rtl_metrics.get("total_kernel_dispatches")) >= len(kernel_names)
            and as_int(rtl_metrics.get("total_dma_copies")) > 0
            and as_int(rtl_metrics.get("total_dma_fills")) > 0
            and as_int(rtl_metrics.get("total_error_interrupts")) > 0,
            "evidence": {
                "phase2_status": phase2.get("status"),
                "rtl_observed_metrics": rtl_metrics,
            },
        },
        {
            "name": "ppa_proxy_links_to_cross_layer_scope",
            "pass": ppa.get("status") == "pass"
            and as_int(ppa.get("source_summary", {}).get("marker_hit_count")) > 0
            and float(ppa_metrics.get("area_proxy_units", 0)) > 0
            and float(ppa_metrics.get("frequency_proxy_index", 0)) > 0
            and {"CC8000L", "CC8000"}.issubset({item.get("tier") for item in ppa.get("public_baseline_tiers", [])}),
            "evidence": {
                "source_summary": ppa.get("source_summary"),
                "proxy_metrics": ppa_metrics,
                "public_baseline_tiers": ppa.get("public_baseline_tiers"),
            },
        },
    ]
    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "status": phase_status(checks),
        "kernel_aliases": KERNEL_ALIASES,
        "checks": checks,
        "artifacts": artifacts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Celviz GPGPU phase-3 cross-layer evidence.")
    parser.add_argument(
        "--artifact-root",
        type=Path,
        default=Path("artifacts/rank_01_vivante_3d_gpgpu_ip"),
        help="Rank 1 artifact root",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/rank_01_vivante_3d_gpgpu_ip/verification/phase3_cross_layer_report.json"),
        help="Output JSON report path",
    )
    args = parser.parse_args()
    report = collect(args.artifact_root)
    write_json(args.output, report)
    passed = sum(1 for item in report["checks"] if item["pass"])
    total = len(report["checks"])
    print(f"celviz_gpgpu_phase3_cross_layer: {report['status']} checks={passed}/{total} output={args.output}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
