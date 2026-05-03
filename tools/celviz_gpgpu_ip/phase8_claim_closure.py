#!/usr/bin/env python3
"""Build Phase-8 closure evidence for known non-complete claim boundaries.

Phase 8 intentionally does not turn external certification or proprietary
compatibility gaps into completion claims. It records current evidence,
blockers, and executable next work packages so the project can keep advancing
without diluting the acceptance language.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "celviz.gpgpu.phase8_claim_closure.v1"
DEFAULT_ARTIFACT_ROOT = Path("artifacts/rank_01_vivante_3d_gpgpu_ip")
CLEAN_ROOM_SCOPE = (
    "Phase-8 claim-closure evidence for the Ventus-based Celviz GPGPU IP proxy; "
    "records current readiness, blockers, and next executable work only. It is "
    "not proprietary Vivante compatibility, not official OpenCL conformance, "
    "not a production Linux DRM driver, not RTL structural coverage closure, "
    "not synthesis/STA/power/DFT/physical/silicon signoff, and not silicon "
    "performance evidence."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"missing required Phase-8 input: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON in Phase-8 input {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"Phase-8 input is not a JSON object: {path}")
    return data


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def status_of(data: Mapping[str, Any]) -> str:
    return str(data.get("status", "missing"))


def metric_percent(data: Mapping[str, Any], key: str) -> float | None:
    value = data.get(key)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def pass_check(name: str, passed: bool, evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "pass": bool(passed),
        "evidence": dict(evidence or {}),
    }


def lane(
    lane_id: str,
    title: str,
    current_state: str,
    target_state: str,
    evidence_paths: list[str],
    blockers: list[str],
    next_steps: list[str],
    checks: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "id": lane_id,
        "title": title,
        "current_state": current_state,
        "target_state": target_state,
        "claim_status": "not_completed",
        "evidence_paths": evidence_paths,
        "blockers": blockers,
        "next_executable_steps": next_steps,
        "checks": checks,
        "status": "pass" if all(item.get("pass") is True for item in checks) else "fail",
    }


def build_report(artifact_root: Path) -> dict[str, Any]:
    verification = artifact_root / "verification"
    synthesis = artifact_root / "synthesis"
    ppa = artifact_root / "ppa"
    driver = artifact_root / "driver_submission"
    os_runtime = artifact_root / "os_runtime"

    opencl_gap_path = verification / "opencl_conformance_gap_map.json"
    e8_path = verification / "verilator_coverage" / "verilator_coverage_report.json"
    synthesis_readiness_path = synthesis / "synthesis_readiness_report.json"
    yosys_probe_path = synthesis / "yosys_synthesis_probe_report.json"
    ppa_proxy_path = ppa / "ppa_proxy_report.json"
    driver_submission_path = driver / "driver_submission_report.json"
    linux_runtime_path = os_runtime / "linux_runtime_evidence.json"

    opencl_gap = load_json(opencl_gap_path)
    e8 = load_json(e8_path)
    synthesis_readiness = load_json(synthesis_readiness_path)
    yosys_probe = load_json(yosys_probe_path)
    ppa_proxy = load_json(ppa_proxy_path)
    driver_submission = load_json(driver_submission_path)
    linux_runtime = load_json(linux_runtime_path)
    phase7_paths = {
        "coalescing": verification / "phase7_coalescing_score_report.json",
        "control_flow_manager": verification / "phase7_control_flow_manager_report.json",
        "memory_streaming": verification / "phase7_memory_streaming_report.json",
        "config_sweep": verification / "phase7_config_sweep_report.json",
        "register_occupancy": verification / "phase7_register_occupancy_report.json",
        "warp_collectives": verification / "phase7_warp_collectives_report.json",
    }
    phase7_reports = {name: load_json(path) for name, path in phase7_paths.items()}

    functional_percent = metric_percent(e8, "functional_coverage_percent")
    source_metrics = e8.get("source_metrics", {})
    line_metrics = e8.get("line_metrics", {})
    toggle_metrics = e8.get("toggle_metrics", {})

    lanes = [
        lane(
            "vivante_proprietary_compatibility",
            "Vivante proprietary compatibility",
            "clean-room Ventus/Celviz proxy only",
            "only after licensed collateral, legal approval, and proprietary ABI/firmware/driver evidence",
            [
                str(artifact_root / "verification" / "acceptance_matrix.json"),
                str(opencl_gap_path),
            ],
            [
                "No licensed Vivante command-stream, firmware, SDK, driver, or ISA collateral is present.",
                "Clean-room boundary forbids using proprietary compatibility language as active acceptance evidence.",
            ],
            [
                "Keep public clean-room compatibility adapters separated from proprietary ABI claims.",
                "Add a public command-ABI compatibility matrix only for behaviors reproduced by local evidence.",
                "Require legal/licensed-collateral gate before any proprietary compatibility target is opened.",
            ],
            [
                pass_check("opencl_gap_boundary_present", status_of(opencl_gap) == "pass", {"status": status_of(opencl_gap)}),
                pass_check("claim_status_not_completed", True),
                pass_check("external_blockers_recorded", True),
            ],
        ),
        lane(
            "official_opencl_conformance",
            "Official OpenCL conformance",
            "OpenCL-like subset evidence with four kernels",
            "Khronos CTS or licensed official conformance suite pass with official runtime/compiler stack",
            [str(opencl_gap_path)],
            [
                "Khronos CTS or licensed official conformance suite is not present.",
                "Full OpenCL C/profile/device-info/precision semantics are not implemented.",
                "Official ICD/runtime/compiler certification package is not present.",
            ],
            [
                "Expand the OpenCL C subset by kernel family before attempting CTS scope.",
                "Add conformance-style negative tests for builtins, memory model, atomics, images, and device info.",
                "Create an ICD/runtime ABI shim only after subset semantics are stable.",
            ],
            [
                pass_check("gap_map_status_pass", status_of(opencl_gap) == "pass", {"status": status_of(opencl_gap)}),
                pass_check("current_subset_kernel_count_ge_4", int(opencl_gap.get("current_evidence", {}).get("metrics", {}).get("kernel_count", 0)) >= 4),
                pass_check("official_gap_declared", bool(opencl_gap.get("official_conformance_gap"))),
            ],
        ),
        lane(
            "production_linux_kernel_drm_driver",
            "Production Linux kernel/DRM driver",
            "Linux userspace runtime plus DRM-like submission proxy",
            "kernel driver with reviewed UAPI, ioctl/GEM/syncobj semantics, CI, and upstream-style integration",
            [str(driver_submission_path), str(linux_runtime_path)],
            [
                "No kernel module, ioctl ABI, GEM object ABI, syncobj ABI, or upstream DRM integration is present.",
                "Current evidence models userspace and DRM-like semantics only.",
            ],
            [
                "Draft a minimal DRM-like UAPI contract for queue, BO, fence, and event semantics.",
                "Add ioctl-level negative tests in the proxy before kernel implementation.",
                "Only then split a real kernel-driver branch with KUnit/selftest style gates.",
            ],
            [
                pass_check("driver_submission_status_pass", status_of(driver_submission) == "pass", {"status": status_of(driver_submission)}),
                pass_check("linux_runtime_status_pass", status_of(linux_runtime) == "pass", {"status": status_of(linux_runtime)}),
                pass_check("kernel_driver_blocker_declared", True),
            ],
        ),
        lane(
            "rtl_structural_coverage_100",
            "RTL structural coverage 100%",
            "Verilator functional coverage 100%; structural metrics reported separately",
            "line/toggle/branch/source structural closure reaches 100% on a defined RTL target",
            [str(e8_path)],
            [
                "Functional acceptance coverage is not structural RTL coverage.",
                "LCOV/source/toggle/line metrics are observational and not currently a 100% closure claim.",
            ],
            [
                "Add directed RTL tests for reset, IRQ, AXI/APB counters, scoreboard hazards, LSU paths, and warp scheduler branch flushes.",
                "Add random command-stream and fault-injection runs against structural metrics.",
                "Create a structural coverage waiver file before any 100% structural claim.",
            ],
            [
                pass_check("e8_status_pass", status_of(e8) == "pass", {"status": status_of(e8)}),
                pass_check("functional_coverage_100_recorded", functional_percent == 100.0, {"functional_coverage_percent": functional_percent}),
                pass_check(
                    "structural_metrics_reported_separately",
                    bool(source_metrics or line_metrics or toggle_metrics or e8.get("lcov_info")),
                    {
                        "source_metrics_status": source_metrics.get("status") if isinstance(source_metrics, dict) else None,
                        "line_metrics_status": line_metrics.get("status") if isinstance(line_metrics, dict) else None,
                        "toggle_metrics_status": toggle_metrics.get("status") if isinstance(toggle_metrics, dict) else None,
                    },
                ),
            ],
        ),
        lane(
            "signoff_synthesis_sta_power_dft_physical_silicon",
            "Synthesis/STA/power/DFT/physical/silicon signoff",
            "synthesis readiness, Yosys probe, and PPA proxy evidence only",
            "target-library synthesis, STA, power, DFT, physical implementation, and silicon signoff complete",
            [str(synthesis_readiness_path), str(yosys_probe_path), str(ppa_proxy_path)],
            [
                "No target technology library, constraints, STA, power activity, DFT insertion, floorplan, P&R, or silicon data is present.",
                "Yosys probe records tool behavior/blockers but is not target-library signoff.",
            ],
            [
                "Add a synthesis target definition and constraints stub when a technology/library target exists.",
                "Add STA/power/DFT/physical checklist gates with required input artifacts.",
                "Keep PPA proxy separate from signed-off PPA numbers.",
            ],
            [
                pass_check("synthesis_readiness_status_pass", status_of(synthesis_readiness) == "pass", {"status": status_of(synthesis_readiness)}),
                pass_check("yosys_probe_status_pass", status_of(yosys_probe) == "pass", {"status": status_of(yosys_probe), "classification": yosys_probe.get("classification")}),
                pass_check("ppa_proxy_status_pass", status_of(ppa_proxy) == "pass", {"status": status_of(ppa_proxy)}),
            ],
        ),
        lane(
            "phase7_proxy_not_silicon_performance",
            "Phase7 performance data boundary",
            "deterministic proxy evidence for coalescing, control flow, streaming, config, occupancy, and collectives",
            "post-silicon or cycle-accurate measured performance on a signed-off implementation",
            [str(path) for path in phase7_paths.values()],
            [
                "Phase7 reports are proxy evidence, not measured silicon performance.",
                "No signed-off physical implementation or post-silicon measurement platform exists.",
            ],
            [
                "Keep Phase7 metrics dimensionless/proxy-labeled in all reports.",
                "Add cycle-accurate counters only after RTL execution paths and structural coverage improve.",
                "Bind future performance claims to synthesis/timing or silicon measurement evidence.",
            ],
            [
                pass_check(
                    "all_phase7_reports_pass",
                    all(status_of(report) == "pass" for report in phase7_reports.values()),
                    {name: status_of(report) for name, report in phase7_reports.items()},
                ),
                pass_check("ppa_proxy_status_pass", status_of(ppa_proxy) == "pass", {"status": status_of(ppa_proxy)}),
                pass_check("silicon_performance_not_claimed", True),
            ],
        ),
    ]

    work_packages = [
        {
            "id": "P8-WP1",
            "lane": "official_opencl_conformance",
            "task": "Add conformance-style OpenCL subset negative tests for unsupported builtins, address spaces, and launch geometry.",
            "acceptance": "A JSON report records pass/fail for each negative case and keeps official conformance claim disabled.",
        },
        {
            "id": "P8-WP2",
            "lane": "production_linux_kernel_drm_driver",
            "task": "Draft a minimal DRM-like UAPI contract for BO, queue, fence, event, and error semantics.",
            "acceptance": "The contract maps each UAPI concept to existing userspace proxy evidence and names missing kernel-only behavior.",
        },
        {
            "id": "P8-WP3",
            "lane": "rtl_structural_coverage_100",
            "task": "Add directed Verilator structural tests for reset, IRQ, AXI/APB counters, scoreboard hazards, LSU, and warp branch flushes.",
            "acceptance": "Structural line/toggle/branch metrics are regenerated and compared to the previous report.",
        },
        {
            "id": "P8-WP4",
            "lane": "signoff_synthesis_sta_power_dft_physical_silicon",
            "task": "Create target-library synthesis/STA/power/DFT/physical artifact requirements without claiming signoff.",
            "acceptance": "The readiness report names every required external input before signoff gates can become completion gates.",
        },
        {
            "id": "P8-WP5",
            "lane": "phase7_proxy_not_silicon_performance",
            "task": "Bind every Phase7 proxy metric to its source evidence and forbid silicon-performance wording.",
            "acceptance": "A boundary checker rejects Phase7 silicon-performance overclaim language in active reports.",
        },
        {
            "id": "P8-WP6",
            "lane": "vivante_proprietary_compatibility",
            "task": "Keep a clean-room compatibility boundary checklist before any vendor-specific feature request is accepted.",
            "acceptance": "The checklist requires licensed collateral, legal approval, and separated evidence roots.",
        },
    ]

    checks = [
        pass_check("all_lanes_status_pass", all(item["status"] == "pass" for item in lanes)),
        pass_check("six_known_non_complete_lanes_present", len(lanes) == 6),
        pass_check("work_packages_present", len(work_packages) >= 6),
        pass_check("clean_room_scope_has_all_boundaries", all(token in CLEAN_ROOM_SCOPE for token in ("not proprietary", "not official OpenCL", "not a production Linux", "not RTL structural", "not synthesis"))),
    ]
    status = "pass" if all(item["pass"] for item in checks) else "fail"
    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "status": status,
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "phase": "phase8_claim_closure",
        "lanes": lanes,
        "work_packages": work_packages,
        "checks": checks,
        "summary": {
            "lanes": len(lanes),
            "lanes_passed": sum(1 for item in lanes if item["status"] == "pass"),
            "work_packages": len(work_packages),
            "completion_claim": "not_completed_for_external_or_signoff_items",
            "engineering_progress_claim": "readiness and next executable work packages are now gated",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Phase-8 claim closure evidence.")
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_ARTIFACT_ROOT / "verification")
    args = parser.parse_args(argv)

    report = build_report(args.artifact_root)
    output = args.output_dir / "phase8_claim_closure_report.json"
    write_json(output, report)
    work_packages = args.output_dir / "phase8_work_packages.json"
    write_json(
        work_packages,
        {
            "schema": "celviz.gpgpu.phase8_work_packages.v1",
            "generated_at": report["generated_at"],
            "status": report["status"],
            "work_packages": report["work_packages"],
        },
    )
    print(
        "celviz_gpgpu_phase8_claim_closure: "
        f"{report['status']} lanes={report['summary']['lanes_passed']}/{report['summary']['lanes']} "
        f"work_packages={report['summary']['work_packages']} output={output}"
    )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
