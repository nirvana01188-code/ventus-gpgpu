#!/usr/bin/env python3
"""Cross-check OpenCL host API shim paths against RTL counters and coverage bins.

The report maps dispatch, event, and buffer host API paths onto existing
control-plane/RTL debug counters and Verilator functional coverage bins.  It is
CTS-readiness evidence only; it does not claim Khronos CTS pass, official
OpenCL conformance, or RTL structural coverage closure.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


SCHEMA = "celviz.gpgpu.opencl_rtl_cts_cross_check.v1"
DEFAULT_ARTIFACT_ROOT = Path("artifacts/rank_01_vivante_3d_gpgpu_ip")
DEFAULT_OUTPUT = DEFAULT_ARTIFACT_ROOT / "verification/opencl_rtl_cts_cross_check.json"
DEFAULT_DOC = Path("docs/celviz-gpgpu-ip/OPENCL_RTL_CTS_CROSS_CHECK.md")
CLEAN_ROOM_SCOPE = (
    "OpenCL host API shim to RTL/coverage cross-check for Celviz GPGPU IP "
    "readiness. This maps local clean-room dispatch/event/buffer paths to "
    "existing RTL debug counters and Verilator functional coverage bins. It is "
    "not Khronos CTS, not official OpenCL conformance, not a product ICD, not "
    "RTL structural coverage 100%, and not silicon signoff."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def artifact(path: Path) -> dict[str, Any]:
    exists = path.exists()
    size = path.stat().st_size if exists else 0
    return {"path": path.as_posix(), "exists": exists, "size_bytes": size, "non_empty": bool(exists and size > 0)}


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def api_set(host_report: Mapping[str, Any]) -> set[str]:
    return {str(item.get("api")) for item in host_report.get("api_call_trace", []) if isinstance(item, Mapping)}


def event_commands(host_report: Mapping[str, Any]) -> set[str]:
    return {str(item.get("command")) for item in host_report.get("event_trace", []) if isinstance(item, Mapping)}


def runtime_command_opcodes(runtime_commands: Mapping[str, Any]) -> set[str]:
    return {str(item.get("opcode")) for item in runtime_commands.get("commands", []) if isinstance(item, Mapping)}


def runtime_kernel_names(runtime_commands: Mapping[str, Any]) -> set[str]:
    return {str(item.get("kernel")) for item in runtime_commands.get("commands", []) if isinstance(item, Mapping) and item.get("opcode") == "kernel_dispatch"}


def completion_records(control_metrics: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [item for item in control_metrics.get("completion_records", []) if isinstance(item, Mapping)]


def counter(control_metrics: Mapping[str, Any], name: str) -> int:
    counters = control_metrics.get("counters", {})
    if isinstance(counters, Mapping):
        return as_int(counters.get(name), 0)
    return 0


def feature_bins(e8: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(item.get("name")): item
        for item in e8.get("feature_bins", [])
        if isinstance(item, Mapping)
    }


def hit_bin(bins: Mapping[str, Mapping[str, Any]], name: str) -> bool:
    return bins.get(name, {}).get("hit") is True


def pass_check(name: str, passed: bool, evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {"name": name, "pass": bool(passed), "evidence": dict(evidence or {})}


def mapping_row(
    path_id: str,
    host_apis: Iterable[str],
    runtime_opcodes: Iterable[str],
    rtl_counters: Iterable[str],
    coverage_bins: Iterable[str],
    host_report: Mapping[str, Any],
    runtime_commands: Mapping[str, Any],
    control_metrics: Mapping[str, Any],
    bins: Mapping[str, Mapping[str, Any]],
    notes: str,
) -> dict[str, Any]:
    observed_apis = api_set(host_report)
    observed_opcodes = runtime_command_opcodes(runtime_commands)
    api_hits = {api: api in observed_apis for api in host_apis}
    opcode_hits = {opcode: opcode in observed_opcodes for opcode in runtime_opcodes}
    counter_hits = {name: counter(control_metrics, name) > 0 for name in rtl_counters}
    bin_hits = {name: hit_bin(bins, name) for name in coverage_bins}
    return {
        "path_id": path_id,
        "host_apis": api_hits,
        "runtime_opcodes": opcode_hits,
        "rtl_debug_counters": counter_hits,
        "coverage_bins": bin_hits,
        "pass": all(api_hits.values()) and all(opcode_hits.values()) and all(counter_hits.values()) and all(bin_hits.values()),
        "notes": notes,
    }


def build_report(artifact_root: Path) -> dict[str, Any]:
    verification = artifact_root / "verification"
    demo_opencl = artifact_root / "demo" / "opencl_subset"
    rtl = artifact_root / "rtl"
    e8_dir = verification / "verilator_coverage"

    paths = {
        "host_api_shim_report": verification / "opencl_host_api_shim_report.json",
        "runtime_commands": demo_opencl / "runtime_commands.json",
        "runtime_metrics": demo_opencl / "runtime_proxy" / "runtime_metrics.json",
        "control_plane_metrics": rtl / "control_plane_metrics.json",
        "verilator_coverage_report": e8_dir / "verilator_coverage_report.json",
        "opencl_cts_readiness": verification / "phase9_opencl_conformance_readiness_report.json",
        "opencl_cts_matrix": verification / "opencl_cts_readiness_matrix.json",
        "supplemental_phase1": verification / "verilator_supplemental_phase1" / "phase1_supplemental_evidence.json",
    }
    artifacts = {name: artifact(path) for name, path in paths.items()}
    host = load_json(paths["host_api_shim_report"])
    runtime = load_json(paths["runtime_commands"])
    runtime_metrics = load_json(paths["runtime_metrics"])
    control = load_json(paths["control_plane_metrics"])
    e8 = load_json(paths["verilator_coverage_report"])
    opencl_ready = load_json(paths["opencl_cts_readiness"])
    supplemental = load_json(paths["supplemental_phase1"])
    bins = feature_bins(e8)
    records = completion_records(control)
    observed_events = event_commands(host)
    kernels = runtime_kernel_names(runtime)
    required_host_apis = {
        "clGetPlatformIDs",
        "clGetDeviceIDs",
        "clGetDeviceInfo",
        "clCreateContext",
        "clCreateCommandQueueWithProperties",
        "clCreateBuffer",
        "clEnqueueWriteBuffer",
        "clCreateProgramWithSource",
        "clBuildProgram",
        "clCreateKernel",
        "clSetKernelArg",
        "clEnqueueNDRangeKernel",
        "clEnqueueReadBuffer",
        "clWaitForEvents",
        "clFinish",
    }

    mappings = [
        mapping_row(
            "host_dispatch_to_kernel_dispatch",
            ("clCreateProgramWithSource", "clBuildProgram", "clCreateKernel", "clSetKernelArg", "clEnqueueNDRangeKernel", "clFinish"),
            ("kernel_dispatch",),
            ("commands_submitted", "commands_completed", "kernel_dispatches", "apb_writes", "apb_reads"),
            ("queues", "native_command_categories", "pending_count_zero"),
            host,
            runtime,
            control,
            bins,
            "Host program/kernel/NDRange lifecycle maps to runtime kernel_dispatch and control-plane command/kernel counters.",
        ),
        mapping_row(
            "host_events_to_interrupt_fence_paths",
            ("clEnqueueNDRangeKernel", "clEnqueueReadBuffer", "clWaitForEvents", "clFinish"),
            ("kernel_dispatch",),
            ("completion_interrupts", "interrupt_clears", "fence_waits", "fence_signals"),
            ("completion_interrupt", "fence_wait", "fence_signal", "pending_count_zero"),
            host,
            runtime,
            control,
            bins,
            "Host event wait/finish readiness maps to proxy completion interrupts, interrupt clear, and fence coverage.",
        ),
        mapping_row(
            "host_buffers_to_dma_and_axi_paths",
            ("clCreateBuffer", "clEnqueueWriteBuffer", "clEnqueueReadBuffer", "clReleaseBuffer"),
            ("kernel_dispatch",),
            ("bytes_read", "bytes_written", "axi_read_transactions", "axi_write_transactions", "dma_copies", "dma_fills"),
            ("dma_fill", "dma_copy", "dma_copy_h2d", "dma_copy_d2h", "native_command_categories"),
            host,
            runtime,
            control,
            bins,
            "Host buffer create/write/read lifecycle maps to existing DMA/fill/copy/AXI evidence bins from the RTL/control-plane suite.",
        ),
        mapping_row(
            "host_negative_api_to_fault_bins",
            ("clGetDeviceInfo", "clCreateCommandQueueWithProperties", "clCreateKernel", "clSetKernelArg", "clCreateBuffer"),
            ("kernel_dispatch",),
            ("commands_failed", "error_interrupts", "mmu_faults", "scheduler_faults"),
            ("error_interrupt", "mmu_fault", "scheduler_fault"),
            host,
            runtime,
            control,
            bins,
            "Host API negative readiness is cross-checked against existing fault/interrupt structural bins; it is not CTS pass evidence.",
        ),
    ]

    checks = [
        pass_check(
            "host_api_trace_present",
            required_host_apis <= api_set(host),
            {
                "host_report_status": host.get("status"),
                "api_call_count": host.get("api_call_count"),
                "missing_required_apis": sorted(required_host_apis - api_set(host)),
            },
        ),
        pass_check("runtime_commands_have_opencl_kernels", kernels >= {"vector_add", "gemm", "conv2d", "image_filter"}, {"kernels": sorted(kernels)}),
        pass_check("runtime_proxy_metrics_pass", runtime_metrics.get("status") == "pass", {"status": runtime_metrics.get("status")}),
        pass_check("control_plane_metrics_pass", control.get("status") == "pass", {"status": control.get("status")}),
        pass_check("verilator_functional_bins_pass", e8.get("status") == "pass" and e8.get("functional_coverage_percent") == 100.0, {"status": e8.get("status"), "functional_coverage_percent": e8.get("functional_coverage_percent")}),
        pass_check("opencl_readiness_scope_present", opencl_ready.get("status") in {"pass", "partial", "blocked_for_conformance"}, {"status": opencl_ready.get("status")}),
        pass_check("supplemental_structural_targets_recorded", supplemental.get("observed_metrics", {}).get("structural_target_hit_count") is not None, supplemental.get("observed_metrics", {})),
        pass_check("dispatch_mapping_pass", mappings[0]["pass"], mappings[0]),
        pass_check("event_mapping_pass", mappings[1]["pass"], mappings[1]),
        pass_check("buffer_mapping_pass", mappings[2]["pass"], mappings[2]),
        pass_check("negative_mapping_pass", mappings[3]["pass"], mappings[3]),
        pass_check("no_cts_or_structural_overclaim", "not Khronos CTS" in CLEAN_ROOM_SCOPE and "not RTL structural coverage 100%" in CLEAN_ROOM_SCOPE),
    ]

    structural_metrics = {
        "line": e8.get("line_metrics"),
        "branch": e8.get("lcov_info", {}).get("branch") if isinstance(e8.get("lcov_info"), Mapping) else None,
        "toggle": e8.get("toggle_metrics"),
        "status": "reported_separately_not_a_closure_claim",
    }

    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "status": "pass" if all(item["pass"] for item in checks) else "fail",
        "cts_ready": False,
        "structural_coverage_closed": False,
        "artifacts": artifacts,
        "checks": checks,
        "path_mappings": mappings,
        "observed": {
            "host_api_count": host.get("api_call_count"),
            "host_event_commands": sorted(observed_events),
            "opencl_runtime_kernels": sorted(kernels),
            "control_command_count": control.get("command_count"),
            "control_counters": control.get("counters", {}),
            "verilator_feature_bins_hit": sorted(name for name, item in bins.items() if item.get("hit") is True),
            "supplemental_structural_metrics": supplemental.get("observed_metrics", {}),
            "structural_metrics": structural_metrics,
        },
        "claim_boundaries": {
            "khronos_cts_pass": False,
            "official_opencl_conformance": False,
            "product_icd": False,
            "rtl_structural_coverage_100": False,
            "silicon_signoff": False,
        },
    }


def render_doc(report: Mapping[str, Any]) -> str:
    lines = [
        "# OpenCL RTL/CTS Readiness Cross-Check",
        "",
        f"Generated: `{report.get('generated_at')}`",
        "",
        f"Status: `{report.get('status')}`",
        "",
        str(report.get("clean_room_scope")),
        "",
        "## Summary",
        "",
        f"- CTS ready: `{str(report.get('cts_ready')).lower()}`",
        f"- RTL structural coverage closed: `{str(report.get('structural_coverage_closed')).lower()}`",
        "- Purpose: map local OpenCL host shim dispatch/event/buffer paths to existing RTL counters and Verilator functional bins.",
        "",
        "## Path Mappings",
        "",
        "| Path | Pass | Host APIs | Runtime opcodes | RTL counters | Coverage bins |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in report.get("path_mappings", []):
        apis = ", ".join(f"{k}:{'Y' if v else 'N'}" for k, v in row.get("host_apis", {}).items())
        opcodes = ", ".join(f"{k}:{'Y' if v else 'N'}" for k, v in row.get("runtime_opcodes", {}).items())
        counters = ", ".join(f"{k}:{'Y' if v else 'N'}" for k, v in row.get("rtl_debug_counters", {}).items())
        bins = ", ".join(f"{k}:{'Y' if v else 'N'}" for k, v in row.get("coverage_bins", {}).items())
        lines.append(f"| `{row.get('path_id')}` | `{str(row.get('pass')).lower()}` | {apis} | {opcodes} | {counters} | {bins} |")

    lines.extend(["", "## Checks", ""])
    for check in report.get("checks", []):
        lines.append(f"- `{check.get('name')}`: `{'pass' if check.get('pass') else 'fail'}`")

    lines.extend(
        [
            "",
            "## Structural Metrics",
            "",
            "These metrics are observations only. They are not a structural coverage closure or waiver signoff.",
            "",
            "```json",
            json.dumps(report.get("observed", {}).get("structural_metrics", {}), indent=2, sort_keys=True),
            "```",
            "",
            "## Claim Boundaries",
            "",
            "```json",
            json.dumps(report.get("claim_boundaries", {}), indent=2, sort_keys=True),
            "```",
            "",
            "## Completion Rule",
            "",
            "This cross-check is complete when the JSON status is `pass` and all mappings show host API coverage, runtime opcode evidence, RTL/debug counter evidence, and Verilator functional-bin evidence. It still does not mean Khronos CTS readiness, official OpenCL conformance, product ICD readiness, RTL structural 100%, or silicon signoff.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate OpenCL host API to RTL/coverage cross-check evidence.")
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--doc-output", type=Path, default=DEFAULT_DOC)
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args()

    report = build_report(args.artifact_root)
    write_json(args.output, report)
    args.doc_output.parent.mkdir(parents=True, exist_ok=True)
    args.doc_output.write_text(render_doc(report), encoding="utf-8")
    passed = sum(1 for item in report["checks"] if item["pass"])
    print(
        "celviz_gpgpu_opencl_rtl_cts_cross_check: "
        f"{report['status']} checks={passed}/{len(report['checks'])} "
        f"output={args.output} doc={args.doc_output}"
    )
    if args.print_summary:
        print(json.dumps({"status": report["status"], "cts_ready": report["cts_ready"], "structural_coverage_closed": report["structural_coverage_closed"]}, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
