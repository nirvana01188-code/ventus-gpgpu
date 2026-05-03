#!/usr/bin/env python3
"""Aggregate Celviz GPGPU verification coverage bins and require 100%.

This report is intentionally a functional/acceptance verification coverage
report. It does not convert Verilator RTL structural line/toggle/source
percentages into a 100% claim; those metrics remain separate observations.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "celviz.gpgpu.verification_coverage_100.v1"
CLEAN_ROOM_SCOPE = (
    "clean-room functional and acceptance verification coverage for the "
    "Ventus-based Celviz GPGPU IP proxy only; no proprietary Vivante "
    "compatibility, proprietary command stream/driver/firmware/SDK claim, "
    "official OpenCL/OpenCV conformance claim, RTL timing closure, PPA, "
    "safety certification, silicon signoff, or production-readiness claim"
)

EXPECTED_E1_OPCODES = (
    "dma_fill",
    "dma_copy",
    "host_to_device",
    "device_to_host",
    "fence_signal",
    "fence_wait",
    "kernel_dispatch",
    "reset",
)
EXPECTED_E1_ERRORS = ("ERR_MMU_FAULT", "ERR_FENCE_WAIT")
EXPECTED_E4_KERNELS = (
    "vector_add",
    "gemm_proxy",
    "convolution_proxy",
    "image_filter",
    "memory_copy",
)
EXPECTED_E5_CONTROL_FIELDS = (
    "apb_traffic",
    "axi_traffic",
    "command_submission",
    "completion_interrupts",
    "dma_alignment",
    "dma_bounds",
    "fault_interrupts",
    "interrupt_clear",
    "invalid_descriptors",
    "reset_behavior",
    "throughput_tier_link",
)
EXPECTED_E5_NEGATIVE_GROUPS = (
    "invalid_descriptors",
    "dma_bounds_alignment",
    "reset_pending_active",
    "command_submission_error_records",
)
EXPECTED_E8_BINS = (
    "queues",
    "dma_fill",
    "dma_copy",
    "dma_copy_h2d",
    "dma_copy_d2h",
    "fence_signal",
    "fence_wait",
    "reset",
    "completion_interrupt",
    "error_interrupt",
    "mmu_fault",
    "scheduler_fault",
    "abi_symbol_coverage",
    "native_command_categories",
    "pending_count_zero",
)
EXPECTED_E7_MARKERS = (
    "PASS=24 FAIL=0 SKIP=0",
    "OVERALL: PASS",
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


def percent(hit: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((float(hit) / float(total)) * 100.0, 3)


def artifact(path: Path) -> dict[str, Any]:
    exists = path.exists()
    size = path.stat().st_size if exists else None
    return {
        "path": str(path),
        "exists": exists,
        "size_bytes": size,
        "non_empty": bool(exists and size and size > 0),
    }


class CoverageBuilder:
    def __init__(self) -> None:
        self.bins: list[dict[str, Any]] = []

    def add(self, group: str, name: str, hit: bool, evidence: Mapping[str, Any] | None = None) -> None:
        self.bins.append(
            {
                "group": group,
                "name": name,
                "hit": bool(hit),
                "evidence": dict(evidence or {}),
            }
        )

    def extend_bool_map(self, group: str, prefix: str, values: Mapping[str, Any], names: tuple[str, ...]) -> None:
        for name in names:
            self.add(group, f"{prefix}.{name}", values.get(name) is True, {"value": values.get(name)})

    def summarize(self) -> dict[str, Any]:
        total = len(self.bins)
        hit = sum(1 for item in self.bins if item["hit"])
        groups: dict[str, dict[str, Any]] = {}
        for item in self.bins:
            group = item["group"]
            groups.setdefault(group, {"total": 0, "hit": 0, "missed_bins": []})
            groups[group]["total"] += 1
            if item["hit"]:
                groups[group]["hit"] += 1
            else:
                groups[group]["missed_bins"].append(item["name"])
        for group_summary in groups.values():
            group_summary["coverage_percent"] = percent(group_summary["hit"], group_summary["total"])
        return {
            "total_bins": total,
            "hit_bins": hit,
            "coverage_percent": percent(hit, total),
            "missed_bins": [
                f"{item['group']}.{item['name']}" for item in self.bins if not item["hit"]
            ],
            "groups": groups,
        }


def monotonic_non_decreasing(values: list[int]) -> bool:
    return all(left <= right for left, right in zip(values, values[1:]))


def collect_report(artifact_root: Path) -> dict[str, Any]:
    builder = CoverageBuilder()

    verification_dir = artifact_root / "verification"
    demo_outputs = artifact_root / "demo" / "outputs"
    model_outputs = artifact_root / "model" / "outputs"
    rtl_dir = artifact_root / "rtl"
    e8_dir = verification_dir / "verilator_coverage"

    files = {
        "acceptance_matrix": verification_dir / "acceptance_matrix.json",
        "e7_one_key_acceptance_log": verification_dir / "e7_one_key_acceptance.log",
        "test_results_log": verification_dir / "test_results.log",
        "control_plane_demo": rtl_dir / "control_plane_demo.json",
        "control_plane_metrics": rtl_dir / "control_plane_metrics.json",
        "e3_native_runtime_evidence": rtl_dir / "e3_native_runtime_evidence.json",
        "e5_negative_boundary_evidence": rtl_dir / "e5_outputs" / "negative_boundary_evidence.json",
        "demo_summary": demo_outputs / "summary.json",
        "demo_golden_comparison": demo_outputs / "golden_comparison.json",
        "demo_queue_trace": demo_outputs / "queue_trace.json",
        "demo_buffer_binds": demo_outputs / "buffer_binds.json",
        "demo_device_tiers": demo_outputs / "device_tiers.json",
        "compute_model_metrics": demo_outputs / "compute_model" / "metrics.json",
        "model_shader_unit_scaling": model_outputs / "shader_unit_scaling.json",
        "e6_integration_evidence": artifact_root / "integration" / "e6_integration_evidence.json",
        "e8_verilator_coverage_report": e8_dir / "verilator_coverage_report.json",
        "e8_coverage_dat": e8_dir / "coverage.dat",
        "e8_coverage_info": e8_dir / "coverage.info",
        "e8_report_index": e8_dir / "report" / "index.html",
        "e8_report_dut": e8_dir / "report" / "dut.v",
        "e8_run_log": e8_dir / "run.log",
        "phase2_integration_report": verification_dir / "phase2_integration_report.json",
        "phase3_cross_layer_report": verification_dir / "phase3_cross_layer_report.json",
        "kernel_lowering_report": artifact_root / "lowering" / "kernel_lowering_report.json",
        "phase4_lowering_integration_report": verification_dir / "phase4_lowering_integration_report.json",
        "microop_execution_report": artifact_root / "microop_execution" / "microop_execution_report.json",
        "phase5_microop_integration_report": verification_dir / "phase5_microop_integration_report.json",
        "compiler_ir_report": artifact_root / "compiler_ir" / "compiler_ir_report.json",
        "phase6_memory_trace_integration_report": verification_dir / "phase6_memory_trace_integration_report.json",
        "driver_submission_report": artifact_root / "driver_submission" / "driver_submission_report.json",
        "synthesis_readiness_report": artifact_root / "synthesis" / "synthesis_readiness_report.json",
        "yosys_synthesis_probe_report": artifact_root / "synthesis" / "yosys_synthesis_probe_report.json",
        "phase7_coalescing_score_report": verification_dir / "phase7_coalescing_score_report.json",
        "phase7_config_sweep_report": verification_dir / "phase7_config_sweep_report.json",
        "phase7_control_flow_manager_report": verification_dir / "phase7_control_flow_manager_report.json",
        "phase7_memory_streaming_report": verification_dir / "phase7_memory_streaming_report.json",
        "phase7_register_occupancy_report": verification_dir / "phase7_register_occupancy_report.json",
        "phase7_warp_collectives_report": verification_dir / "phase7_warp_collectives_report.json",
        "opencl_conformance_gap_map": verification_dir / "opencl_conformance_gap_map.json",
        "phase8_claim_closure_report": verification_dir / "phase8_claim_closure_report.json",
        "phase8_work_packages": verification_dir / "phase8_work_packages.json",
        "phase8_work_package_artifacts_report": verification_dir / "phase8_work_package_artifacts" / "phase8_work_package_artifacts_report.json",
        "phase9_opencl_conformance_readiness_report": verification_dir / "phase9_opencl_conformance_readiness_report.json",
        "phase9_opencl_subset_conformance_tests": verification_dir / "opencl_subset_conformance_tests.json",
        "phase9_opencl_icd_runtime_contract": verification_dir / "opencl_icd_runtime_contract.json",
        "phase9_opencl_readiness_gates": verification_dir / "phase9_opencl_readiness_gates.json",
        "phase9_memory_conformance_gate": verification_dir / "phase9_memory_conformance_readiness_gate.json",
        "phase9_memory_completion_columns": verification_dir / "phase9_memory_conformance_completion_columns.json",
        "phase9_driver_os_conformance": verification_dir / "phase9_driver_os_conformance_readiness.json",
        "phase9_productization_gates": verification_dir / "phase9_productization_gates.json",
        "phase9_opencl_cts_readiness_matrix": verification_dir / "opencl_cts_readiness_matrix.json",
        "eda_methodology_report": artifact_root.parent / "celviz-methodology" / "methodology_verification_report.json",
        "eda_methodology_bootstrap_matrix": artifact_root.parent / "celviz-methodology" / "bootstrap_acceptance_matrix.json",
    }

    artifacts = {name: artifact(path) for name, path in files.items()}
    for name, info in artifacts.items():
        builder.add("artifacts", name, info["non_empty"], info)

    matrix = load_json(files["acceptance_matrix"])
    control_demo = load_json(files["control_plane_demo"])
    control_metrics = load_json(files["control_plane_metrics"])
    e3 = load_json(files["e3_native_runtime_evidence"])
    e5_negative = load_json(files["e5_negative_boundary_evidence"])
    demo_summary = load_json(files["demo_summary"])
    golden = load_json(files["demo_golden_comparison"])
    queue_trace = load_json(files["demo_queue_trace"])
    buffer_binds = load_json(files["demo_buffer_binds"])
    device_tiers = load_json(files["demo_device_tiers"])
    compute_metrics = load_json(files["compute_model_metrics"])
    shader_scaling = load_json(files["model_shader_unit_scaling"])
    e6 = load_json(files["e6_integration_evidence"])
    e8 = load_json(files["e8_verilator_coverage_report"])
    phase2 = load_json(files["phase2_integration_report"])
    phase3 = load_json(files["phase3_cross_layer_report"])
    lowering = load_json(files["kernel_lowering_report"])
    phase4 = load_json(files["phase4_lowering_integration_report"])
    microop = load_json(files["microop_execution_report"])
    phase5 = load_json(files["phase5_microop_integration_report"])
    compiler_ir = load_json(files["compiler_ir_report"])
    phase6_memory = load_json(files["phase6_memory_trace_integration_report"])
    driver_submission = load_json(files["driver_submission_report"])
    synthesis_readiness = load_json(files["synthesis_readiness_report"])
    yosys_synthesis_probe = load_json(files["yosys_synthesis_probe_report"])
    phase7_coalescing = load_json(files["phase7_coalescing_score_report"])
    phase7_config_sweep = load_json(files["phase7_config_sweep_report"])
    phase7_control_flow_manager = load_json(files["phase7_control_flow_manager_report"])
    phase7_memory_streaming = load_json(files["phase7_memory_streaming_report"])
    phase7_register_occupancy = load_json(files["phase7_register_occupancy_report"])
    phase7_warp_collectives = load_json(files["phase7_warp_collectives_report"])
    opencl_conformance_gap_map = load_json(files["opencl_conformance_gap_map"])
    phase8_claim_closure = load_json(files["phase8_claim_closure_report"])
    phase8_work_packages = load_json(files["phase8_work_packages"])
    phase8_work_package_artifacts = load_json(files["phase8_work_package_artifacts_report"])
    phase9_opencl = load_json(files["phase9_opencl_conformance_readiness_report"])
    phase9_subset_tests = load_json(files["phase9_opencl_subset_conformance_tests"])
    phase9_icd_contract = load_json(files["phase9_opencl_icd_runtime_contract"])
    phase9_opencl_gates = load_json(files["phase9_opencl_readiness_gates"])
    phase9_memory = load_json(files["phase9_memory_conformance_gate"])
    phase9_memory_completion = load_json(files["phase9_memory_completion_columns"])
    phase9_driver_os = load_json(files["phase9_driver_os_conformance"])
    phase9_productization = load_json(files["phase9_productization_gates"])
    phase9_cts_matrix = load_json(files["phase9_opencl_cts_readiness_matrix"])
    eda_methodology = load_json(files["eda_methodology_report"])
    eda_methodology_bootstrap = load_json(files["eda_methodology_bootstrap_matrix"])
    e7_log = files["e7_one_key_acceptance_log"].read_text(encoding="utf-8", errors="replace")
    test_results_log = files["test_results_log"].read_text(encoding="utf-8", errors="replace")

    builder.add(
        "matrix",
        "schema",
        matrix.get("schema") == "celviz.gpgpu.acceptance_matrix.v1",
        {"schema": matrix.get("schema")},
    )
    gates = matrix.get("gates", [])
    builder.add("matrix", "gates_present", isinstance(gates, list) and len(gates) >= 20, {"gate_count": len(gates)})
    for gate in gates:
        gate_id = str(gate.get("id", "<missing>"))
        builder.add("matrix_gates", gate_id, bool(gate_id and gate.get("pass_condition")), {"required": gate.get("required")})

    for marker in EXPECTED_E7_MARKERS:
        builder.add("e7_acceptance_log", marker, marker in e7_log, {"path": str(files["e7_one_key_acceptance_log"])})
    builder.add("verification_harness", "celviz_gpgpu_ip_verification_pass", "celviz_gpgpu_ip_verification: pass" in test_results_log)

    opcodes = {str(command.get("opcode")) for command in control_demo.get("commands", [])}
    command_categories = set(opcodes)
    for command in control_demo.get("commands", []):
        if command.get("transfer") in {"h2d", "d2h"}:
            command_categories.add({"h2d": "host_to_device", "d2h": "device_to_host"}[command["transfer"]])
    for opcode in EXPECTED_E1_OPCODES:
        builder.add("e1_runtime_command_stream", opcode, opcode in command_categories, {"categories": sorted(command_categories)})
    expected_errors = {str(command.get("expect_error")) for command in control_demo.get("commands", []) if command.get("expect_error")}
    for error in EXPECTED_E1_ERRORS:
        builder.add("e1_expected_errors", error, error in expected_errors, {"expected_errors": sorted(expected_errors)})
    queue_state = control_metrics.get("queue_state", {})
    for queue_id, queue in sorted(queue_state.items()):
        submitted = as_int(queue.get("submitted"), -1)
        retired = as_int(queue.get("retired"), -2)
        builder.add(
            "e1_queue_lifecycle",
            f"queue_{queue_id}_closed",
            submitted == retired and submitted >= 0,
            {"submitted": submitted, "retired": retired},
        )

    builder.add("e3_native_runtime", "build_pass", e3.get("build", {}).get("result") == "pass")
    builder.add("e3_native_runtime", "require_runtime_bind_pass", e3.get("require_runtime_bind", {}).get("result") == "pass")
    runtime_summary = e3.get("runtime_summary", {})
    builder.add("e3_native_runtime", "pending_count_zero", as_int(runtime_summary.get("pending_count"), -1) == 0)
    native_acceptance = e3.get("native_runtime_acceptance", {})
    builder.add("e3_native_runtime", "native_acceptance_pass", native_acceptance.get("result") == "pass")
    for name, feature in sorted(native_acceptance.get("feature_categories", {}).items()):
        builder.add("e3_native_runtime_features", name, feature.get("result") == "pass", feature)

    builder.add("e4_demo", "summary_status_pass", demo_summary.get("status") == "pass")
    builder.add("e4_demo", "golden_status_pass", golden.get("status") == "pass")
    for kernel in EXPECTED_E4_KERNELS:
        builder.add("e4_kernel_golden", kernel, golden.get("pass_by_kernel", {}).get(kernel) is True)
        builder.add("e4_compute_model", kernel, compute_metrics.get("pass_by_workload", {}).get(kernel) is True)
    phases_by_kernel: dict[str, set[str]] = {}
    for event in queue_trace.get("events", []):
        kernel = event.get("kernel")
        phase = event.get("phase")
        if kernel and phase:
            phases_by_kernel.setdefault(str(kernel), set()).add(str(phase))
    for kernel in EXPECTED_E4_KERNELS:
        phases = phases_by_kernel.get(kernel, set())
        builder.add(
            "e4_queue_trace",
            f"{kernel}_submit_wait_readback",
            {"submit", "wait", "readback"}.issubset(phases),
            {"phases": sorted(phases)},
        )
    kernel_bindings = buffer_binds.get("kernel_bindings", {})
    for kernel in EXPECTED_E4_KERNELS:
        bindings = kernel_bindings.get(kernel, [])
        accesses = {str(item.get("access")) for item in bindings if isinstance(item, dict)}
        builder.add(
            "e4_buffer_bindings",
            kernel,
            "read" in accesses and "write" in accesses,
            {"binding_count": len(bindings), "accesses": sorted(accesses)},
        )
    tiers = sorted(device_tiers.get("devices", []), key=lambda item: as_int(item.get("shader_units_vec1")))
    builder.add("e4_tier_scaling", "runtime_tier_count", len(tiers) >= 4, {"tier_count": len(tiers)})
    builder.add(
        "e4_tier_scaling",
        "runtime_fp32_monotonic",
        monotonic_non_decreasing([as_int(item.get("fp32_ops_per_cycle")) for item in tiers]),
    )
    builder.add(
        "e4_tier_scaling",
        "runtime_fp16_monotonic",
        monotonic_non_decreasing([as_int(item.get("fp16_ops_per_cycle")) for item in tiers]),
    )
    model_tiers = sorted(shader_scaling.get("tiers", []), key=lambda item: as_int(item.get("shader_units_vec1")))
    builder.add("e4_model_scaling", "model_tier_count", len(model_tiers) >= 4, {"tier_count": len(model_tiers)})
    builder.add(
        "e4_model_scaling",
        "model_fp32_monotonic",
        monotonic_non_decreasing([as_int(item.get("fp32_ops_per_cycle")) for item in model_tiers]),
    )
    builder.add(
        "e4_model_scaling",
        "model_fp16_monotonic",
        monotonic_non_decreasing([as_int(item.get("fp16_ops_per_cycle")) for item in model_tiers]),
    )

    builder.add("e5_control_plane", "metrics_status_pass", control_metrics.get("status") == "pass")
    builder.extend_bool_map(
        "e5_control_plane",
        "coverage",
        control_metrics.get("e5_verification_coverage", {}),
        EXPECTED_E5_CONTROL_FIELDS,
    )
    negative_coverage = e5_negative.get("coverage", {})
    for group in EXPECTED_E5_NEGATIVE_GROUPS:
        builder.add(
            "e5_negative_boundary",
            group,
            negative_coverage.get(group, {}).get("covered") is True,
            negative_coverage.get(group, {}),
        )
    for check in e5_negative.get("acceptance_checks", []):
        builder.add(
            "e5_negative_acceptance_checks",
            str(check.get("name", "<unnamed>")),
            check.get("result") == "pass",
            check,
        )

    builder.add("e6_integration", "status_pass", e6.get("status") == "pass")
    builder.add("e6_integration", "e6_status_pass_proxy", e6.get("e6_status") == "pass_proxy")
    for check in e6.get("checks", []):
        builder.add("e6_integration_checks", str(check.get("name", "<unnamed>")), check.get("pass") is True, check)

    builder.add("e8_verilator_functional", "status_pass", e8.get("status") == "pass")
    builder.add(
        "e8_verilator_functional",
        "functional_coverage_100",
        float(e8.get("functional_coverage_percent", -1.0)) == 100.0,
        {"functional_coverage_percent": e8.get("functional_coverage_percent")},
    )
    feature_hits = {str(item.get("name")): item for item in e8.get("feature_bins", [])}
    for name in EXPECTED_E8_BINS:
        item = feature_hits.get(name, {})
        builder.add("e8_verilator_functional_bins", name, item.get("hit") is True, item)
    builder.add("e8_verilator_functional", "requirements_no_failures", e8.get("requirements", {}).get("failures") == [])
    builder.add("e8_verilator_functional", "artifact_failures_empty", e8.get("artifact_failures") == [])

    builder.add("phase2_integration", "status_pass", phase2.get("status") == "pass")
    for check in phase2.get("checks", []):
        builder.add(
            "phase2_integration_checks",
            str(check.get("name", "<unnamed>")),
            check.get("pass") is True,
            check.get("evidence", {}),
        )

    builder.add("phase3_cross_layer", "status_pass", phase3.get("status") == "pass")
    for check in phase3.get("checks", []):
        builder.add(
            "phase3_cross_layer_checks",
            str(check.get("name", "<unnamed>")),
            check.get("pass") is True,
            check.get("evidence", {}),
        )

    builder.add("kernel_lowering", "status_pass", lowering.get("status") == "pass")
    for check in lowering.get("checks", []):
        builder.add("kernel_lowering_checks", str(check.get("name", "<unnamed>")), check.get("pass") is True, check)
    builder.add("phase4_lowering_integration", "status_pass", phase4.get("status") == "pass")
    for check in phase4.get("checks", []):
        builder.add(
            "phase4_lowering_integration_checks",
            str(check.get("name", "<unnamed>")),
            check.get("pass") is True,
            check.get("evidence", {}),
        )

    builder.add("microop_execution", "status_pass", microop.get("status") == "pass")
    for check in microop.get("checks", []):
        builder.add("microop_execution_checks", str(check.get("name", "<unnamed>")), check.get("pass") is True, check)
    for kernel in microop.get("kernels", []):
        kernel_name = str(kernel.get("kernel", "<unnamed>"))
        builder.add(
            "microop_execution_kernels",
            kernel_name,
            kernel.get("status") == "pass"
            and as_int(kernel.get("uops_executed")) > 0
            and as_int(kernel.get("memory_event_count")) > 0
            and bool(kernel.get("result_sha256")),
            kernel,
        )
    builder.add("phase5_microop_integration", "status_pass", phase5.get("status") == "pass")
    for check in phase5.get("checks", []):
        builder.add(
            "phase5_microop_integration_checks",
            str(check.get("name", "<unnamed>")),
            check.get("pass") is True,
            check.get("evidence", {}),
        )

    phase6_reports = {
        "phase6_compiler_ir": compiler_ir,
        "phase6_memory_trace": phase6_memory,
        "phase6_driver_submission": driver_submission,
        "phase6_synthesis_readiness": synthesis_readiness,
        "phase6_yosys_synthesis_probe": yosys_synthesis_probe,
        "phase7_coalescing_score": phase7_coalescing,
        "phase7_config_sweep": phase7_config_sweep,
        "phase7_control_flow_manager": phase7_control_flow_manager,
        "phase7_memory_streaming": phase7_memory_streaming,
        "phase7_register_occupancy": phase7_register_occupancy,
        "phase7_warp_collectives": phase7_warp_collectives,
        "opencl_conformance_gap_map": opencl_conformance_gap_map,
        "phase8_claim_closure": phase8_claim_closure,
        "phase8_work_package_artifacts": phase8_work_package_artifacts,
        "phase9_opencl_conformance_readiness": phase9_opencl,
        "phase9_opencl_subset_conformance_tests": phase9_subset_tests,
        "phase9_opencl_icd_runtime_contract": phase9_icd_contract,
        "phase9_opencl_readiness_gates": phase9_opencl_gates,
        "phase9_memory_conformance_gate": phase9_memory,
        "phase9_driver_os_conformance": phase9_driver_os,
        "celviz_eda_methodology": eda_methodology,
    }
    for group, report in phase6_reports.items():
        builder.add(group, "status_pass", report.get("status") == "pass")
        for check in report.get("checks", []):
            builder.add(
                f"{group}_checks",
                str(check.get("name", "<unnamed>")),
                check.get("pass") is True,
                check.get("evidence", check),
            )

    builder.add(
        "phase8_work_packages",
        "schema",
        phase8_work_packages.get("schema") == "celviz.gpgpu.phase8_work_packages.v1",
        {"schema": phase8_work_packages.get("schema")},
    )
    builder.add(
        "phase8_work_packages",
        "status_pass",
        phase8_work_packages.get("status") == "pass",
        {"status": phase8_work_packages.get("status")},
    )
    work_packages = phase8_work_packages.get("work_packages", [])
    builder.add(
        "phase8_work_packages",
        "package_count",
        isinstance(work_packages, list) and len(work_packages) >= 6,
        {"package_count": len(work_packages) if isinstance(work_packages, list) else 0},
    )
    artifact_paths = phase8_work_package_artifacts.get("artifact_paths", {})
    builder.add(
        "phase8_work_package_artifacts",
        "artifact_path_count",
        isinstance(artifact_paths, dict) and len(artifact_paths) >= 6,
        {"artifact_count": len(artifact_paths) if isinstance(artifact_paths, dict) else 0},
    )

    builder.add(
        "phase9_opencl_conformance_readiness",
        "schema",
        phase9_opencl.get("schema") == "celviz.gpgpu.phase9_opencl_conformance_readiness.v1",
        {"schema": phase9_opencl.get("schema")},
    )
    phase9_paths = phase9_opencl.get("artifact_paths", {})
    builder.add(
        "phase9_opencl_conformance_readiness",
        "artifact_path_count",
        isinstance(phase9_paths, dict) and len(phase9_paths) == 4,
        {"artifact_count": len(phase9_paths) if isinstance(phase9_paths, dict) else 0},
    )
    builder.add(
        "phase9_opencl_conformance_readiness",
        "requirement_depth",
        as_int(phase9_opencl.get("requirement_count")) >= 12,
        {"requirement_count": phase9_opencl.get("requirement_count")},
    )
    builder.add(
        "phase9_opencl_conformance_readiness",
        "no_official_conformance_overclaim",
        "not official OpenCL conformance" in str(phase9_opencl.get("clean_room_scope", "")),
        {"clean_room_scope": phase9_opencl.get("clean_room_scope")},
    )
    builder.add(
        "phase9_opencl_subset_conformance_tests",
        "positive_depth",
        as_int(phase9_subset_tests.get("positive_count")) >= 9,
        {"positive_count": phase9_subset_tests.get("positive_count")},
    )
    builder.add(
        "phase9_opencl_subset_conformance_tests",
        "negative_depth",
        as_int(phase9_subset_tests.get("negative_count")) >= 12,
        {"negative_count": phase9_subset_tests.get("negative_count")},
    )
    builder.add(
        "phase9_opencl_icd_runtime_contract",
        "api_surface_depth",
        len(phase9_icd_contract.get("host_api_contract", [])) >= 16,
        {"api_count": len(phase9_icd_contract.get("host_api_contract", []))},
    )
    builder.add(
        "phase9_opencl_readiness_gates",
        "gate_depth",
        len(phase9_opencl_gates.get("gates", [])) >= 6,
        {"gate_count": len(phase9_opencl_gates.get("gates", []))},
    )
    builder.add(
        "phase9_opencl_cts_readiness_matrix",
        "matrix_depth",
        len(phase9_cts_matrix.get("requirements", [])) >= 12,
        {"requirement_count": len(phase9_cts_matrix.get("requirements", []))},
    )
    memory_summary = phase9_memory.get("completion_summary", {})
    builder.add(
        "phase9_memory_conformance_gate",
        "surface_depth",
        len(phase9_memory.get("surfaces", [])) >= 11,
        {"surface_count": len(phase9_memory.get("surfaces", []))},
    )
    builder.add(
        "phase9_memory_conformance_gate",
        "official_conformance_claim_false",
        memory_summary.get("official_conformance_claim") is False,
        memory_summary if isinstance(memory_summary, dict) else {},
    )
    builder.add(
        "phase9_memory_completion_columns",
        "row_depth",
        len(phase9_memory_completion.get("rows", [])) >= 11,
        {"row_count": len(phase9_memory_completion.get("rows", []))},
    )
    builder.add(
        "phase9_driver_os_conformance",
        "lane_depth",
        phase9_driver_os.get("summary", {}).get("lane_count") == 5,
        phase9_driver_os.get("summary", {}),
    )
    builder.add(
        "phase9_driver_os_conformance",
        "no_kernel_driver_claim",
        "not a production linux kernel drm driver" in str(phase9_driver_os.get("clean_room_scope", "")).lower(),
        {"clean_room_scope": phase9_driver_os.get("clean_room_scope")},
    )
    builder.add(
        "phase9_productization_gates",
        "status_boundary",
        phase9_productization.get("status") == "blocked_for_productization",
        {"status": phase9_productization.get("status"), "blocked_gates": phase9_productization.get("blocked_gates", [])},
    )
    builder.add(
        "phase9_productization_gates",
        "gate_depth",
        len(phase9_productization.get("gates", [])) >= 6,
        {"gate_count": len(phase9_productization.get("gates", []))},
    )

    builder.add(
        "celviz_eda_methodology_bootstrap",
        "schema",
        eda_methodology_bootstrap.get("schema") == "celviz.gpgpu.acceptance_matrix.bootstrap.v1",
        {"schema": eda_methodology_bootstrap.get("schema")},
    )
    bootstrap_phases = eda_methodology_bootstrap.get("required_phase_sequence", [])
    bootstrap_gates = eda_methodology_bootstrap.get("gates", [])
    builder.add(
        "celviz_eda_methodology_bootstrap",
        "phase_depth",
        isinstance(bootstrap_phases, list) and len(bootstrap_phases) >= 17,
        {"phase_count": len(bootstrap_phases) if isinstance(bootstrap_phases, list) else 0},
    )
    builder.add(
        "celviz_eda_methodology_bootstrap",
        "gate_depth",
        isinstance(bootstrap_gates, list) and len(bootstrap_gates) >= 16,
        {"gate_count": len(bootstrap_gates) if isinstance(bootstrap_gates, list) else 0},
    )
    expected_bootstrap_gates = {
        "boundary_check",
        "source_hook_check",
        "acceptance_matrix_json_check",
        "runtime_abi_check",
        "microop_execution_check",
        "synthesis_readiness_check",
        "functional_coverage_100_check",
        "methodology_bootstrap_check",
    }
    bootstrap_gate_ids = {str(gate.get("id", "")) for gate in bootstrap_gates if isinstance(gate, dict)}
    for gate_id in sorted(expected_bootstrap_gates):
        builder.add(
            "celviz_eda_methodology_bootstrap_gates",
            gate_id,
            gate_id in bootstrap_gate_ids,
            {"bootstrap_gate_ids": sorted(bootstrap_gate_ids)},
        )
    builder.add(
        "celviz_eda_methodology_bootstrap",
        "claim_boundaries",
        bool(eda_methodology_bootstrap.get("claim_boundary_template", {}).get("forbidden_without_evidence")),
        eda_methodology_bootstrap.get("claim_boundary_template", {}),
    )

    summary = builder.summarize()
    structural = {
        "status": "reported_separately_not_part_of_100_percent_functional_gate",
        "source_metrics": e8.get("source_metrics"),
        "line_metrics": e8.get("line_metrics"),
        "toggle_metrics": e8.get("toggle_metrics"),
        "lcov_info": {
            "line": e8.get("lcov_info", {}).get("line"),
            "branch": e8.get("lcov_info", {}).get("branch"),
            "toggle": e8.get("lcov_info", {}).get("toggle"),
        },
    }

    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "status": "pass" if summary["coverage_percent"] == 100.0 else "fail",
        "coverage_kind": "functional_acceptance_verification_bins",
        "coverage_percent": summary["coverage_percent"],
        "hit_bins": summary["hit_bins"],
        "total_bins": summary["total_bins"],
        "missed_bins": summary["missed_bins"],
        "groups": summary["groups"],
        "bins": builder.bins,
        "artifacts": artifacts,
        "rtl_structural_coverage_observation": structural,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a Celviz GPGPU 100% verification coverage report.")
    parser.add_argument(
        "--artifact-root",
        default=Path("artifacts/rank_01_vivante_3d_gpgpu_ip"),
        type=Path,
        help="Rank 1 artifact root",
    )
    parser.add_argument(
        "--output",
        default=Path("artifacts/rank_01_vivante_3d_gpgpu_ip/verification/verification_coverage_100.json"),
        type=Path,
        help="Output JSON report path",
    )
    parser.add_argument("--require-100", action="store_true", help="Exit non-zero unless coverage is exactly 100%%")
    args = parser.parse_args(argv)

    try:
        report = collect_report(args.artifact_root)
    except Exception as exc:  # pragma: no cover - command-line guard
        print(f"celviz_gpgpu_verification_coverage_100: fail collect_error={exc}", file=sys.stderr)
        return 1

    write_json(args.output, report)
    print(
        "celviz_gpgpu_verification_coverage_100: "
        f"{report['status']} coverage={report['coverage_percent']:.3f}% "
        f"hit={report['hit_bins']} total={report['total_bins']} "
        f"output={args.output}"
    )
    if args.require_100 and report["coverage_percent"] != 100.0:
        for missed in report["missed_bins"]:
            print(f"  - missed: {missed}", file=sys.stderr)
        return 1
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
