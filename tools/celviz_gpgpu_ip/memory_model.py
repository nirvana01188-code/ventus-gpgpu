#!/usr/bin/env python3
"""Clean-room memory-system phase-1 model for Celviz GPGPU IP.

This tool models observable memory semantics for GPGPU proxy evidence:
global/local/constant address spaces, cache and scratchpad proxy behavior,
coalescing groups, DMA copy/fill, and kernel load/store events. It is
deterministic, standard-library only, and intentionally does not claim
Vivante RTL, firmware, driver, compiler, cache microarchitecture, or API
conformance behavior.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence


SCHEMA = "celviz.gpgpu.memory_model.phase1.v1"
EVENT_SCHEMA = "celviz.gpgpu.memory_event.v1"
DEFAULT_ARTIFACT_ROOT = Path("artifacts/rank_01_vivante_3d_gpgpu_ip/memory")
CLEAN_ROOM_SCOPE = (
    "clean-room functional memory proxy; no proprietary Vivante cache, LSU, "
    "DMA engine, command stream, firmware, driver, SDK, compiler, timing, PPA, "
    "or API conformance claim"
)
CACHE_LINE_BYTES = 32
COALESCING_SEGMENT_BYTES = 32
GLOBAL_ALIGNMENT_BYTES = 4
DMA_ALIGNMENT_BYTES = 4
CONSTANT_SIZE_BYTES = 64
GLOBAL_SIZE_BYTES = 256
LOCAL_SIZE_BYTES = 96
LOCAL_GROUP_BYTES = 48


class MemoryModelError(ValueError):
    """Raised when a modeled operation violates the phase-1 contract."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_json(value: Any) -> str:
    blob = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(blob)


