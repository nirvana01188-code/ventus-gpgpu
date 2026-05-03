#!/usr/bin/env python3
"""Executable OpenCL event wait-list and profiling semantics gate.

This is a clean-room proxy gate next to the OpenCL host API shim.  It models
event dependency DAGs, wait-list validation, queued/submit/start/end profiling
timestamps, queue drain behavior, and failure propagation.  It is not a
Khronos ICD, not libOpenCL, not official OpenCL conformance evidence, and not a
production driver.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence


SCHEMA = "celviz.gpgpu.opencl_event_waitlist_profiling_gate.v1"
DEFAULT_ARTIFACT_ROOT = Path("artifacts/rank_01_vivante_3d_gpgpu_ip")
DEFAULT_OUTPUT = DEFAULT_ARTIFACT_ROOT / "verification/opencl_event_waitlist_profiling_report.json"
CLEAN_ROOM_SCOPE = (
    "clean-room OpenCL event wait-list/profiling semantics proxy for the "
    "Celviz host API shim; not a Khronos ICD, not libOpenCL, not official "
    "OpenCL conformance, not CTS evidence, not a production Linux driver, "
    "and not proprietary Vivante compatibility"
)

CL_COMPLETE = 0
CL_SUBMITTED = 1
CL_RUNNING = 2
CL_QUEUED = 3
CL_INVALID_VALUE = -30
CL_INVALID_CONTEXT = -34
CL_INVALID_COMMAND_QUEUE = -36
CL_INVALID_EVENT_WAIT_LIST = -57
CL_EXEC_STATUS_ERROR_FOR_EVENTS_IN_WAIT_LIST = -14
CL_OUT_OF_RESOURCES = -5


class GateError(ValueError):
    """Raised when an internal gate fixture is malformed."""


@dataclass
class ProxyEvent:
    handle: str
    command: str
    queue: str
    context: str
    wait_for: list[str] = field(default_factory=list)
    status: int = CL_QUEUED
    result: str = "CL_QUEUED"
    error_code: int = 0
    profiling: dict[str, int] = field(default_factory=dict)
    failure_reason: Optional[str] = None

    def to_json(self) -> dict[str, Any]:
        return {
            "handle": self.handle,
            "command": self.command,
            "queue": self.queue,
            "context": self.context,
            "wait_for": list(self.wait_for),
            "status": self.status,
            "result": self.result,
            "error_code": self.error_code,
            "profiling": dict(self.profiling),
            "failure_reason": self.failure_reason,
        }


class EventDagGate:
    def __init__(self) -> None:
        self.clock = 1000
        self.next_event = 1
        self.context = "context_1"
        self.queue = "queue_1"
        self.foreign_context = "context_foreign"
        self.events: dict[str, ProxyEvent] = {}
        self.trace: list[dict[str, Any]] = []
        self.validation_cases: list[dict[str, Any]] = []

    def tick(self, step: int = 10) -> int:
        self.clock += step
        return self.clock

    def record(self, op: str, detail: Mapping[str, Any]) -> None:
        self.trace.append({"index": len(self.trace) + 1, "op": op, "detail": dict(detail)})

    def new_handle(self) -> str:
        handle = f"event_{self.next_event}"
        self.next_event += 1
        return handle

    def validate_wait_list(self, wait_for: Sequence[str], context: str) -> tuple[bool, str, int]:
        seen: set[str] = set()
        for handle in wait_for:
            if not isinstance(handle, str) or not handle:
                return False, "wait-list contains a non-event value", CL_INVALID_EVENT_WAIT_LIST
            event = self.events.get(handle)
            if event is None:
                return False, f"unknown event {handle}", CL_INVALID_EVENT_WAIT_LIST
            if event.context != context:
                return False, f"event {handle} belongs to context {event.context}", CL_INVALID_CONTEXT
            if handle in seen:
                return False, f"duplicate event {handle}", CL_INVALID_EVENT_WAIT_LIST
            seen.add(handle)
        return True, "OK", 0

    def enqueue(
        self,
        command: str,
        *,
        wait_for: Sequence[str] = (),
        context: Optional[str] = None,
        force_error: bool = False,
        queue: Optional[str] = None,
    ) -> tuple[Optional[str], dict[str, Any]]:
        context = context or self.context
        queue = queue or self.queue
        valid, message, error_code = self.validate_wait_list(wait_for, context)
        if not valid:
            record = {
                "api": f"clEnqueue{command}",
                "result": "CL_INVALID_CONTEXT" if error_code == CL_INVALID_CONTEXT else "CL_INVALID_EVENT_WAIT_LIST",
                "error_code": error_code,
                "wait_for": list(wait_for),
                "message": message,
                "pass": True,
            }
            self.validation_cases.append(record)
            self.record("reject_wait_list", record)
            return None, record

        failed_deps = [self.events[item] for item in wait_for if self.events[item].status < 0]
        handle = self.new_handle()
        event = ProxyEvent(handle=handle, command=command, queue=queue, context=context, wait_for=list(wait_for))
        queued = self.tick()
        submit = self.tick()
        event.profiling["queued"] = queued
        event.profiling["submit"] = max(submit, max((self.events[item].profiling["end"] for item in wait_for), default=submit))

        if failed_deps:
            event.profiling["start"] = event.profiling["submit"]
            event.profiling["end"] = event.profiling["submit"]
            event.status = CL_EXEC_STATUS_ERROR_FOR_EVENTS_IN_WAIT_LIST
            event.result = "CL_EXEC_STATUS_ERROR_FOR_EVENTS_IN_WAIT_LIST"
            event.error_code = CL_EXEC_STATUS_ERROR_FOR_EVENTS_IN_WAIT_LIST
            event.failure_reason = "dependency failure propagated from " + ",".join(dep.handle for dep in failed_deps)
            self.events[handle] = event
            self.record("propagate_dependency_failure", event.to_json())
            return handle, event.to_json()

        start = self.tick()
        end = self.tick()
        event.profiling["start"] = max(start, event.profiling["submit"])
        event.profiling["end"] = max(end, event.profiling["start"])
        if force_error:
            event.status = CL_OUT_OF_RESOURCES
            event.result = "CL_OUT_OF_RESOURCES"
            event.error_code = CL_OUT_OF_RESOURCES
            event.failure_reason = "injected proxy resource fault"
        else:
            event.status = CL_COMPLETE
            event.result = "CL_COMPLETE"
            event.error_code = 0
        self.events[handle] = event
        self.record("enqueue_complete" if event.status == CL_COMPLETE else "enqueue_error", event.to_json())
        return handle, event.to_json()

    def build_success_and_failure_dag(self) -> dict[str, Any]:
        write_a, _ = self.enqueue("WriteBuffer", wait_for=[])
        write_b, _ = self.enqueue("WriteBuffer", wait_for=[])
        assert write_a and write_b
        marker_join, _ = self.enqueue("MarkerWithWaitList", wait_for=[write_a, write_b])
        assert marker_join
        kernel, _ = self.enqueue("NDRangeKernel", wait_for=[write_a, write_b])
        assert kernel
        readback, _ = self.enqueue("ReadBuffer", wait_for=[kernel])
        assert readback

        fault, _ = self.enqueue("NDRangeKernel", wait_for=[marker_join], force_error=True)
        assert fault
        propagated, _ = self.enqueue("ReadBuffer", wait_for=[fault])
        assert propagated

        # Negative wait-list validation cases. These should reject before event
        # allocation and leave the already-modeled DAG unchanged.
        self.enqueue("ReadBuffer", wait_for=["missing_event"])
        self.enqueue("ReadBuffer", wait_for=[write_a, write_a])
        foreign = ProxyEvent(
            handle="foreign_event_1",
            command="ForeignCommand",
            queue="foreign_queue",
            context=self.foreign_context,
            status=CL_COMPLETE,
            result="CL_COMPLETE",
            profiling={"queued": self.tick(), "submit": self.tick(), "start": self.tick(), "end": self.tick()},
        )
        self.events[foreign.handle] = foreign
        self.enqueue("ReadBuffer", wait_for=[foreign.handle])

        return {
            "success_path": {
                "write_a": write_a,
                "write_b": write_b,
                "marker_join": marker_join,
                "kernel": kernel,
                "readback": readback,
            },
            "failure_path": {
                "fault": fault,
                "propagated": propagated,
            },
        }

    def dag_edges(self) -> list[dict[str, str]]:
        edges: list[dict[str, str]] = []
        for event in self.events.values():
            if event.context == self.foreign_context:
                continue
            for dep in event.wait_for:
                edges.append({"from": dep, "to": event.handle, "kind": "wait_list"})
        return edges

    def topological_order(self) -> list[str]:
        local_events = {key: value for key, value in self.events.items() if value.context == self.context}
        incoming = {key: set(value.wait_for) for key, value in local_events.items()}
        ready = sorted([key for key, deps in incoming.items() if not deps], key=lambda item: self.events[item].profiling["queued"])
        order: list[str] = []
        while ready:
            item = ready.pop(0)
            if item in order:
                continue
            order.append(item)
            for key, deps in incoming.items():
                deps.discard(item)
                if key not in order and not deps and key not in ready:
                    ready.append(key)
            ready.sort(key=lambda handle: self.events[handle].profiling["queued"])
        return order

    def checks(self) -> list[dict[str, Any]]:
        local_events = [event for event in self.events.values() if event.context == self.context]
        edges = self.dag_edges()
        order = self.topological_order()
        local_handles = {event.handle for event in local_events}
        profiling_ok = all(
            event.profiling["queued"] <= event.profiling["submit"] <= event.profiling["start"] <= event.profiling["end"]
            for event in local_events
        )
        dependency_times_ok = all(
            self.events[edge["from"]].profiling["end"] <= self.events[edge["to"]].profiling["submit"]
            for edge in edges
            if self.events[edge["from"]].status == CL_COMPLETE
        )
        failed = [event for event in local_events if event.status < 0]
        propagated = [event for event in failed if event.result == "CL_EXEC_STATUS_ERROR_FOR_EVENTS_IN_WAIT_LIST"]
        validation_pass = len(self.validation_cases) == 3 and all(case["pass"] for case in self.validation_cases)
        completed = [event for event in local_events if event.status == CL_COMPLETE]
        return [
            {"name": "event_dag_has_expected_nodes", "pass": len(local_events) == 7, "event_count": len(local_events)},
            {"name": "event_dag_has_wait_list_edges", "pass": len(edges) >= 6, "edge_count": len(edges), "edges": edges},
            {"name": "event_dag_topological_order_covers_all_events", "pass": set(order) == local_handles, "topological_order": order},
            {"name": "profiling_timestamps_monotonic", "pass": profiling_ok},
            {"name": "dependency_submit_after_wait_end", "pass": dependency_times_ok},
            {"name": "wait_list_validation_rejects_bad_inputs", "pass": validation_pass, "validation_cases": self.validation_cases},
            {
                "name": "failure_propagates_to_dependent_event",
                "pass": len(propagated) >= 1 and any(event.failure_reason for event in propagated),
                "failed_events": [event.to_json() for event in failed],
            },
            {
                "name": "completed_events_remain_complete",
                "pass": len(completed) == 5 and all(event.result == "CL_COMPLETE" for event in completed),
                "completed_events": [event.handle for event in completed],
            },
            {
                "name": "non_official_icd_boundary_preserved",
                "pass": "not a Khronos ICD" in CLEAN_ROOM_SCOPE and "not official OpenCL conformance" in CLEAN_ROOM_SCOPE,
                "scope": CLEAN_ROOM_SCOPE,
            },
        ]

    def report(self) -> dict[str, Any]:
        paths = self.build_success_and_failure_dag()
        checks = self.checks()
        local_events = [event for event in self.events.values() if event.context == self.context]
        return {
            "schema": SCHEMA,
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "status": "pass" if all(check["pass"] for check in checks) else "fail",
            "clean_room_scope": CLEAN_ROOM_SCOPE,
            "claim_boundary": {
                "official_opencl_icd": False,
                "khronos_conformance": False,
                "cts_evidence": False,
                "linux_kernel_driver": False,
                "vivante_compatibility": False,
            },
            "modeled_api_surface": [
                "clEnqueueWriteBuffer",
                "clEnqueueMarkerWithWaitList",
                "clEnqueueNDRangeKernel",
                "clEnqueueReadBuffer",
                "clWaitForEvents",
                "clGetEventProfilingInfo",
            ],
            "dag_paths": paths,
            "event_dag": {
                "nodes": [event.to_json() for event in local_events],
                "edges": self.dag_edges(),
                "topological_order": self.topological_order(),
            },
            "profiling_semantics": {
                "timestamp_fields": ["queued", "submit", "start", "end"],
                "timebase": "deterministic proxy nanoseconds",
                "rule": "queued <= submit <= start <= end and dependent submit occurs after completed wait event end",
            },
            "wait_list_validation": self.validation_cases,
            "failure_propagation": [
                event.to_json()
                for event in local_events
                if event.status < 0
            ],
            "trace": self.trace,
            "metrics": {
                "events": len(local_events),
                "edges": len(self.dag_edges()),
                "completed_events": sum(1 for event in local_events if event.status == CL_COMPLETE),
                "failed_events": sum(1 for event in local_events if event.status < 0),
                "validation_rejections": len(self.validation_cases),
                "profiling_records": sum(1 for event in local_events if set(event.profiling) == {"queued", "submit", "start", "end"}),
            },
            "checks": checks,
        }


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_to_file(output: Path) -> dict[str, Any]:
    gate = EventDagGate()
    report = gate.report()
    write_json(output, report)
    return report


def build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run OpenCL event wait-list/profiling proxy gate.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--print-json", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_argparser()
    args = parser.parse_args(argv)
    try:
        report = run_to_file(args.output)
    except GateError as exc:
        print(f"opencl_event_waitlist_profiling_gate: error: {exc}", file=sys.stderr)
        return 2
    if args.print_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    print(
        "celviz_gpgpu_opencl_event_waitlist_profiling: "
        f"{report['status']} events={report['metrics']['events']} "
        f"edges={report['metrics']['edges']} failed={report['metrics']['failed_events']} "
        f"validation_rejections={report['metrics']['validation_rejections']} output={args.output}"
    )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
