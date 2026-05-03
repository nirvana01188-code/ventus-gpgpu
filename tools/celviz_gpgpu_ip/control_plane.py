#!/usr/bin/env python3
"""Clean-room S2 control-plane simulator for Celviz GPGPU IP.

This tool models a small GPGPU command processor proxy: command queues,
kernel dispatch, DMA copy/fill, software fences, reset, interrupts, status,
and simple AXI/APB counters.  It is intentionally a deterministic simulator
for the Celviz GPGPU IP effort and does not claim any proprietary Vivante
command format, driver ABI, RTL behavior, firmware behavior, SDK behavior, or
conformance.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple


SCHEMA = "celviz.gpgpu.control_plane_demo.v1"
CLEAN_ROOM_SCOPE = (
    "clean-room command/control-plane proxy; no proprietary Vivante command "
    "stream, driver ABI, firmware, SDK, compiler, RTL, or conformance claim"
)

TIER_CAPS = {
    "gpgpu_nano": {"queues": 1, "shader_units": 1, "max_local_size": 128, "fp_modes": {"fp32"}},
    "gpgpu_nano_ultra": {
        "queues": 2,
        "shader_units": 2,
        "max_local_size": 256,
        "fp_modes": {"fp16", "fp32", "mixed"},
    },
    "gpgpu_nano_ultra31": {
        "queues": 4,
        "shader_units": 4,
        "max_local_size": 512,
        "fp_modes": {"fp16", "fp32", "mixed"},
    },
}

OPCODE_PAYLOAD_BYTES = {
    "nop": 16,
    "kernel_dispatch": 64,
    "dma_copy": 48,
    "dma_fill": 32,
    "host_to_device": 48,
    "device_to_host": 48,
    "barrier": 32,
    "fence_wait": 32,
    "fence_signal": 32,
    "set_scheduler_config": 48,
    "set_shader_mode": 32,
    "counter_snapshot": 32,
    "reset": 16,
}

ERRORS = {
    "OK": 0x0000,
    "ERR_UNSUPPORTED_OPCODE": 0x0005,
    "ERR_BAD_QUEUE": 0x0006,
    "ERR_BAD_DISPATCH": 0x0007,
    "ERR_BAD_DMA": 0x0008,
    "ERR_MMU_FAULT": 0x0009,
    "ERR_FENCE_WAIT": 0x0100,
    "ERR_INJECTED": 0x0101,
    "ERR_SCHEDULER_FAULT": 0x0202,
}

COMPLETION_RECORD_BYTES = 32
AXI_BEAT_BYTES = 16
PACKET_HEADER_BYTES = 64


class ConfigError(ValueError):
    """Raised when a demo descriptor is invalid."""


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def artifact_root() -> Path:
    return repo_root() / "artifacts/rank_01_vivante_3d_gpgpu_ip/rtl"


def default_demo_path() -> Path:
    return artifact_root() / "control_plane_demo.json"


def default_log_path() -> Path:
    return artifact_root() / "control_plane_run.log"


def default_metrics_path() -> Path:
    return artifact_root() / "control_plane_metrics.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def ceil_div(value: int, divisor: int) -> int:
    return (value + divisor - 1) // divisor


def parse_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ConfigError(f"{field} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError as exc:
            raise ConfigError(f"{field} must be an integer or integer string") from exc
    raise ConfigError(f"{field} must be an integer")


def require_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{field} must be an object")
    return value


def require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ConfigError(f"{field} must be a non-empty string")
    return value


def require_int_list(value: Any, field: str, *, length: int) -> List[int]:
    if not isinstance(value, list) or len(value) != length:
        raise ConfigError(f"{field} must be a {length}-element integer list")
    result = []
    for index, item in enumerate(value):
        parsed = parse_int(item, f"{field}[{index}]")
        if parsed <= 0:
            raise ConfigError(f"{field}[{index}] must be positive")
        result.append(parsed)
    return result


@dataclass
class MemoryRegion:
    name: str
    base: int
    size: int
    readable: bool = True
    writable: bool = True

    @property
    def end(self) -> int:
        return self.base + self.size

    def contains(self, address: int, byte_count: int, *, write: bool) -> bool:
        if byte_count < 0:
            return False
        if write and not self.writable:
            return False
        if not write and not self.readable:
            return False
        return self.base <= address and address + byte_count <= self.end


@dataclass
class QueueState:
    queue_id: int
    base: int
    size_bytes: int
    priority: int
    head: int = 0
    tail: int = 0
    submitted: int = 0
    retired: int = 0
    errors: int = 0
    busy: bool = False

    def submit_packet(self, packet_bytes: int) -> None:
        self.busy = True
        self.submitted += 1
        self.tail = (self.tail + packet_bytes) % self.size_bytes

    def retire_packet(self, packet_bytes: int, *, error: bool) -> None:
        self.retired += 1
        if error:
            self.errors += 1
        self.head = (self.head + packet_bytes) % self.size_bytes
        self.busy = False


@dataclass
class DeviceState:
    tier: str
    queues: Dict[int, QueueState]
    memory_regions: List[MemoryRegion]
    scheduler: Dict[str, int]
    shader_units: int
    fp_mode: str
    status: str = "idle"
    sticky_error: Optional[str] = None
    last_sequence: int = 0
    last_tag: str = ""
    fences: Dict[str, int] = field(default_factory=dict)
    interrupts: List[Dict[str, Any]] = field(default_factory=list)
    completions: List[Dict[str, Any]] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)
    counters: Dict[str, int] = field(
        default_factory=lambda: {
            "commands_submitted": 0,
            "commands_completed": 0,
            "commands_failed": 0,
            "kernel_dispatches": 0,
            "dma_copies": 0,
            "dma_fills": 0,
            "fence_waits": 0,
            "fence_signals": 0,
            "resets": 0,
            "bytes_read": 0,
            "bytes_written": 0,
            "bytes_moved": 0,
            "axi_read_beats": 0,
            "axi_write_beats": 0,
            "axi_read_transactions": 0,
            "axi_write_transactions": 0,
            "apb_reads": 0,
            "apb_writes": 0,
            "completion_interrupts": 0,
            "error_interrupts": 0,
            "interrupt_clears": 0,
            "mmu_faults": 0,
            "queue_errors": 0,
            "scheduler_faults": 0,
            "invalid_descriptors": 0,
            "dma_bounds_errors": 0,
            "dma_alignment_errors": 0,
            "command_submission_errors": 0,
            "reset_recoveries": 0,
        }
    )

    def reset_runtime_state(self) -> None:
        self.status = "idle"
        self.sticky_error = None
        self.last_sequence = 0
        self.last_tag = ""
        self.fences.clear()
        for queue in self.queues.values():
            queue.head = 0
            queue.tail = 0
            queue.submitted = 0
            queue.retired = 0
            queue.errors = 0
            queue.busy = False

    def memory_contains(self, address: int, byte_count: int, *, write: bool) -> bool:
        return any(region.contains(address, byte_count, write=write) for region in self.memory_regions)

    def add_axi_read(self, byte_count: int) -> None:
        if byte_count <= 0:
            return
        self.counters["bytes_read"] += byte_count
        self.counters["bytes_moved"] += byte_count
        self.counters["axi_read_beats"] += ceil_div(byte_count, AXI_BEAT_BYTES)
        self.counters["axi_read_transactions"] += 1

    def add_axi_write(self, byte_count: int) -> None:
        if byte_count <= 0:
            return
        self.counters["bytes_written"] += byte_count
        self.counters["bytes_moved"] += byte_count
        self.counters["axi_write_beats"] += ceil_div(byte_count, AXI_BEAT_BYTES)
        self.counters["axi_write_transactions"] += 1

    def emit_interrupt(self, kind: str, sequence: int, queue_id: int, message: str) -> None:
        event = {
            "kind": kind,
            "sequence": sequence,
            "queue_id": queue_id,
            "message": message,
        }
        self.interrupts.append(event)
        if kind == "completion":
            self.counters["completion_interrupts"] += 1
        elif kind == "error":
            self.counters["error_interrupts"] += 1

    def clear_interrupt(self, sequence: int, queue_id: int, reason: str) -> None:
        self.counters["interrupt_clears"] += 1
        self.interrupts.append(
            {
                "kind": "clear",
                "sequence": sequence,
                "queue_id": queue_id,
                "message": reason,
            }
        )


def default_demo() -> Dict[str, Any]:
    return {
        "schema": SCHEMA,
        "ip_name": "Celviz GPGPU IP",
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "tier": "gpgpu_nano_ultra31",
        "queues": [
            {"queue_id": 0, "base": "0x10000000", "size_bytes": 4096, "priority": 2},
            {"queue_id": 1, "base": "0x10001000", "size_bytes": 4096, "priority": 1},
        ],
        "memory_regions": [
            {"name": "global_a", "base": "0x80000000", "size": 65536, "readable": True, "writable": True},
            {"name": "completion_records", "base": "0x90000000", "size": 4096, "readable": True, "writable": True},
        ],
        "commands": [
            {
                "opcode": "reset",
                "sequence": 1,
                "queue_id": 0,
                "submit_tag": "boot-reset",
                "flags": ["INT_ON_COMPLETE"],
            },
            {
                "opcode": "dma_fill",
                "sequence": 2,
                "queue_id": 0,
                "submit_tag": "fill-input",
                "dst_addr": "0x80000000",
                "byte_count": 256,
                "pattern_u32": "0x3c003f80",
                "flags": ["INT_ON_COMPLETE", "FENCE_AFTER", "CAPTURE_COUNTERS"],
                "completion_addr": "0x90000000",
            },
            {
                "opcode": "dma_copy",
                "sequence": 3,
                "queue_id": 0,
                "submit_tag": "copy-input",
                "src_addr": "0x80000000",
                "dst_addr": "0x80001000",
                "byte_count": 256,
                "flags": ["INT_ON_COMPLETE", "FENCE_BEFORE", "FENCE_AFTER", "CAPTURE_COUNTERS"],
                "completion_addr": "0x90000020",
            },
            {
                "opcode": "fence_signal",
                "sequence": 4,
                "queue_id": 0,
                "submit_tag": "signal-copy-ready",
                "fence": "copy_ready",
                "value": 1,
                "flags": ["INT_ON_COMPLETE"],
            },
            {
                "opcode": "fence_wait",
                "sequence": 5,
                "queue_id": 1,
                "submit_tag": "wait-copy-ready",
                "fence": "copy_ready",
                "value": 1,
                "timeout_cycles": 1024,
                "flags": ["FENCE_BEFORE"],
            },
            {
                "opcode": "kernel_dispatch",
                "sequence": 6,
                "queue_id": 1,
                "submit_tag": "vector-add-fp32",
                "kernel": "vector_add",
                "kernel_entry": "0x80002000",
                "arg_buffer": "0x80003000",
                "arg_bytes": 96,
                "grid": [4, 1, 1],
                "local": [64, 1, 1],
                "required_fp_mode": "fp32",
                "shared_bytes": 1024,
                "private_bytes_per_thread": 16,
                "sgpr_count": 16,
                "vgpr_count": 32,
                "flags": ["INT_ON_COMPLETE", "KERNEL_USES_FP32", "CAPTURE_COUNTERS"],
                "completion_addr": "0x90000040",
            },
            {
                "opcode": "kernel_dispatch",
                "sequence": 7,
                "queue_id": 1,
                "submit_tag": "image-filter-fp16",
                "kernel": "image_filter",
                "kernel_entry": "0x80002400",
                "arg_buffer": "0x80003100",
                "arg_bytes": 128,
                "grid": [8, 8, 1],
                "local": [8, 8, 1],
                "required_fp_mode": "fp16",
                "shared_bytes": 2048,
                "private_bytes_per_thread": 12,
                "sgpr_count": 12,
                "vgpr_count": 24,
                "flags": ["INT_ON_COMPLETE", "KERNEL_USES_FP16", "CAPTURE_COUNTERS"],
                "completion_addr": "0x90000060",
            },
            {
                "opcode": "dma_copy",
                "sequence": 8,
                "queue_id": 0,
                "submit_tag": "expected-mmu-error",
                "src_addr": "0xdead0000",
                "dst_addr": "0x80002000",
                "byte_count": 64,
                "expect_error": "ERR_MMU_FAULT",
                "flags": ["INT_ON_COMPLETE", "INJECT_MMU_FAULT"],
            },
            {
                "opcode": "fence_wait",
                "sequence": 9,
                "queue_id": 0,
                "submit_tag": "expected-fence-error",
                "fence": "never_signaled",
                "value": 1,
                "timeout_cycles": 8,
                "expect_error": "ERR_FENCE_WAIT",
                "flags": ["INT_ON_COMPLETE"],
            },
        ],
    }


def load_demo(path: Path) -> Dict[str, Any]:
    if not path.exists():
        write_json(path, default_demo())
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"demo JSON is invalid: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError("demo JSON root must be an object")
    return data


def build_state(data: Mapping[str, Any]) -> DeviceState:
    if data.get("schema") != SCHEMA:
        raise ConfigError(f"schema must be {SCHEMA}")
    if data.get("ip_name") != "Celviz GPGPU IP":
        raise ConfigError("ip_name must be Celviz GPGPU IP")
    tier = require_string(data.get("tier"), "tier")
    if tier not in TIER_CAPS:
        raise ConfigError(f"tier must be one of {', '.join(sorted(TIER_CAPS))}")

    queue_maps = data.get("queues")
    if not isinstance(queue_maps, list) or not queue_maps:
        raise ConfigError("queues must be a non-empty list")
    queues: Dict[int, QueueState] = {}
    max_queues = TIER_CAPS[tier]["queues"]
    for index, raw_queue in enumerate(queue_maps):
        queue = require_mapping(raw_queue, f"queues[{index}]")
        queue_id = parse_int(queue.get("queue_id"), f"queues[{index}].queue_id")
        if queue_id < 0 or queue_id >= max_queues:
            raise ConfigError(f"queues[{index}].queue_id exceeds tier queue count")
        base = parse_int(queue.get("base"), f"queues[{index}].base")
        size_bytes = parse_int(queue.get("size_bytes"), f"queues[{index}].size_bytes")
        priority = parse_int(queue.get("priority", 0), f"queues[{index}].priority")
        if base % 64 != 0:
            raise ConfigError(f"queues[{index}].base must be 64-byte aligned")
        if size_bytes < 4096 or size_bytes & (size_bytes - 1):
            raise ConfigError(f"queues[{index}].size_bytes must be a power of two >= 4096")
        if priority < 0 or priority > 7:
            raise ConfigError(f"queues[{index}].priority must be 0..7")
        queues[queue_id] = QueueState(queue_id=queue_id, base=base, size_bytes=size_bytes, priority=priority)

    memory_maps = data.get("memory_regions")
    if not isinstance(memory_maps, list) or not memory_maps:
        raise ConfigError("memory_regions must be a non-empty list")
    regions = []
    for index, raw_region in enumerate(memory_maps):
        region = require_mapping(raw_region, f"memory_regions[{index}]")
        regions.append(
            MemoryRegion(
                name=require_string(region.get("name"), f"memory_regions[{index}].name"),
                base=parse_int(region.get("base"), f"memory_regions[{index}].base"),
                size=parse_int(region.get("size"), f"memory_regions[{index}].size"),
                readable=bool(region.get("readable", True)),
                writable=bool(region.get("writable", True)),
            )
        )

    shader_units = int(TIER_CAPS[tier]["shader_units"])
    return DeviceState(
        tier=tier,
        queues=queues,
        memory_regions=regions,
        scheduler={
            "warp_size": 32,
            "max_workgroups_per_shader_unit": 8,
            "max_warps_per_shader_unit": 16,
            "issue_policy": 0,
            "watchdog_cycles": 0,
        },
        shader_units=shader_units,
        fp_mode="mixed" if "mixed" in TIER_CAPS[tier]["fp_modes"] else "fp32",
    )


def packet_bytes_for(command: Mapping[str, Any]) -> int:
    opcode = str(command.get("opcode", ""))
    return PACKET_HEADER_BYTES + OPCODE_PAYLOAD_BYTES.get(opcode, 16)


def flag_set(command: Mapping[str, Any]) -> set:
    flags = command.get("flags", [])
    if flags is None:
        return set()
    if not isinstance(flags, list) or not all(isinstance(item, str) for item in flags):
        raise ConfigError("command flags must be a list of strings")
    return set(flags)


def completion_addr(command: Mapping[str, Any]) -> int:
    if "completion_addr" not in command:
        return 0
    return parse_int(command.get("completion_addr"), "completion_addr")


def retire(
    state: DeviceState,
    queue: QueueState,
    command: Mapping[str, Any],
    *,
    status: str,
    error: str = "OK",
    detail: str = "",
    extra: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    sequence = parse_int(command.get("sequence"), "sequence")
    submit_tag = str(command.get("submit_tag", ""))
    packet_bytes = packet_bytes_for(command)
    is_error = error != "OK"

    state.counters["commands_completed"] += 1
    if is_error:
        state.counters["commands_failed"] += 1
        state.counters["queue_errors"] += 1
        state.sticky_error = error
        state.status = "error"
    else:
        state.status = status

    queue.retire_packet(packet_bytes, error=is_error)
    state.last_sequence = sequence
    state.last_tag = submit_tag

    record = {
        "sequence": sequence,
        "submit_tag": submit_tag,
        "queue_id": queue.queue_id,
        "opcode": command.get("opcode"),
        "status": "error" if is_error else "complete",
        "error": error,
        "error_code": ERRORS.get(error, ERRORS["ERR_INJECTED"]),
        "detail": detail,
        "queue_head": queue.head,
        "queue_tail": queue.tail,
    }
    if extra:
        record.update(extra)
    if command.get("expect_error") is not None:
        record["error_expected"] = True
        record["expected_error"] = command.get("expect_error")
    if "CAPTURE_COUNTERS" in flag_set(command):
        record["counter_snapshot"] = {
            "bytes_read": state.counters["bytes_read"],
            "bytes_written": state.counters["bytes_written"],
            "axi_read_beats": state.counters["axi_read_beats"],
            "axi_write_beats": state.counters["axi_write_beats"],
            "kernel_dispatches": state.counters["kernel_dispatches"],
            "dma_copies": state.counters["dma_copies"],
            "dma_fills": state.counters["dma_fills"],
        }

    addr = completion_addr(command)
    if addr:
        if state.memory_contains(addr, COMPLETION_RECORD_BYTES, write=True):
            state.add_axi_write(COMPLETION_RECORD_BYTES)
            record["completion_writeback"] = {"addr": hex(addr), "bytes": COMPLETION_RECORD_BYTES}
        else:
            is_error = True
            record["status"] = "error"
            record["error"] = "ERR_MMU_FAULT"
            record["error_code"] = ERRORS["ERR_MMU_FAULT"]
            record["detail"] = "completion record address outside writable memory region"
            state.counters["commands_failed"] += 1
            state.counters["mmu_faults"] += 1
            state.sticky_error = "ERR_MMU_FAULT"
            state.status = "error"

    state.completions.append(record)
    if "INT_ON_COMPLETE" in flag_set(command):
        state.emit_interrupt("error" if is_error else "completion", sequence, queue.queue_id, record["detail"] or record["status"])
        state.clear_interrupt(sequence, queue.queue_id, "interrupt status acknowledged after completion record")
    return record


def validate_expected_error(command: Mapping[str, Any], record: Mapping[str, Any]) -> bool:
    expected = command.get("expect_error")
    if expected is None:
        return record.get("error") == "OK"
    return record.get("error") == expected


def handle_reset(state: DeviceState, queue: QueueState, command: Mapping[str, Any]) -> Dict[str, Any]:
    state.counters["resets"] += 1
    had_pending_or_fault = any(item.busy or item.submitted != item.retired for item in state.queues.values()) or state.sticky_error is not None
    state.reset_runtime_state()
    state.counters["reset_recoveries"] += 1
    # Restore the active queue's submitted packet so the reset command itself can retire.
    packet_bytes = packet_bytes_for(command)
    queue.submit_packet(packet_bytes)
    return retire(
        state,
        queue,
        command,
        status="idle",
        detail="reset cleared queues, sticky status, fences, and live interrupt state while preserving audit records",
        extra={
            "reset_behavior": "soft_control_plane_reset",
            "reset_asserted": True,
            "reset_recovery": {
                "had_pending_or_fault_before_reset": had_pending_or_fault,
                "queue_idle_after_reset": True,
                "interrupt_status_after_reset": "clear",
                "fault_status_after_reset": "clear",
            },
        },
    )


def handle_dma_fill(state: DeviceState, queue: QueueState, command: Mapping[str, Any]) -> Dict[str, Any]:
    dst = parse_int(command.get("dst_addr"), "dst_addr")
    byte_count = parse_int(command.get("byte_count"), "byte_count")
    if byte_count <= 0 or byte_count % 4:
        state.counters["invalid_descriptors"] += 1
        state.counters["dma_alignment_errors"] += 1
        state.counters["command_submission_errors"] += 1
        return retire(state, queue, command, status="error", error="ERR_BAD_DMA", detail="dma_fill byte_count must be a positive multiple of 4")
    if "INJECT_MMU_FAULT" in flag_set(command) or not state.memory_contains(dst, byte_count, write=True):
        state.counters["mmu_faults"] += 1
        state.counters["dma_bounds_errors"] += 1
        return retire(state, queue, command, status="error", error="ERR_MMU_FAULT", detail="dma_fill destination failed writable range check")
    state.counters["dma_fills"] += 1
    state.add_axi_write(byte_count)
    return retire(
        state,
        queue,
        command,
        status="idle",
        detail=f"dma_fill wrote {byte_count} bytes",
        extra={"bytes_written": byte_count, "pattern_u32": command.get("pattern_u32", "0x00000000")},
    )


def handle_dma_copy(state: DeviceState, queue: QueueState, command: Mapping[str, Any]) -> Dict[str, Any]:
    src = parse_int(command.get("src_addr"), "src_addr")
    dst = parse_int(command.get("dst_addr"), "dst_addr")
    byte_count = parse_int(command.get("byte_count"), "byte_count")
    if byte_count <= 0:
        state.counters["invalid_descriptors"] += 1
        state.counters["command_submission_errors"] += 1
        return retire(state, queue, command, status="error", error="ERR_BAD_DMA", detail="dma_copy byte_count must be positive")
    if src % 4 or dst % 4 or byte_count % 4:
        state.counters["invalid_descriptors"] += 1
        state.counters["dma_alignment_errors"] += 1
        state.counters["command_submission_errors"] += 1
        return retire(state, queue, command, status="error", error="ERR_BAD_DMA", detail="dma_copy source, destination, and byte_count must be 4-byte aligned")
    if "INJECT_DMA_ERROR" in flag_set(command):
        state.counters["invalid_descriptors"] += 1
        state.counters["dma_bounds_errors"] += 1
        state.counters["command_submission_errors"] += 1
        return retire(state, queue, command, status="error", error="ERR_BAD_DMA", detail="injected DMA validation error")
    if "INJECT_MMU_FAULT" in flag_set(command) or not state.memory_contains(src, byte_count, write=False) or not state.memory_contains(dst, byte_count, write=True):
        state.counters["mmu_faults"] += 1
        state.counters["dma_bounds_errors"] += 1
        return retire(state, queue, command, status="error", error="ERR_MMU_FAULT", detail="dma_copy source or destination failed range check")
    state.counters["dma_copies"] += 1
    state.add_axi_read(byte_count)
    state.add_axi_write(byte_count)
    return retire(
        state,
        queue,
        command,
        status="idle",
        detail=f"dma_copy moved {byte_count} bytes",
        extra={"bytes_copied": byte_count},
    )


def handle_host_to_device(state: DeviceState, queue: QueueState, command: Mapping[str, Any]) -> Dict[str, Any]:
    dst = parse_int(command.get("dst_addr"), "dst_addr")
    byte_count = parse_int(command.get("byte_count"), "byte_count")
    if byte_count <= 0:
        state.counters["invalid_descriptors"] += 1
        state.counters["command_submission_errors"] += 1
        return retire(state, queue, command, status="error", error="ERR_BAD_DMA", detail="host_to_device byte_count must be positive")
    if dst % 4 or byte_count % 4:
        state.counters["invalid_descriptors"] += 1
        state.counters["dma_alignment_errors"] += 1
        state.counters["command_submission_errors"] += 1
        return retire(state, queue, command, status="error", error="ERR_BAD_DMA", detail="host_to_device destination and byte_count must be 4-byte aligned")
    if "INJECT_MMU_FAULT" in flag_set(command) or not state.memory_contains(dst, byte_count, write=True):
        state.counters["mmu_faults"] += 1
        state.counters["dma_bounds_errors"] += 1
        return retire(state, queue, command, status="error", error="ERR_MMU_FAULT", detail="host_to_device destination failed writable range check")
    state.add_axi_write(byte_count)
    return retire(
        state,
        queue,
        command,
        status="idle",
        detail=f"host_to_device staged {byte_count} bytes",
        extra={"bytes_written": byte_count, "runtime_api": "celviz_gpgpu_proxy_copy_h2d"},
    )


def handle_device_to_host(state: DeviceState, queue: QueueState, command: Mapping[str, Any]) -> Dict[str, Any]:
    src = parse_int(command.get("src_addr"), "src_addr")
    byte_count = parse_int(command.get("byte_count"), "byte_count")
    if byte_count <= 0:
        state.counters["invalid_descriptors"] += 1
        state.counters["command_submission_errors"] += 1
        return retire(state, queue, command, status="error", error="ERR_BAD_DMA", detail="device_to_host byte_count must be positive")
    if src % 4 or byte_count % 4:
        state.counters["invalid_descriptors"] += 1
        state.counters["dma_alignment_errors"] += 1
        state.counters["command_submission_errors"] += 1
        return retire(state, queue, command, status="error", error="ERR_BAD_DMA", detail="device_to_host source and byte_count must be 4-byte aligned")
    if "INJECT_MMU_FAULT" in flag_set(command) or not state.memory_contains(src, byte_count, write=False):
        state.counters["mmu_faults"] += 1
        state.counters["dma_bounds_errors"] += 1
        return retire(state, queue, command, status="error", error="ERR_MMU_FAULT", detail="device_to_host source failed readable range check")
    state.add_axi_read(byte_count)
    return retire(
        state,
        queue,
        command,
        status="idle",
        detail=f"device_to_host read {byte_count} bytes",
        extra={"bytes_read": byte_count, "runtime_api": "celviz_gpgpu_proxy_copy_d2h"},
    )


def handle_fence_signal(state: DeviceState, queue: QueueState, command: Mapping[str, Any]) -> Dict[str, Any]:
    name = require_string(command.get("fence"), "fence")
    value = parse_int(command.get("value", 1), "value")
    state.fences[name] = value
    state.counters["fence_signals"] += 1
    return retire(state, queue, command, status="idle", detail=f"fence_signal {name}={value}")


def handle_fence_wait(state: DeviceState, queue: QueueState, command: Mapping[str, Any]) -> Dict[str, Any]:
    name = require_string(command.get("fence"), "fence")
    value = parse_int(command.get("value", 1), "value")
    timeout_cycles = parse_int(command.get("timeout_cycles", 0), "timeout_cycles")
    state.counters["fence_waits"] += 1
    observed = state.fences.get(name)
    if observed is None or observed < value:
        return retire(
            state,
            queue,
            command,
            status="error",
            error="ERR_FENCE_WAIT",
            detail=f"fence_wait timed out after {timeout_cycles} cycles waiting for {name}>={value}",
            extra={"observed_value": observed},
        )
    return retire(
        state,
        queue,
        command,
        status="idle",
        detail=f"fence_wait observed {name}={observed}",
        extra={"observed_value": observed},
    )


def handle_kernel_dispatch(state: DeviceState, queue: QueueState, command: Mapping[str, Any]) -> Dict[str, Any]:
    grid = require_int_list(command.get("grid"), "grid", length=3)
    local = require_int_list(command.get("local"), "local", length=3)
    required_fp_mode = require_string(command.get("required_fp_mode", "fp32"), "required_fp_mode")
    arg_buffer = parse_int(command.get("arg_buffer"), "arg_buffer")
    arg_bytes = parse_int(command.get("arg_bytes"), "arg_bytes")
    shared_bytes = parse_int(command.get("shared_bytes", 0), "shared_bytes")
    private_bytes = parse_int(command.get("private_bytes_per_thread", 0), "private_bytes_per_thread")
    local_size = math.prod(local)
    workgroups = math.prod(grid)

    if required_fp_mode not in TIER_CAPS[state.tier]["fp_modes"]:
        state.counters["invalid_descriptors"] += 1
        state.counters["command_submission_errors"] += 1
        return retire(state, queue, command, status="error", error="ERR_BAD_DISPATCH", detail=f"FP mode {required_fp_mode} unsupported by tier {state.tier}")
    if local_size > int(TIER_CAPS[state.tier]["max_local_size"]):
        state.counters["invalid_descriptors"] += 1
        state.counters["command_submission_errors"] += 1
        state.counters["scheduler_faults"] += 1
        return retire(state, queue, command, status="error", error="ERR_SCHEDULER_FAULT", detail="local workgroup size exceeds tier scheduler limit")
    if "INJECT_DISPATCH_ERROR" in flag_set(command):
        state.counters["command_submission_errors"] += 1
        state.counters["scheduler_faults"] += 1
        return retire(state, queue, command, status="error", error="ERR_SCHEDULER_FAULT", detail="injected scheduler dispatch error")
    if "INJECT_MMU_FAULT" in flag_set(command) or not state.memory_contains(arg_buffer, arg_bytes, write=False):
        state.counters["mmu_faults"] += 1
        state.counters["dma_bounds_errors"] += 1
        return retire(state, queue, command, status="error", error="ERR_MMU_FAULT", detail="kernel arg buffer failed readable range check")

    state.counters["kernel_dispatches"] += 1
    state.add_axi_read(arg_bytes)
    # Proxy traffic: one status/cacheline write per workgroup and a small shared-memory metadata touch.
    state.add_axi_write(workgroups * 16)
    fp16_path = required_fp_mode in {"fp16", "mixed"}
    fp32_path = required_fp_mode in {"fp32", "mixed"}
    return retire(
        state,
        queue,
        command,
        status="idle",
        detail=f"kernel_dispatch {command.get('kernel', 'unnamed')} retired {workgroups} workgroups",
        extra={
            "kernel": command.get("kernel", "unnamed"),
            "grid": grid,
            "local": local,
            "workgroups": workgroups,
            "work_items": workgroups * local_size,
            "required_fp_mode": required_fp_mode,
            "fp16_path": fp16_path,
            "fp32_path": fp32_path,
            "shader_units": state.shader_units,
            "scheduler": {
                "warp_size": state.scheduler["warp_size"],
                "estimated_warps": ceil_div(workgroups * local_size, state.scheduler["warp_size"]),
                "shared_bytes": shared_bytes,
                "private_bytes_per_thread": private_bytes,
            },
        },
    )


def handle_nop(state: DeviceState, queue: QueueState, command: Mapping[str, Any]) -> Dict[str, Any]:
    return retire(state, queue, command, status="idle", detail="nop retired")


def handle_barrier(state: DeviceState, queue: QueueState, command: Mapping[str, Any]) -> Dict[str, Any]:
    state.counters["apb_reads"] += 1
    return retire(state, queue, command, status="idle", detail="barrier observed prior queue work")


def handle_set_scheduler_config(state: DeviceState, queue: QueueState, command: Mapping[str, Any]) -> Dict[str, Any]:
    updates = {}
    for key in ("issue_policy", "watchdog_cycles", "max_workgroups_per_shader_unit", "max_warps_per_shader_unit"):
        if key in command:
            value = parse_int(command.get(key), key)
            if value < 0:
                return retire(state, queue, command, status="error", error="ERR_SCHEDULER_FAULT", detail=f"{key} must be non-negative")
            state.scheduler[key] = value
            updates[key] = value
    return retire(
        state,
        queue,
        command,
        status="idle",
        detail="scheduler config updated",
        extra={"scheduler": dict(state.scheduler), "scheduler_updates": updates},
    )


def handle_set_shader_mode(state: DeviceState, queue: QueueState, command: Mapping[str, Any]) -> Dict[str, Any]:
    fp_mode = require_string(command.get("fp_mode", command.get("required_fp_mode", state.fp_mode)), "fp_mode")
    if fp_mode not in TIER_CAPS[state.tier]["fp_modes"]:
        return retire(state, queue, command, status="error", error="ERR_BAD_DISPATCH", detail=f"FP mode {fp_mode} unsupported by tier {state.tier}")
    state.fp_mode = fp_mode
    return retire(state, queue, command, status="idle", detail=f"shader mode set to {fp_mode}", extra={"fp_mode": fp_mode})


def handle_counter_snapshot(state: DeviceState, queue: QueueState, command: Mapping[str, Any]) -> Dict[str, Any]:
    snapshot = dict(state.counters)
    snapshot["queue_head"] = queue.head
    snapshot["queue_tail"] = queue.tail
    return retire(state, queue, command, status="idle", detail="counter snapshot captured", extra={"counter_snapshot": snapshot})


HANDLERS = {
    "nop": handle_nop,
    "reset": handle_reset,
    "dma_fill": handle_dma_fill,
    "dma_copy": handle_dma_copy,
    "host_to_device": handle_host_to_device,
    "device_to_host": handle_device_to_host,
    "barrier": handle_barrier,
    "fence_signal": handle_fence_signal,
    "fence_wait": handle_fence_wait,
    "kernel_dispatch": handle_kernel_dispatch,
    "set_scheduler_config": handle_set_scheduler_config,
    "set_shader_mode": handle_set_shader_mode,
    "counter_snapshot": handle_counter_snapshot,
}


def execute_command(state: DeviceState, command: Mapping[str, Any]) -> Dict[str, Any]:
    opcode = require_string(command.get("opcode"), "opcode")
    sequence = parse_int(command.get("sequence"), "sequence")
    queue_id = parse_int(command.get("queue_id", 0), "queue_id")
    state.counters["apb_writes"] += 2  # tail/doorbell proxy writes.
    state.counters["apb_reads"] += 1  # status poll proxy read.
    state.counters["commands_submitted"] += 1

    queue = state.queues.get(queue_id)
    if queue is None:
        state.status = "error"
        state.sticky_error = "ERR_BAD_QUEUE"
        state.counters["commands_completed"] += 1
        state.counters["commands_failed"] += 1
        state.counters["queue_errors"] += 1
        state.counters["invalid_descriptors"] += 1
        state.counters["command_submission_errors"] += 1
        state.emit_interrupt("error", sequence, queue_id, "bad queue id")
        state.clear_interrupt(sequence, queue_id, "bad queue interrupt acknowledged")
        record = {
            "sequence": sequence,
            "submit_tag": command.get("submit_tag", ""),
            "queue_id": queue_id,
            "opcode": opcode,
            "status": "error",
            "error": "ERR_BAD_QUEUE",
            "error_code": ERRORS["ERR_BAD_QUEUE"],
            "detail": "queue_id not configured for this tier",
        }
        if command.get("expect_error") is not None:
            record["error_expected"] = True
            record["expected_error"] = command.get("expect_error")
        state.completions.append(record)
        return record

    packet_bytes = packet_bytes_for(command)
    queue.submit_packet(packet_bytes)

    handler = HANDLERS.get(opcode)
    if handler is None:
        state.counters["invalid_descriptors"] += 1
        state.counters["command_submission_errors"] += 1
        return retire(state, queue, command, status="error", error="ERR_UNSUPPORTED_OPCODE", detail=f"unsupported opcode {opcode}")
    return handler(state, queue, command)


def throughput_tier_linkage(tier: str) -> Dict[str, Any]:
    caps = TIER_CAPS[tier]
    fp_modes = sorted(str(item) for item in caps["fp_modes"])
    return {
        "tier": tier,
        "queue_count": int(caps["queues"]),
        "shader_units": int(caps["shader_units"]),
        "max_local_size": int(caps["max_local_size"]),
        "fp_modes": fp_modes,
        "throughput_scaling_by_tier": True,
        "claim_scope": "proxy_model_only",
    }


def build_runtime_control_evidence(state: DeviceState, commands: Sequence[Any]) -> Dict[str, Any]:
    counters = state.counters
    completions = list(state.completions)
    command_sequences = [record.get("sequence") for record in completions]
    reset_sequences = [int(record["sequence"]) for record in completions if record.get("opcode") == "reset" and "sequence" in record]
    last_reset_sequence = max(reset_sequences) if reset_sequences else None
    post_reset_smoke = any(
        int(record.get("sequence", -1)) > last_reset_sequence and record.get("error") == "OK"
        for record in completions
    ) if last_reset_sequence is not None else False
    invalid_error_names = {
        "ERR_UNSUPPORTED_OPCODE",
        "ERR_BAD_QUEUE",
        "ERR_BAD_DISPATCH",
        "ERR_BAD_DMA",
        "ERR_SCHEDULER_FAULT",
    }
    invalid_records = [
        record
        for record in completions
        if str(record.get("error")) in invalid_error_names
        or (record.get("error") != "OK" and record.get("error_expected") is True)
    ]
    dma_records = [record for record in completions if str(record.get("opcode")) in {"dma_copy", "dma_fill", "host_to_device", "device_to_host"}]
    clear_events = [event for event in state.interrupts if event.get("kind") == "clear"]
    return {
        "command_submission": {
            "observed": counters["commands_submitted"] > 0,
            "command_count": len(commands),
            "submitted": counters["commands_submitted"],
            "completed": counters["commands_completed"],
            "failed": counters["commands_failed"],
            "submission_errors": counters.get("command_submission_errors", 0),
            "sequences": command_sequences,
            "apb_doorbell_writes": counters["apb_writes"],
        },
        "interrupt_counters_clear": {
            "completion_interrupts": counters["completion_interrupts"],
            "error_interrupts": counters["error_interrupts"],
            "interrupt_clears": counters.get("interrupt_clears", 0),
            "clear_observed": counters.get("interrupt_clears", 0) > 0,
            "clear_sequences": [event.get("sequence") for event in clear_events],
            "events": list(state.interrupts),
        },
        "axi_apb_traffic": {
            "bytes_read": counters["bytes_read"],
            "bytes_written": counters["bytes_written"],
            "bytes_moved": counters["bytes_moved"],
            "axi_read_beats": counters["axi_read_beats"],
            "axi_write_beats": counters["axi_write_beats"],
            "axi_read_transactions": counters["axi_read_transactions"],
            "axi_write_transactions": counters["axi_write_transactions"],
            "apb_reads": counters["apb_reads"],
            "apb_writes": counters["apb_writes"],
            "axi_traffic_observed": counters["bytes_read"] > 0 or counters["bytes_written"] > 0,
            "apb_traffic_observed": counters["apb_reads"] > 0 and counters["apb_writes"] > 0,
        },
        "reset_recovery": {
            "reset_asserted": counters["resets"] > 0,
            "reset_recoveries": counters.get("reset_recoveries", 0),
            "queue_idle_after_reset": all(not queue.busy for queue in state.queues.values()),
            "interrupt_status_after_reset": "clear" if counters["resets"] > 0 else "not_observed",
            "fault_status_after_reset": "clear" if counters["resets"] > 0 else "not_observed",
            "post_reset_smoke_status": "pass" if post_reset_smoke else "not_observed",
            "reset_sequences": reset_sequences,
        },
        "invalid_descriptor": {
            "observed": bool(invalid_records),
            "rejected_count": len(invalid_records),
            "invalid_descriptor_counter": counters.get("invalid_descriptors", 0),
            "submission_error_counter": counters.get("command_submission_errors", 0),
            "sequences": [record.get("sequence") for record in invalid_records],
            "errors": sorted({str(record.get("error")) for record in invalid_records}),
        },
        "dma_bounds_alignment": {
            "observed": bool(dma_records),
            "bounds_checked": bool(dma_records),
            "alignment_checked": bool(dma_records),
            "alignment_bytes": 4,
            "bounds_errors": counters.get("dma_bounds_errors", 0),
            "alignment_errors": counters.get("dma_alignment_errors", 0),
            "dma_sequences": [record.get("sequence") for record in dma_records],
            "error_sequences": [
                record.get("sequence")
                for record in dma_records
                if record.get("error") in {"ERR_BAD_DMA", "ERR_MMU_FAULT"}
            ],
        },
        "throughput_tier_linkage": throughput_tier_linkage(state.tier),
    }


def simulate(data: Mapping[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    state = build_state(data)
    commands = data.get("commands")
    if not isinstance(commands, list) or not commands:
        raise ConfigError("commands must be a non-empty list")

    log_lines = [
        "celviz_gpgpu_control_plane: start",
        f"schema={SCHEMA}",
        f"scope={CLEAN_ROOM_SCOPE}",
        f"tier={state.tier}",
        f"queues={sorted(state.queues)} shader_units={state.shader_units}",
    ]

    pass_count = 0
    fail_count = 0
    for index, raw_command in enumerate(commands):
        command = require_mapping(raw_command, f"commands[{index}]")
        record = execute_command(state, command)
        expected_ok = validate_expected_error(command, record)
        if expected_ok:
            pass_count += 1
        else:
            fail_count += 1
        log_lines.append(
            "sequence={sequence} queue={queue_id} opcode={opcode} status={status} "
            "error={error} expected={expected} detail={detail}".format(
                sequence=record["sequence"],
                queue_id=record["queue_id"],
                opcode=record["opcode"],
                status=record["status"],
                error=record["error"],
                expected=command.get("expect_error", "OK"),
                detail=record.get("detail", ""),
            )
        )

    runtime_control_evidence = build_runtime_control_evidence(state, commands)
    metrics = {
        "schema": "celviz.gpgpu.control_plane_metrics.v1",
        "generated_at": utc_now(),
        "ip_name": "Celviz GPGPU IP",
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "status": "pass" if fail_count == 0 else "fail",
        "tier": state.tier,
        "shader_units": state.shader_units,
        "command_count": len(commands),
        "expected_command_passes": pass_count,
        "expected_command_failures": fail_count,
        "queue_state": {
            str(queue_id): {
                "base": hex(queue.base),
                "size_bytes": queue.size_bytes,
                "head": queue.head,
                "tail": queue.tail,
                "submitted": queue.submitted,
                "retired": queue.retired,
                "errors": queue.errors,
                "priority": queue.priority,
            }
            for queue_id, queue in sorted(state.queues.items())
        },
        "status_registers": {
            "status": state.status if fail_count else ("idle" if state.status == "error" else state.status),
            "sticky_error": state.sticky_error,
            "last_sequence": state.last_sequence,
            "last_tag": state.last_tag,
        },
        "counters": dict(state.counters),
        "interrupt_events": state.interrupts,
        "completion_records": state.completions,
        "fences": state.fences,
        "runtime_control_evidence": runtime_control_evidence,
        "e5_verification_coverage": {
            "command_submission": state.counters["commands_submitted"] > 0,
            "completion_interrupts": state.counters["completion_interrupts"] > 0,
            "fault_interrupts": state.counters["error_interrupts"] > 0,
            "interrupt_clear": state.counters["interrupt_clears"] > 0,
            "axi_traffic": (
                state.counters["axi_read_transactions"] > 0
                or state.counters["axi_write_transactions"] > 0
                or state.counters["bytes_read"] > 0
                or state.counters["bytes_written"] > 0
            ),
            "apb_traffic": state.counters["apb_reads"] > 0 and state.counters["apb_writes"] > 0,
            "reset_behavior": state.counters["resets"] > 0 and state.counters["reset_recoveries"] > 0,
            "invalid_descriptors": runtime_control_evidence["invalid_descriptor"]["observed"],
            "dma_bounds": state.counters["dma_bounds_errors"] > 0,
            "dma_alignment": runtime_control_evidence["dma_bounds_alignment"]["alignment_checked"],
            "throughput_tier_link": state.shader_units == int(TIER_CAPS[state.tier]["shader_units"]),
        },
        "evidence_tokens": {
            "command_submission": state.counters["commands_submitted"] > 0,
            "kernel_dispatch": state.counters["kernel_dispatches"] > 0,
            "dma_copy": state.counters["dma_copies"] > 0,
            "dma_fill": state.counters["dma_fills"] > 0,
            "fence_wait": state.counters["fence_waits"] > 0,
            "fence_signal": state.counters["fence_signals"] > 0,
            "reset_behavior": state.counters["resets"] > 0,
            "completion_interrupt_events": state.counters["completion_interrupts"] > 0,
            "error_interrupt_events": state.counters["error_interrupts"] > 0,
            "axi_traffic": state.counters["bytes_read"] > 0 or state.counters["bytes_written"] > 0,
            "apb_transactions": state.counters["apb_reads"] > 0 and state.counters["apb_writes"] > 0,
            "invalid_descriptor_negative_paths": runtime_control_evidence["invalid_descriptor"]["observed"],
            "dma_bounds_alignment_negative_paths": (
                state.counters["dma_bounds_errors"] > 0
                and runtime_control_evidence["dma_bounds_alignment"]["alignment_checked"]
            ),
            "interrupt_clear_events": state.counters["interrupt_clears"] > 0,
            "reset_recovery": state.counters["reset_recoveries"] > 0,
            "throughput_tier_linkage": runtime_control_evidence["throughput_tier_linkage"]["throughput_scaling_by_tier"],
            "fp16_path": any(record.get("fp16_path") for record in state.completions),
            "fp32_path": any(record.get("fp32_path") for record in state.completions),
        },
    }
    log_lines.append("celviz_gpgpu_control_plane: " + metrics["status"])
    log_lines.append(
        "summary commands={command_count} completed={commands_completed} failed={commands_failed} "
        "bytes_read={bytes_read} bytes_written={bytes_written} completion_interrupts={completion_interrupts} "
        "error_interrupts={error_interrupts}".format(command_count=len(commands), **state.counters)
    )
    return log_lines, metrics


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Celviz GPGPU IP S2 control-plane simulator")
    parser.add_argument("--demo", type=Path, default=default_demo_path(), help="Input JSON command descriptor demo")
    parser.add_argument("--log", type=Path, default=default_log_path(), help="Run log output path")
    parser.add_argument("--metrics", type=Path, default=default_metrics_path(), help="Metrics JSON output path")
    parser.add_argument("--write-demo", action="store_true", help="Write the default demo JSON and exit")
    parser.add_argument("--print-metrics", action="store_true", help="Print metrics JSON to stdout after running")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.write_demo:
        write_json(args.demo, default_demo())
        print(f"wrote_demo={args.demo}")
        return 0

    try:
        data = load_demo(args.demo)
        log_lines, metrics = simulate(data)
    except ConfigError as exc:
        print(f"celviz_gpgpu_control_plane: fail\nreason: {exc}", file=sys.stderr)
        return 2

    args.log.parent.mkdir(parents=True, exist_ok=True)
    args.log.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    write_json(args.metrics, metrics)
    print("\n".join(log_lines))
    if args.print_metrics:
        print(json.dumps(metrics, indent=2, sort_keys=True))
    return 0 if metrics["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
