#!/usr/bin/env python3
"""Phase 9 memory-object flags/map/unmap/sub-buffer readiness gate.

This clean-room tool models a narrow OpenCL-like memory-object contract for
productization readiness evidence. It covers CL_MEM_READ_WRITE, READ_ONLY,
WRITE_ONLY, COPY_HOST_PTR, USE_HOST_PTR, map/unmap, sub-buffer creation, and
bounds/error negative cases. It is not an official OpenCL conformance test,
Khronos CTS result, production ICD, or driver ABI.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA = "celviz.gpgpu.phase9_memory_object_flags_gate.v1"
COMPLETION_SCHEMA = "celviz.gpgpu.phase9_memory_object_completion_columns.v1"
DEFAULT_ARTIFACT_ROOT = Path("artifacts/rank_01_vivante_3d_gpgpu_ip")
DEFAULT_REPORT = DEFAULT_ARTIFACT_ROOT / "verification/phase9_memory_object_flags_map_gate.json"
DEFAULT_COMPLETION = DEFAULT_ARTIFACT_ROOT / "verification/phase9_memory_object_flags_completion_columns.json"
DEFAULT_DOC = Path("docs/celviz-gpgpu-ip/PHASE9_MEMORY_OBJECT_FLAGS_GATES.md")
DEFAULT_LOG = DEFAULT_ARTIFACT_ROOT / "verification/phase9_memory_object_flags_gate.log"
CLEAN_ROOM_SCOPE = (
    "Phase 9 clean-room memory-object flags/map/unmap/sub-buffer readiness gate; "
    "not official OpenCL conformance, not Khronos CTS, not a production ICD, "
    "not a stable UAPI, not proprietary Vivante compatibility, and not driver or silicon signoff"
)
FLAGS = (
    "CL_MEM_READ_WRITE",
    "CL_MEM_READ_ONLY",
    "CL_MEM_WRITE_ONLY",
    "CL_MEM_COPY_HOST_PTR",
    "CL_MEM_USE_HOST_PTR",
)
ACCESS_OPS = ("kernel_read", "kernel_write", "host_map_read", "host_map_write")


class MemoryObjectError(ValueError):
    """Expected error for invalid memory-object operations."""


@dataclass
class MemoryObject:
    object_id: str
    size: int
    flags: set[str]
    storage: bytearray
    host_alias: bytearray | None = None
    parent: str | None = None
    origin: int = 0
    maps: dict[str, tuple[int, int, str]] = field(default_factory=dict)

    def check_bounds(self, offset: int, size: int) -> None:
        if offset < 0 or size <= 0 or offset + size > self.size:
            raise MemoryObjectError(f"bounds violation object={self.object_id} offset={offset} size={size}")

    @property
    def device_can_read(self) -> bool:
        return "CL_MEM_WRITE_ONLY" not in self.flags

    @property
    def device_can_write(self) -> bool:
        return "CL_MEM_READ_ONLY" not in self.flags


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def deterministic_host(size: int, salt: int) -> bytearray:
    return bytearray(((index * 31 + salt * 17 + 9) & 0xFF) for index in range(size))


def event(events: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
    record = {"event_id": len(events), "schema": "celviz.gpgpu.memory_object_event.v1"}
    record.update(kwargs)
    events.append(record)
    return record


def expect_error(events: list[dict[str, Any]], *, name: str, expected: str, action: Any, **base: Any) -> dict[str, Any]:
    try:
        action()
    except MemoryObjectError as exc:
        detail = str(exc)
        passed = expected in detail
        return event(events, scenario=name, status="expected_error", expected_error=expected, detail=detail, passed=passed, **base)
    return event(events, scenario=name, status="unexpected_ok", expected_error=expected, detail="operation unexpectedly passed", passed=False, **base)


class MemoryObjectModel:
    def __init__(self) -> None:
        self.objects: dict[str, MemoryObject] = {}
        self.events: list[dict[str, Any]] = []
        self.next_map_id = 0

    def create_buffer(self, object_id: str, size: int, flags: Sequence[str], host_ptr: bytearray | None = None) -> MemoryObject:
        flag_set = set(flags)
        access_flags = flag_set.intersection({"CL_MEM_READ_WRITE", "CL_MEM_READ_ONLY", "CL_MEM_WRITE_ONLY"})
        if len(access_flags) != 1:
            raise MemoryObjectError("exactly one access flag is required")
        if "CL_MEM_COPY_HOST_PTR" in flag_set and "CL_MEM_USE_HOST_PTR" in flag_set:
            raise MemoryObjectError("COPY_HOST_PTR and USE_HOST_PTR are mutually exclusive in this proxy gate")
        if ("CL_MEM_COPY_HOST_PTR" in flag_set or "CL_MEM_USE_HOST_PTR" in flag_set) and host_ptr is None:
            raise MemoryObjectError("host pointer flag requires host_ptr")
        if host_ptr is not None and len(host_ptr) < size:
            raise MemoryObjectError("host_ptr bounds violation")
        if "CL_MEM_USE_HOST_PTR" in flag_set:
            storage = host_ptr if host_ptr is not None else bytearray(size)
            alias = host_ptr
            host_semantics = "host_alias"
        elif "CL_MEM_COPY_HOST_PTR" in flag_set:
            storage = bytearray(host_ptr[:size]) if host_ptr is not None else bytearray(size)
            alias = None
            host_semantics = "host_copy_snapshot"
        else:
            storage = bytearray(size)
            alias = None
            host_semantics = "device_allocation"
        obj = MemoryObject(object_id=object_id, size=size, flags=flag_set, storage=storage, host_alias=alias)
        self.objects[object_id] = obj
        event(
            self.events,
            scenario="create_buffer",
            operation="create_buffer",
            object_id=object_id,
            flags=sorted(flag_set),
            size=size,
            host_semantics=host_semantics,
            status="ok",
            storage_sha256=sha256_bytes(bytes(storage)),
        )
        return obj

    def kernel_read(self, object_id: str, offset: int, size: int) -> bytes:
        obj = self.objects[object_id]
        obj.check_bounds(offset, size)
        if not obj.device_can_read:
            raise MemoryObjectError("device read violates CL_MEM_WRITE_ONLY")
        payload = bytes(obj.storage[offset : offset + size])
        event(self.events, scenario="kernel_read", operation="kernel_read", object_id=object_id, offset=offset, size=size, status="ok", payload_sha256=sha256_bytes(payload))
        return payload

    def kernel_write(self, object_id: str, offset: int, payload: bytes) -> None:
        obj = self.objects[object_id]
        obj.check_bounds(offset, len(payload))
        if not obj.device_can_write:
            raise MemoryObjectError("device write violates CL_MEM_READ_ONLY")
        obj.storage[offset : offset + len(payload)] = payload
        event(self.events, scenario="kernel_write", operation="kernel_write", object_id=object_id, offset=offset, size=len(payload), status="ok", payload_sha256=sha256_bytes(payload))

    def map_buffer(self, object_id: str, offset: int, size: int, access: str) -> str:
        obj = self.objects[object_id]
        obj.check_bounds(offset, size)
        if access not in {"read", "write", "read_write"}:
            raise MemoryObjectError("unsupported map access")
        for map_offset, map_size, _access in obj.maps.values():
            if max(offset, map_offset) < min(offset + size, map_offset + map_size):
                raise MemoryObjectError("overlapping map range")
        map_id = f"map{self.next_map_id}"
        self.next_map_id += 1
        obj.maps[map_id] = (offset, size, access)
        event(self.events, scenario="map_buffer", operation="map", object_id=object_id, map_id=map_id, offset=offset, size=size, access=access, status="ok")
        return map_id

    def unmap_buffer(self, object_id: str, map_id: str) -> None:
        obj = self.objects[object_id]
        if map_id not in obj.maps:
            raise MemoryObjectError("unknown map id")
        offset, size, access = obj.maps.pop(map_id)
        event(self.events, scenario="unmap_buffer", operation="unmap", object_id=object_id, map_id=map_id, offset=offset, size=size, access=access, status="ok")

    def create_sub_buffer(self, child_id: str, parent_id: str, origin: int, size: int, flags: Sequence[str] | None = None) -> MemoryObject:
        parent = self.objects[parent_id]
        parent.check_bounds(origin, size)
        child_flags = set(flags) if flags is not None else set(parent.flags)
        if not child_flags.issubset(parent.flags):
            raise MemoryObjectError("sub-buffer flags cannot broaden parent access")
        child = MemoryObject(
            object_id=child_id,
            size=size,
            flags=child_flags,
            storage=parent.storage[origin : origin + size],
            host_alias=None,
            parent=parent_id,
            origin=origin,
        )
        self.objects[child_id] = child
        event(self.events, scenario="create_sub_buffer", operation="create_sub_buffer", object_id=child_id, parent_id=parent_id, origin=origin, size=size, flags=sorted(child_flags), status="ok")
        return child


def run_model() -> dict[str, Any]:
    model = MemoryObjectModel()
    host_a = deterministic_host(64, 1)
    host_b = deterministic_host(64, 7)

    rw = model.create_buffer("buf_rw", 64, ["CL_MEM_READ_WRITE"])
    ro = model.create_buffer("buf_ro_copy", 64, ["CL_MEM_READ_ONLY", "CL_MEM_COPY_HOST_PTR"], host_ptr=host_a)
    wo = model.create_buffer("buf_wo", 64, ["CL_MEM_WRITE_ONLY"])
    use = model.create_buffer("buf_use_host", 64, ["CL_MEM_READ_WRITE", "CL_MEM_USE_HOST_PTR"], host_ptr=host_b)

    model.kernel_write("buf_rw", 0, b"RWOK")
    rw_readback = model.kernel_read("buf_rw", 0, 4)
    ro_payload = model.kernel_read("buf_ro_copy", 0, 8)
    host_a[0:4] = b"HOST"
    ro_still_snapshot = model.kernel_read("buf_ro_copy", 0, 4)
    model.kernel_write("buf_wo", 0, b"WROK")
    host_b[0:4] = b"ALIA"
    use_alias_payload = model.kernel_read("buf_use_host", 0, 4)

    map_id = model.map_buffer("buf_rw", 8, 16, "read_write")
    model.unmap_buffer("buf_rw", map_id)
    sub = model.create_sub_buffer("buf_rw_sub", "buf_rw", 16, 16)
    model.kernel_write("buf_rw_sub", 0, b"SUB!")
    sub_payload = model.kernel_read("buf_rw_sub", 0, 4)

    negative = [
        expect_error(model.events, name="negative_read_write_missing_access_flag", expected="exactly one access flag", action=lambda: model.create_buffer("bad_flags", 16, []), operation="create_buffer"),
        expect_error(model.events, name="negative_copy_and_use_host_ptr", expected="mutually exclusive", action=lambda: model.create_buffer("bad_ptr_flags", 16, ["CL_MEM_READ_WRITE", "CL_MEM_COPY_HOST_PTR", "CL_MEM_USE_HOST_PTR"], host_ptr=deterministic_host(16, 2)), operation="create_buffer"),
        expect_error(model.events, name="negative_copy_host_ptr_missing_ptr", expected="host pointer flag requires host_ptr", action=lambda: model.create_buffer("bad_copy_no_ptr", 16, ["CL_MEM_READ_WRITE", "CL_MEM_COPY_HOST_PTR"]), operation="create_buffer"),
        expect_error(model.events, name="negative_read_only_kernel_write", expected="CL_MEM_READ_ONLY", action=lambda: model.kernel_write("buf_ro_copy", 0, b"NOPE"), operation="kernel_write", object_id="buf_ro_copy"),
        expect_error(model.events, name="negative_write_only_kernel_read", expected="CL_MEM_WRITE_ONLY", action=lambda: model.kernel_read("buf_wo", 0, 4), operation="kernel_read", object_id="buf_wo"),
        expect_error(model.events, name="negative_map_bounds", expected="bounds", action=lambda: model.map_buffer("buf_rw", 60, 8, "read"), operation="map", object_id="buf_rw"),
        expect_error(model.events, name="negative_unmap_unknown", expected="unknown map id", action=lambda: model.unmap_buffer("buf_rw", "missing_map"), operation="unmap", object_id="buf_rw"),
        expect_error(model.events, name="negative_sub_buffer_bounds", expected="bounds", action=lambda: model.create_sub_buffer("bad_sub", "buf_rw", 60, 8), operation="create_sub_buffer", object_id="buf_rw"),
        expect_error(model.events, name="negative_sub_buffer_broaden_flags", expected="broaden", action=lambda: model.create_sub_buffer("bad_sub_flags", "buf_ro_copy", 0, 8, ["CL_MEM_READ_WRITE"]), operation="create_sub_buffer", object_id="buf_ro_copy"),
    ]

    flag_rows = [
        {
            "flag": flag,
            "readiness": "ready_proxy",
            "completion": "complete_for_proxy_gate",
            "covered_by": [event["event_id"] for event in model.events if flag in event.get("flags", [])],
            "boundary": "OpenCL-like proxy flag semantics only; not CTS or production ICD behavior",
        }
        for flag in FLAGS
    ]
    operation_rows = [
        {
            "operation": "map/unmap",
            "readiness": "ready_proxy",
            "completion": "complete_for_proxy_gate",
            "covered_by": [event["event_id"] for event in model.events if event.get("operation") in {"map", "unmap"}],
            "negative_cases": [event["scenario"] for event in negative if event.get("operation") in {"map", "unmap"}],
        },
        {
            "operation": "sub-buffer",
            "readiness": "ready_proxy",
            "completion": "complete_for_proxy_gate",
            "covered_by": [event["event_id"] for event in model.events if event.get("operation") == "create_sub_buffer"],
            "negative_cases": [event["scenario"] for event in negative if event.get("operation") == "create_sub_buffer"],
        },
        {
            "operation": "bounds negative tests",
            "readiness": "ready_proxy",
            "completion": "complete_for_proxy_gate",
            "covered_by": [event["event_id"] for event in model.events if event.get("status") == "expected_error" and "bounds" in event.get("detail", "")],
            "negative_cases": [event["scenario"] for event in negative if "bounds" in event.get("detail", "")],
        },
    ]
    checks = [
        {"name": "all_requested_flags_covered", "pass": all(row["covered_by"] for row in flag_rows)},
        {"name": "read_write_kernel_roundtrip", "pass": rw_readback == b"RWOK"},
        {"name": "read_only_copy_host_ptr_snapshot", "pass": ro_payload == bytes(deterministic_host(64, 1)[:8]) and ro_still_snapshot != b"HOST"},
        {"name": "write_only_rejects_kernel_read", "pass": any(event.get("scenario") == "negative_write_only_kernel_read" and event.get("passed") for event in negative)},
        {"name": "use_host_ptr_alias_visible", "pass": use_alias_payload == b"ALIA"},
        {"name": "map_unmap_positive_and_negative", "pass": any(event.get("operation") == "map" and event.get("status") == "ok" for event in model.events) and any(event.get("operation") == "unmap" and event.get("status") == "ok" for event in model.events) and any(event.get("scenario") == "negative_unmap_unknown" and event.get("passed") for event in negative)},
        {"name": "sub_buffer_positive_and_negative", "pass": sub_payload == b"SUB!" and any(event.get("scenario") == "negative_sub_buffer_bounds" and event.get("passed") for event in negative)},
        {"name": "bounds_negative_tests_present", "pass": sum(1 for event in negative if "bounds" in event.get("detail", "") and event.get("passed")) >= 2},
        {"name": "negative_cases_all_expected", "pass": all(event.get("status") == "expected_error" and event.get("passed") is True for event in negative)},
    ]
    summary = {
        "status": "pass" if all(check["pass"] for check in checks) else "fail",
        "flag_count": len(flag_rows),
        "operation_gate_count": len(operation_rows),
        "event_count": len(model.events),
        "negative_case_count": len(negative),
        "official_conformance_claim": False,
    }
    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "status": summary["status"],
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "summary": summary,
        "flag_gates": flag_rows,
        "operation_gates": operation_rows,
        "events": model.events,
        "object_summary": {
            object_id: {
                "size": obj.size,
                "flags": sorted(obj.flags),
                "parent": obj.parent,
                "origin": obj.origin,
                "storage_sha256": sha256_bytes(bytes(obj.storage)),
                "host_alias": obj.host_alias is not None,
            }
            for object_id, obj in sorted(model.objects.items())
        },
        "checks": checks,
        "claim_boundary": "Proxy readiness evidence only; not official OpenCL memory-object conformance.",
    }


def completion_columns(report: Mapping[str, Any]) -> dict[str, Any]:
    rows = []
    for row in report["flag_gates"]:
        rows.append(
            {
                "kind": "flag",
                "name": row["flag"],
                "readiness": row["readiness"],
                "completion": row["completion"],
                "covered_by": row["covered_by"],
                "blockers": [],
                "next_actions": ["map proxy behavior to OpenCL error-code table and CTS-shaped API fixtures"],
            }
        )
    for row in report["operation_gates"]:
        rows.append(
            {
                "kind": "operation",
                "name": row["operation"],
                "readiness": row["readiness"],
                "completion": row["completion"],
                "covered_by": row["covered_by"],
                "blockers": [],
                "next_actions": ["connect runtime API event wait-list and blocking/non-blocking semantics before conformance claims"],
            }
        )
    return {
        "schema": COMPLETION_SCHEMA,
        "generated_at": report["generated_at"],
        "status": report["status"],
        "columns": ["kind", "name", "readiness", "completion", "covered_by", "blockers", "next_actions"],
        "rows": rows,
        "summary": {
            "row_count": len(rows),
            "complete_for_proxy_gate": sum(1 for row in rows if row["completion"] == "complete_for_proxy_gate"),
            "official_conformance_claim": False,
        },
    }


def render_doc(report: Mapping[str, Any], report_path: Path, completion_path: Path) -> str:
    lines = [
        "# Phase 9 Memory Object Flags Gates",
        "",
        "Status: memory object flags/map/unmap/sub-buffer readiness gate completed for clean-room proxy evidence.",
        "",
        "Run:",
        "",
        "```sh",
        "bash scripts/verify_celviz_gpgpu_phase9_memory_object_flags.sh",
        "```",
        "",
        "Generated evidence:",
        "",
        f"- `{report_path.as_posix()}`",
        f"- `{completion_path.as_posix()}`",
        "",
        "Boundary: " + CLEAN_ROOM_SCOPE + ".",
        "",
        "## Summary",
        "",
        f"- Flags covered: `{report['summary']['flag_count']}`",
        f"- Operation gates: `{report['summary']['operation_gate_count']}`",
        f"- Negative cases: `{report['summary']['negative_case_count']}`",
        f"- Official conformance claim: `{str(report['summary']['official_conformance_claim']).lower()}`",
        "",
        "## Completion Columns",
        "",
        "| Kind | Name | Readiness | Completion |",
        "| --- | --- | --- | --- |",
    ]
    for row in completion_columns(report)["rows"]:
        lines.append(f"| `{row['kind']}` | `{row['name']}` | `{row['readiness']}` | `{row['completion']}` |")
    lines.extend(
        [
            "",
            "## Checks",
            "",
        ]
    )
    for check in report["checks"]:
        lines.append(f"- `{check['name']}`: `{str(check['pass']).lower()}`")
    lines.append("")
    return "\n".join(lines)


def write_log(path: Path, report: Mapping[str, Any]) -> None:
    summary = report["summary"]
    lines = [
        "Celviz GPGPU IP Phase9 memory object flags/map/unmap/sub-buffer gate",
        f"schema={report['schema']}",
        f"status={report['status']}",
        f"flag_count={summary['flag_count']}",
        f"operation_gate_count={summary['operation_gate_count']}",
        f"negative_case_count={summary['negative_case_count']}",
        f"event_count={summary['event_count']}",
        "official_conformance_claim=false",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--completion", type=Path, default=DEFAULT_COMPLETION)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--print-summary", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_model()
    completion = completion_columns(report)
    write_json(args.report, report)
    write_json(args.completion, completion)
    args.doc.parent.mkdir(parents=True, exist_ok=True)
    args.doc.write_text(render_doc(report, args.report, args.completion), encoding="utf-8")
    write_log(args.log, report)
    if args.print_summary:
        print(json.dumps(report["summary"], indent=2, sort_keys=True))
    else:
        summary = report["summary"]
        print(
            "celviz_gpgpu_phase9_memory_object_flags_gate: "
            f"{report['status']} flags={summary['flag_count']} "
            f"ops={summary['operation_gate_count']} negatives={summary['negative_case_count']}"
        )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
