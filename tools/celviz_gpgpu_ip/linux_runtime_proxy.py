#!/usr/bin/env python3
"""Linux userspace runtime and DRM-like submission proxy for Celviz GPGPU IP.

This is a clean-room userspace model.  It intentionally stops at the
non-driver boundary: device/context/BO/queue/fence/event semantics are modeled
as JSON evidence, but no Linux kernel DRM driver, ioctl ABI, GEM object, syncobj
ABI, or upstream kernel integration is claimed.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple


SCHEMA = "celviz.gpgpu.linux_userspace_runtime.v1"
EVIDENCE_SCHEMA = "celviz.gpgpu.linux_userspace_runtime_evidence.v1"
CLEAN_ROOM_SCOPE = (
    "clean-room Linux userspace runtime plus DRM-like submission proxy; "
    "models OS queue/fence/event semantics only and does not implement or "
    "claim a kernel DRM driver, ioctl ABI, GEM object ABI, firmware ABI, or "
    "proprietary Vivante compatibility"
)

ERRNO = {
    "OK": 0,
    "EINVAL": -22,
    "ENOENT": -2,
    "EACCES": -13,
    "ENOMEM": -12,
    "ETIMEDOUT": -110,
    "EIO": -5,
}

EVENT_READABLE = 0x1
EVENT_ERROR = 0x2


class ProxyConfigError(ValueError):
    """Raised when the Linux runtime proxy fixture is malformed."""


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def artifact_root(root: Path) -> Path:
    return root / "artifacts/rank_01_vivante_3d_gpgpu_ip/os_runtime"


def default_fixture(root: Path) -> Path:
    return artifact_root(root) / "linux_runtime_fixture.json"


def default_evidence(root: Path) -> Path:
    return artifact_root(root) / "linux_runtime_evidence.json"


def default_log(root: Path) -> Path:
    return artifact_root(root) / "linux_runtime_check.log"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProxyConfigError(f"fixture not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ProxyConfigError(f"fixture JSON is invalid: {exc}") from exc
    if not isinstance(data, dict):
        raise ProxyConfigError("fixture root must be an object")
    return data


def parse_int(value: Any, field: str, *, default: Optional[int] = None) -> int:
    if value is None and default is not None:
        return default
    if isinstance(value, bool):
        raise ProxyConfigError(f"{field} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError as exc:
            raise ProxyConfigError(f"{field} must be an integer or integer string") from exc
    raise ProxyConfigError(f"{field} must be an integer")


def require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProxyConfigError(f"{field} must be a non-empty string")
    return value


def require_list(value: Any, field: str) -> List[Any]:
    if not isinstance(value, list):
        raise ProxyConfigError(f"{field} must be a list")
    return value


def require_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ProxyConfigError(f"{field} must be an object")
    return value


def access_flags(value: Any) -> set[str]:
    if value is None:
        return {"read", "write"}
    if isinstance(value, str):
        aliases = {
            "rw": {"read", "write"},
            "read_write": {"read", "write"},
            "read": {"read"},
            "write": {"write"},
            "read_only": {"read"},
            "write_only": {"write"},
        }
        return set(aliases.get(value, {value}))
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return set(value)
    raise ProxyConfigError("access flags must be a string or string list")


@dataclass
class BO:
    handle: int
    label: str
    size: int
    flags: set[str]
    mapped: bool = False
    map_count: int = 0
    gpu_va: Optional[int] = None
    data: bytearray = field(default_factory=bytearray)

    def to_json(self) -> Dict[str, Any]:
        return {
            "handle": self.handle,
            "label": self.label,
            "size": self.size,
            "flags": sorted(self.flags),
            "mapped": self.mapped,
            "map_count": self.map_count,
            "gpu_va": hex(self.gpu_va) if self.gpu_va is not None else None,
        }


@dataclass
class Fence:
    handle: int
    name: str
    timeline_value: int = 0
    signaled: bool = False
    error: Optional[str] = None

    def to_json(self) -> Dict[str, Any]:
        return {
            "handle": self.handle,
            "name": self.name,
            "timeline_value": self.timeline_value,
            "signaled": self.signaled,
            "error": self.error,
        }


@dataclass
class Event:
    event_id: int
    kind: str
    source: str
    queue_id: int
    fence_handle: Optional[int]
    sequence: Optional[int]
    status: str
    errno: int
    poll_mask: int
    payload: Dict[str, Any]

    def to_json(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "kind": self.kind,
            "source": self.source,
            "queue_id": self.queue_id,
            "fence_handle": self.fence_handle,
            "sequence": self.sequence,
            "status": self.status,
            "errno": self.errno,
            "poll_mask": self.poll_mask,
            "readable": bool(self.poll_mask & EVENT_READABLE),
            "error": bool(self.poll_mask & EVENT_ERROR),
            "payload": self.payload,
        }


@dataclass
class Queue:
    queue_id: int
    context_id: int
    priority: int
    submitted: int = 0
    retired: int = 0
    errors: int = 0
    head: int = 0
    tail: int = 0

    @property
    def pending(self) -> int:
        return max(0, self.submitted - self.retired)

    def to_json(self) -> Dict[str, Any]:
        return {
            "queue_id": self.queue_id,
            "context_id": self.context_id,
            "priority": self.priority,
            "submitted": self.submitted,
            "retired": self.retired,
            "errors": self.errors,
            "pending": self.pending,
            "head": self.head,
            "tail": self.tail,
            "lifecycle": "error" if self.errors else ("busy" if self.pending else "idle"),
        }


class LinuxRuntimeProxy:
    def __init__(self, fixture: Mapping[str, Any]) -> None:
        if fixture.get("schema", SCHEMA) != SCHEMA:
            raise ProxyConfigError(f"schema must be {SCHEMA}")
        self.fixture = fixture
        self.clock = 0
        self.device_opened = False
        self.device_node = str(fixture.get("device_node", "/dev/dri/renderD128"))
        self.device_fd: Optional[int] = None
        self.context_id: Optional[int] = None
        self.next_bo = 1
        self.next_fence = 1
        self.next_event = 1
        self.next_sequence = 1
        self.next_gpu_va = 0x80000000
        self.bos: Dict[int, BO] = {}
        self.fences: Dict[int, Fence] = {}
        self.events: List[Event] = []
        self.queues: Dict[int, Queue] = {}
        self.submissions: List[Dict[str, Any]] = []
        self.timeline: List[Dict[str, Any]] = []
        self.counters: Dict[str, int] = {
            "device_opens": 0,
            "context_creates": 0,
            "bo_allocs": 0,
            "bo_maps": 0,
            "bo_gpu_maps": 0,
            "queue_creates": 0,
            "submits": 0,
            "submit_success": 0,
            "submit_errors": 0,
            "fence_creates": 0,
            "fence_signals": 0,
            "fence_waits": 0,
            "fence_timeouts": 0,
            "events_generated": 0,
            "events_polled": 0,
            "completion_events": 0,
            "error_events": 0,
        }

    def tick(self, op: str, detail: Mapping[str, Any]) -> None:
        self.clock += 1
        self.timeline.append({"time": self.clock, "op": op, "detail": dict(detail)})

    def emit_event(
        self,
        *,
        kind: str,
        source: str,
        queue_id: int,
        fence_handle: Optional[int],
        sequence: Optional[int],
        status: str,
        errno: int,
        payload: Mapping[str, Any],
    ) -> Event:
        poll_mask = EVENT_READABLE | (EVENT_ERROR if errno != 0 else 0)
        event = Event(
            event_id=self.next_event,
            kind=kind,
            source=source,
            queue_id=queue_id,
            fence_handle=fence_handle,
            sequence=sequence,
            status=status,
            errno=errno,
            poll_mask=poll_mask,
            payload=dict(payload),
        )
        self.next_event += 1
        self.events.append(event)
        self.counters["events_generated"] += 1
        if errno == 0:
            self.counters["completion_events"] += 1
        else:
            self.counters["error_events"] += 1
        self.tick("event_emit", event.to_json())
        return event

    def open_device(self, spec: Mapping[str, Any]) -> None:
        self.device_node = str(spec.get("node", self.device_node))
        self.device_fd = parse_int(spec.get("fd", 128), "open.fd")
        self.device_opened = True
        self.counters["device_opens"] += 1
        self.tick("device_open", {"node": self.device_node, "fd": self.device_fd, "boundary": "userspace_proxy_only"})

    def create_context(self, spec: Mapping[str, Any]) -> None:
        if not self.device_opened:
            raise ProxyConfigError("context_create requires device_open first")
        self.context_id = parse_int(spec.get("context_id", 1), "context.context_id")
        self.counters["context_creates"] += 1
        self.tick("context_create", {"context_id": self.context_id, "fd": self.device_fd})

    def alloc_bo(self, spec: Mapping[str, Any]) -> None:
        label = require_string(spec.get("label", f"bo{self.next_bo}"), "bo.label")
        size = parse_int(spec.get("size", spec.get("size_bytes")), f"bo.{label}.size")
        if size <= 0:
            raise ProxyConfigError(f"bo.{label}.size must be positive")
        handle = parse_int(spec.get("handle", self.next_bo), f"bo.{label}.handle")
        if handle in self.bos:
            raise ProxyConfigError(f"duplicate BO handle: {handle}")
        flags = access_flags(spec.get("flags", spec.get("access")))
        pattern = parse_int(spec.get("fill", 0), f"bo.{label}.fill", default=0) & 0xFF
        self.bos[handle] = BO(handle=handle, label=label, size=size, flags=flags, data=bytearray([pattern] * size))
        self.next_bo = max(self.next_bo, handle + 1)
        self.counters["bo_allocs"] += 1
        self.tick("bo_alloc", self.bos[handle].to_json())

    def map_bo(self, spec: Mapping[str, Any]) -> None:
        bo = self.get_bo(spec.get("handle"), "map.handle")
        if "read" not in bo.flags and "write" not in bo.flags:
            raise ProxyConfigError(f"BO {bo.handle} has no CPU mapping access")
        bo.mapped = True
        bo.map_count += 1
        self.counters["bo_maps"] += 1
        self.tick("bo_map", bo.to_json())

    def gpu_map_bo(self, spec: Mapping[str, Any]) -> None:
        bo = self.get_bo(spec.get("handle"), "gpu_map.handle")
        gpu_va = parse_int(spec.get("gpu_va", self.next_gpu_va), "gpu_map.gpu_va")
        bo.gpu_va = gpu_va
        self.next_gpu_va = max(self.next_gpu_va, gpu_va + ((bo.size + 0xFFF) & ~0xFFF))
        self.counters["bo_gpu_maps"] += 1
        self.tick("bo_gpu_map", bo.to_json())

    def create_queue(self, spec: Mapping[str, Any]) -> None:
        if self.context_id is None:
            raise ProxyConfigError("queue_create requires context_create first")
        queue_id = parse_int(spec.get("queue_id", len(self.queues)), "queue.queue_id")
        if queue_id in self.queues:
            raise ProxyConfigError(f"duplicate queue_id: {queue_id}")
        self.queues[queue_id] = Queue(
            queue_id=queue_id,
            context_id=self.context_id,
            priority=parse_int(spec.get("priority", 0), "queue.priority"),
        )
        self.counters["queue_creates"] += 1
        self.tick("queue_create", self.queues[queue_id].to_json())

    def create_fence(self, spec: Mapping[str, Any]) -> None:
        handle = parse_int(spec.get("handle", self.next_fence), "fence.handle")
        if handle in self.fences:
            raise ProxyConfigError(f"duplicate fence handle: {handle}")
        fence = Fence(handle=handle, name=str(spec.get("name", f"fence{handle}")))
        self.fences[handle] = fence
        self.next_fence = max(self.next_fence, handle + 1)
        self.counters["fence_creates"] += 1
        self.tick("fence_create", fence.to_json())

    def get_bo(self, raw_handle: Any, field: str) -> BO:
        handle = parse_int(raw_handle, field)
        bo = self.bos.get(handle)
        if bo is None:
            raise ProxyConfigError(f"unknown BO handle: {handle}")
        return bo

    def get_queue(self, raw_queue: Any) -> Queue:
        queue_id = parse_int(raw_queue, "submit.queue_id", default=0)
        queue = self.queues.get(queue_id)
        if queue is None:
            raise ProxyConfigError(f"unknown queue_id: {queue_id}")
        return queue

    def get_fence(self, raw_handle: Any, field: str) -> Fence:
        handle = parse_int(raw_handle, field)
        fence = self.fences.get(handle)
        if fence is None:
            raise ProxyConfigError(f"unknown fence handle: {handle}")
        return fence

    def validate_bo_refs(self, refs: Iterable[Mapping[str, Any]]) -> Tuple[bool, str]:
        for index, raw_ref in enumerate(refs):
            ref = require_mapping(raw_ref, f"submit.bo_refs[{index}]")
            bo = self.get_bo(ref.get("handle"), f"submit.bo_refs[{index}].handle")
            required = access_flags(ref.get("access", "read_write"))
            if "read" in required and "read" not in bo.flags:
                return False, f"BO {bo.handle} lacks read access"
            if "write" in required and "write" not in bo.flags:
                return False, f"BO {bo.handle} lacks write access"
            if bo.gpu_va is None:
                return False, f"BO {bo.handle} is not GPU mapped"
        return True, "OK"

    def submit(self, spec: Mapping[str, Any]) -> None:
        queue = self.get_queue(spec.get("queue_id", 0))
        sequence = parse_int(spec.get("sequence", self.next_sequence), "submit.sequence")
        self.next_sequence = max(self.next_sequence, sequence + 1)
        fence = self.get_fence(spec.get("out_fence"), "submit.out_fence")
        opcode = str(spec.get("opcode", "kernel_dispatch"))
        bo_refs = [require_mapping(item, "submit.bo_refs[]") for item in spec.get("bo_refs", [])]
        force_error = spec.get("force_error")
        ok, message = self.validate_bo_refs(bo_refs)
        errno_name = "OK"
        status = "complete"
        if force_error:
            ok = False
            errno_name = str(force_error)
            message = str(spec.get("error_message", errno_name))
        elif not ok:
            errno_name = "EACCES"
            status = "error"
        if not ok:
            status = "error"
        errno = ERRNO.get(errno_name, ERRNO["EIO"])

        queue.submitted += 1
        queue.tail += 1
        self.counters["submits"] += 1
        self.tick(
            "drm_ioctl_submit",
            {
                "ioctl": "DRM_IOCTL_CELVIZ_GPGPU_SUBMIT_PROXY",
                "queue_id": queue.queue_id,
                "sequence": sequence,
                "opcode": opcode,
                "bo_refs": bo_refs,
                "out_fence": fence.handle,
                "boundary": "mock_ioctl_descriptor_no_kernel_driver",
            },
        )

        if errno == 0:
            queue.retired += 1
            queue.head += 1
            fence.signaled = True
            fence.timeline_value = sequence
            self.counters["submit_success"] += 1
            self.counters["fence_signals"] += 1
        else:
            queue.retired += 1
            queue.head += 1
            queue.errors += 1
            fence.signaled = True
            fence.timeline_value = sequence
            fence.error = errno_name
            self.counters["submit_errors"] += 1

        record = {
            "sequence": sequence,
            "queue_id": queue.queue_id,
            "context_id": queue.context_id,
            "opcode": opcode,
            "status": status,
            "errno_name": errno_name,
            "errno": errno,
            "message": message,
            "bo_refs": bo_refs,
            "out_fence": fence.to_json(),
            "completion_path": "eventfd_poll_style_readable_event",
        }
        self.submissions.append(record)
        self.emit_event(
            kind="completion" if errno == 0 else "error",
            source="submit",
            queue_id=queue.queue_id,
            fence_handle=fence.handle,
            sequence=sequence,
            status=status,
            errno=errno,
            payload=record,
        )

    def wait_fence(self, spec: Mapping[str, Any]) -> None:
        fence = self.get_fence(spec.get("handle"), "wait.handle")
        timeout_ms = parse_int(spec.get("timeout_ms", 0), "wait.timeout_ms", default=0)
        self.counters["fence_waits"] += 1
        if fence.signaled:
            errno = ERRNO["OK"] if fence.error is None else ERRNO.get(fence.error, ERRNO["EIO"])
            status = "signaled" if fence.error is None else "error"
        else:
            errno = ERRNO["ETIMEDOUT"]
            status = "timeout"
            self.counters["fence_timeouts"] += 1
        payload = {"fence": fence.to_json(), "timeout_ms": timeout_ms, "wait_status": status, "errno": errno}
        self.tick("fence_wait", payload)
        self.emit_event(
            kind="fence_wait",
            source="fence",
            queue_id=parse_int(spec.get("queue_id", 0), "wait.queue_id", default=0),
            fence_handle=fence.handle,
            sequence=fence.timeline_value or None,
            status=status,
            errno=errno,
            payload=payload,
        )

    def poll_events(self, spec: Mapping[str, Any]) -> None:
        limit = parse_int(spec.get("max_events", len(self.events)), "poll.max_events", default=len(self.events))
        readable = [event.to_json() for event in self.events if event.poll_mask & EVENT_READABLE]
        polled = readable[:limit]
        self.counters["events_polled"] += len(polled)
        self.tick(
            "event_poll",
            {
                "poll_fd_model": "eventfd/epoll proxy",
                "requested": limit,
                "returned": len(polled),
                "events": polled,
            },
        )

    def run_operation(self, raw_op: Mapping[str, Any]) -> None:
        op = require_string(raw_op.get("op"), "operations[].op")
        handlers = {
            "device_open": self.open_device,
            "context_create": self.create_context,
            "bo_alloc": self.alloc_bo,
            "bo_map": self.map_bo,
            "bo_gpu_map": self.gpu_map_bo,
            "queue_create": self.create_queue,
            "fence_create": self.create_fence,
            "submit": self.submit,
            "fence_wait": self.wait_fence,
            "event_poll": self.poll_events,
        }
        handler = handlers.get(op)
        if handler is None:
            raise ProxyConfigError(f"unsupported operation: {op}")
        handler(raw_op)

    def run(self) -> Dict[str, Any]:
        for raw_op in require_list(self.fixture.get("operations"), "operations"):
            self.run_operation(require_mapping(raw_op, "operations[]"))
        return self.evidence()

    def evidence(self) -> Dict[str, Any]:
        open_ok = self.device_opened and self.context_id is not None
        bo_ok = bool(self.bos) and all(bo.mapped and bo.gpu_va is not None for bo in self.bos.values())
        submit_ok = self.counters["submit_success"] >= 1
        error_ok = self.counters["submit_errors"] >= 1 and self.counters["error_events"] >= 1
        fence_ok = self.counters["fence_waits"] >= 2 and self.counters["fence_signals"] >= 1
        event_ok = self.counters["events_polled"] >= 1 and any(event.poll_mask & EVENT_READABLE for event in self.events)
        queue_ok = bool(self.queues) and all(queue.pending == 0 for queue in self.queues.values())
        checks = [
            {"name": "device_context_open", "pass": open_ok},
            {"name": "bo_alloc_map_gpu_va", "pass": bo_ok},
            {"name": "drm_like_submit_completion", "pass": submit_ok},
            {"name": "fence_wait_signal", "pass": fence_ok},
            {"name": "event_poll_readable", "pass": event_ok},
            {"name": "completion_error_path", "pass": error_ok},
            {"name": "queue_retired_no_pending", "pass": queue_ok},
            {"name": "clean_room_non_driver_boundary", "pass": True},
        ]
        status = "pass" if all(check["pass"] for check in checks) else "fail"
        return {
            "schema": EVIDENCE_SCHEMA,
            "generated_at": utc_now(),
            "status": status,
            "scope": CLEAN_ROOM_SCOPE,
            "boundary": {
                "mode": "userspace_proxy",
                "kernel_driver_claim": False,
                "ioctl_claim": "mock descriptor only",
                "device_node_model": self.device_node,
            },
            "device": {
                "opened": self.device_opened,
                "node": self.device_node,
                "fd": self.device_fd,
                "context_id": self.context_id,
            },
            "bos": [bo.to_json() for bo in self.bos.values()],
            "queues": [queue.to_json() for queue in self.queues.values()],
            "fences": [fence.to_json() for fence in self.fences.values()],
            "submissions": self.submissions,
            "events": [event.to_json() for event in self.events],
            "counters": self.counters,
            "timeline": self.timeline,
            "checks": checks,
        }


def default_fixture_payload() -> Dict[str, Any]:
    return {
        "schema": SCHEMA,
        "scope": CLEAN_ROOM_SCOPE,
        "device_node": "/dev/dri/renderD128",
        "operations": [
            {"op": "device_open", "node": "/dev/dri/renderD128", "fd": 128},
            {"op": "context_create", "context_id": 7},
            {"op": "queue_create", "queue_id": 0, "priority": 1},
            {"op": "bo_alloc", "handle": 1, "label": "input", "size": 4096, "flags": ["read", "write"], "fill": 17},
            {"op": "bo_alloc", "handle": 2, "label": "output", "size": 4096, "flags": ["read", "write"], "fill": 0},
            {"op": "bo_alloc", "handle": 3, "label": "read_only_fault", "size": 1024, "flags": ["read"], "fill": 85},
            {"op": "bo_map", "handle": 1},
            {"op": "bo_map", "handle": 2},
            {"op": "bo_map", "handle": 3},
            {"op": "bo_gpu_map", "handle": 1, "gpu_va": "0x80000000"},
            {"op": "bo_gpu_map", "handle": 2, "gpu_va": "0x80001000"},
            {"op": "bo_gpu_map", "handle": 3, "gpu_va": "0x80002000"},
            {"op": "fence_create", "handle": 1, "name": "submit_ok"},
            {
                "op": "submit",
                "queue_id": 0,
                "sequence": 1,
                "opcode": "kernel_dispatch",
                "bo_refs": [
                    {"handle": 1, "access": "read"},
                    {"handle": 2, "access": "write"},
                ],
                "out_fence": 1,
            },
            {"op": "fence_wait", "handle": 1, "timeout_ms": 1000},
            {"op": "fence_create", "handle": 2, "name": "submit_error"},
            {
                "op": "submit",
                "queue_id": 0,
                "sequence": 2,
                "opcode": "dma_fill",
                "bo_refs": [{"handle": 3, "access": "write"}],
                "out_fence": 2,
            },
            {"op": "fence_wait", "handle": 2, "timeout_ms": 1000},
            {"op": "event_poll", "max_events": 8},
        ],
    }


def run_to_files(*, fixture_path: Path, evidence_path: Path, log_path: Path, print_json: bool = False) -> Dict[str, Any]:
    if not fixture_path.exists():
        write_json(fixture_path, default_fixture_payload())
    fixture = load_json(fixture_path)
    proxy = LinuxRuntimeProxy(fixture)
    evidence = proxy.run()
    evidence["artifact_manifest"] = {
        "fixture": str(fixture_path),
        "evidence": str(evidence_path),
        "log": str(log_path),
    }
    write_json(evidence_path, evidence)
    log_lines = [
        "celviz_gpgpu_linux_runtime_proxy: start",
        f"schema={SCHEMA}",
        f"scope={CLEAN_ROOM_SCOPE}",
        f"device={evidence['device']['node']} context={evidence['device']['context_id']}",
        "summary submits={submits} submit_success={submit_success} submit_errors={submit_errors} events={events_generated}".format(
            **evidence["counters"]
        ),
        "checks " + ",".join(f"{check['name']}={'pass' if check['pass'] else 'fail'}" for check in evidence["checks"]),
        "celviz_gpgpu_linux_runtime_proxy: " + evidence["status"],
    ]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    if print_json:
        print(json.dumps(evidence, indent=2, sort_keys=True))
    return evidence


def build_argparser() -> argparse.ArgumentParser:
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=default_fixture(root), help="Linux runtime proxy fixture JSON")
    parser.add_argument("--evidence", type=Path, default=default_evidence(root), help="Output evidence JSON")
    parser.add_argument("--log", type=Path, default=default_log(root), help="Output run log")
    parser.add_argument("--print-json", action="store_true", help="Print evidence JSON to stdout")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_argparser()
    args = parser.parse_args(argv)
    try:
        evidence = run_to_files(fixture_path=args.fixture, evidence_path=args.evidence, log_path=args.log, print_json=args.print_json)
    except ProxyConfigError as exc:
        parser.error(str(exc))
        return 2
    return 0 if evidence["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
