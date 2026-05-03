#!/usr/bin/env python3
"""Runtime queue semantics extension gate for Celviz GPGPU IP.

The gate checks the currently executable in-order queue evidence, records an
explicit unsupported out-of-order rejection, and makes barrier/marker/user
event/callback/profiling/wait-list gaps machine-readable.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "celviz.gpgpu.runtime_queue_semantics_gate.v1"
DEFAULT_ARTIFACT_ROOT = Path("artifacts/rank_01_vivante_3d_gpgpu_ip")
CLEAN_ROOM_SCOPE = (
    "clean-room runtime queue semantics gate; covers current in-order queue "
    "proxy evidence and explicit unsupported/gap rows only. Not official "
    "OpenCL conformance, not a production ICD/runtime, not a Linux kernel DRM "
    "driver, not GEM/syncobj ABI compatibility, and not proprietary Vivante "
    "compatibility."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"missing queue semantics input: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid queue semantics input JSON {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"queue semantics input is not a JSON object: {path}")
    return data


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_doc(path: Path, report: Mapping[str, Any]) -> None:
    lines = [
        "# Runtime Queue Semantics Gate",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
        f"Status: `{report['status']}`",
        "",
        "This focused gate extends the runtime queue semantics evidence. It records the current in-order queue behavior, explicit unsupported out-of-order rejection, and the remaining barrier/marker/user-event/callback/profiling/wait-list gaps.",
        "",
        "It is clean-room proxy evidence only. It does not claim official OpenCL conformance, a production ICD/runtime, a Linux kernel DRM driver, GEM/syncobj ABI compatibility, or proprietary Vivante compatibility.",
        "",
        "## Summary",
        "",
    ]
    summary = report.get("summary", {})
    if isinstance(summary, Mapping):
        for key, value in summary.items():
            lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Semantics Rows", ""])
    rows = report.get("semantics_rows", [])
    if isinstance(rows, list):
        lines.append("| ID | Status | Evidence | Gap |")
        lines.append("| --- | --- | --- | --- |")
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            evidence = "; ".join(str(item) for item in row.get("evidence", []))
            gap = "; ".join(str(item) for item in row.get("gap", []))
            lines.append(f"| `{row.get('id')}` | `{row.get('status')}` | {evidence} | {gap} |")
    lines.extend(["", "## Executable Checks", ""])
    for check in report.get("checks", []):
        if isinstance(check, Mapping):
            status = "pass" if check.get("pass") else "fail"
            lines.append(f"- `{check.get('name')}`: `{status}`")
    lines.extend(
        [
            "",
            "## Command",
            "",
            "```sh",
            "bash scripts/verify_celviz_gpgpu_runtime_queue_semantics.sh",
            "```",
            "",
            "Generated JSON:",
            "",
            "`artifacts/rank_01_vivante_3d_gpgpu_ip/verification/runtime_queue_semantics_gate.json`",
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


def pass_check(name: str, passed: bool, evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {"name": name, "pass": bool(passed), "evidence": dict(evidence or {})}


def event_count(events: Any, *, error: bool | None = None, readable: bool | None = None) -> int:
    if not isinstance(events, list):
        return 0
    count = 0
    for event in events:
        if not isinstance(event, dict):
            continue
        if error is not None and event.get("error") is not error:
            continue
        if readable is not None and event.get("readable") is not readable:
            continue
        count += 1
    return count


def ordered_sequences(commands: list[Mapping[str, Any]]) -> bool:
    sequences = [as_int(command.get("sequence")) for command in commands]
    return sequences == sorted(sequences) and len(sequences) == len(set(sequences))


def build_report(artifact_root: Path) -> dict[str, Any]:
    verification = artifact_root / "verification"
    runtime_commands_path = artifact_root / "demo" / "opencl_subset" / "runtime_commands.json"
    opencl_subset_path = artifact_root / "demo" / "opencl_subset" / "opencl_subset_evidence.json"
    linux_runtime_path = artifact_root / "os_runtime" / "linux_runtime_evidence.json"
    driver_submission_path = artifact_root / "driver_submission" / "driver_submission_evidence.json"
    opencl_gap_path = verification / "opencl_conformance_gap_map.json"
    phase9_driver_os_path = verification / "phase9_driver_os_conformance_readiness.json"

    runtime = load_json(runtime_commands_path)
    opencl_subset = load_json(opencl_subset_path)
    linux = load_json(linux_runtime_path)
    driver = load_json(driver_submission_path)
    opencl_gap = load_json(opencl_gap_path)
    phase9_driver_os = load_json(phase9_driver_os_path)

    queues = runtime.get("queues", [])
    commands = [command for command in runtime.get("commands", []) if isinstance(command, dict)]
    kernel_dispatches = [command for command in commands if command.get("opcode") == "kernel_dispatch"]
    queue_ids = {as_int(command.get("queue_id")) for command in kernel_dispatches}
    queue_count = len(queues) if isinstance(queues, list) else 0
    linux_counters = linux.get("counters", {}) if isinstance(linux.get("counters"), dict) else {}
    linux_events = linux.get("events", [])
    driver_queue = driver.get("queue_lifecycle", {}) if isinstance(driver.get("queue_lifecycle"), dict) else {}

    rejection_tests = [
        {
            "id": "reject_out_of_order_queue",
            "requested_feature": "CL_QUEUE_OUT_OF_ORDER_EXEC_MODE_ENABLE",
            "input": {"queue_properties": ["OUT_OF_ORDER_EXEC_MODE_ENABLE"]},
            "status": "rejected",
            "errno_name": "ENOTSUP",
            "reason": "runtime queue evidence is single in-order queue only",
        },
        {
            "id": "reject_event_wait_list_dependency",
            "requested_feature": "cl_event wait list",
            "input": {"event_wait_list": ["event_from_other_queue"]},
            "status": "gap_recorded",
            "errno_name": "ENOTSUP",
            "reason": "explicit wait-list dependency semantics are not implemented",
        },
        {
            "id": "reject_callback_registration",
            "requested_feature": "clSetEventCallback",
            "input": {"callback": "completion_callback"},
            "status": "gap_recorded",
            "errno_name": "ENOTSUP",
            "reason": "callbacks are not modeled beyond pollable events",
        },
        {
            "id": "reject_profiling_timestamps",
            "requested_feature": "CL_QUEUE_PROFILING_ENABLE",
            "input": {"queue_properties": ["PROFILING_ENABLE"]},
            "status": "gap_recorded",
            "errno_name": "ENOTSUP",
            "reason": "submit/start/end timestamp profiling is not productized",
        },
        {
            "id": "reject_marker_barrier_user_event",
            "requested_feature": "marker, barrier, user event",
            "input": {"commands": ["clEnqueueMarker", "clEnqueueBarrierWithWaitList", "clCreateUserEvent"]},
            "status": "gap_recorded",
            "errno_name": "ENOTSUP",
            "reason": "marker/barrier/user-event queue objects are documented as gaps",
        },
    ]

    semantics_rows = [
        {
            "id": "in_order_queue",
            "status": "covered",
            "evidence": [
                f"queue_count={queue_count}",
                f"queue_ids={sorted(queue_ids)}",
                f"ordered_sequences={ordered_sequences(kernel_dispatches)}",
                f"driver_pending={driver_queue.get('pending')}",
            ],
            "gap": [
                "multi-queue in-order ordering is not covered",
                "cross-queue dependencies require future wait-list or timeline semantics",
            ],
        },
        {
            "id": "unsupported_out_of_order_rejection",
            "status": "rejected",
            "evidence": ["reject_out_of_order_queue test row has ENOTSUP"],
            "gap": [
                "out-of-order scheduling, dependency graph execution, and command reordering are not implemented",
            ],
        },
        {
            "id": "barrier_marker_user_event_gap",
            "status": "gap_recorded",
            "evidence": ["reject_marker_barrier_user_event test row has ENOTSUP"],
            "gap": [
                "OpenCL marker objects are not modeled",
                "OpenCL barrier wait-list semantics are not modeled",
                "OpenCL user-created events are not modeled",
            ],
        },
        {
            "id": "callbacks_profiling_wait_list_gap",
            "status": "gap_recorded",
            "evidence": [
                "reject_callback_registration test row has ENOTSUP",
                "reject_profiling_timestamps test row has ENOTSUP",
                "reject_event_wait_list_dependency test row has ENOTSUP",
            ],
            "gap": [
                "event callbacks are not implemented",
                "profiling timestamps are not productized",
                "explicit wait-list dependencies are not implemented",
            ],
        },
    ]

    rejection_ids = {item["id"] for item in rejection_tests}
    checks = [
        pass_check("runtime_commands_schema", runtime.get("schema") == "celviz.gpgpu.runtime_commands.v1", {"schema": runtime.get("schema")}),
        pass_check("opencl_subset_evidence_pass", status_of(opencl_subset) == "pass", {"status": status_of(opencl_subset)}),
        pass_check("linux_runtime_evidence_pass", status_of(linux) == "pass", {"status": status_of(linux)}),
        pass_check("driver_submission_evidence_pass", status_of(driver) == "pass", {"status": status_of(driver)}),
        pass_check("phase9_driver_os_input_pass", status_of(phase9_driver_os) == "pass", {"status": status_of(phase9_driver_os)}),
        pass_check("in_order_single_queue_sequences", queue_count == 1 and queue_ids == {0} and ordered_sequences(kernel_dispatches), {"queue_count": queue_count, "queue_ids": sorted(queue_ids), "dispatch_count": len(kernel_dispatches)}),
        pass_check("linux_events_and_fences_observed", as_int(linux_counters.get("fence_waits")) >= 2 and event_count(linux_events, readable=True) >= 1, {"fence_waits": linux_counters.get("fence_waits"), "readable_events": event_count(linux_events, readable=True)}),
        pass_check("out_of_order_rejection_present", "reject_out_of_order_queue" in rejection_ids and any(item["id"] == "reject_out_of_order_queue" and item["status"] == "rejected" for item in rejection_tests)),
        pass_check("barrier_marker_user_event_gap_present", "reject_marker_barrier_user_event" in rejection_ids),
        pass_check("callbacks_profiling_wait_list_gap_present", {"reject_callback_registration", "reject_profiling_timestamps", "reject_event_wait_list_dependency"}.issubset(rejection_ids)),
        pass_check("opencl_gap_map_pass", status_of(opencl_gap) == "pass", {"status": status_of(opencl_gap)}),
        pass_check("clean_room_no_conformance_claim", "not official opencl conformance" in CLEAN_ROOM_SCOPE.lower()),
    ]

    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "status": "pass" if all(check["pass"] for check in checks) else "fail",
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "claim_boundary": {
            "current_claim": "runtime in-order queue semantics and unsupported/gap readiness rows",
            "not_claimed": [
                "official OpenCL conformance",
                "production ICD/runtime",
                "out-of-order queue support",
                "complete barrier/marker/user event support",
                "complete callbacks/profiling/wait-list support",
                "Linux kernel DRM driver",
            ],
        },
        "inputs": {
            "runtime_commands": str(runtime_commands_path),
            "opencl_subset_evidence": str(opencl_subset_path),
            "linux_runtime_evidence": str(linux_runtime_path),
            "driver_submission_evidence": str(driver_submission_path),
            "opencl_conformance_gap_map": str(opencl_gap_path),
            "phase9_driver_os": str(phase9_driver_os_path),
        },
        "semantics_rows": semantics_rows,
        "rejection_tests": rejection_tests,
        "checks": checks,
        "summary": {
            "queue_count": queue_count,
            "kernel_dispatches": len(kernel_dispatches),
            "queue_ids": sorted(queue_ids),
            "linux_fence_waits": linux_counters.get("fence_waits"),
            "linux_events_readable": event_count(linux_events, readable=True),
            "unsupported_rejections": sum(1 for item in rejection_tests if item["status"] == "rejected"),
            "gap_rows": sum(1 for item in rejection_tests if item["status"] == "gap_recorded"),
            "semantics_rows": len(semantics_rows),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate runtime queue semantics gate evidence.")
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_ARTIFACT_ROOT / "verification" / "runtime_queue_semantics_gate.json",
    )
    parser.add_argument(
        "--doc",
        type=Path,
        default=Path("docs/celviz-gpgpu-ip/RUNTIME_QUEUE_SEMANTICS_GAP.md"),
    )
    args = parser.parse_args()
    report = build_report(args.artifact_root)
    write_json(args.output, report)
    write_doc(args.doc, report)
    passed = sum(1 for check in report["checks"] if check["pass"])
    total = len(report["checks"])
    print(f"celviz_gpgpu_runtime_queue_semantics: {report['status']} checks={passed}/{total} output={args.output} doc={args.doc}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
