#!/usr/bin/env python3
"""Phase-9 driver/OS queue-fence-event conformance-readiness gate."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "celviz.gpgpu.phase9_driver_os_conformance_readiness.v1"
DEFAULT_ARTIFACT_ROOT = Path("artifacts/rank_01_vivante_3d_gpgpu_ip")
CLEAN_ROOM_SCOPE = (
    "Phase-9 driver/OS queue-fence-event conformance-readiness gate; "
    "DRM-like submission and OpenCL-like queue semantics are clean-room "
    "readiness evidence only. Not a production Linux kernel DRM driver, not a "
    "stable kernel UAPI, not GEM/syncobj ABI compatibility, not official "
    "OpenCL conformance, not proprietary Vivante compatibility, and not "
    "silicon or product signoff."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"missing Phase-9 driver/OS input: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid Phase-9 driver/OS input JSON {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"Phase-9 driver/OS input is not a JSON object: {path}")
    return data


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_doc(path: Path, report: Mapping[str, Any]) -> None:
    lines = [
        "# Phase 9 Driver/OS Conformance Readiness",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
        f"Status: `{report['status']}`",
        "",
        "This is a clean-room productization-readiness gate for DRM-like submission, queue/fence/event semantics, fault/error paths, and the gap from the Linux userspace runtime proxy to OpenCL queue semantics.",
        "",
        "It does not claim a production Linux kernel DRM driver, stable kernel UAPI, GEM/syncobj ABI compatibility, official OpenCL conformance, proprietary Vivante compatibility, or silicon/product signoff.",
        "",
        "## Summary",
        "",
    ]
    summary = report.get("summary", {})
    if isinstance(summary, Mapping):
        for key, value in summary.items():
            lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Lanes", ""])
    lanes = report.get("lanes", [])
    if isinstance(lanes, list):
        for lane in lanes:
            if not isinstance(lane, Mapping):
                continue
            lines.extend(
                [
                    f"### {lane.get('title')}",
                    "",
                    f"- Lane ID: `{lane.get('id')}`",
                    f"- Status: `{lane.get('status')}`",
                    f"- Claim status: `{lane.get('claim_status')}`",
                    "",
                    "Current evidence:",
                ]
            )
            for item in lane.get("current_evidence", []):
                lines.append(f"- `{item}`")
            lines.extend(["", "Productization gap:"])
            for item in lane.get("productization_gap", []):
                lines.append(f"- {item}")
            lines.extend(["", "Executable tests:"])
            for item in lane.get("executable_tests", []):
                lines.append(f"- `{item}`")
            lines.extend(["", "Checks:"])
            for check in lane.get("checks", []):
                if isinstance(check, Mapping):
                    status = "pass" if check.get("pass") is True else "fail"
                    lines.append(f"- `{check.get('name')}`: `{status}`")
            lines.append("")
    lines.extend(
        [
            "## Generated Evidence",
            "",
            "`artifacts/rank_01_vivante_3d_gpgpu_ip/verification/phase9_driver_os_conformance_readiness.json`",
            "",
            "## Focused Command",
            "",
            "```sh",
            "bash scripts/verify_celviz_gpgpu_phase9_driver_os.sh",
            "```",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def status_of(data: Mapping[str, Any]) -> str:
    return str(data.get("status", "missing"))


def check_names(data: Mapping[str, Any]) -> set[str]:
    raw_checks = data.get("checks", [])
    if not isinstance(raw_checks, list):
        return set()
    return {str(check.get("name")) for check in raw_checks if isinstance(check, dict)}


def count_events(events: Any, key: str, expected: bool) -> int:
    if not isinstance(events, list):
        return 0
    return sum(1 for event in events if isinstance(event, dict) and event.get(key) is expected)


def pass_check(name: str, passed: bool, evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {"name": name, "pass": bool(passed), "evidence": dict(evidence or {})}


def lane(
    lane_id: str,
    title: str,
    current_evidence: list[str],
    productization_gap: list[str],
    executable_tests: list[str],
    checks: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "id": lane_id,
        "title": title,
        "status": "pass" if all(check.get("pass") is True for check in checks) else "fail",
        "claim_status": "readiness_proxy_not_productized",
        "current_evidence": current_evidence,
        "productization_gap": productization_gap,
        "executable_tests": executable_tests,
        "checks": checks,
    }


def build_report(artifact_root: Path) -> dict[str, Any]:
    verification = artifact_root / "verification"
    phase8 = verification / "phase8_work_package_artifacts"
    driver_evidence_path = artifact_root / "driver_submission" / "driver_submission_evidence.json"
    driver_report_path = artifact_root / "driver_submission" / "driver_submission_report.json"
    linux_path = artifact_root / "os_runtime" / "linux_runtime_evidence.json"
    opencl_gap_path = verification / "opencl_conformance_gap_map.json"
    drm_contract_path = phase8 / "drm_uapi_contract.json"

    driver = load_json(driver_evidence_path)
    driver_report = load_json(driver_report_path)
    linux = load_json(linux_path)
    opencl_gap = load_json(opencl_gap_path)
    drm_contract = load_json(drm_contract_path)

    driver_metrics = driver.get("metrics", {}) if isinstance(driver.get("metrics"), dict) else {}
    linux_counters = linux.get("counters", {}) if isinstance(linux.get("counters"), dict) else {}
    linux_events = linux.get("events", [])
    driver_events = driver.get("event_lifecycle", [])
    driver_errors = driver.get("error_paths", [])
    driver_fences = driver.get("fence_lifecycle", [])
    driver_queue = driver.get("queue_lifecycle", {}) if isinstance(driver.get("queue_lifecycle"), dict) else {}
    boundary = driver.get("boundary", {}) if isinstance(driver.get("boundary"), dict) else {}
    linux_boundary = linux.get("boundary", {}) if isinstance(linux.get("boundary"), dict) else {}

    required_driver_checks = {
        "clean_room_non_driver_boundary",
        "linux_input_has_queue_fence_event_evidence",
        "kernel_dispatch_set_aligned",
        "queue_pending_zero",
        "all_driver_fences_signaled",
        "completion_events_readable",
        "error_paths_present",
        "linux_input_error_path_observed",
    }
    required_linux_checks = {
        "device_context_open",
        "bo_alloc_map_gpu_va",
        "drm_like_submit_completion",
        "fence_wait_signal",
        "event_poll_readable",
        "completion_error_path",
        "queue_retired_no_pending",
        "clean_room_non_driver_boundary",
    }

    lanes = [
        lane(
            "drm_like_submission",
            "DRM-like Submission",
            [str(driver_evidence_path), str(driver_report_path), str(drm_contract_path)],
            [
                "No Linux kernel module, ioctl number allocation, or stable UAPI is present.",
                "No copy_from_user validation, command parser hardening, scheduler entity, preemption, hang recovery, or security review exists.",
                "Current submit descriptors are clean-room proxy evidence, not kernel ABI compatibility.",
            ],
            [
                "bash scripts/verify_celviz_gpgpu_driver_submission.sh",
                "PYTHONDONTWRITEBYTECODE=1 python3 tools/celviz_gpgpu_ip/verify_linux_runtime_proxy.py --reuse-existing",
            ],
            [
                pass_check("driver_submission_evidence_pass", status_of(driver) == "pass", {"status": status_of(driver)}),
                pass_check("driver_submission_report_pass", status_of(driver_report) == "pass", {"status": status_of(driver_report)}),
                pass_check("driver_checks_present", required_driver_checks.issubset(check_names(driver)), {"missing": sorted(required_driver_checks.difference(check_names(driver)))}),
                pass_check("kernel_dispatch_alignment_pass", bool(driver.get("kernel_dispatch_alignment", {}).get("aligned")), {"dispatches": driver_metrics.get("runtime_kernel_dispatches")}),
                pass_check(
                    "boundary_no_kernel_or_uapi_claim",
                    boundary.get("kernel_driver_claim") is False and boundary.get("ioctl_abi_claim") is False and boundary.get("gem_syncobj_abi_claim") is False,
                    boundary,
                ),
            ],
        ),
        lane(
            "queue_fence_event_lifecycle",
            "Queue/Fence/Event Lifecycle",
            [str(driver_evidence_path), str(linux_path)],
            [
                "No real eventfd/epoll wakeup, syncobj/timeline semaphore, or cross-process sharing ABI is present.",
                "Queue priority and retirement are modeled but not tied to a kernel scheduler entity.",
                "Current evidence exercises one proxy queue; multi-queue and out-of-order semantics remain open.",
            ],
            [
                "bash scripts/verify_celviz_gpgpu_driver_submission.sh",
                "PYTHONDONTWRITEBYTECODE=1 python3 tools/celviz_gpgpu_ip/verify_linux_runtime_proxy.py --reuse-existing",
            ],
            [
                pass_check("queue_no_pending", as_int(driver_queue.get("pending")) == 0, driver_queue),
                pass_check("fences_all_signaled", bool(driver_fences) and all(isinstance(item, dict) and item.get("signaled") is True for item in driver_fences), {"fence_count": len(driver_fences) if isinstance(driver_fences, list) else 0}),
                pass_check("completion_events_readable", count_events(driver_events, "readable", True) >= as_int(driver_metrics.get("completion_events")), {"readable_events": count_events(driver_events, "readable", True)}),
                pass_check("linux_events_polled", as_int(linux_counters.get("events_polled")) >= 1 and count_events(linux_events, "readable", True) >= 1, {"events_polled": linux_counters.get("events_polled")}),
                pass_check("linux_checks_present", required_linux_checks.issubset(check_names(linux)), {"missing": sorted(required_linux_checks.difference(check_names(linux)))}),
            ],
        ),
        lane(
            "fault_error_paths",
            "Fault/Error Paths",
            [str(driver_evidence_path), str(linux_path), str(drm_contract_path)],
            [
                "No real GPU MMU fault interrupt, guilty-context accounting, reset recovery, or hangcheck is present.",
                "No kernel command parser rejects user pointers or malformed submit packets.",
                "Current errno mapping is readiness vocabulary, not a frozen UAPI.",
            ],
            [
                "bash scripts/verify_celviz_gpgpu_driver_submission.sh",
                "PYTHONDONTWRITEBYTECODE=1 python3 tools/celviz_gpgpu_ip/verify_linux_runtime_proxy.py --reuse-existing",
            ],
            [
                pass_check("driver_error_paths_present", isinstance(driver_errors, list) and len(driver_errors) >= 3, {"error_path_count": len(driver_errors) if isinstance(driver_errors, list) else 0}),
                pass_check("linux_error_events_present", count_events(linux_events, "error", True) >= 1 and as_int(linux_counters.get("submit_errors")) >= 1, {"error_events": count_events(linux_events, "error", True), "submit_errors": linux_counters.get("submit_errors")}),
                pass_check("invalid_queue_and_eacces_observed", "EINVAL" in json.dumps(driver_errors) and "EACCES" in json.dumps(driver_errors), {"error_path_count": len(driver_errors) if isinstance(driver_errors, list) else 0}),
                pass_check("drm_contract_pass", status_of(drm_contract) == "pass", {"status": status_of(drm_contract)}),
            ],
        ),
        lane(
            "opencl_queue_semantics_gap",
            "Linux Runtime To OpenCL Queue Semantics Gap",
            [str(linux_path), str(opencl_gap_path), str(drm_contract_path)],
            [
                "OpenCL in-order queue behavior is modeled, but out-of-order queues, event wait lists, callbacks, profiling timestamps, user events, command barriers, and multi-queue synchronization are not complete.",
                "OpenCL memory object lifetime, map/unmap blocking modes, SVM, images, samplers, atomics, and local-memory semantics remain outside current readiness evidence.",
                "No official OpenCL ICD/runtime stack or Khronos CTS package is present.",
            ],
            [
                "bash scripts/verify_celviz_gpgpu_opencl_conformance_gap_map.sh",
                "PYTHONDONTWRITEBYTECODE=1 python3 tools/celviz_gpgpu_ip/verify_linux_runtime_proxy.py --reuse-existing",
            ],
            [
                pass_check("opencl_gap_map_pass", status_of(opencl_gap) == "pass", {"status": status_of(opencl_gap)}),
                pass_check("official_conformance_gap_declared", bool(opencl_gap.get("official_conformance_gap")), {"gap_count": len(opencl_gap.get("official_conformance_gap", [])) if isinstance(opencl_gap.get("official_conformance_gap"), list) else 0}),
                pass_check("current_kernel_subset_ge_4", as_int(opencl_gap.get("current_evidence", {}).get("metrics", {}).get("kernel_count")) >= 4, {"kernel_count": opencl_gap.get("current_evidence", {}).get("metrics", {}).get("kernel_count")}),
                pass_check("linux_boundary_no_driver_claim", linux_boundary.get("kernel_driver_claim") is False, linux_boundary),
            ],
        ),
        lane(
            "executable_test_matrix",
            "Executable Test Matrix",
            [str(driver_evidence_path), str(linux_path), str(opencl_gap_path), str(drm_contract_path)],
            [
                "Focused readiness gates are not full product CI.",
                "Kernel selftests, KUnit, CTS, fuzzing, long-run stress, and security review are not present.",
            ],
            [
                "bash scripts/verify_celviz_gpgpu_driver_submission.sh",
                "PYTHONDONTWRITEBYTECODE=1 python3 tools/celviz_gpgpu_ip/verify_linux_runtime_proxy.py --reuse-existing",
                "bash scripts/verify_celviz_gpgpu_opencl_conformance_gap_map.sh",
                "bash scripts/verify_celviz_gpgpu_phase8_work_packages.sh",
                "bash scripts/verify_celviz_gpgpu_phase9_driver_os.sh",
            ],
            [
                pass_check("driver_input_pass", status_of(driver) == "pass"),
                pass_check("linux_input_pass", status_of(linux) == "pass"),
                pass_check("opencl_gap_input_pass", status_of(opencl_gap) == "pass"),
                pass_check("drm_contract_input_pass", status_of(drm_contract) == "pass"),
            ],
        ),
    ]

    checks = [
        pass_check("all_lanes_pass", all(item["status"] == "pass" for item in lanes), {"lane_status": {item["id"]: item["status"] for item in lanes}}),
        pass_check("clean_room_non_driver_scope", "not a production linux kernel drm driver" in CLEAN_ROOM_SCOPE.lower()),
        pass_check("drm_like_submission_covered", any(item["id"] == "drm_like_submission" and item["status"] == "pass" for item in lanes)),
        pass_check("queue_fence_event_covered", any(item["id"] == "queue_fence_event_lifecycle" and item["status"] == "pass" for item in lanes)),
        pass_check("fault_error_paths_covered", any(item["id"] == "fault_error_paths" and item["status"] == "pass" for item in lanes)),
        pass_check("opencl_queue_semantics_gap_recorded", any(item["id"] == "opencl_queue_semantics_gap" and item["status"] == "pass" for item in lanes)),
        pass_check("executable_tests_listed", any(item["id"] == "executable_test_matrix" and len(item["executable_tests"]) >= 5 for item in lanes)),
    ]

    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "status": "pass" if all(check["pass"] for check in checks) else "fail",
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "claim_boundary": {
            "current_claim": "driver/OS queue/fence/event conformance-readiness proxy evidence",
            "not_claimed": [
                "production Linux kernel DRM driver",
                "stable kernel UAPI",
                "GEM/syncobj ABI compatibility",
                "official OpenCL conformance",
                "proprietary Vivante compatibility",
                "silicon or product signoff",
            ],
        },
        "inputs": {
            "driver_submission_evidence": str(driver_evidence_path),
            "driver_submission_report": str(driver_report_path),
            "linux_runtime_evidence": str(linux_path),
            "opencl_conformance_gap_map": str(opencl_gap_path),
            "phase8_drm_uapi_contract": str(drm_contract_path),
        },
        "lanes": lanes,
        "checks": checks,
        "summary": {
            "lane_count": len(lanes),
            "passing_lanes": sum(1 for item in lanes if item["status"] == "pass"),
            "driver_runtime_kernel_dispatches": driver_metrics.get("runtime_kernel_dispatches"),
            "driver_completion_events": driver_metrics.get("completion_events"),
            "driver_error_paths": driver_metrics.get("error_paths"),
            "linux_submits": linux_counters.get("submits"),
            "linux_submit_errors": linux_counters.get("submit_errors"),
            "linux_events_polled": linux_counters.get("events_polled"),
            "opencl_current_kernel_count": opencl_gap.get("current_evidence", {}).get("metrics", {}).get("kernel_count"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Phase-9 driver/OS conformance-readiness evidence.")
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_ARTIFACT_ROOT / "verification" / "phase9_driver_os_conformance_readiness.json",
    )
    parser.add_argument(
        "--doc",
        type=Path,
        default=Path("docs/celviz-gpgpu-ip/PHASE9_DRIVER_OS_CONFORMANCE_READINESS.md"),
    )
    args = parser.parse_args()
    report = build_report(args.artifact_root)
    write_json(args.output, report)
    write_doc(args.doc, report)
    passed = sum(1 for check in report["checks"] if check["pass"])
    total = len(report["checks"])
    print(f"celviz_gpgpu_phase9_driver_os: {report['status']} checks={passed}/{total} output={args.output} doc={args.doc}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