def write_json(path: Path, payload: Mapping[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return sha256_bytes(path.read_bytes())


def stable_u8(index: int, *, salt: int = 0) -> int:
    return (index * 37 + 17 + salt * 11) & 0xFF


def hexdump_head(data: bytes, count: int = 16) -> list[int]:
    return list(data[:count])


@dataclass
class MemorySpace:
    name: str
    size_bytes: int
    base: int
    mutable: bool
    alignment_bytes: int = GLOBAL_ALIGNMENT_BYTES
    data: bytearray = field(default_factory=bytearray)

    def __post_init__(self) -> None:
        if not self.data:
            self.data = bytearray(self.size_bytes)
        if len(self.data) != self.size_bytes:
            raise MemoryModelError(f"{self.name} data length does not match size")

    def check(self, offset: int, size: int, *, alignment: Optional[int] = None, write: bool = False) -> None:
        if size <= 0:
            raise MemoryModelError(f"{self.name} access size must be positive")
        align = self.alignment_bytes if alignment is None else alignment
        if offset < 0 or offset + size > self.size_bytes:
            raise MemoryModelError(f"{self.name} bounds violation offset={offset} size={size}")
        if align > 1 and offset % align != 0:
            raise MemoryModelError(f"{self.name} alignment violation offset={offset} alignment={align}")
        if write and not self.mutable:
            raise MemoryModelError(f"{self.name} is read-only")

    def read(self, offset: int, size: int, *, alignment: Optional[int] = None) -> bytes:
        self.check(offset, size, alignment=alignment, write=False)
        return bytes(self.data[offset : offset + size])

    def write(self, offset: int, payload: bytes, *, alignment: Optional[int] = None) -> None:
        self.check(offset, len(payload), alignment=alignment, write=True)
        self.data[offset : offset + len(payload)] = payload


@dataclass
class MemoryState:
    spaces: dict[str, MemorySpace]
    events: list[dict[str, Any]] = field(default_factory=list)
    cache_lines: set[tuple[str, int]] = field(default_factory=set)
    event_index: int = 0

    def emit(
        self,
        *,
        category: str,
        operation: str,
        address_space: str,
        offset: int,
        size_bytes: int,
        status: str = "ok",
        detail: str = "",
        source: str = "model",
        **extra: Any,
    ) -> dict[str, Any]:
        space = self.spaces.get(address_space)
        absolute = None if space is None else space.base + offset
        record: dict[str, Any] = {
            "schema": EVENT_SCHEMA,
            "event_id": self.event_index,
            "category": category,
            "operation": operation,
            "source": source,
            "address_space": address_space,
            "offset": offset,
            "absolute_address": None if absolute is None else hex(absolute),
            "size_bytes": size_bytes,
            "status": status,
            "detail": detail,
        }
        record.update(extra)
        self.events.append(record)
        self.event_index += 1
        return record


def initial_state() -> MemoryState:
    global_data = bytearray(stable_u8(i) for i in range(GLOBAL_SIZE_BYTES))
    constant_data = bytearray(stable_u8(i, salt=5) for i in range(CONSTANT_SIZE_BYTES))
    return MemoryState(
        spaces={
            "global": MemorySpace("global", GLOBAL_SIZE_BYTES, 0x8000_0000, True, GLOBAL_ALIGNMENT_BYTES, global_data),
            "local": MemorySpace("local", LOCAL_SIZE_BYTES, 0x0000_0000, True, GLOBAL_ALIGNMENT_BYTES),
            "constant": MemorySpace("constant", CONSTANT_SIZE_BYTES, 0x9000_0000, False, GLOBAL_ALIGNMENT_BYTES, constant_data),
            "host": MemorySpace(
                "host",
                256,
                0x1000_0000,
                True,
                DMA_ALIGNMENT_BYTES,
                bytearray(stable_u8(i, salt=9) for i in range(256)),
            ),
        }
    )


def cache_probe(state: MemoryState, address_space: str, offset: int, size: int) -> dict[str, Any]:
    line_start = offset // CACHE_LINE_BYTES
    line_end = (offset + size - 1) // CACHE_LINE_BYTES
    lines = [(address_space, line) for line in range(line_start, line_end + 1)]
    hits = sum(1 for line in lines if line in state.cache_lines)
    misses = len(lines) - hits
    for line in lines:
        state.cache_lines.add(line)
    return {
        "cache_model": "direct functional line-presence proxy",
        "line_bytes": CACHE_LINE_BYTES,
        "line_indices": [line for _, line in lines],
        "hits": hits,
        "misses": misses,
        "hit": misses == 0,
    }


def coalescing_group(lanes: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    groups: dict[tuple[str, int], list[Mapping[str, Any]]] = {}
    for lane in lanes:
        segment = int(lane["offset"]) // COALESCING_SEGMENT_BYTES
        groups.setdefault((str(lane["address_space"]), segment), []).append(lane)

    group_rows = []
    for (address_space, segment), items in sorted(groups.items()):
        offsets = [int(item["offset"]) for item in items]
        sizes = [int(item["size_bytes"]) for item in items]
        group_rows.append(
            {
                "address_space": address_space,
                "segment_index": segment,
                "segment_base_offset": segment * COALESCING_SEGMENT_BYTES,
                "lane_ids": [int(item["lane_id"]) for item in items],
                "lane_count": len(items),
                "byte_span": [min(offsets), max(offset + size for offset, size in zip(offsets, sizes))],
                "proxy_transactions": 1,
            }
        )

    return {
        "segment_bytes": COALESCING_SEGMENT_BYTES,
        "lane_count": len(lanes),
        "group_count": len(group_rows),
        "naive_transactions": len(lanes),
        "coalesced_transactions": len(group_rows),
        "groups": group_rows,
    }


def record_negative(
    state: MemoryState,
    *,
    name: str,
    operation: str,
    address_space: str,
    offset: int,
    size_bytes: int,
    expected_error: str,
    action: Any,
) -> dict[str, Any]:
    try:
        action()
    except MemoryModelError as exc:
        status = "expected_error"
        detail = str(exc)
        passed = expected_error in detail
    else:
        status = "unexpected_ok"
        detail = "operation completed but an error was expected"
        passed = False
    event = state.emit(
        category="negative",
        operation=operation,
        address_space=address_space,
        offset=offset,
        size_bytes=size_bytes,
        status=status,
        detail=detail,
        source=name,
        expected_error=expected_error,
        pass_=passed,
    )
    event["pass"] = event.pop("pass_")
    return event


def dma_copy(
    state: MemoryState,
    *,
    name: str,
    src_space: str,
    src_offset: int,
    dst_space: str,
    dst_offset: int,
    size: int,
) -> dict[str, Any]:
    src = state.spaces[src_space]
    dst = state.spaces[dst_space]
    payload = src.read(src_offset, size, alignment=DMA_ALIGNMENT_BYTES)
    dst.write(dst_offset, payload, alignment=DMA_ALIGNMENT_BYTES)
    checksum = sha256_bytes(payload)
    return state.emit(
        category="dma",
        operation="copy",
        source=name,
        address_space=dst_space,
        offset=dst_offset,
        size_bytes=size,
        detail=f"{src_space}[{src_offset}:{src_offset + size}] -> {dst_space}[{dst_offset}:{dst_offset + size}]",
        src_address_space=src_space,
        src_offset=src_offset,
        dst_address_space=dst_space,
        dst_offset=dst_offset,
        bytes_sha256=checksum,
        payload_head=hexdump_head(payload),
    )


def dma_fill(state: MemoryState, *, name: str, dst_space: str, dst_offset: int, pattern: int, size: int) -> dict[str, Any]:
    payload = bytes([pattern & 0xFF]) * size
    state.spaces[dst_space].write(dst_offset, payload, alignment=DMA_ALIGNMENT_BYTES)
    return state.emit(
        category="dma",
        operation="fill",
        source=name,
        address_space=dst_space,
        offset=dst_offset,
        size_bytes=size,
        detail=f"fill {dst_space}[{dst_offset}:{dst_offset + size}] pattern=0x{pattern & 0xFF:02x}",
        pattern=hex(pattern & 0xFF),
        bytes_sha256=sha256_bytes(payload),
        payload_head=hexdump_head(payload),
    )


def kernel_load(
    state: MemoryState,
    *,
    name: str,
    address_space: str,
    offset: int,
    size: int,
    lane_id: Optional[int] = None,
) -> bytes:
    payload = state.spaces[address_space].read(offset, size)
    cache = cache_probe(state, address_space, offset, size) if address_space in {"global", "constant"} else None
    state.emit(
        category="kernel",
        operation="load",
        source=name,
        address_space=address_space,
        offset=offset,
        size_bytes=size,
        detail=f"kernel load from {address_space}",
        lane_id=lane_id,
        cache=cache,
        read_only=address_space == "constant",
        bytes_sha256=sha256_bytes(payload),
        payload_head=hexdump_head(payload),
    )
    return payload


def kernel_store(
    state: MemoryState,
    *,
    name: str,
    address_space: str,
    offset: int,
    payload: bytes,
    lane_id: Optional[int] = None,
) -> None:
    state.spaces[address_space].write(offset, payload)
    cache = cache_probe(state, address_space, offset, len(payload)) if address_space == "global" else None
    state.emit(
        category="kernel",
        operation="store",
        source=name,
        address_space=address_space,
        offset=offset,
        size_bytes=len(payload),
        detail=f"kernel store to {address_space}",
        lane_id=lane_id,
        cache=cache,
        bytes_sha256=sha256_bytes(payload),
        payload_head=hexdump_head(payload),
    )


def scratchpad_local_roundtrip(state: MemoryState) -> dict[str, Any]:
    group_id = 0
    base = group_id * LOCAL_GROUP_BYTES
    lanes = []
    for lane_id in range(8):
        payload = bytes([(lane_id + 1) * 3, (lane_id + 1) * 3 + 1, (lane_id + 1) * 3 + 2, (lane_id + 1) * 3 + 3])
        offset = base + lane_id * 4
        kernel_store(state, name="scratchpad_local_roundtrip", address_space="local", offset=offset, payload=payload, lane_id=lane_id)
        readback = kernel_load(state, name="scratchpad_local_roundtrip", address_space="local", offset=offset, size=4, lane_id=lane_id)
        lanes.append({"lane_id": lane_id, "offset": offset, "payload": list(payload), "readback": list(readback), "pass": payload == readback})
    return {
        "address_space": "local",
        "scratchpad_model": "per-workgroup local byte-addressed scratchpad proxy",
        "group_id": group_id,
        "group_base_offset": base,
        "group_size_bytes": LOCAL_GROUP_BYTES,
        "lane_roundtrips": lanes,
        "pass": all(row["pass"] for row in lanes),
    }


def run_scenario() -> dict[str, Any]:
    state = initial_state()
    pre_global = bytes(state.spaces["global"].data)
    host_to_device = dma_copy(state, name="h2d_copy", src_space="host", src_offset=0, dst_space="global", dst_offset=0, size=64)
    fill = dma_fill(state, name="dma_fill", dst_space="global", dst_offset=96, pattern=0xA5, size=32)

    lanes = [
        {"lane_id": lane_id, "address_space": "global", "offset": lane_id * 4, "size_bytes": 4}
        for lane_id in range(8)
    ]
    group = coalescing_group(lanes)
    loaded_words = []
    for lane in lanes:
        payload = kernel_load(
            state,
            name="coalesced_global_load",
            address_space="global",
            offset=int(lane["offset"]),
            size=int(lane["size_bytes"]),
            lane_id=int(lane["lane_id"]),
        )
        loaded_words.append(list(payload))

    store_payload = bytes((value ^ 0x5A) & 0xFF for word in loaded_words[:4] for value in word)
    kernel_store(state, name="kernel_global_store", address_space="global", offset=128, payload=store_payload)
    scratchpad = scratchpad_local_roundtrip(state)

    const_first = kernel_load(state, name="constant_read_first", address_space="constant", offset=0, size=16)
    const_second = kernel_load(state, name="constant_read_cached", address_space="constant", offset=0, size=16)
    d2h = dma_copy(state, name="d2h_copy", src_space="global", src_offset=128, dst_space="host", dst_offset=128, size=16)

    negative_cases = [
        record_negative(
            state,
            name="negative_global_bounds",
            operation="load",
            address_space="global",
            offset=GLOBAL_SIZE_BYTES - 2,
            size_bytes=4,
            expected_error="bounds",
            action=lambda: state.spaces["global"].read(GLOBAL_SIZE_BYTES - 2, 4),
        ),
        record_negative(
            state,
            name="negative_global_alignment",
            operation="load",
            address_space="global",
            offset=2,
            size_bytes=4,
            expected_error="alignment",
            action=lambda: state.spaces["global"].read(2, 4),
        ),
        record_negative(
            state,
            name="negative_constant_store",
            operation="store",
            address_space="constant",
            offset=0,
            size_bytes=4,
            expected_error="read-only",
            action=lambda: state.spaces["constant"].write(0, b"FAIL"),
        ),
        record_negative(
            state,
            name="negative_dma_alignment",
            operation="copy",
            address_space="global",
            offset=3,
            size_bytes=8,
            expected_error="alignment",
            action=lambda: dma_copy(state, name="bad_dma_alignment", src_space="host", src_offset=0, dst_space="global", dst_offset=3, size=8),
        ),
        record_negative(
            state,
            name="negative_local_bounds",
            operation="store",
            address_space="local",
            offset=LOCAL_SIZE_BYTES - 1,
            size_bytes=4,
            expected_error="bounds",
            action=lambda: state.spaces["local"].write(LOCAL_SIZE_BYTES - 1, b"ABCD"),
        ),
    ]

    checks = [
        {
            "name": "global_memory_h2d_visible_to_kernel",
            "pass": bytes(state.spaces["global"].data[:64]) == bytes(state.spaces["host"].data[:64]),
        },
        {
            "name": "dma_fill_pattern_visible",
            "pass": bytes(state.spaces["global"].data[96:128]) == bytes([0xA5]) * 32,
        },
        {
            "name": "kernel_global_store_visible_to_d2h",
            "pass": bytes(state.spaces["host"].data[128:144]) == store_payload,
        },
        {
            "name": "coalescing_reduces_transactions",
            "pass": group["coalesced_transactions"] < group["naive_transactions"] and group["group_count"] == 1,
        },
        {
            "name": "local_scratchpad_roundtrip",
            "pass": scratchpad["pass"] is True,
        },
        {
            "name": "constant_reads_are_read_only_and_cacheable_proxy",
            "pass": const_first == const_second
            and any(event["source"] == "constant_read_cached" and event.get("cache", {}).get("hit") for event in state.events),
        },
        {
            "name": "bounds_alignment_negative_cases",
            "pass": all(case.get("status") == "expected_error" and case.get("pass") is True for case in negative_cases),
        },
        {
            "name": "unified_dma_kernel_event_model",
            "pass": {event["category"] for event in state.events} >= {"dma", "kernel", "negative"}
            and all(event.get("schema") == EVENT_SCHEMA for event in state.events),
        },
    ]

    final_global = bytes(state.spaces["global"].data)
    categories: dict[str, int] = {}
    operations: dict[str, int] = {}
    for event in state.events:
        categories[event["category"]] = categories.get(event["category"], 0) + 1
        operations[event["operation"]] = operations.get(event["operation"], 0) + 1

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "ip_name": "Celviz GPGPU IP",
        "rank": 1,
        "stage": "memory_system_phase1",
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "semantics": {
            "global": "mutable device memory visible to DMA and kernel load/store events",
            "local": "mutable per-workgroup scratchpad proxy; not host DMA visible in this phase",
            "constant": "read-only device memory visible to kernel loads and cacheable in the proxy",
            "cache": "functional line-presence proxy with hit/miss evidence only",
            "coalescing": "lane accesses sharing an address-space segment collapse into one proxy transaction group",
            "dma_kernel_event_model": "DMA copy/fill and kernel load/store share one ordered event schema",
        },
        "parameters": {
            "global_size_bytes": GLOBAL_SIZE_BYTES,
            "local_size_bytes": LOCAL_SIZE_BYTES,
            "local_group_bytes": LOCAL_GROUP_BYTES,
            "constant_size_bytes": CONSTANT_SIZE_BYTES,
            "alignment_bytes": GLOBAL_ALIGNMENT_BYTES,
            "dma_alignment_bytes": DMA_ALIGNMENT_BYTES,
            "cache_line_bytes": CACHE_LINE_BYTES,
            "coalescing_segment_bytes": COALESCING_SEGMENT_BYTES,
        },
        "scenario": {
            "h2d_copy": host_to_device,
            "dma_fill": fill,
            "coalescing_group": group,
            "global_load_words_head": loaded_words[:4],
            "kernel_store_payload_head": hexdump_head(store_payload),
            "scratchpad_local": scratchpad,
            "constant_read": {
                "first_sha256": sha256_bytes(const_first),
                "second_sha256": sha256_bytes(const_second),
                "payload_head": hexdump_head(const_first),
            },
            "d2h_copy": d2h,
            "negative_cases": negative_cases,
        },
        "events": state.events,
        "summary": {
            "status": "pass" if all(check["pass"] for check in checks) else "fail",
            "event_count": len(state.events),
            "categories": categories,
            "operations": operations,
            "global_initial_sha256": sha256_bytes(pre_global),
            "global_final_sha256": sha256_bytes(final_global),
            "host_final_sha256": sha256_bytes(bytes(state.spaces["host"].data)),
            "event_trace_sha256": sha256_json(state.events),
        },
        "checks": checks,
        "claim_boundary": CLEAN_ROOM_SCOPE,
    }


def build_readme(evidence_path: Path) -> str:
    return "\n".join(
        [
            "# Celviz GPGPU IP Memory System Phase 1",
            "",
            "This directory contains focused clean-room memory-system evidence for Rank 1 GPGPU IP work.",
            "",
            "Covered semantics:",
            "",
            "- global memory: DMA-visible mutable device memory",
            "- local memory: per-workgroup scratchpad proxy",
            "- constant memory: read-only kernel-loadable memory",
            "- cache proxy: deterministic line-presence hit/miss evidence",
            "- coalescing proxy: lane segment grouping evidence",
            "- unified events: DMA copy/fill and kernel load/store share one ordered event schema",
            "- negative cases: bounds, alignment, and constant-store rejection",
            "",
            f"Primary evidence: `{evidence_path.name}`",
            "",
            "Scope: clean-room functional proxy only; no proprietary Vivante RTL, firmware, driver, SDK, compiler, cache microarchitecture, timing, PPA, or conformance claim.",
            "",
        ]
    )


def write_outputs(payload: Mapping[str, Any], artifact_root: Path) -> dict[str, str]:
    artifact_root.mkdir(parents=True, exist_ok=True)
    evidence_path = artifact_root / "memory_system_phase1_evidence.json"
    trace_path = artifact_root / "memory_event_trace.json"
    summary_path = artifact_root / "summary.json"
    log_path = artifact_root / "run.log"
    readme_path = artifact_root / "README.md"

    trace = {
        "schema": "celviz.gpgpu.memory_event_trace.v1",
        "event_schema": EVENT_SCHEMA,
        "event_count": len(payload["events"]),
        "events": payload["events"],
        "event_trace_sha256": payload["summary"]["event_trace_sha256"],
    }
    summary = {
        "schema": "celviz.gpgpu.memory_model.summary.v1",
        "status": payload["summary"]["status"],
        "checks": payload["checks"],
        "summary": payload["summary"],
        "evidence": evidence_path.as_posix(),
        "trace": trace_path.as_posix(),
    }

    hashes = {
        "memory_system_phase1_evidence.json": write_json(evidence_path, payload),
        "memory_event_trace.json": write_json(trace_path, trace),
        "summary.json": write_json(summary_path, summary),
    }
    readme_path.write_text(build_readme(evidence_path), encoding="utf-8")
    hashes["README.md"] = sha256_bytes(readme_path.read_bytes())

    lines = [
        "Celviz GPGPU IP memory system phase-1 model run",
        f"schema={SCHEMA}",
        f"artifact_root={artifact_root}",
        f"event_count={payload['summary']['event_count']}",
        "categories="
        + ",".join(f"{name}:{count}" for name, count in sorted(payload["summary"]["categories"].items())),
        "operations="
        + ",".join(f"{name}:{count}" for name, count in sorted(payload["summary"]["operations"].items())),
        "checks=" + ",".join(f"{check['name']}={str(check['pass']).lower()}" for check in payload["checks"]),
        f"event_trace_sha256={payload['summary']['event_trace_sha256']}",
        f"evidence={evidence_path}",
        f"trace={trace_path}",
        f"status={payload['summary']['status']}",
    ]
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    hashes["run.log"] = sha256_bytes(log_path.read_bytes())
    return hashes


def verify_payload(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema") != SCHEMA:
        errors.append(f"schema mismatch: {payload.get('schema')!r}")
    checks = payload.get("checks")
    if not isinstance(checks, list) or not checks:
        errors.append("checks must be a non-empty list")
    else:
        for check in checks:
            if not isinstance(check, dict) or check.get("pass") is not True:
                errors.append(f"check failed: {check}")
    events = payload.get("events")
    if not isinstance(events, list) or not events:
        errors.append("events must be a non-empty list")
    else:
        ids = [event.get("event_id") for event in events if isinstance(event, dict)]
        if ids != list(range(len(events))):
            errors.append("event ids are not contiguous from zero")
        categories = {event.get("category") for event in events if isinstance(event, dict)}
        if not {"dma", "kernel", "negative"}.issubset(categories):
            errors.append(f"missing event categories: {sorted({'dma', 'kernel', 'negative'} - categories)}")
        required_ops = {"copy", "fill", "load", "store"}
        ops = {event.get("operation") for event in events if isinstance(event, dict)}
        if not required_ops.issubset(ops):
            errors.append(f"missing event operations: {sorted(required_ops - ops)}")
    summary = payload.get("summary")
    if not isinstance(summary, dict) or summary.get("status") != "pass":
        errors.append("summary.status is not pass")
    return errors


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--print-summary", action="store_true")
    parser.add_argument("--verify", action="store_true", help="run focused verification and return non-zero on failure")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    payload = run_scenario()
    hashes = write_outputs(payload, args.artifact_root)
    errors = verify_payload(payload) if args.verify else []
    if args.print_summary:
        print(json.dumps({"summary": payload["summary"], "checks": payload["checks"], "hashes": hashes}, indent=2, sort_keys=True))
    else:
        print(f"wrote {args.artifact_root / 'memory_system_phase1_evidence.json'}")
        print(f"wrote {args.artifact_root / 'memory_event_trace.json'}")
        print(f"status={payload['summary']['status']}")
    if errors:
        for error in errors:
            print(f"memory_model_verify_error: {error}", file=sys.stderr)
        return 1
    return 0 if payload["summary"]["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
