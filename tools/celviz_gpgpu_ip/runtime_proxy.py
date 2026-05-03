#!/usr/bin/env python3
"""Runtime command layer for the Celviz GPGPU IP Ventus proxy.

This module is intentionally small and dependency-free.  It accepts a runtime
JSON command stream or a Ventus-style kernel metadata JSON, validates the queue
and memory contract, executes the command sequence through the local
control-plane model, and optionally binds to a compiled ``ventus_rtlsim`` shared
library for host/device copy and native metadata dispatch calls.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

try:  # Support both ``python runtime_proxy.py`` and package-style imports.
    from . import control_plane
except ImportError:  # pragma: no cover - direct script fallback
    import control_plane  # type: ignore


RUNTIME_SCHEMA = "celviz.gpgpu.runtime_commands.v1"
METADATA_SCHEMA = "celviz.gpgpu.ventus_metadata.v1"
STATUS_SCHEMA = "celviz.gpgpu.runtime_status.v1"
METRICS_SCHEMA = "celviz.gpgpu.runtime_metrics.v1"
ABI_VERSION = 1
CELVIZ_GPGPU_RUNTIME_PROXY_MAGIC = "0x31555643"
ABI_MAGIC = CELVIZ_GPGPU_RUNTIME_PROXY_MAGIC

CLEAN_ROOM_SCOPE = (
    "clean-room runtime command proxy aligned to the public Ventus rtlsim C API; "
    "not OpenCL conformance, not Vivante command-stream compatibility, and not "
    "a proprietary driver/firmware ABI"
)

TIER_ALIASES = {
    "gpgpu_nano": "gpgpu_nano",
    "nano": "gpgpu_nano",
    "celviz-nano-proxy": "gpgpu_nano",
    "gpgpu_nano_ultra": "gpgpu_nano_ultra",
    "nano_ultra": "gpgpu_nano_ultra",
    "micro": "gpgpu_nano_ultra",
    "celviz-micro-proxy": "gpgpu_nano_ultra",
    "gpgpu_nano_ultra31": "gpgpu_nano_ultra31",
    "nano_ultra31": "gpgpu_nano_ultra31",
    "small": "gpgpu_nano_ultra31",
    "full": "gpgpu_nano_ultra31",
    "celviz-small-proxy": "gpgpu_nano_ultra31",
    "celviz-full-proxy": "gpgpu_nano_ultra31",
}

TIER_IDS = {
    "gpgpu_nano": 1,
    "gpgpu_nano_ultra": 2,
    "gpgpu_nano_ultra31": 3,
}

OPCODE_ENUM = {
    "nop": 0x0000,
    "kernel_dispatch": 0x0001,
    "dma_copy": 0x0002,
    "dma_fill": 0x0003,
    "barrier": 0x0004,
    "set_scheduler_config": 0x0005,
    "set_shader_mode": 0x0006,
    "counter_snapshot": 0x0007,
    # Proxy runtime API extensions.  These map to celviz_gpgpu_proxy_copy_*()
    # helpers in celviz_gpgpu_runtime_proxy.h rather than packet opcodes.
    "host_to_device": 0x1001,
    "device_to_host": 0x1002,
    "fence_wait": 0x1010,
    "fence_signal": 0x1011,
    "reset": 0x1012,
}

STATUS_ENUM = {
    "new": 0,
    "queued": 1,
    "submitted": 2,
    "running": 3,
    "complete": 4,
    "error": 5,
    "cancelled": 6,
    "timeout": 7,
}

ERROR_ENUM = {
    "OK": 0x0000,
    "ERR_UNSUPPORTED_OPCODE": 0x0005,
    "ERR_BAD_QUEUE": 0x0006,
    "ERR_BAD_DISPATCH": 0x0007,
    "ERR_BAD_DMA": 0x0008,
    "ERR_MMU_FAULT": 0x0009,
    "ERR_FENCE_WAIT": 0x0100,
    "ERR_INJECTED": 0x0101,
    "ERR_RTLSIM_FATAL": 0x0200,
    "ERR_RTLSIM_TIME_EXCEEDED": 0x0201,
    "ERR_SCHEDULER_FAULT": 0x0202,
}

OPCODE_NAMES = {value: name for name, value in OPCODE_ENUM.items()}
STATUS_NAMES = {value: name for name, value in STATUS_ENUM.items()}
ERROR_NAMES = {value: name for name, value in ERROR_ENUM.items()}

OPCODE_ALIASES = {
    "enqueue_kernel": "kernel_dispatch",
    "kernel": "kernel_dispatch",
    "copy_h2d": "host_to_device",
    "h2d": "host_to_device",
    "write_buffer": "host_to_device",
    "copy_d2h": "device_to_host",
    "d2h": "device_to_host",
    "read_buffer": "device_to_host",
    "fence": "fence_signal",
    "counter": "counter_snapshot",
}


class RuntimeProxyError(ValueError):
    """Raised when runtime command input does not match the proxy ABI."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path, label: str) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeProxyError(f"{label} JSON not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeProxyError(f"{label} JSON is invalid: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeProxyError(f"{label} JSON root must be an object")
    return data


def parse_int(value: Any, field: str, *, default: Optional[int] = None) -> int:
    if value is None and default is not None:
        return default
    if isinstance(value, bool):
        raise RuntimeProxyError(f"{field} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError as exc:
            raise RuntimeProxyError(f"{field} must be an integer or integer string") from exc
    raise RuntimeProxyError(f"{field} must be an integer")


def require_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeProxyError(f"{field} must be an object")
    return value


def require_list(value: Any, field: str) -> List[Any]:
    if not isinstance(value, list):
        raise RuntimeProxyError(f"{field} must be a list")
    return value


def require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeProxyError(f"{field} must be a non-empty string")
    return value


def normalize_tier(value: Any) -> str:
    tier = require_string(value, "tier")
    normalized = TIER_ALIASES.get(tier)
    if normalized is None:
        raise RuntimeProxyError(f"tier must be one of {', '.join(sorted(TIER_ALIASES))}")
    return normalized


def int_list3(value: Any, field: str, *, default: Optional[Sequence[int]] = None) -> List[int]:
    if value is None and default is not None:
        return [int(item) for item in default]
    if not isinstance(value, list) or len(value) not in {1, 2, 3}:
        raise RuntimeProxyError(f"{field} must be a 1-, 2-, or 3-element integer list")
    result = [parse_int(item, f"{field}[{index}]") for index, item in enumerate(value)]
    if any(item <= 0 for item in result):
        raise RuntimeProxyError(f"{field} entries must be positive")
    while len(result) < 3:
        result.append(1)
    return result


def normalize_flags(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, int):
        flags = []
        if value & 1:
            flags.append("INT_ON_COMPLETE")
        if value & 2:
            flags.append("CAPTURE_COUNTERS")
        return flags
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RuntimeProxyError("flags must be a string list or integer bitmask")
    return list(value)


def queue_count_for_tier(tier: str) -> int:
    return int(control_plane.TIER_CAPS[tier]["queues"])


def default_queues(tier: str) -> List[Dict[str, Any]]:
    queues = []
    for queue_id in range(queue_count_for_tier(tier)):
        queues.append(
            {
                "queue_id": queue_id,
                "base": hex(0x10000000 + queue_id * 0x1000),
                "size_bytes": 4096,
                "priority": max(0, queue_count_for_tier(tier) - queue_id - 1),
            }
        )
    return queues


def normalize_queues(data: Mapping[str, Any], tier: str) -> List[Dict[str, Any]]:
    raw_queues = data.get("queues")
    if raw_queues is None:
        return default_queues(tier)
    queues = require_list(raw_queues, "queues")
    if not queues:
        raise RuntimeProxyError("queues must not be empty")
    normalized: List[Dict[str, Any]] = []
    seen = set()
    for index, raw_queue in enumerate(queues):
        queue = require_mapping(raw_queue, f"queues[{index}]")
        queue_id = parse_int(queue.get("queue_id", queue.get("id", index)), f"queues[{index}].queue_id")
        if queue_id in seen:
            raise RuntimeProxyError(f"duplicate queue_id: {queue_id}")
        seen.add(queue_id)
        normalized.append(
            {
                "queue_id": queue_id,
                "base": hex(parse_int(queue.get("base", queue.get("ring_base", 0x10000000 + queue_id * 0x1000)), f"queues[{index}].base")),
                "size_bytes": parse_int(queue.get("size_bytes", queue.get("ring_size_bytes", 4096)), f"queues[{index}].size_bytes"),
                "priority": parse_int(queue.get("priority", 0), f"queues[{index}].priority"),
            }
        )
    return normalized


def normalize_memory_regions(data: Mapping[str, Any]) -> List[Dict[str, Any]]:
    regions: List[Dict[str, Any]] = []
    for index, raw_region in enumerate(data.get("memory_regions", []) or []):
        region = require_mapping(raw_region, f"memory_regions[{index}]")
        regions.append(
            {
                "name": require_string(region.get("name"), f"memory_regions[{index}].name"),
                "base": hex(parse_int(region.get("base"), f"memory_regions[{index}].base")),
                "size": parse_int(region.get("size", region.get("size_bytes")), f"memory_regions[{index}].size"),
                "readable": bool(region.get("readable", True)),
                "writable": bool(region.get("writable", True)),
            }
        )

    for index, raw_buffer in enumerate(data.get("buffers", []) or []):
        buffer = require_mapping(raw_buffer, f"buffers[{index}]")
        address = buffer.get("device_address", buffer.get("base"))
        if address is None:
            continue
        flags = str(buffer.get("access", "read_write"))
        regions.append(
            {
                "name": str(buffer.get("id", f"buffer_{index}")),
                "base": hex(parse_int(address, f"buffers[{index}].device_address")),
                "size": parse_int(buffer.get("size_bytes", buffer.get("alloc_size_bytes")), f"buffers[{index}].size_bytes"),
                "readable": "write_only" not in flags and flags != "write",
                "writable": "read_only" not in flags and flags != "read",
            }
        )
    if not regions:
        regions = [
            {"name": "runtime_global", "base": "0x80000000", "size": 0x100000, "readable": True, "writable": True},
            {"name": "runtime_completion", "base": "0x90000000", "size": 0x10000, "readable": True, "writable": True},
        ]
    return regions


def command_opcode(raw_opcode: Any, field: str) -> str:
    opcode = require_string(raw_opcode, field)
    opcode = OPCODE_ALIASES.get(opcode, opcode)
    if opcode not in OPCODE_ENUM:
        raise RuntimeProxyError(f"{field} unsupported by runtime proxy: {opcode}")
    return opcode


def normalize_commands(data: Mapping[str, Any]) -> List[Dict[str, Any]]:
    raw_commands = require_list(data.get("commands"), "commands")
    if not raw_commands:
        raise RuntimeProxyError("commands must not be empty")
    normalized: List[Dict[str, Any]] = []
    for index, raw_command in enumerate(raw_commands):
        command = dict(require_mapping(raw_command, f"commands[{index}]"))
        opcode = command_opcode(command.get("opcode"), f"commands[{index}].opcode")
        command["opcode"] = opcode
        command["sequence"] = parse_int(command.get("sequence", index + 1), f"commands[{index}].sequence")
        command["queue_id"] = parse_int(command.get("queue_id", 0), f"commands[{index}].queue_id")
        command["submit_tag"] = str(command.get("submit_tag", f"{opcode}-{command['sequence']}"))
        command["flags"] = normalize_flags(command.get("flags", ["INT_ON_COMPLETE", "CAPTURE_COUNTERS"]))
        if opcode == "host_to_device":
            dst = command.get("dst_addr", command.get("dst", command.get("device_address")))
            command["dst_addr"] = hex(parse_int(dst, f"commands[{index}].dst_addr"))
            command["byte_count"] = parse_int(command.get("byte_count", command.get("size_bytes")), f"commands[{index}].byte_count")
        elif opcode == "device_to_host":
            src = command.get("src_addr", command.get("src", command.get("device_address")))
            command["src_addr"] = hex(parse_int(src, f"commands[{index}].src_addr"))
            command["byte_count"] = parse_int(command.get("byte_count", command.get("size_bytes")), f"commands[{index}].byte_count")
        elif opcode in {"dma_copy", "dma_fill"}:
            if opcode == "dma_copy":
                command["src_addr"] = hex(parse_int(command.get("src_addr", command.get("src")), f"commands[{index}].src_addr"))
            command["dst_addr"] = hex(parse_int(command.get("dst_addr", command.get("dst")), f"commands[{index}].dst_addr"))
            command["byte_count"] = parse_int(command.get("byte_count", command.get("size_bytes")), f"commands[{index}].byte_count")
        elif opcode == "kernel_dispatch":
            metadata = command.get("ventus_metadata")
            if isinstance(metadata, dict):
                command["_ventus_metadata"] = normalize_metadata_record(metadata)
            command["grid"] = int_list3(command.get("grid", command.get("kernel_size")), f"commands[{index}].grid", default=[1, 1, 1])
            command["local"] = int_list3(command.get("local"), f"commands[{index}].local", default=[32, 1, 1])
            command["arg_buffer"] = hex(parse_int(command.get("arg_buffer", command.get("metaDataBaseAddr", 0x80000000)), f"commands[{index}].arg_buffer"))
            command["arg_bytes"] = parse_int(command.get("arg_bytes", command.get("arg_size_bytes", 64)), f"commands[{index}].arg_bytes")
            command["required_fp_mode"] = str(command.get("required_fp_mode", "fp32"))
        elif opcode in {"fence_wait", "fence_signal"}:
            command["fence"] = require_string(command.get("fence"), f"commands[{index}].fence")
            command["value"] = parse_int(command.get("value", 1), f"commands[{index}].value")
        normalized.append(command)
    return normalized


def normalize_runtime_json(data: Mapping[str, Any]) -> Dict[str, Any]:
    if data.get("schema") == control_plane.SCHEMA:
        return dict(data)
    if data.get("schema") != RUNTIME_SCHEMA:
        raise RuntimeProxyError(f"schema must be {RUNTIME_SCHEMA} or {control_plane.SCHEMA}")
    if data.get("ip_name", "Celviz GPGPU IP") != "Celviz GPGPU IP":
        raise RuntimeProxyError("ip_name must be Celviz GPGPU IP")
    tier = normalize_tier(data.get("tier", "gpgpu_nano_ultra31"))
    return {
        "schema": control_plane.SCHEMA,
        "ip_name": "Celviz GPGPU IP",
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "tier": tier,
        "queues": normalize_queues(data, tier),
        "memory_regions": normalize_memory_regions(data),
        "commands": normalize_commands(data),
    }


def normalize_metadata_record(data: Mapping[str, Any]) -> Dict[str, Any]:
    metadata = dict(data.get("metadata", data))
    name = require_string(metadata.get("name", "kernel"), "metadata.name")
    kernel_size = int_list3(metadata.get("kernel_size", metadata.get("grid")), "metadata.kernel_size", default=[1, 1, 1])
    wf_size = parse_int(metadata.get("wf_size", metadata.get("warp_size", 32)), "metadata.wf_size")
    wg_size = parse_int(metadata.get("wg_size", metadata.get("warps_per_workgroup", 1)), "metadata.wg_size")
    buffer_base = [parse_int(item, f"metadata.buffer_base[{i}]") for i, item in enumerate(metadata.get("buffer_base", []))]
    buffer_size = [parse_int(item, f"metadata.buffer_size[{i}]") for i, item in enumerate(metadata.get("buffer_size", []))]
    buffer_allocsize = [
        parse_int(item, f"metadata.buffer_allocsize[{i}]")
        for i, item in enumerate(metadata.get("buffer_allocsize", buffer_size))
    ]
    if len(buffer_allocsize) < len(buffer_base):
        buffer_allocsize.extend(buffer_size[len(buffer_allocsize):])
    return {
        "name": name,
        "startaddr": parse_int(metadata.get("startaddr", metadata.get("kernel_entry", 0)), "metadata.startaddr"),
        "kernel_id": parse_int(metadata.get("kernel_id", 0), "metadata.kernel_id"),
        "kernel_size": kernel_size,
        "wf_size": wf_size,
        "wg_size": wg_size,
        "metaDataBaseAddr": parse_int(metadata.get("metaDataBaseAddr", metadata.get("arg_buffer", 0x80000000)), "metadata.metaDataBaseAddr"),
        "ldsSize": parse_int(metadata.get("ldsSize", metadata.get("shared_bytes", 0)), "metadata.ldsSize"),
        "pdsSize": parse_int(metadata.get("pdsSize", metadata.get("private_bytes_per_thread", 0)), "metadata.pdsSize"),
        "sgprUsage": parse_int(metadata.get("sgprUsage", metadata.get("sgpr_count", 0)), "metadata.sgprUsage"),
        "vgprUsage": parse_int(metadata.get("vgprUsage", metadata.get("vgpr_count", 0)), "metadata.vgprUsage"),
        "pdsBaseAddr": parse_int(metadata.get("pdsBaseAddr", 0), "metadata.pdsBaseAddr"),
        "num_buffer": parse_int(metadata.get("num_buffer", len(buffer_base)), "metadata.num_buffer"),
        "buffer_base": buffer_base,
        "buffer_size": buffer_size,
        "buffer_allocsize": buffer_allocsize,
    }


def runtime_json_from_metadata(metadata_json: Mapping[str, Any], data_json: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    metadata = normalize_metadata_record(metadata_json)
    tier = normalize_tier(metadata_json.get("tier", "gpgpu_nano_ultra31"))
    regions = []
    for index, base in enumerate(metadata["buffer_base"]):
        size = metadata["buffer_allocsize"][index] if index < len(metadata["buffer_allocsize"]) else metadata["buffer_size"][index]
        regions.append(
            {
                "name": f"metadata_buffer_{index}",
                "base": hex(base),
                "size": max(1, size),
                "readable": True,
                "writable": True,
            }
        )
    if not any(region["base"] == hex(metadata["metaDataBaseAddr"]) for region in regions):
        regions.append(
            {
                "name": "metadata_arg_buffer",
                "base": hex(metadata["metaDataBaseAddr"]),
                "size": max(4096, metadata["num_buffer"] * 32 + 64),
                "readable": True,
                "writable": True,
            }
        )
    regions.append(
        {
            "name": "runtime_completion",
            "base": "0x90000000",
            "size": 0x10000,
            "readable": True,
            "writable": True,
        }
    )
    if data_json:
        for index, raw_buffer in enumerate(data_json.get("buffers", []) or []):
            buffer = require_mapping(raw_buffer, f"data.buffers[{index}]")
            regions.append(
                {
                    "name": str(buffer.get("id", f"data_buffer_{index}")),
                    "base": hex(parse_int(buffer.get("device_address", buffer.get("base")), f"data.buffers[{index}].device_address")),
                    "size": parse_int(buffer.get("size_bytes", buffer.get("byte_count")), f"data.buffers[{index}].size_bytes"),
                    "readable": True,
                    "writable": True,
                }
            )
    return {
        "schema": RUNTIME_SCHEMA,
        "ip_name": "Celviz GPGPU IP",
        "tier": tier,
        "queues": default_queues(tier)[:1],
        "memory_regions": regions,
        "commands": [
            {
                "opcode": "kernel_dispatch",
                "sequence": 1,
                "queue_id": 0,
                "submit_tag": f"metadata-dispatch-{metadata['name']}",
                "kernel": metadata["name"],
                "kernel_entry": hex(metadata["startaddr"]),
                "arg_buffer": hex(metadata["metaDataBaseAddr"]),
                "arg_bytes": max(64, metadata["num_buffer"] * 32),
                "grid": metadata["kernel_size"],
                "local": [metadata["wf_size"] * max(metadata["wg_size"], 1), 1, 1],
                "required_fp_mode": str(metadata_json.get("required_fp_mode", "fp32")),
                "shared_bytes": metadata["ldsSize"],
                "private_bytes_per_thread": metadata["pdsSize"],
                "sgpr_count": metadata["sgprUsage"],
                "vgpr_count": metadata["vgprUsage"],
                "flags": ["INT_ON_COMPLETE", "CAPTURE_COUNTERS"],
                "completion_addr": "0x90000000",
                "ventus_metadata": metadata,
            }
        ],
    }


class VentusKernelMetadata(ctypes.Structure):
    _fields_ = [
        ("name", ctypes.c_char_p),
        ("data", ctypes.c_void_p),
        ("startaddr", ctypes.c_uint64),
        ("kernel_id", ctypes.c_uint64),
        ("kernel_size", ctypes.c_uint64 * 3),
        ("wf_size", ctypes.c_uint64),
        ("wg_size", ctypes.c_uint64),
        ("metaDataBaseAddr", ctypes.c_uint64),
        ("ldsSize", ctypes.c_uint64),
        ("pdsSize", ctypes.c_uint64),
        ("sgprUsage", ctypes.c_uint64),
        ("vgprUsage", ctypes.c_uint64),
        ("pdsBaseAddr", ctypes.c_uint64),
        ("num_buffer", ctypes.c_uint64),
        ("buffer_base", ctypes.POINTER(ctypes.c_uint64)),
        ("buffer_size", ctypes.POINTER(ctypes.c_uint64)),
        ("buffer_allocsize", ctypes.POINTER(ctypes.c_uint64)),
    ]


class VentusRtlsimStepResult(ctypes.Structure):
    _fields_ = [("error", ctypes.c_bool), ("time_exceed", ctypes.c_bool), ("idle", ctypes.c_bool)]


class VentusRtlsimLogFileConfig(ctypes.Structure):
    _fields_ = [("enable", ctypes.c_bool), ("level", ctypes.c_char_p), ("filename", ctypes.c_char_p)]


class VentusRtlsimLogConsoleConfig(ctypes.Structure):
    _fields_ = [("enable", ctypes.c_bool), ("level", ctypes.c_char_p)]


class VentusRtlsimLogConfig(ctypes.Structure):
    _fields_ = [
        ("file", VentusRtlsimLogFileConfig),
        ("console", VentusRtlsimLogConsoleConfig),
        ("level", ctypes.c_char_p),
    ]


class VentusRtlsimPmemConfig(ctypes.Structure):
    _fields_ = [("pagesize", ctypes.c_uint64), ("auto_alloc", ctypes.c_uint64)]


class VentusRtlsimWaveformConfig(ctypes.Structure):
    _fields_ = [
        ("enable", ctypes.c_bool),
        ("time_begin", ctypes.c_uint64),
        ("time_end", ctypes.c_uint64),
        ("levels", ctypes.c_int),
        ("filename", ctypes.c_char_p),
    ]


class VentusRtlsimSnapshotConfig(ctypes.Structure):
    _fields_ = [
        ("enable", ctypes.c_bool),
        ("time_interval", ctypes.c_uint64),
        ("num_max", ctypes.c_int),
        ("filename", ctypes.c_char_p),
    ]


class VentusRtlsimVerilatorConfig(ctypes.Structure):
    _fields_ = [("argc", ctypes.c_int), ("argv", ctypes.POINTER(ctypes.c_char_p))]


class VentusRtlsimConfig(ctypes.Structure):
    _fields_ = [
        ("sim_time_max", ctypes.c_uint64),
        ("log", VentusRtlsimLogConfig),
        ("pmem", VentusRtlsimPmemConfig),
        ("waveform", VentusRtlsimWaveformConfig),
        ("snapshot", VentusRtlsimSnapshotConfig),
        ("verilator", VentusRtlsimVerilatorConfig),
    ]


class CelvizGpgpuDeviceTier(ctypes.Structure):
    _fields_ = [
        ("abi_version", ctypes.c_uint32),
        ("tier_id", ctypes.c_int),
        ("tier_name", ctypes.c_char_p),
        ("public_reference_tier", ctypes.c_char_p),
        ("queue_count", ctypes.c_uint32),
        ("shader_unit_count", ctypes.c_uint32),
        ("warp_size", ctypes.c_uint32),
        ("max_workgroup_size", ctypes.c_uint32),
        ("address_bits", ctypes.c_uint32),
        ("fp32_ops_per_cycle", ctypes.c_uint32),
        ("fp16_ops_per_cycle", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
    ]


class CelvizGpgpuQueue(ctypes.Structure):
    _fields_ = [
        ("queue_id", ctypes.c_uint32),
        ("context_id", ctypes.c_uint32),
        ("priority", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("ring_base", ctypes.c_uint64),
        ("ring_size_bytes", ctypes.c_uint64),
        ("head", ctypes.c_uint64),
        ("tail", ctypes.c_uint64),
        ("doorbell", ctypes.c_uint64),
        ("submitted", ctypes.c_uint64),
        ("retired", ctypes.c_uint64),
        ("errors", ctypes.c_uint64),
    ]


class CelvizGpgpuCommandStatus(ctypes.Structure):
    _fields_ = [
        ("abi_version", ctypes.c_uint32),
        ("queue_id", ctypes.c_uint32),
        ("context_id", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("sequence", ctypes.c_uint64),
        ("opcode", ctypes.c_int),
        ("status", ctypes.c_int),
        ("error", ctypes.c_int),
        ("submit_tag", ctypes.c_uint64),
        ("submit_time", ctypes.c_uint64),
        ("start_time", ctypes.c_uint64),
        ("end_time", ctypes.c_uint64),
    ]


class CelvizGpgpuEventStatus(ctypes.Structure):
    _fields_ = [
        ("abi_version", ctypes.c_uint32),
        ("event_flags", ctypes.c_uint32),
        ("command", CelvizGpgpuCommandStatus),
        ("fault_address", ctypes.c_uint64),
        ("fault_access", ctypes.c_uint32),
        ("shader_context", ctypes.c_uint32),
    ]


class CelvizGpgpuRuntimeMetrics(ctypes.Structure):
    _fields_ = [
        ("commands_submitted", ctypes.c_uint64),
        ("commands_completed", ctypes.c_uint64),
        ("commands_failed", ctypes.c_uint64),
        ("kernel_dispatches", ctypes.c_uint64),
        ("dma_copies", ctypes.c_uint64),
        ("dma_fills", ctypes.c_uint64),
        ("fence_waits", ctypes.c_uint64),
        ("fence_signals", ctypes.c_uint64),
        ("resets", ctypes.c_uint64),
        ("bytes_read", ctypes.c_uint64),
        ("bytes_written", ctypes.c_uint64),
        ("bytes_moved", ctypes.c_uint64),
        ("axi_read_beats", ctypes.c_uint64),
        ("axi_write_beats", ctypes.c_uint64),
        ("axi_read_transactions", ctypes.c_uint64),
        ("axi_write_transactions", ctypes.c_uint64),
        ("completion_interrupts", ctypes.c_uint64),
        ("error_interrupts", ctypes.c_uint64),
        ("mmu_faults", ctypes.c_uint64),
        ("queue_errors", ctypes.c_uint64),
        ("scheduler_faults", ctypes.c_uint64),
        ("rtlsim_time", ctypes.c_uint64),
    ]


class CelvizGpgpuRuntimeProxy(ctypes.Structure):
    _fields_ = [
        ("sim", ctypes.c_void_p),
        ("device", CelvizGpgpuDeviceTier),
        ("queues", ctypes.POINTER(CelvizGpgpuQueue)),
        ("queue_count", ctypes.c_uint32),
        ("user_data", ctypes.c_void_p),
    ]


@dataclass
class NativeMetadata:
    metadata: VentusKernelMetadata
    name_bytes: bytes
    buffer_base: Any
    buffer_size: Any
    buffer_allocsize: Any


class RuntimeLibrary:
    """Thin ctypes bridge for the Ventus runtime proxy C API."""

    REQUIRED_SYMBOLS = (
        "ventus_rtlsim_get_default_config",
        "ventus_rtlsim_init",
        "ventus_rtlsim_finish",
        "ventus_rtlsim_step",
        "ventus_rtlsim_add_kernel",
        "ventus_rtlsim_pmemcpy_h2d",
        "ventus_rtlsim_pmemcpy_d2h",
        "ventus_rtlsim_get_time",
        "celviz_gpgpu_device_tier_get_default",
        "celviz_gpgpu_runtime_proxy_attach",
        "celviz_gpgpu_runtime_proxy_detach",
        "celviz_gpgpu_runtime_proxy_submit_copy_h2d",
        "celviz_gpgpu_runtime_proxy_submit_copy_d2h",
        "celviz_gpgpu_runtime_proxy_submit_fill",
        "celviz_gpgpu_runtime_proxy_get_device",
        "celviz_gpgpu_runtime_proxy_get_queue_count",
        "celviz_gpgpu_runtime_proxy_get_queue_snapshot",
        "celviz_gpgpu_runtime_proxy_get_pending_count",
        "celviz_gpgpu_runtime_proxy_get_metrics",
        "celviz_gpgpu_runtime_proxy_reset_metrics",
        "celviz_gpgpu_runtime_proxy_signal_named_fence",
        "celviz_gpgpu_runtime_proxy_wait_named_fence",
    )
    OPTIONAL_SYMBOLS = (
        "celviz_gpgpu_runtime_proxy_get_queue_by_id",
        "celviz_gpgpu_runtime_proxy_get_queue_pending_count",
        "celviz_gpgpu_runtime_proxy_reset_queue",
        "celviz_gpgpu_runtime_proxy_submit_kernel",
        "celviz_gpgpu_runtime_proxy_inject_next_error",
        "celviz_gpgpu_runtime_proxy_submit_fault",
        "celviz_gpgpu_runtime_proxy_step",
        "celviz_gpgpu_runtime_proxy_get_command_status",
        "celviz_gpgpu_runtime_proxy_get_last_event",
        "celviz_gpgpu_runtime_proxy_get_fence_value",
        "celviz_gpgpu_runtime_proxy_get_named_fence_value",
        "celviz_gpgpu_runtime_proxy_signal_fence",
        "celviz_gpgpu_runtime_proxy_wait_fence",
    )

    def __init__(self, path: Path) -> None:
        self.path = path
        self.lib = ctypes.CDLL(str(path))
        missing = [symbol for symbol in self.REQUIRED_SYMBOLS if not hasattr(self.lib, symbol)]
        if missing:
            raise RuntimeProxyError(f"runtime library missing required symbols: {', '.join(missing)}")
        self.optional_symbols = {symbol: hasattr(self.lib, symbol) for symbol in self.OPTIONAL_SYMBOLS}
        self.lib.ventus_rtlsim_get_default_config.argtypes = [ctypes.POINTER(VentusRtlsimConfig)]
        self.lib.ventus_rtlsim_init.restype = ctypes.c_void_p
        self.lib.ventus_rtlsim_init.argtypes = [ctypes.POINTER(VentusRtlsimConfig)]
        self.lib.ventus_rtlsim_finish.argtypes = [ctypes.c_void_p, ctypes.c_bool]
        self.lib.ventus_rtlsim_step.argtypes = [ctypes.c_void_p]
        self.lib.ventus_rtlsim_step.restype = ctypes.POINTER(VentusRtlsimStepResult)
        self.lib.ventus_rtlsim_add_kernel.argtypes = [ctypes.c_void_p, ctypes.POINTER(VentusKernelMetadata), ctypes.c_void_p]
        self.lib.ventus_rtlsim_pmemcpy_h2d.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_uint64]
        self.lib.ventus_rtlsim_pmemcpy_h2d.restype = ctypes.c_bool
        self.lib.ventus_rtlsim_pmemcpy_d2h.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64, ctypes.c_uint64]
        self.lib.ventus_rtlsim_pmemcpy_d2h.restype = ctypes.c_bool
        self.lib.ventus_rtlsim_get_time.argtypes = [ctypes.c_void_p]
        self.lib.ventus_rtlsim_get_time.restype = ctypes.c_uint64
        self.lib.celviz_gpgpu_device_tier_get_default.argtypes = [ctypes.POINTER(CelvizGpgpuDeviceTier)]
        self.lib.celviz_gpgpu_runtime_proxy_attach.argtypes = [
            ctypes.POINTER(CelvizGpgpuRuntimeProxy),
            ctypes.c_void_p,
            ctypes.POINTER(CelvizGpgpuDeviceTier),
            ctypes.POINTER(CelvizGpgpuQueue),
            ctypes.c_uint32,
        ]
        self.lib.celviz_gpgpu_runtime_proxy_attach.restype = ctypes.c_int
        self.lib.celviz_gpgpu_runtime_proxy_detach.argtypes = [ctypes.POINTER(CelvizGpgpuRuntimeProxy)]
        self.lib.celviz_gpgpu_runtime_proxy_submit_copy_h2d.argtypes = [
            ctypes.POINTER(CelvizGpgpuRuntimeProxy),
            ctypes.c_uint32,
            ctypes.c_uint64,
            ctypes.c_void_p,
            ctypes.c_uint64,
            ctypes.POINTER(CelvizGpgpuCommandStatus),
        ]
        self.lib.celviz_gpgpu_runtime_proxy_submit_copy_h2d.restype = ctypes.c_int
        self.lib.celviz_gpgpu_runtime_proxy_submit_copy_d2h.argtypes = [
            ctypes.POINTER(CelvizGpgpuRuntimeProxy),
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_uint64,
            ctypes.c_uint64,
            ctypes.POINTER(CelvizGpgpuCommandStatus),
        ]
        self.lib.celviz_gpgpu_runtime_proxy_submit_copy_d2h.restype = ctypes.c_int
        self.lib.celviz_gpgpu_runtime_proxy_submit_fill.argtypes = [
            ctypes.POINTER(CelvizGpgpuRuntimeProxy),
            ctypes.c_uint32,
            ctypes.c_uint64,
            ctypes.c_uint32,
            ctypes.c_uint64,
            ctypes.POINTER(CelvizGpgpuCommandStatus),
        ]
        self.lib.celviz_gpgpu_runtime_proxy_submit_fill.restype = ctypes.c_int
        self.lib.celviz_gpgpu_runtime_proxy_get_device.argtypes = [
            ctypes.POINTER(CelvizGpgpuRuntimeProxy),
            ctypes.POINTER(CelvizGpgpuDeviceTier),
        ]
        self.lib.celviz_gpgpu_runtime_proxy_get_device.restype = ctypes.c_bool
        self.lib.celviz_gpgpu_runtime_proxy_get_queue_count.argtypes = [ctypes.POINTER(CelvizGpgpuRuntimeProxy)]
        self.lib.celviz_gpgpu_runtime_proxy_get_queue_count.restype = ctypes.c_uint32
        self.lib.celviz_gpgpu_runtime_proxy_get_queue_snapshot.argtypes = [
            ctypes.POINTER(CelvizGpgpuRuntimeProxy),
            ctypes.c_uint32,
            ctypes.POINTER(CelvizGpgpuQueue),
        ]
        self.lib.celviz_gpgpu_runtime_proxy_get_queue_snapshot.restype = ctypes.c_bool
        self.lib.celviz_gpgpu_runtime_proxy_get_pending_count.argtypes = [ctypes.POINTER(CelvizGpgpuRuntimeProxy)]
        self.lib.celviz_gpgpu_runtime_proxy_get_pending_count.restype = ctypes.c_uint64
        self.lib.celviz_gpgpu_runtime_proxy_get_metrics.argtypes = [
            ctypes.POINTER(CelvizGpgpuRuntimeProxy),
            ctypes.POINTER(CelvizGpgpuRuntimeMetrics),
        ]
        self.lib.celviz_gpgpu_runtime_proxy_get_metrics.restype = ctypes.c_bool
        self.lib.celviz_gpgpu_runtime_proxy_reset_metrics.argtypes = [ctypes.POINTER(CelvizGpgpuRuntimeProxy)]
        self.lib.celviz_gpgpu_runtime_proxy_reset_metrics.restype = ctypes.c_bool
        self.lib.celviz_gpgpu_runtime_proxy_signal_named_fence.argtypes = [
            ctypes.POINTER(CelvizGpgpuRuntimeProxy),
            ctypes.c_char_p,
            ctypes.c_uint64,
            ctypes.POINTER(CelvizGpgpuEventStatus),
        ]
        self.lib.celviz_gpgpu_runtime_proxy_signal_named_fence.restype = ctypes.c_int
        self.lib.celviz_gpgpu_runtime_proxy_wait_named_fence.argtypes = [
            ctypes.POINTER(CelvizGpgpuRuntimeProxy),
            ctypes.c_char_p,
            ctypes.c_uint64,
            ctypes.c_uint64,
            ctypes.POINTER(CelvizGpgpuEventStatus),
        ]
        self.lib.celviz_gpgpu_runtime_proxy_wait_named_fence.restype = ctypes.c_int
        self.bind_optional_symbols()

    def has_symbol(self, name: str) -> bool:
        return bool(self.optional_symbols.get(name, hasattr(self.lib, name)))

    def bind_optional(self, name: str, argtypes: Sequence[Any], restype: Any) -> None:
        if self.has_symbol(name):
            symbol = getattr(self.lib, name)
            symbol.argtypes = list(argtypes)
            symbol.restype = restype

    def bind_optional_symbols(self) -> None:
        self.bind_optional(
            "celviz_gpgpu_runtime_proxy_get_queue_by_id",
            [ctypes.POINTER(CelvizGpgpuRuntimeProxy), ctypes.c_uint32, ctypes.POINTER(CelvizGpgpuQueue)],
            ctypes.c_bool,
        )
        self.bind_optional(
            "celviz_gpgpu_runtime_proxy_get_queue_pending_count",
            [ctypes.POINTER(CelvizGpgpuRuntimeProxy), ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint64)],
            ctypes.c_bool,
        )
        self.bind_optional(
            "celviz_gpgpu_runtime_proxy_reset_queue",
            [ctypes.POINTER(CelvizGpgpuRuntimeProxy), ctypes.c_uint32, ctypes.c_bool, ctypes.POINTER(CelvizGpgpuEventStatus)],
            ctypes.c_int,
        )
        self.bind_optional(
            "celviz_gpgpu_runtime_proxy_inject_next_error",
            [ctypes.POINTER(CelvizGpgpuRuntimeProxy), ctypes.c_uint32, ctypes.c_int, ctypes.c_uint64],
            ctypes.c_int,
        )
        self.bind_optional(
            "celviz_gpgpu_runtime_proxy_submit_fault",
            [ctypes.POINTER(CelvizGpgpuRuntimeProxy), ctypes.c_uint32, ctypes.c_int, ctypes.c_uint64, ctypes.POINTER(CelvizGpgpuCommandStatus)],
            ctypes.c_int,
        )
        self.bind_optional(
            "celviz_gpgpu_runtime_proxy_step",
            [ctypes.POINTER(CelvizGpgpuRuntimeProxy), ctypes.POINTER(CelvizGpgpuEventStatus)],
            ctypes.c_int,
        )
        self.bind_optional(
            "celviz_gpgpu_runtime_proxy_get_command_status",
            [ctypes.POINTER(CelvizGpgpuRuntimeProxy), ctypes.c_uint32, ctypes.c_uint64, ctypes.POINTER(CelvizGpgpuCommandStatus)],
            ctypes.c_bool,
        )
        self.bind_optional(
            "celviz_gpgpu_runtime_proxy_get_last_event",
            [ctypes.POINTER(CelvizGpgpuRuntimeProxy), ctypes.POINTER(CelvizGpgpuEventStatus)],
            ctypes.c_bool,
        )
        self.bind_optional(
            "celviz_gpgpu_runtime_proxy_get_fence_value",
            [ctypes.POINTER(CelvizGpgpuRuntimeProxy)],
            ctypes.c_uint64,
        )
        self.bind_optional(
            "celviz_gpgpu_runtime_proxy_get_named_fence_value",
            [ctypes.POINTER(CelvizGpgpuRuntimeProxy), ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint64)],
            ctypes.c_bool,
        )
        self.bind_optional(
            "celviz_gpgpu_runtime_proxy_signal_fence",
            [ctypes.POINTER(CelvizGpgpuRuntimeProxy), ctypes.c_uint64, ctypes.POINTER(CelvizGpgpuEventStatus)],
            ctypes.c_int,
        )
        self.bind_optional(
            "celviz_gpgpu_runtime_proxy_wait_fence",
            [ctypes.POINTER(CelvizGpgpuRuntimeProxy), ctypes.c_uint64, ctypes.c_uint64, ctypes.POINTER(CelvizGpgpuEventStatus)],
            ctypes.c_int,
        )

    def init_sim(self, *, sim_time_max: int = 100000) -> ctypes.c_void_p:
        config = VentusRtlsimConfig()
        self.lib.ventus_rtlsim_get_default_config(ctypes.byref(config))
        config.sim_time_max = int(sim_time_max)
        config.pmem.auto_alloc = 1
        config.log.console.enable = False
        config.log.file.enable = False
        config.waveform.enable = False
        config.snapshot.enable = False
        sim = self.lib.ventus_rtlsim_init(ctypes.byref(config))
        if not sim:
            raise RuntimeProxyError("ventus_rtlsim_init returned null")
        return sim

    def attach_proxy(self, sim: ctypes.c_void_p, descriptor: Mapping[str, Any]) -> Tuple[CelvizGpgpuRuntimeProxy, Any]:
        device = CelvizGpgpuDeviceTier()
        self.lib.celviz_gpgpu_device_tier_get_default(ctypes.byref(device))
        tier = str(descriptor["tier"])
        caps = control_plane.TIER_CAPS[tier]
        device.tier_id = TIER_IDS[tier]
        device.queue_count = len(descriptor["queues"])
        device.shader_unit_count = int(caps["shader_units"])
        device.max_workgroup_size = int(caps["max_local_size"])
        device.fp16_ops_per_cycle = device.fp32_ops_per_cycle * 2 if "fp16" in caps["fp_modes"] else 0

        queue_arr = (CelvizGpgpuQueue * len(descriptor["queues"]))()
        for index, queue in enumerate(descriptor["queues"]):
            queue_arr[index].queue_id = parse_int(queue.get("queue_id", index), f"queues[{index}].queue_id")
            queue_arr[index].priority = parse_int(queue.get("priority", 0), f"queues[{index}].priority")
            queue_arr[index].flags = 0x1 | 0x2 | 0x100
            queue_arr[index].ring_base = parse_int(queue.get("base"), f"queues[{index}].base")
            queue_arr[index].ring_size_bytes = parse_int(queue.get("size_bytes"), f"queues[{index}].size_bytes")

        proxy = CelvizGpgpuRuntimeProxy()
        error = self.lib.celviz_gpgpu_runtime_proxy_attach(
            ctypes.byref(proxy), sim, ctypes.byref(device), queue_arr, len(queue_arr)
        )
        if error != ERROR_ENUM["OK"]:
            raise RuntimeProxyError(f"celviz_gpgpu_runtime_proxy_attach failed: {error}")
        return proxy, queue_arr

    def make_native_metadata(self, payload: Mapping[str, Any]) -> NativeMetadata:
        metadata = normalize_metadata_record(payload)
        name_bytes = str(metadata["name"]).encode("utf-8")
        base_arr = (ctypes.c_uint64 * len(metadata["buffer_base"]))(*metadata["buffer_base"]) if metadata["buffer_base"] else None
        size_arr = (ctypes.c_uint64 * len(metadata["buffer_size"]))(*metadata["buffer_size"]) if metadata["buffer_size"] else None
        alloc_arr = (
            (ctypes.c_uint64 * len(metadata["buffer_allocsize"]))(*metadata["buffer_allocsize"])
            if metadata["buffer_allocsize"]
            else None
        )
        native = VentusKernelMetadata()
        native.name = ctypes.c_char_p(name_bytes)
        native.data = None
        native.startaddr = int(metadata["startaddr"])
        native.kernel_id = int(metadata["kernel_id"])
        native.kernel_size = (ctypes.c_uint64 * 3)(*metadata["kernel_size"])
        native.wf_size = int(metadata["wf_size"])
        native.wg_size = int(metadata["wg_size"])
        native.metaDataBaseAddr = int(metadata["metaDataBaseAddr"])
        native.ldsSize = int(metadata["ldsSize"])
        native.pdsSize = int(metadata["pdsSize"])
        native.sgprUsage = int(metadata["sgprUsage"])
        native.vgprUsage = int(metadata["vgprUsage"])
        native.pdsBaseAddr = int(metadata["pdsBaseAddr"])
        native.num_buffer = int(metadata["num_buffer"])
        native.buffer_base = base_arr
        native.buffer_size = size_arr
        native.buffer_allocsize = alloc_arr
        return NativeMetadata(native, name_bytes, base_arr, size_arr, alloc_arr)


def discover_runtime_library(runtime_lib: Optional[Path]) -> Tuple[Optional[RuntimeLibrary], Dict[str, Any]]:
    raw_path = runtime_lib or (Path(os.environ["CELVIZ_GPGPU_RUNTIME_LIB"]) if os.environ.get("CELVIZ_GPGPU_RUNTIME_LIB") else None)
    if raw_path is None:
        return None, {"mode": "dry_run", "reason": "no runtime library path provided"}
    path = raw_path.resolve()
    if not path.exists():
        return None, {"mode": "dry_run", "library_path": str(path), "reason": "runtime library not found"}
    try:
        bridge = RuntimeLibrary(path)
    except Exception as exc:
        return None, {"mode": "dry_run", "library_path": str(path), "reason": repr(exc)}
    return bridge, {
        "mode": "ctypes_bound",
        "library_path": str(path),
        "symbols": list(RuntimeLibrary.REQUIRED_SYMBOLS),
        "optional_symbols": {
            "present": [symbol for symbol, present in bridge.optional_symbols.items() if present],
            "missing": [symbol for symbol, present in bridge.optional_symbols.items() if not present],
        },
    }


def command_data_bytes(command: Mapping[str, Any], base_dir: Path) -> bytes:
    if "data_hex" in command:
        return bytes.fromhex(str(command["data_hex"]).replace(" ", ""))
    if "data_file" in command:
        path = Path(str(command["data_file"]))
        if not path.is_absolute():
            path = base_dir / path
        return path.read_bytes()
    return bytes(int(command.get("fill_byte", 0)) & 0xFF for _ in range(parse_int(command.get("byte_count"), "byte_count")))


def dma_fill_bytes(command: Mapping[str, Any]) -> bytes:
    byte_count = parse_int(command.get("byte_count"), "byte_count")
    if "pattern_u32" in command:
        pattern = parse_int(command.get("pattern_u32"), "pattern_u32").to_bytes(4, "little", signed=False)
        return (pattern * ((byte_count + 3) // 4))[:byte_count]
    return bytes(int(command.get("fill_byte", 0)) & 0xFF for _ in range(byte_count))


def c_status_record(status: CelvizGpgpuCommandStatus) -> Dict[str, Any]:
    opcode_value = int(status.opcode)
    status_value = int(status.status)
    error_value = int(status.error)
    return {
        "abi_version": int(status.abi_version),
        "queue_id": int(status.queue_id),
        "context_id": int(status.context_id),
        "flags": int(status.flags),
        "sequence": int(status.sequence),
        "opcode": OPCODE_NAMES.get(opcode_value, f"unknown_{opcode_value}"),
        "opcode_value": opcode_value,
        "status": STATUS_NAMES.get(status_value, f"unknown_{status_value}"),
        "status_value": status_value,
        "error": ERROR_NAMES.get(error_value, f"unknown_{error_value}"),
        "error_value": error_value,
        "submit_tag": int(status.submit_tag),
        "submit_time": int(status.submit_time),
        "start_time": int(status.start_time),
        "end_time": int(status.end_time),
    }


def c_queue_snapshot(queue: CelvizGpgpuQueue) -> Dict[str, Any]:
    submitted = int(queue.submitted)
    retired = int(queue.retired)
    errors = int(queue.errors)
    pending = max(0, submitted - retired)
    return {
        "queue_id": int(queue.queue_id),
        "context_id": int(queue.context_id),
        "priority": int(queue.priority),
        "flags": int(queue.flags),
        "ring_base": hex(int(queue.ring_base)),
        "ring_size_bytes": int(queue.ring_size_bytes),
        "head": int(queue.head),
        "tail": int(queue.tail),
        "doorbell": int(queue.doorbell),
        "submitted": submitted,
        "retired": retired,
        "errors": errors,
        "pending_count": pending,
        "lifecycle": "error" if errors else ("busy" if pending else "idle"),
    }


def c_metrics_snapshot(metrics: CelvizGpgpuRuntimeMetrics) -> Dict[str, int]:
    return {field: int(getattr(metrics, field)) for field, _ctype in CelvizGpgpuRuntimeMetrics._fields_}


def c_event_snapshot(event: CelvizGpgpuEventStatus) -> Dict[str, Any]:
    return {
        "abi_version": int(event.abi_version),
        "event_flags": int(event.event_flags),
        "command": c_status_record(event.command),
        "fault_address": hex(int(event.fault_address)),
        "fault_access": int(event.fault_access),
        "shader_context": int(event.shader_context),
    }


def c_device_snapshot(device: CelvizGpgpuDeviceTier) -> Dict[str, Any]:
    return {
        "abi_version": int(device.abi_version),
        "tier_id": int(device.tier_id),
        "tier_name": device.tier_name.decode("utf-8") if device.tier_name else "",
        "public_reference_tier": device.public_reference_tier.decode("utf-8") if device.public_reference_tier else "",
        "queue_count": int(device.queue_count),
        "shader_unit_count": int(device.shader_unit_count),
        "warp_size": int(device.warp_size),
        "max_workgroup_size": int(device.max_workgroup_size),
        "address_bits": int(device.address_bits),
        "fp32_ops_per_cycle": int(device.fp32_ops_per_cycle),
        "fp16_ops_per_cycle": int(device.fp16_ops_per_cycle),
        "flags": int(device.flags),
    }


def expected_error_name(command: Mapping[str, Any]) -> Optional[str]:
    expected = command.get("expect_error", command.get("expected_error"))
    if expected is None:
        return None
    expected_name = str(expected)
    if expected_name not in ERROR_ENUM:
        raise RuntimeProxyError(f"unknown expected native error: {expected_name}")
    return expected_name


def native_error_values(result: Mapping[str, Any]) -> List[int]:
    values = []
    for key, value in result.items():
        if key.endswith("error_value"):
            values.append(int(value))
    return values


def native_result_passed(result: Mapping[str, Any]) -> bool:
    expected = result.get("expected_error")
    if expected is not None:
        expected_value = ERROR_ENUM.get(str(expected))
        return expected_value is not None and expected_value in native_error_values(result)
    return bool(result.get("ok"))


def native_result_status(result: Mapping[str, Any]) -> str:
    if result.get("skipped"):
        return "skipped"
    if "error" in result or "runtime_init_error" in result:
        return "error"
    return "pass" if native_result_passed(result) else "fail"


def native_abi_symbol_coverage(bridge: RuntimeLibrary) -> Dict[str, Any]:
    present = [symbol for symbol in RuntimeLibrary.REQUIRED_SYMBOLS if hasattr(bridge.lib, symbol)]
    missing = [symbol for symbol in RuntimeLibrary.REQUIRED_SYMBOLS if symbol not in present]
    optional_present = [symbol for symbol in RuntimeLibrary.OPTIONAL_SYMBOLS if bridge.has_symbol(symbol)]
    optional_missing = [symbol for symbol in RuntimeLibrary.OPTIONAL_SYMBOLS if symbol not in optional_present]
    return {
        "required_count": len(RuntimeLibrary.REQUIRED_SYMBOLS),
        "present_count": len(present),
        "missing_count": len(missing),
        "complete": not missing,
        "present_symbols": present,
        "missing_symbols": missing,
        "optional_count": len(RuntimeLibrary.OPTIONAL_SYMBOLS),
        "optional_present_count": len(optional_present),
        "optional_missing_count": len(optional_missing),
        "optional_present_symbols": optional_present,
        "optional_missing_symbols": optional_missing,
    }


def native_queue_totals(queue_snapshots: Sequence[Mapping[str, Any]], pending_count: int) -> Dict[str, int]:
    return {
        "queue_count": len(queue_snapshots),
        "submitted": sum(int(queue.get("submitted", 0)) for queue in queue_snapshots),
        "retired": sum(int(queue.get("retired", 0)) for queue in queue_snapshots),
        "errors": sum(int(queue.get("errors", 0)) for queue in queue_snapshots),
        "pending_count": int(pending_count),
        "ring_size_bytes": sum(int(queue.get("ring_size_bytes", 0)) for queue in queue_snapshots),
    }


def optional_queue_pending_count(bridge: RuntimeLibrary, proxy: CelvizGpgpuRuntimeProxy, queue_id: int) -> Optional[int]:
    if not bridge.has_symbol("celviz_gpgpu_runtime_proxy_get_queue_pending_count"):
        return None
    pending = ctypes.c_uint64()
    ok = bool(
        bridge.lib.celviz_gpgpu_runtime_proxy_get_queue_pending_count(
            ctypes.byref(proxy), ctypes.c_uint32(queue_id), ctypes.byref(pending)
        )
    )
    return int(pending.value) if ok else None


def maybe_request_native_error_injection(
    bridge: RuntimeLibrary,
    proxy: CelvizGpgpuRuntimeProxy,
    command: Mapping[str, Any],
    queue_id: int,
) -> Optional[Dict[str, Any]]:
    flags = set(command.get("flags", []) or [])
    expected = expected_error_name(command)
    requested_error = expected
    if "INJECT_MMU_FAULT" in flags:
        requested_error = "ERR_MMU_FAULT"
    elif "INJECT_DMA_ERROR" in flags:
        requested_error = "ERR_BAD_DMA"
    elif "INJECT_DISPATCH_ERROR" in flags:
        requested_error = "ERR_SCHEDULER_FAULT"
    if requested_error is None:
        return None

    address = command.get("fault_address", command.get("src_addr", command.get("dst_addr", command.get("arg_buffer", 0))))
    fault_address = parse_int(address, "fault_address", default=0)
    payload: Dict[str, Any] = {
        "requested": True,
        "error": requested_error,
        "error_value": ERROR_ENUM[requested_error],
        "fault_address": hex(fault_address),
        "available": bridge.has_symbol("celviz_gpgpu_runtime_proxy_inject_next_error"),
    }
    if not payload["available"]:
        return payload
    result = int(
        bridge.lib.celviz_gpgpu_runtime_proxy_inject_next_error(
            ctypes.byref(proxy), ctypes.c_uint32(queue_id), ERROR_ENUM[requested_error], ctypes.c_uint64(fault_address)
        )
    )
    payload.update({"called": "celviz_gpgpu_runtime_proxy_inject_next_error", "return_error_value": result, "ok": result == ERROR_ENUM["OK"]})
    return payload


def augment_native_result(
    bridge: RuntimeLibrary,
    proxy: CelvizGpgpuRuntimeProxy,
    result: MutableMapping[str, Any],
) -> None:
    queue_id_raw = result.get("queue_id")
    if queue_id_raw is None:
        return
    queue_id = int(queue_id_raw)

    if bridge.has_symbol("celviz_gpgpu_runtime_proxy_get_queue_by_id"):
        queue = CelvizGpgpuQueue()
        ok = bool(bridge.lib.celviz_gpgpu_runtime_proxy_get_queue_by_id(ctypes.byref(proxy), ctypes.c_uint32(queue_id), ctypes.byref(queue)))
        result["queue_snapshot_after_ok"] = ok
        if ok:
            result["queue_snapshot_after"] = c_queue_snapshot(queue)

    result["pending_count_after"] = int(bridge.lib.celviz_gpgpu_runtime_proxy_get_pending_count(ctypes.byref(proxy)))
    queue_pending = optional_queue_pending_count(bridge, proxy, queue_id)
    if queue_pending is not None:
        result["queue_pending_count_after"] = queue_pending

    if bridge.has_symbol("celviz_gpgpu_runtime_proxy_get_command_status"):
        for source_key, dest_key in (("status", "polled_status"), ("read_status", "read_polled_status"), ("write_status", "write_polled_status")):
            source = result.get(source_key)
            if not isinstance(source, Mapping) or "sequence" not in source:
                continue
            if int(source["sequence"]) == 0:
                continue
            status = CelvizGpgpuCommandStatus()
            ok = bool(
                bridge.lib.celviz_gpgpu_runtime_proxy_get_command_status(
                    ctypes.byref(proxy), ctypes.c_uint32(queue_id), ctypes.c_uint64(int(source["sequence"])), ctypes.byref(status)
                )
            )
            result[f"{dest_key}_ok"] = ok
            if ok:
                result[dest_key] = c_status_record(status)

    if bridge.has_symbol("celviz_gpgpu_runtime_proxy_get_last_event"):
        event = CelvizGpgpuEventStatus()
        ok = bool(bridge.lib.celviz_gpgpu_runtime_proxy_get_last_event(ctypes.byref(proxy), ctypes.byref(event)))
        result["last_event_after_ok"] = ok
        if ok:
            result["last_event_after"] = c_event_snapshot(event)


def native_pass_fail_summary(results: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    by_opcode: Dict[str, Dict[str, int]] = {}
    summary = {"total": len(results), "passed": 0, "failed": 0, "skipped": 0, "errors": 0}
    for result in results:
        opcode = str(result.get("opcode", "runtime"))
        status = native_result_status(result)
        opcode_summary = by_opcode.setdefault(opcode, {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "errors": 0})
        opcode_summary["total"] += 1
        if status == "pass":
            summary["passed"] += 1
            opcode_summary["passed"] += 1
        elif status == "skipped":
            summary["skipped"] += 1
            opcode_summary["skipped"] += 1
        elif status == "error":
            summary["errors"] += 1
            summary["failed"] += 1
            opcode_summary["errors"] += 1
            opcode_summary["failed"] += 1
        else:
            summary["failed"] += 1
            opcode_summary["failed"] += 1
    return {**summary, "status": "pass" if summary["failed"] == 0 else "fail", "by_opcode": by_opcode}


def native_runtime_acceptance(
    results: Sequence[Mapping[str, Any]],
    *,
    bridge: Optional[RuntimeLibrary] = None,
    native_proxy_snapshot: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    category_opcodes = {
        "dma_fill": {"dma_fill"},
        "dma_copy": {"dma_copy"},
        "fence": {"fence_signal", "fence_wait"},
    }
    categories: Dict[str, Dict[str, Any]] = {}
    missing = []
    for category, opcodes in category_opcodes.items():
        observed = [result for result in results if str(result.get("opcode")) in opcodes]
        passed = [result for result in observed if native_result_passed(result)]
        failed = [result for result in observed if not native_result_passed(result)]
        if not observed:
            missing.append(category)
        categories[category] = {
            "opcodes": sorted(opcodes),
            "observed": len(observed),
            "passed": len(passed),
            "failed": len(failed),
            "sequences": [int(result["sequence"]) for result in observed if "sequence" in result],
            "expected_error_passes": sum(1 for result in passed if result.get("expected_error") is not None),
        }

    feature_categories: Dict[str, Dict[str, Any]] = {}
    snapshot = native_proxy_snapshot or {}
    queues = snapshot.get("queues", [])
    if not isinstance(queues, list):
        queues = []
    queue_totals = snapshot.get("queue_totals", {})
    feature_categories["queue_lifecycle"] = {
        "available": bridge is not None,
        "observed": len(queues),
        "pending_count": int(queue_totals.get("pending_count", 0)) if isinstance(queue_totals, Mapping) else 0,
        "errors": int(queue_totals.get("errors", 0)) if isinstance(queue_totals, Mapping) else 0,
        "status": "pass" if queues else "partial",
    }

    status_polls = [
        result
        for result in results
        if result.get("polled_status_ok") is not None
        or result.get("read_polled_status_ok") is not None
        or result.get("write_polled_status_ok") is not None
    ]
    failed_polls = [
        result
        for result in results
        if result.get("polled_status_ok") is False
        or result.get("read_polled_status_ok") is False
        or result.get("write_polled_status_ok") is False
    ]
    status_polling_available = bridge.has_symbol("celviz_gpgpu_runtime_proxy_get_command_status") if bridge is not None else False
    feature_categories["status_polling"] = {
        "available": status_polling_available,
        "observed": len(status_polls),
        "failed": len(failed_polls),
        "status": "pass" if status_polling_available and status_polls and not failed_polls else ("partial" if status_polling_available else "unavailable"),
    }

    last_event_observed = [result for result in results if result.get("last_event_after_ok") is True]
    last_event_available = bridge.has_symbol("celviz_gpgpu_runtime_proxy_get_last_event") if bridge is not None else False
    feature_categories["last_event"] = {
        "available": last_event_available,
        "observed": len(last_event_observed),
        "status": "pass" if last_event_available and last_event_observed else ("partial" if last_event_available else "unavailable"),
    }

    injections = [result.get("error_injection") for result in results if isinstance(result.get("error_injection"), Mapping)]
    injection_calls = [injection for injection in injections if injection.get("called")]
    injection_failures = [injection for injection in injection_calls if injection.get("ok") is False]
    injection_available = bridge.has_symbol("celviz_gpgpu_runtime_proxy_inject_next_error") if bridge is not None else False
    feature_categories["error_injection"] = {
        "available": injection_available,
        "requested": len(injections),
        "observed": len(injection_calls),
        "failed": len(injection_failures),
        "status": "pass" if injection_calls and not injection_failures else ("partial" if injections else "not_requested"),
    }

    failed_categories = [name for name, data in categories.items() if int(data["failed"]) > 0]
    failed_features = [name for name, data in feature_categories.items() if data.get("status") == "fail"]
    if failed_categories:
        status = "fail"
    elif missing:
        status = "partial"
    else:
        status = "pass"
    return {
        "status": status,
        "required_categories": sorted(category_opcodes),
        "missing_categories": missing,
        "failed_categories": failed_categories,
        "categories": categories,
        "feature_categories": feature_categories,
        "failed_feature_categories": failed_features,
    }


def annotate_native_expected_errors(results: Sequence[MutableMapping[str, Any]], commands: Sequence[Mapping[str, Any]]) -> None:
    expected_by_sequence = {}
    for command in commands:
        expected = expected_error_name(command)
        if expected is not None:
            expected_by_sequence[int(command["sequence"])] = expected
    for result in results:
        sequence = result.get("sequence")
        if sequence is not None and int(sequence) in expected_by_sequence:
            result["expected_error"] = expected_by_sequence[int(sequence)]


def build_status_records(completions: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    records = []
    for completion in completions:
        opcode = str(completion.get("opcode", "nop"))
        error = str(completion.get("error", "OK"))
        status_name = "error" if error != "OK" or completion.get("status") == "error" else "complete"
        sequence = parse_int(completion.get("sequence"), "completion.sequence", default=0)
        records.append(
            {
                "abi_version": ABI_VERSION,
                "queue_id": parse_int(completion.get("queue_id", 0), "completion.queue_id"),
                "context_id": 0,
                "flags": 0,
                "sequence": sequence,
                "opcode": opcode,
                "opcode_value": OPCODE_ENUM.get(opcode, 0xFFFF),
                "status": status_name,
                "status_value": STATUS_ENUM[status_name],
                "error": error,
                "error_value": ERROR_ENUM.get(error, ERROR_ENUM["ERR_INJECTED"]),
                "submit_tag": completion.get("submit_tag", ""),
                "submit_time": sequence,
                "start_time": sequence,
                "end_time": sequence + 1,
                "detail": completion.get("detail", ""),
                "queue_head": completion.get("queue_head"),
                "queue_tail": completion.get("queue_tail"),
            }
        )
        if completion.get("error_expected") is True:
            records[-1]["error_expected"] = True
            records[-1]["expected_error"] = completion.get("expected_error")
    return records


def command_status_summary(records: Sequence[Mapping[str, Any]], native_results: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    by_status: Dict[str, int] = {}
    by_error: Dict[str, int] = {}
    by_opcode: Dict[str, int] = {}
    for record in records:
        by_status[str(record.get("status", "unknown"))] = by_status.get(str(record.get("status", "unknown")), 0) + 1
        by_error[str(record.get("error", "unknown"))] = by_error.get(str(record.get("error", "unknown")), 0) + 1
        by_opcode[str(record.get("opcode", "unknown"))] = by_opcode.get(str(record.get("opcode", "unknown")), 0) + 1
    native_polled = sum(
        1
        for result in native_results
        if result.get("polled_status_ok") is True
        or result.get("read_polled_status_ok") is True
        or result.get("write_polled_status_ok") is True
    )
    return {
        "total": len(records),
        "by_status": by_status,
        "by_error": by_error,
        "by_opcode": by_opcode,
        "last_command": records[-1] if records else {},
        "native_polled_status_records": native_polled,
    }


def control_queue_lifecycle(descriptor: Mapping[str, Any], metrics: Mapping[str, Any]) -> Dict[str, Any]:
    queue_state = metrics.get("queue_state", {})
    queues = []
    for queue in descriptor["queues"]:
        queue_id = parse_int(queue.get("queue_id"), "queue.queue_id")
        state = queue_state.get(str(queue_id), {}) if isinstance(queue_state, Mapping) else {}
        submitted = int(state.get("submitted", 0))
        retired = int(state.get("retired", 0))
        errors = int(state.get("errors", 0))
        pending = max(0, submitted - retired)
        queues.append(
            {
                "queue_id": queue_id,
                "base": queue.get("base"),
                "size_bytes": queue.get("size_bytes"),
                "priority": queue.get("priority", 0),
                "head": int(state.get("head", 0)),
                "tail": int(state.get("tail", 0)),
                "submitted": submitted,
                "retired": retired,
                "errors": errors,
                "pending_count": pending,
                "lifecycle": "error" if errors else ("busy" if pending else "idle"),
            }
        )
    return {
        "source": "control_plane",
        "queue_count": len(queues),
        "queues": queues,
        "totals": native_queue_totals(queues, sum(int(queue["pending_count"]) for queue in queues)),
    }


def runtime_queue_lifecycle(
    descriptor: Mapping[str, Any],
    metrics: Mapping[str, Any],
    native_proxy_snapshot: Mapping[str, Any],
) -> Dict[str, Any]:
    lifecycle = control_queue_lifecycle(descriptor, metrics)
    native_queues = native_proxy_snapshot.get("queues", [])
    if isinstance(native_queues, list) and native_queues:
        lifecycle["native"] = {
            "source": "ctypes_runtime_proxy",
            "queue_count": len(native_queues),
            "queues": native_queues,
            "totals": native_proxy_snapshot.get("queue_totals", native_queue_totals(native_queues, 0)),
        }
    return lifecycle


def runtime_last_event(metrics: Mapping[str, Any], native_proxy_snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    native_event = native_proxy_snapshot.get("last_event")
    if isinstance(native_event, Mapping):
        return {"source": "ctypes_runtime_proxy", "event": dict(native_event)}
    completions = metrics.get("completion_records", [])
    if isinstance(completions, list) and completions:
        return {"source": "control_plane", "event": completions[-1]}
    return {"source": "none", "event": {}}


def artifact_manifest(output_dir: Path, log_path: Path) -> Dict[str, str]:
    return {
        "runtime_metrics": str(output_dir / "runtime_metrics.json"),
        "runtime_status": str(output_dir / "runtime_status.json"),
        "run_log": str(log_path),
    }


def build_runtime_evidence(
    *,
    bridge_bound: bool,
    runtime_bridge: Mapping[str, Any],
    descriptor: Mapping[str, Any],
    control_metrics: Mapping[str, Any],
    queue_lifecycle: Mapping[str, Any],
    native_proxy_snapshot: Mapping[str, Any],
    native_command_results: Sequence[Mapping[str, Any]],
    command_status_summary: Mapping[str, Any],
    last_event: Mapping[str, Any],
    native_acceptance: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    control_totals = queue_lifecycle.get("totals", {})
    native_totals = native_proxy_snapshot.get("queue_totals", {})
    native_queues = native_proxy_snapshot.get("queues", [])
    native_metrics = native_proxy_snapshot.get("metrics", {})
    abi_symbol_coverage = native_proxy_snapshot.get("abi_symbol_coverage", {})
    native_summary = native_proxy_snapshot.get("native_pass_fail_summary", {})

    if not isinstance(control_totals, Mapping):
        control_totals = {}
    if not isinstance(native_totals, Mapping):
        native_totals = {}
    if not isinstance(native_queues, list):
        native_queues = []
    if not isinstance(native_metrics, Mapping):
        native_metrics = {}
    if not isinstance(abi_symbol_coverage, Mapping):
        abi_symbol_coverage = {}
    if not isinstance(native_summary, Mapping):
        native_summary = {}
    control_evidence = control_metrics.get("runtime_control_evidence", {})
    if not isinstance(control_evidence, Mapping):
        control_evidence = {}

    native_pending = native_proxy_snapshot.get("pending_count")
    if native_pending is None:
        native_pending = native_totals.get("pending_count", 0)

    evidence: Dict[str, Any] = {
        "runtime_bridge_mode": runtime_bridge.get("mode", "unknown"),
        "runtime_library_bound": bridge_bound,
        "command_count": len(descriptor["commands"]),
        "queue_snapshots": {
            "control_plane": queue_lifecycle.get("queues", []),
            "native_runtime": native_queues,
        },
        "queue_totals": {
            "control_plane": dict(control_totals),
            "native_runtime": dict(native_totals),
        },
        "pending_count": {
            "control_plane": int(control_totals.get("pending_count", 0)),
            "native_runtime": int(native_pending or 0),
        },
        "metrics": {
            "control_plane_counters": control_metrics.get("counters", {}),
            "native_runtime_metrics": dict(native_metrics),
        },
        "command_submission": dict(control_evidence.get("command_submission", {})),
        "interrupt_counters_clear": dict(control_evidence.get("interrupt_counters_clear", {})),
        "axi_apb_traffic": dict(control_evidence.get("axi_apb_traffic", {})),
        "reset_recovery": dict(control_evidence.get("reset_recovery", {})),
        "invalid_descriptor": dict(control_evidence.get("invalid_descriptor", {})),
        "dma_bounds_alignment": dict(control_evidence.get("dma_bounds_alignment", {})),
        "throughput_tier_linkage": dict(
            control_evidence.get("throughput_tier_linkage", control_plane.throughput_tier_linkage(str(descriptor["tier"])))
        ),
        "abi_symbol_coverage": dict(abi_symbol_coverage),
        "native_command_results": list(native_command_results),
        "native_command_summary": dict(native_summary),
        "last_event": last_event,
        "validation": {
            "native_queue_snapshot_count": len(native_queues),
            "native_queue_totals_match_snapshots": (
                int(native_totals.get("queue_count", len(native_queues))) == len(native_queues)
                if bridge_bound
                else None
            ),
            "native_pending_matches_snapshot": (
                int(native_totals.get("pending_count", native_pending or 0)) == int(native_pending or 0)
                if bridge_bound
                else None
            ),
            "native_metrics_ok": native_proxy_snapshot.get("metrics_ok") if bridge_bound else None,
            "native_device_ok": native_proxy_snapshot.get("device_ok") if bridge_bound else None,
            "native_abi_complete": abi_symbol_coverage.get("complete") if bridge_bound else None,
            "native_command_results_observed": len(native_command_results),
            "command_status_records": int(command_status_summary.get("total", 0)),
            "last_event_source": last_event.get("source", "none"),
        },
    }
    if native_acceptance is not None:
        evidence["native_runtime_acceptance"] = dict(native_acceptance)
    return evidence


def execute_runtime(
    runtime_data: Mapping[str, Any],
    *,
    runtime_lib: Optional[Path] = None,
    dry_run: bool = False,
    require_runtime: bool = False,
    base_dir: Optional[Path] = None,
) -> Tuple[List[str], Dict[str, Any]]:
    descriptor = normalize_runtime_json(runtime_data)
    bridge, bridge_status = discover_runtime_library(runtime_lib)
    if require_runtime and bridge is None:
        raise RuntimeProxyError(f"required runtime library unavailable: {bridge_status.get('reason', 'unknown')}")
    if dry_run:
        bridge = None
        bridge_status = {**bridge_status, "mode": "dry_run_forced"}

    log_lines = [
        "celviz_gpgpu_runtime_proxy: start",
        f"schema={RUNTIME_SCHEMA}",
        f"control_schema={control_plane.SCHEMA}",
        f"scope={CLEAN_ROOM_SCOPE}",
        f"tier={descriptor['tier']}",
        f"runtime_bridge={bridge_status['mode']}",
        "c_api=ventus_rtlsim_add_kernel,ventus_rtlsim_pmemcpy_h2d,ventus_rtlsim_pmemcpy_d2h,ventus_rtlsim_step",
    ]

    base_dir = base_dir or Path.cwd()
    native_command_results: List[Dict[str, Any]] = []
    native_proxy_snapshot: Dict[str, Any] = {}
    # Native calls are intentionally opportunistic.  The control-plane model is
    # still authoritative for full command validation/status.  When a compiled
    # RTL library is present, this path also exercises the Celviz runtime proxy
    # C ABI directly and records the native queue/metrics snapshot.
    if bridge is not None:
        sim = None
        proxy: Optional[CelvizGpgpuRuntimeProxy] = None
        try:
            sim = bridge.init_sim()
            proxy, _queue_storage = bridge.attach_proxy(sim, descriptor)
            def append_native_result(result: MutableMapping[str, Any]) -> None:
                augment_native_result(bridge, proxy, result)
                native_command_results.append(dict(result))

            for command in descriptor["commands"]:
                opcode = str(command.get("opcode"))
                queue_id = parse_int(command.get("queue_id", 0), "queue_id")
                try:
                    injection = maybe_request_native_error_injection(bridge, proxy, command, queue_id)
                    if opcode == "reset":
                        ok = bool(bridge.lib.celviz_gpgpu_runtime_proxy_reset_metrics(ctypes.byref(proxy)))
                        result: Dict[str, Any] = {
                            "sequence": command["sequence"],
                            "opcode": opcode,
                            "called": "celviz_gpgpu_runtime_proxy_reset_metrics",
                            "queue_id": queue_id,
                            "ok": ok,
                        }
                        if bridge.has_symbol("celviz_gpgpu_runtime_proxy_reset_queue"):
                            event = CelvizGpgpuEventStatus()
                            reset_error = bridge.lib.celviz_gpgpu_runtime_proxy_reset_queue(
                                ctypes.byref(proxy), ctypes.c_uint32(queue_id), True, ctypes.byref(event)
                            )
                            result["queue_reset"] = {
                                "called": "celviz_gpgpu_runtime_proxy_reset_queue",
                                "error_value": int(reset_error),
                                "ok": int(reset_error) == ERROR_ENUM["OK"],
                                "event": c_event_snapshot(event),
                            }
                        append_native_result(result)
                    elif opcode == "dma_fill":
                        data = dma_fill_bytes(command)
                        dst = parse_int(command.get("dst_addr"), "dst_addr")
                        pattern = parse_int(command.get("pattern_u32", 0), "pattern_u32")
                        status = CelvizGpgpuCommandStatus()
                        error = bridge.lib.celviz_gpgpu_runtime_proxy_submit_fill(
                            ctypes.byref(proxy), queue_id, dst, pattern, len(data), ctypes.byref(status)
                        )
                        result = {
                            "sequence": command["sequence"],
                            "opcode": opcode,
                            "called": "celviz_gpgpu_runtime_proxy_submit_fill",
                            "queue_id": queue_id,
                            "dst_addr": hex(dst),
                            "pattern_u32": hex(pattern),
                            "bytes": len(data),
                            "data_sha256": sha256_bytes(data),
                            "status": c_status_record(status),
                            "error_value": int(error),
                            "ok": error == ERROR_ENUM["OK"],
                        }
                        if injection is not None:
                            result["error_injection"] = injection
                        append_native_result(result)
                    elif opcode == "host_to_device":
                        data = command_data_bytes(command, base_dir)
                        dst = parse_int(command.get("dst_addr"), "dst_addr")
                        buf = ctypes.create_string_buffer(data)
                        status = CelvizGpgpuCommandStatus()
                        error = bridge.lib.celviz_gpgpu_runtime_proxy_submit_copy_h2d(
                            ctypes.byref(proxy), queue_id, dst, buf, len(data), ctypes.byref(status)
                        )
                        result = {
                            "sequence": command["sequence"],
                            "opcode": opcode,
                            "called": "celviz_gpgpu_runtime_proxy_submit_copy_h2d",
                            "queue_id": queue_id,
                            "dst_addr": hex(dst),
                            "bytes": len(data),
                            "data_sha256": sha256_bytes(data),
                            "status": c_status_record(status),
                            "error_value": int(error),
                            "ok": error == ERROR_ENUM["OK"],
                        }
                        if injection is not None:
                            result["error_injection"] = injection
                        append_native_result(result)
                    elif opcode == "device_to_host":
                        size = parse_int(command.get("byte_count"), "byte_count")
                        src = parse_int(command.get("src_addr"), "src_addr")
                        buf = ctypes.create_string_buffer(size)
                        status = CelvizGpgpuCommandStatus()
                        error = bridge.lib.celviz_gpgpu_runtime_proxy_submit_copy_d2h(
                            ctypes.byref(proxy), queue_id, buf, src, size, ctypes.byref(status)
                        )
                        result = {
                            "sequence": command["sequence"],
                            "opcode": opcode,
                            "called": "celviz_gpgpu_runtime_proxy_submit_copy_d2h",
                            "queue_id": queue_id,
                            "src_addr": hex(src),
                            "bytes": size,
                            "data_sha256": sha256_bytes(bytes(buf.raw)),
                            "status": c_status_record(status),
                            "error_value": int(error),
                            "ok": error == ERROR_ENUM["OK"],
                        }
                        if injection is not None:
                            result["error_injection"] = injection
                        append_native_result(result)
                    elif opcode == "dma_copy":
                        size = parse_int(command.get("byte_count"), "byte_count")
                        src = parse_int(command.get("src_addr"), "src_addr")
                        dst = parse_int(command.get("dst_addr"), "dst_addr")
                        buf = ctypes.create_string_buffer(size)
                        read_status = CelvizGpgpuCommandStatus()
                        write_status = CelvizGpgpuCommandStatus()
                        injected_fault = "INJECT_MMU_FAULT" in set(command.get("flags", [])) and (
                            injection is None or not injection.get("called")
                        )
                        read_error = ERROR_ENUM["ERR_MMU_FAULT"] if injected_fault else bridge.lib.celviz_gpgpu_runtime_proxy_submit_copy_d2h(
                            ctypes.byref(proxy), queue_id, buf, src, size, ctypes.byref(read_status)
                        )
                        write_error = ERROR_ENUM["ERR_MMU_FAULT"]
                        if read_error == ERROR_ENUM["OK"]:
                            write_error = bridge.lib.celviz_gpgpu_runtime_proxy_submit_copy_h2d(
                                ctypes.byref(proxy), queue_id, dst, buf, size, ctypes.byref(write_status)
                            )
                        result = {
                            "sequence": command["sequence"],
                            "opcode": opcode,
                            "called": "celviz_gpgpu_runtime_proxy_submit_copy_d2h+submit_copy_h2d",
                            "queue_id": queue_id,
                            "src_addr": hex(src),
                            "dst_addr": hex(dst),
                            "bytes": size,
                            "read_status": c_status_record(read_status),
                            "write_status": c_status_record(write_status),
                            "read_error_value": int(read_error),
                            "write_error_value": int(write_error),
                            "ok": read_error == ERROR_ENUM["OK"] and write_error == ERROR_ENUM["OK"],
                        }
                        if injection is not None:
                            result["error_injection"] = injection
                        append_native_result(result)
                    elif opcode == "fence_signal":
                        event = CelvizGpgpuEventStatus()
                        fence_name = require_string(command.get("fence"), "fence").encode("utf-8")
                        value = parse_int(command.get("value", 1), "value")
                        error = bridge.lib.celviz_gpgpu_runtime_proxy_signal_named_fence(
                            ctypes.byref(proxy), fence_name, value, ctypes.byref(event)
                        )
                        append_native_result(
                            {
                                "sequence": command["sequence"],
                                "opcode": opcode,
                                "called": "celviz_gpgpu_runtime_proxy_signal_named_fence",
                                "queue_id": queue_id,
                                "fence": fence_name.decode("utf-8"),
                                "value": value,
                                "event": c_event_snapshot(event),
                                "error_value": int(error),
                                "ok": error == ERROR_ENUM["OK"],
                            }
                        )
                    elif opcode == "fence_wait":
                        event = CelvizGpgpuEventStatus()
                        fence_name = require_string(command.get("fence"), "fence").encode("utf-8")
                        value = parse_int(command.get("value", 1), "value")
                        timeout = parse_int(command.get("timeout_cycles", 0), "timeout_cycles", default=0)
                        error = bridge.lib.celviz_gpgpu_runtime_proxy_wait_named_fence(
                            ctypes.byref(proxy), fence_name, value, timeout, ctypes.byref(event)
                        )
                        append_native_result(
                            {
                                "sequence": command["sequence"],
                                "opcode": opcode,
                                "called": "celviz_gpgpu_runtime_proxy_wait_named_fence",
                                "queue_id": queue_id,
                                "fence": fence_name.decode("utf-8"),
                                "value": value,
                                "timeout_cycles": timeout,
                                "event_flags": int(event.event_flags),
                                "event_status": c_status_record(event.command),
                                "event": c_event_snapshot(event),
                                "error_value": int(error),
                                "ok": error == ERROR_ENUM["OK"],
                            }
                        )
                    elif opcode == "kernel_dispatch" and isinstance(command.get("_ventus_metadata"), dict):
                        native = bridge.make_native_metadata(command["_ventus_metadata"])
                        bridge.lib.ventus_rtlsim_add_kernel(sim, ctypes.byref(native.metadata), None)
                        terminal = {"error": False, "time_exceed": False, "idle": False}
                        steps = 0
                        for steps in range(1, 100001):
                            step_ptr = bridge.lib.ventus_rtlsim_step(sim)
                            if not step_ptr:
                                break
                            step = step_ptr.contents
                            terminal = {"error": bool(step.error), "time_exceed": bool(step.time_exceed), "idle": bool(step.idle)}
                            if step.error or step.time_exceed or step.idle:
                                break
                        result = {
                            "sequence": command["sequence"],
                            "opcode": opcode,
                            "called": "ventus_rtlsim_add_kernel+ventus_rtlsim_step",
                            "queue_id": queue_id,
                            "metadata_name": native.name_bytes.decode("utf-8"),
                            "steps": steps,
                            "terminal": terminal,
                            "rtlsim_time": int(bridge.lib.ventus_rtlsim_get_time(sim)),
                            "ok": terminal.get("idle") is True,
                        }
                        if injection is not None:
                            result["error_injection"] = injection
                        append_native_result(result)
                    elif opcode == "kernel_dispatch":
                        result = (
                            {
                                "sequence": command["sequence"],
                                "opcode": opcode,
                                "called": "celviz_gpgpu_runtime_proxy_submit_kernel",
                                "queue_id": queue_id,
                                "ok": False,
                                "skipped": "no executable Ventus metadata supplied for native RTL dispatch",
                            }
                        )
                        if injection is not None:
                            result["error_injection"] = injection
                        append_native_result(result)
                except Exception as exc:  # pragma: no cover - depends on external shared library
                    native_command_results.append({"sequence": command.get("sequence"), "opcode": opcode, "queue_id": queue_id, "error": repr(exc)})
            if proxy is not None:
                device = CelvizGpgpuDeviceTier()
                metrics_c = CelvizGpgpuRuntimeMetrics()
                queue_count = int(bridge.lib.celviz_gpgpu_runtime_proxy_get_queue_count(ctypes.byref(proxy)))
                queue_snapshots = []
                for index in range(queue_count):
                    queue = CelvizGpgpuQueue()
                    if bridge.lib.celviz_gpgpu_runtime_proxy_get_queue_snapshot(ctypes.byref(proxy), index, ctypes.byref(queue)):
                        snapshot = c_queue_snapshot(queue)
                        queue_pending = optional_queue_pending_count(bridge, proxy, int(snapshot["queue_id"]))
                        if queue_pending is not None:
                            snapshot["queue_pending_count"] = queue_pending
                        queue_snapshots.append(snapshot)
                device_ok = bool(bridge.lib.celviz_gpgpu_runtime_proxy_get_device(ctypes.byref(proxy), ctypes.byref(device)))
                metrics_ok = bool(bridge.lib.celviz_gpgpu_runtime_proxy_get_metrics(ctypes.byref(proxy), ctypes.byref(metrics_c)))
                pending_count = int(bridge.lib.celviz_gpgpu_runtime_proxy_get_pending_count(ctypes.byref(proxy)))
                native_proxy_snapshot = {
                    "device": c_device_snapshot(device) if device_ok else {},
                    "queues": queue_snapshots,
                    "queue_totals": native_queue_totals(queue_snapshots, pending_count),
                    "metrics": c_metrics_snapshot(metrics_c) if metrics_ok else {},
                    "pending_count": pending_count,
                    "device_ok": device_ok,
                    "metrics_ok": metrics_ok,
                }
                if bridge.has_symbol("celviz_gpgpu_runtime_proxy_get_last_event"):
                    event = CelvizGpgpuEventStatus()
                    event_ok = bool(bridge.lib.celviz_gpgpu_runtime_proxy_get_last_event(ctypes.byref(proxy), ctypes.byref(event)))
                    native_proxy_snapshot["last_event_ok"] = event_ok
                    if event_ok:
                        native_proxy_snapshot["last_event"] = c_event_snapshot(event)
                if bridge.has_symbol("celviz_gpgpu_runtime_proxy_get_fence_value"):
                    native_proxy_snapshot["fence_value"] = int(bridge.lib.celviz_gpgpu_runtime_proxy_get_fence_value(ctypes.byref(proxy)))
        except Exception as exc:  # pragma: no cover - depends on external shared library
            native_command_results.append({"runtime_init_error": repr(exc)})
            bridge_status = {**bridge_status, "mode": "ctypes_bound_init_failed", "runtime_init_error": repr(exc)}
        finally:
            if sim is not None and proxy is not None:
                bridge.lib.celviz_gpgpu_runtime_proxy_detach(ctypes.byref(proxy))
            if sim is not None:
                bridge.lib.ventus_rtlsim_finish(sim, False)

    native_acceptance: Optional[Dict[str, Any]] = None
    if bridge is not None:
        annotate_native_expected_errors(native_command_results, descriptor["commands"])
        native_summary = native_pass_fail_summary(native_command_results)
        native_proxy_snapshot.setdefault("queue_totals", native_queue_totals(native_proxy_snapshot.get("queues", []), 0))
        native_proxy_snapshot["abi_symbol_coverage"] = native_abi_symbol_coverage(bridge)
        native_proxy_snapshot["native_pass_fail_summary"] = native_summary
        native_acceptance = native_runtime_acceptance(
            native_command_results,
            bridge=bridge,
            native_proxy_snapshot=native_proxy_snapshot,
        )

    log_control, metrics = control_plane.simulate(descriptor)
    log_lines.extend(log_control[1:])
    status_records = build_status_records(metrics.get("completion_records", []))
    queue_lifecycle = runtime_queue_lifecycle(descriptor, metrics, native_proxy_snapshot)
    last_event = runtime_last_event(metrics, native_proxy_snapshot)
    status_summary = command_status_summary(status_records, native_command_results)
    top_status = "pass" if metrics.get("status") == "pass" else "fail"
    runtime_evidence = build_runtime_evidence(
        bridge_bound=bridge is not None,
        runtime_bridge=bridge_status,
        descriptor=descriptor,
        control_metrics=metrics,
        queue_lifecycle=queue_lifecycle,
        native_proxy_snapshot=native_proxy_snapshot,
        native_command_results=native_command_results,
        command_status_summary=status_summary,
        last_event=last_event,
        native_acceptance=native_acceptance,
    )
    runtime_metrics: MutableMapping[str, Any] = {
        "schema": METRICS_SCHEMA,
        "generated_at": utc_now(),
        "status": top_status,
        "abi": {
            "version": ABI_VERSION,
            "magic": ABI_MAGIC,
            "header": "sim-verilator/celviz_gpgpu_runtime_proxy.h",
            "tier_id": TIER_IDS[str(descriptor["tier"])],
            "opcode_values": OPCODE_ENUM,
            "status_values": STATUS_ENUM,
            "error_values": ERROR_ENUM,
        },
        "runtime_bridge": bridge_status,
        "native_command_results": native_command_results,
        "native_proxy_snapshot": native_proxy_snapshot,
        "runtime_evidence": runtime_evidence,
        "control_plane_metrics": metrics,
        "command_status_records": status_records,
        "command_status_summary": status_summary,
        "queue_lifecycle": queue_lifecycle,
        "pending_count": int(queue_lifecycle["totals"]["pending_count"]),
        "last_event": last_event,
        "metrics": {
            "control_plane_counters": metrics.get("counters", {}),
            "native_runtime_metrics": native_proxy_snapshot.get("metrics", {}),
        },
        "summary": {
            "commands_submitted": metrics["counters"]["commands_submitted"],
            "commands_completed": metrics["counters"]["commands_completed"],
            "commands_failed": metrics["counters"]["commands_failed"],
            "queue_count": len(descriptor["queues"]),
            "completion_count": len(status_records),
            "pending_count": int(queue_lifecycle["totals"]["pending_count"]),
            "last_event_source": last_event["source"],
            "rtlsim_library_bound": bridge is not None,
            "dry_run": bridge is None,
        },
    }
    if native_acceptance is not None:
        runtime_metrics["native_runtime_acceptance"] = native_acceptance
    log_lines.append(
        "runtime_summary commands={commands_submitted} completed={commands_completed} failed={commands_failed} dry_run={dry_run}".format(
            **runtime_metrics["summary"]
        )
    )
    if native_acceptance is not None:
        log_lines.append(
            "native_runtime_acceptance status={status} missing={missing} failed={failed}".format(
                status=native_acceptance["status"],
                missing=",".join(native_acceptance["missing_categories"]) or "none",
                failed=",".join(native_acceptance["failed_categories"]) or "none",
            )
        )
    log_lines.append("celviz_gpgpu_runtime_proxy: " + top_status)
    return log_lines, runtime_metrics


def run_to_files(
    *,
    commands_path: Optional[Path],
    metadata_path: Optional[Path],
    data_path: Optional[Path],
    output_dir: Path,
    log_path: Path,
    runtime_lib: Optional[Path] = None,
    dry_run: bool = False,
    require_runtime: bool = False,
    print_status: bool = False,
) -> Dict[str, Any]:
    if commands_path is None and metadata_path is None:
        raise RuntimeProxyError("either commands_path or metadata_path is required")
    if commands_path is not None:
        runtime_data = load_json(commands_path, "runtime commands")
        base_dir = commands_path.parent
    else:
        assert metadata_path is not None
        metadata_json = load_json(metadata_path, "metadata")
        data_json = load_json(data_path, "data") if data_path is not None else None
        runtime_data = runtime_json_from_metadata(metadata_json, data_json)
        base_dir = metadata_path.parent

    log_lines, metrics = execute_runtime(
        runtime_data,
        runtime_lib=runtime_lib,
        dry_run=dry_run,
        require_runtime=require_runtime,
        base_dir=base_dir,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts = artifact_manifest(output_dir, log_path)
    metrics["artifact_manifest"] = artifacts
    if isinstance(metrics.get("runtime_evidence"), dict):
        metrics["runtime_evidence"]["artifact_manifest"] = artifacts
    write_json(output_dir / "runtime_metrics.json", metrics)
    status_payload: MutableMapping[str, Any] = {
        "schema": STATUS_SCHEMA,
        "generated_at": utc_now(),
        "status": metrics["status"],
        "scope": CLEAN_ROOM_SCOPE,
        "summary": metrics["summary"],
        "runtime_bridge": metrics["runtime_bridge"],
        "queue_lifecycle": metrics["queue_lifecycle"],
        "pending_count": metrics["pending_count"],
        "metrics": metrics["metrics"],
        "last_event": metrics["last_event"],
        "runtime_evidence": metrics["runtime_evidence"],
        "native_command_results": metrics["native_command_results"],
        "command_status_summary": metrics["command_status_summary"],
        "command_status_records": metrics["command_status_records"],
        "artifact_manifest": artifacts,
        "metrics_path": artifacts["runtime_metrics"],
    }
    for evidence_key in (
        "command_submission",
        "interrupt_counters_clear",
        "axi_apb_traffic",
        "reset_recovery",
        "invalid_descriptor",
        "dma_bounds_alignment",
        "throughput_tier_linkage",
    ):
        status_payload[evidence_key] = metrics["runtime_evidence"].get(evidence_key, {})
    if "native_runtime_acceptance" in metrics:
        status_payload["native_runtime_acceptance"] = metrics["native_runtime_acceptance"]
        status_payload["native_acceptance_summary"] = {
            "status": metrics["native_runtime_acceptance"]["status"],
            "missing_categories": metrics["native_runtime_acceptance"]["missing_categories"],
            "failed_categories": metrics["native_runtime_acceptance"]["failed_categories"],
            "feature_categories": metrics["native_runtime_acceptance"].get("feature_categories", {}),
        }
        status_payload["native_proxy_snapshot"] = metrics["native_proxy_snapshot"]
    write_json(output_dir / "runtime_status.json", status_payload)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    if print_status:
        print(json.dumps(metrics, indent=2, sort_keys=True))
    return metrics
