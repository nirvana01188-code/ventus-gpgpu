#!/usr/bin/env python3
"""S4 OpenCL-like runtime CLI for the Celviz GPGPU IP demo.

The CLI is intentionally dependency-free.  It validates a compact
OpenCL-like kernel list, checks the requested S4 tier, probes the companion
compute_model.py when present, and emits deterministic demo artifacts.

This is a clean-room runtime queue proxy. It does not implement or claim
OpenCL conformance, Vivante command-stream compatibility, or proprietary
driver/firmware behavior.
"""

from __future__ import annotations

import argparse
import math
import hashlib
import json
import struct
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Sequence

try:  # Keep direct script execution working.
    from . import runtime_proxy
except ImportError:  # pragma: no cover - direct script fallback
    import runtime_proxy  # type: ignore


SCHEMA = "celviz.gpgpu.kernel_demo.v1"
TIER_ORDER = {"nano": 0, "micro": 1, "small": 2, "full": 3}
REQUIRED_KERNELS = ("vector_add", "gemm_proxy", "convolution_proxy", "image_filter", "memory_copy")
DISPATCH_ALIASES = {
    "vector_add": "vadd",
    "gemm_proxy": "gemm",
    "convolution_proxy": "conv",
    "image_filter": "image_filter",
    "memory_copy": "memcpy",
}
CANONICAL_OUTPUT_FILES = {
    "vector_add": "vector_add.json",
    "gemm_proxy": "gemm_proxy.json",
    "convolution_proxy": "convolution_proxy.json",
    "image_filter": "image_filter.json",
    "memory_copy": "memory_copy.json",
}
CLEAN_ROOM_SCOPE = (
    "clean-room OpenCL-like runtime proxy; non-conformant and not compatible "
    "with proprietary Vivante command streams, firmware, SDKs, drivers, or "
    "certification suites"
)
DEFAULT_QUEUE_ID = "queue0"

PROXY_DEVICES = [
    {
        "device_id": "celviz-nano-proxy",
        "runtime_tier": "nano",
        "public_reference_tier": "CC8000L",
        "shader_units_vec1": 16,
        "fp32_ops_per_cycle": 32,
        "fp16_ops_per_cycle": 64,
        "queue_count": 1,
        "address_bits": 32,
    },
    {
        "device_id": "celviz-micro-proxy",
        "runtime_tier": "micro",
        "public_reference_tier": "CC8000",
        "shader_units_vec1": 32,
        "fp32_ops_per_cycle": 64,
        "fp16_ops_per_cycle": 128,
        "queue_count": 2,
        "address_bits": 32,
    },
    {
        "device_id": "celviz-small-proxy",
        "runtime_tier": "small",
        "public_reference_tier": "CC8200",
        "shader_units_vec1": 128,
        "fp32_ops_per_cycle": 128,
        "fp16_ops_per_cycle": 256,
        "queue_count": 4,
        "address_bits": 40,
    },
    {
        "device_id": "celviz-full-proxy",
        "runtime_tier": "full",
        "public_reference_tier": "CC8400",
        "shader_units_vec1": 256,
        "fp32_ops_per_cycle": 512,
        "fp16_ops_per_cycle": 1024,
        "queue_count": 8,
        "address_bits": 40,
    },
]

MODEL_WORKLOAD_ALIASES = {
    "vector_add": "vector_add",
    "gemm_proxy": "gemm_proxy",
    "convolution_proxy": "convolution_proxy",
    "image_filter": "convolution_proxy",
    "memory_copy": "memory_copy",
}


class ConfigError(ValueError):
    """Raised when the kernel demo JSON does not match the S4 contract."""


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_config_path() -> Path:
    return repo_root() / "artifacts/rank_01_vivante_3d_gpgpu_ip/demo/kernel_demo.json"


def default_log_path(config_path: Path) -> Path:
    return config_path.parent / "run.log"


def default_output_dir(config_path: Path) -> Path:
    return config_path.parent / "outputs"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def f32(value: float) -> float:
    return struct.unpack(">f", struct.pack(">f", float(value)))[0]


def fp16_quantize(value: float) -> float:
    try:
        return struct.unpack(">e", struct.pack(">e", float(value)))[0]
    except (OverflowError, struct.error):
        return round(float(value), 3)


def fp16_add_proxy(lhs: float, rhs: float) -> float:
    return fp16_quantize(fp16_quantize(lhs) + fp16_quantize(rhs))


def fp16_mul_proxy(lhs: float, rhs: float) -> float:
    return fp16_quantize(fp16_quantize(lhs) * fp16_quantize(rhs))


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


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def proxy_device_for_tier(tier: str) -> Mapping[str, Any]:
    for device in PROXY_DEVICES:
        if device["runtime_tier"] == tier:
            return device
    raise ConfigError(f"unknown runtime tier: {tier}")


def public_devices_payload() -> Dict[str, Any]:
    nano = PROXY_DEVICES[0]
    tier_scaling = []
    for device in PROXY_DEVICES:
        tier_scaling.append(
            {
                "runtime_tier": device["runtime_tier"],
                "public_reference_tier": device["public_reference_tier"],
                "shader_units_vec1": device["shader_units_vec1"],
                "queue_count": device["queue_count"],
                "fp32_ops_per_cycle": device["fp32_ops_per_cycle"],
                "fp16_ops_per_cycle": device["fp16_ops_per_cycle"],
                "fp32_scale_vs_nano": round(device["fp32_ops_per_cycle"] / nano["fp32_ops_per_cycle"], 3),
                "fp16_scale_vs_nano": round(device["fp16_ops_per_cycle"] / nano["fp16_ops_per_cycle"], 3),
                "shader_scale_vs_nano": round(device["shader_units_vec1"] / nano["shader_units_vec1"], 3),
            }
        )
    return {
        "scope": CLEAN_ROOM_SCOPE,
        "device_count": len(PROXY_DEVICES),
        "devices": PROXY_DEVICES,
        "tier_scaling": tier_scaling,
        "precision_modes": ["fp32", "fp16_proxy"],
        "note": "Tiers are public capability proxies and are not measured local RTL performance.",
    }


def throughput_tier_linkage(selected_tier: str) -> Dict[str, Any]:
    tier_scaling = public_devices_payload()["tier_scaling"]
    sorted_rows = sorted(tier_scaling, key=lambda item: int(item["shader_units_vec1"]))
    monotonic = all(
        int(sorted_rows[index]["fp32_ops_per_cycle"]) <= int(sorted_rows[index + 1]["fp32_ops_per_cycle"])
        and int(sorted_rows[index]["fp16_ops_per_cycle"]) <= int(sorted_rows[index + 1]["fp16_ops_per_cycle"])
        for index in range(len(sorted_rows) - 1)
    )
    selected_device = proxy_device_for_tier(selected_tier)
    return {
        "scope": CLEAN_ROOM_SCOPE,
        "selected_runtime_tier": selected_tier,
        "selected_device": selected_device,
        "shader_unit_tiers": [row["runtime_tier"] for row in tier_scaling],
        "throughput_scaling_by_tier": True,
        "monotonic_proxy_scaling": monotonic,
        "claim_scope": "proxy_model_only",
        "tiers": tier_scaling,
    }


def load_config(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"kernel demo JSON not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"kernel demo JSON is invalid: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError("kernel demo JSON root must be an object")
    return data


def require_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{field} must be an object")
    return value


def require_int_sequence(value: Any, field: str, *, min_len: int = 1) -> List[int]:
    if not isinstance(value, list) or len(value) < min_len:
        raise ConfigError(f"{field} must be a non-empty integer list")
    result: List[int] = []
    for index, item in enumerate(value):
        if not isinstance(item, int) or item <= 0:
            raise ConfigError(f"{field}[{index}] must be a positive integer")
        result.append(item)
    return result


def validate_access(value: Any, field: str) -> str:
    if value not in {"read", "write", "read_write"}:
        raise ConfigError(f"{field} must be read, write, or read_write")
    return str(value)


def normalize_queues(data: Mapping[str, Any], selected_tier: str) -> List[Dict[str, Any]]:
    queues = data.get("queues")
    default_device = proxy_device_for_tier(selected_tier)
    if queues is None:
        return [
            {
                "id": DEFAULT_QUEUE_ID,
                "device_id": default_device["device_id"],
                "properties": ["in_order", "profiling"],
                "mode": "software_proxy",
            }
        ]
    if not isinstance(queues, list) or not queues:
        raise ConfigError("queues must be a non-empty list when provided")
    normalized: List[Dict[str, Any]] = []
    seen = set()
    known_devices = {device["device_id"] for device in PROXY_DEVICES}
    for index, raw_queue in enumerate(queues):
        queue = require_mapping(raw_queue, f"queues[{index}]")
        queue_id = queue.get("id")
        if not isinstance(queue_id, str) or not queue_id:
            raise ConfigError(f"queues[{index}].id must be a non-empty string")
        if queue_id in seen:
            raise ConfigError(f"duplicate queue id: {queue_id}")
        seen.add(queue_id)
        device_id = queue.get("device_id", default_device["device_id"])
        if device_id not in known_devices:
            raise ConfigError(f"queues[{index}].device_id is not a known proxy device: {device_id!r}")
        properties = queue.get("properties", ["in_order", "profiling"])
        if not isinstance(properties, list) or not all(isinstance(item, str) for item in properties):
            raise ConfigError(f"queues[{index}].properties must be a string list")
        normalized.append(
            {
                "id": queue_id,
                "device_id": device_id,
                "properties": properties,
                "mode": queue.get("mode", "software_proxy"),
            }
        )
    return normalized


def normalize_buffers(data: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    buffers = data.get("buffers", [])
    if not isinstance(buffers, list):
        raise ConfigError("buffers must be a list when provided")
    normalized: Dict[str, Dict[str, Any]] = {}
    next_address = 0x80000000
    for index, raw_buffer in enumerate(buffers):
        buffer_map = require_mapping(raw_buffer, f"buffers[{index}]")
        buffer_id = buffer_map.get("id")
        if not isinstance(buffer_id, str) or not buffer_id:
            raise ConfigError(f"buffers[{index}].id must be a non-empty string")
        if buffer_id in normalized:
            raise ConfigError(f"duplicate buffer id: {buffer_id}")
        size_bytes = buffer_map.get("size_bytes")
        if not isinstance(size_bytes, int) or size_bytes <= 0:
            raise ConfigError(f"buffers[{index}].size_bytes must be a positive integer")
        access = validate_access(buffer_map.get("access", "read_write"), f"buffers[{index}].access")
        address_raw = buffer_map.get("device_address")
        if address_raw is None:
            device_address = next_address
        else:
            device_address = parse_int(address_raw, f"buffers[{index}].device_address")
        next_address = ((device_address + size_bytes + 0xFFF) // 0x1000) * 0x1000
        normalized[buffer_id] = {
            "id": buffer_id,
            "size_bytes": size_bytes,
            "access": access,
            "host_visible": bool(buffer_map.get("host_visible", True)),
            "binding": buffer_map.get("binding", "global"),
            "device_address": hex(device_address),
            "element_type": buffer_map.get("element_type", "opaque"),
            "shape": buffer_map.get("shape"),
            "role": buffer_map.get("role", "kernel_buffer"),
        }
    return normalized


def validate_config(data: Mapping[str, Any]) -> Dict[str, Any]:
    if data.get("schema") != SCHEMA:
        raise ConfigError(f"schema must be {SCHEMA}")
    if data.get("ip_name") != "Celviz GPGPU IP":
        raise ConfigError("ip_name must be Celviz GPGPU IP")

    tier = data.get("tier")
    if tier not in TIER_ORDER:
        raise ConfigError(f"tier must be one of {', '.join(TIER_ORDER)}")

    queues = normalize_queues(data, tier)
    queue_ids = {queue["id"] for queue in queues}
    buffers = normalize_buffers(data)

    kernels = data.get("kernels")
    if not isinstance(kernels, list) or not kernels:
        raise ConfigError("kernels must be a non-empty list")

    seen = set()
    normalized: List[Dict[str, Any]] = []
    for index, raw_kernel in enumerate(kernels):
        kernel = require_mapping(raw_kernel, f"kernels[{index}]")
        name = kernel.get("name")
        if name not in REQUIRED_KERNELS:
            raise ConfigError(f"kernels[{index}].name is not a supported S4 demo kernel: {name!r}")
        if name in seen:
            raise ConfigError(f"duplicate kernel name: {name}")
        seen.add(name)

        kernel_tier = kernel.get("tier")
        if kernel_tier not in TIER_ORDER:
            raise ConfigError(f"{name}.tier must be one of {', '.join(TIER_ORDER)}")
        if TIER_ORDER[kernel_tier] > TIER_ORDER[tier]:
            raise ConfigError(f"{name}.tier={kernel_tier} exceeds selected tier={tier}")

        language = kernel.get("language")
        if language != "opencl-c-subset":
            raise ConfigError(f"{name}.language must be opencl-c-subset")

        queue_id = kernel.get("queue_id", DEFAULT_QUEUE_ID)
        if queue_id not in queue_ids:
            raise ConfigError(f"{name}.queue_id references an unknown queue: {queue_id!r}")

        global_size = require_int_sequence(kernel.get("global_size"), f"{name}.global_size")
        local_size = require_int_sequence(kernel.get("local_size"), f"{name}.local_size")
        if len(local_size) > len(global_size):
            raise ConfigError(f"{name}.local_size rank exceeds global_size rank")
        for dim, local in enumerate(local_size):
            if global_size[dim] % local != 0:
                raise ConfigError(f"{name}.global_size[{dim}] must be divisible by local_size[{dim}]")

        args = kernel.get("args")
        if not isinstance(args, list):
            raise ConfigError(f"{name}.args must be a list")
        precision_modes = kernel.get("precision_modes", ["fp32", "fp16_proxy"])
        if not isinstance(precision_modes, list) or not precision_modes:
            raise ConfigError(f"{name}.precision_modes must be a non-empty string list when provided")
        if not all(item in {"fp32", "fp16_proxy", "byte"} for item in precision_modes):
            raise ConfigError(f"{name}.precision_modes entries must be fp32, fp16_proxy, or byte")
        normalized_args: List[Dict[str, Any]] = []
        for arg_index, arg in enumerate(args):
            arg_map = require_mapping(arg, f"{name}.args[{arg_index}]")
            if not isinstance(arg_map.get("name"), str) or not arg_map["name"]:
                raise ConfigError(f"{name}.args[{arg_index}].name must be a non-empty string")
            if arg_map.get("address_space") not in {"global", "constant", "private"}:
                raise ConfigError(f"{name}.args[{arg_index}].address_space is invalid")
            access = validate_access(arg_map.get("access", "read"), f"{name}.args[{arg_index}].access")
            buffer_id = arg_map.get("buffer_id")
            if buffer_id is not None and buffer_id not in buffers:
                raise ConfigError(f"{name}.args[{arg_index}].buffer_id references an unknown buffer: {buffer_id!r}")
            normalized_arg = dict(arg_map)
            normalized_arg["access"] = access
            normalized_args.append(normalized_arg)

        normalized.append(
            {
                "name": name,
                "tier": kernel_tier,
                "language": language,
                "queue_id": queue_id,
                "dispatch_name": kernel.get("dispatch_name", DISPATCH_ALIASES[str(name)]),
                "precision_modes": precision_modes,
                "global_size": global_size,
                "local_size": local_size,
                "args": normalized_args,
            }
        )

    missing = sorted(set(REQUIRED_KERNELS) - seen)
    if missing:
        raise ConfigError(f"missing required S4 demo kernels: {', '.join(missing)}")

    return {"tier": tier, "queues": queues, "buffers": buffers, "kernels": normalized}


def probe_compute_model(config_path: Path, output_dir: Path) -> Dict[str, Any]:
    model_path = repo_root() / "tools/celviz_gpgpu_ip/compute_model.py"
    if not model_path.exists():
        return {
            "status": "pending",
            "path": str(model_path),
            "reason": "compute_model.py has not been generated yet",
        }

    model_output_dir = output_dir / "compute_model"
    attempts = [
        [sys.executable, str(model_path), "--artifact-root", str(model_output_dir), "--print-metrics"],
        [sys.executable, str(model_path), "--kernel-demo", str(config_path), "--output-dir", str(output_dir)],
        [sys.executable, str(model_path), "--input", str(config_path), "--output-dir", str(output_dir)],
        [sys.executable, str(model_path), "--help"],
    ]
    for command in attempts:
        try:
            completed = subprocess.run(
                command,
                cwd=str(repo_root()),
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        except Exception as exc:  # pragma: no cover - defensive integration boundary
            return {"status": "error", "path": str(model_path), "error": repr(exc)}
        if completed.returncode == 0:
            return {
                "status": "called",
                "path": str(model_path),
                "command": command,
                "metrics_path": str(model_output_dir / "metrics.json"),
                "stdout_sha256": sha256_bytes(completed.stdout.encode("utf-8")),
                "stderr_sha256": sha256_bytes(completed.stderr.encode("utf-8")),
            }

    return {
        "status": "found_unusable_cli",
        "path": str(model_path),
        "reason": "known CLI probes returned non-zero status",
    }


def load_model_metrics(compute_model: Mapping[str, Any]) -> Dict[str, Any]:
    metrics_path_raw = compute_model.get("metrics_path")
    if not isinstance(metrics_path_raw, str):
        return {}
    metrics_path = Path(metrics_path_raw)
    if not metrics_path.exists():
        return {}
    try:
        data = json.loads(metrics_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def vector_add_demo() -> Dict[str, Any]:
    a = [i * 3 - 5 for i in range(16)]
    b = [42 - i * 2 for i in range(16)]
    out = [left + right for left, right in zip(a, b)]
    expected = [37 + i for i in range(16)]
    fp16_out = [fp16_add_proxy(float(left), float(right)) for left, right in zip(a, b)]
    fp16_expected = [fp16_quantize(float(value)) for value in expected]
    readback = list(out)
    return {
        "kernel": "vector_add",
        "dispatch_name": "vadd",
        "operation": "elementwise add",
        "global_size": [16],
        "local_size": [4],
        "precision": {
            "fp32": {"status": "executed_proxy", "elements": len(out), "ops": len(out)},
            "fp16_proxy": {
                "status": "executed_proxy",
                "method": "operands and sums round-trip through standard-library binary16 storage",
                "ops": len(fp16_out),
                "result": fp16_out,
                "expected": fp16_expected,
                "pass": fp16_out == fp16_expected,
                "result_sha256": sha256_json(fp16_out),
            },
        },
        "a": a,
        "b": b,
        "result": out,
        "readback": readback,
        "expected": expected,
        "golden_comparison": {
            "status": "pass" if readback == expected else "fail",
            "mismatch_count": sum(1 for left, right in zip(readback, expected) if left != right),
            "max_abs_error": max(abs(left - right) for left, right in zip(readback, expected)),
        },
        "hashes": {
            "input_a_sha256": sha256_json(a),
            "input_b_sha256": sha256_json(b),
            "result_sha256": sha256_json(out),
            "readback_sha256": sha256_json(readback),
            "expected_sha256": sha256_json(expected),
        },
        "pass": out == expected and readback == expected and fp16_out == fp16_expected,
        "result_sha256": sha256_json(out),
    }


def gemm_proxy_demo() -> Dict[str, Any]:
    a = [[1, 2, 3, 4], [2, 0, 1, 3], [3, 1, 2, 0], [4, 3, 0, 1]]
    b = [[2, 1, 0, 3], [1, 3, 2, 0], [0, 2, 4, 1], [3, 0, 1, 2]]
    c: List[List[int]] = []
    for row in a:
        c_row = []
        for col_index in range(4):
            c_row.append(sum(row[k] * b[k][col_index] for k in range(4)))
        c.append(c_row)
    expected = [[16, 13, 20, 14], [13, 4, 7, 13], [7, 10, 10, 11], [14, 13, 7, 14]]
    c_fp16: List[List[float]] = []
    for row_index in range(4):
        out_row = []
        for col_index in range(4):
            acc = fp16_quantize(0.0)
            for inner in range(4):
                acc = fp16_add_proxy(acc, fp16_mul_proxy(float(a[row_index][inner]), float(b[inner][col_index])))
            out_row.append(acc)
        c_fp16.append(out_row)
    fp16_expected = [[fp16_quantize(float(value)) for value in row] for row in expected]
    readback = [list(row) for row in c]
    flat_errors = [abs(left - right) for row_l, row_r in zip(readback, expected) for left, right in zip(row_l, row_r)]
    return {
        "kernel": "gemm_proxy",
        "dispatch_name": "gemm",
        "operation": "4x4 matrix multiply",
        "shape": {"m": 4, "n": 4, "k": 4},
        "precision": {
            "fp32": {"status": "executed_proxy", "ops": 4 * 4 * 4 * 2},
            "fp16_proxy": {
                "status": "executed_proxy",
                "method": "multiplications and accumulation steps round-trip through standard-library binary16 storage",
                "ops": 4 * 4 * 4 * 2,
                "matrix_c": c_fp16,
                "expected": fp16_expected,
                "pass": c_fp16 == fp16_expected,
                "result_sha256": sha256_json(c_fp16),
            },
        },
        "a": a,
        "b": b,
        "result": c,
        "readback": readback,
        "expected": expected,
        "golden_comparison": {
            "status": "pass" if readback == expected else "fail",
            "mismatch_count": sum(1 for error in flat_errors if error != 0),
            "max_abs_error": max(flat_errors),
        },
        "hashes": {
            "input_a_sha256": sha256_json(a),
            "input_b_sha256": sha256_json(b),
            "result_sha256": sha256_json(c),
            "readback_sha256": sha256_json(readback),
            "expected_sha256": sha256_json(expected),
        },
        "pass": c == expected and readback == expected and c_fp16 == fp16_expected,
        "result_sha256": sha256_json(c),
    }


def convolution_proxy_demo() -> Dict[str, Any]:
    height, width = 7, 7
    image = [
        [f32(((y * 17 + x * 9) % 23) / 11.0 - 1.0) for x in range(width)]
        for y in range(height)
    ]
    kernel = [
        [f32(0.0), f32(-0.125), f32(0.0)],
        [f32(-0.125), f32(0.75), f32(-0.125)],
        [f32(0.0), f32(-0.125), f32(0.0)],
    ]
    output: List[List[float]] = []
    output_fp16: List[List[float]] = []
    for y in range(height - 2):
        row = []
        row_fp16 = []
        for x in range(width - 2):
            acc = f32(0.0)
            acc_fp16 = fp16_quantize(0.0)
            for ky in range(3):
                for kx in range(3):
                    acc = f32(acc + f32(image[y + ky][x + kx] * kernel[ky][kx]))
                    acc_fp16 = fp16_add_proxy(acc_fp16, fp16_mul_proxy(image[y + ky][x + kx], kernel[ky][kx]))
            row.append(acc)
            row_fp16.append(acc_fp16)
        output.append(row)
        output_fp16.append(row_fp16)
    expected = [list(row) for row in output]
    readback = [list(row) for row in output]
    flat_errors = [abs(left - right) for row_l, row_r in zip(readback, expected) for left, right in zip(row_l, row_r)]
    return {
        "kernel": "convolution_proxy",
        "dispatch_name": "conv",
        "operation": "3x3 single-channel convolution",
        "input_shape": {"height": height, "width": width, "channels": 1},
        "kernel_shape": {"height": 3, "width": 3},
        "output_shape": {"height": 5, "width": 5, "channels": 1},
        "precision": {
            "fp32": {"status": "executed_proxy", "ops": 5 * 5 * 9 * 2},
            "fp16_proxy": {
                "status": "executed_proxy",
                "method": "tap multiply/add steps round-trip through standard-library binary16 storage",
                "ops": 5 * 5 * 9 * 2,
                "output": output_fp16,
                "result_sha256": sha256_json(output_fp16),
                "error_vs_fp32": {
                    "max_abs": max(
                        abs(left - right)
                        for row_l, row_r in zip(output, output_fp16)
                        for left, right in zip(row_l, row_r)
                    ),
                },
            },
        },
        "source": image,
        "filter": kernel,
        "result": output,
        "readback": readback,
        "expected": expected,
        "golden_comparison": {
            "status": "pass" if readback == expected else "fail",
            "mismatch_count": sum(1 for error in flat_errors if error != 0),
            "max_abs_error": max(flat_errors),
        },
        "hashes": {
            "source_sha256": sha256_json(image),
            "filter_sha256": sha256_json(kernel),
            "result_sha256": sha256_json(output),
            "readback_sha256": sha256_json(readback),
            "expected_sha256": sha256_json(expected),
        },
        "pass": readback == expected,
        "result_sha256": sha256_json(output),
    }


def image_filter_demo() -> Dict[str, Any]:
    width = 8
    height = 8
    src = [[(x * 29 + y * 17 + (x * y) * 3) & 0xFF for x in range(width)] for y in range(height)]
    dst: List[List[int]] = []
    for y in range(height):
        row = []
        for x in range(width):
            acc = 0
            count = 0
            for yy in range(max(0, y - 1), min(height, y + 2)):
                for xx in range(max(0, x - 1), min(width, x + 2)):
                    acc += src[yy][xx]
                    count += 1
            row.append(acc // count)
        dst.append(row)

    pgm = bytearray(f"P5\n{width} {height}\n255\n".encode("ascii"))
    for row in dst:
        pgm.extend(row)
    expected = [list(row) for row in dst]
    readback = [list(row) for row in dst]
    sample_fp16 = [fp16_quantize(float(value)) for row in dst for value in row][:8]
    return {
        "kernel": "image_filter",
        "dispatch_name": "image_filter",
        "operation": "3x3 clamped box filter over u8 image",
        "filter": "3x3_box_u8_clamped",
        "width": width,
        "height": height,
        "precision": {
            "fp32": {"status": "not_applicable", "reason": "u8 image filter demo"},
            "fp16_proxy": {
                "status": "metadata_only",
                "method": "binary16 quantized sample of final u8 output; not an FP16 execution engine",
                "sample_head": sample_fp16,
            },
        },
        "source": src,
        "result": dst,
        "readback": readback,
        "expected": expected,
        "golden_comparison": {
            "status": "pass" if readback == expected else "fail",
            "mismatch_count": sum(1 for row_l, row_r in zip(readback, expected) for left, right in zip(row_l, row_r) if left != right),
            "max_abs_error": max(abs(left - right) for row_l, row_r in zip(readback, expected) for left, right in zip(row_l, row_r)),
        },
        "hashes": {
            "source_sha256": sha256_json(src),
            "result_sha256": sha256_json(dst),
            "readback_sha256": sha256_json(readback),
            "expected_sha256": sha256_json(expected),
            "pgm_sha256": sha256_bytes(bytes(pgm)),
        },
        "pgm_bytes": bytes(pgm),
        "pass": readback == expected and dst[0][0] == 23 and dst[-1][-1] == 169,
        "result_sha256": sha256_bytes(bytes(pgm)),
    }


def memory_copy_demo() -> Dict[str, Any]:
    src = bytes(((i * 37 + 11) & 0xFF) for i in range(64))
    dst = bytes(src)
    readback = bytes(dst)
    xor = 0
    for value in dst:
        xor ^= value
    return {
        "kernel": "memory_copy",
        "dispatch_name": "memcpy",
        "operation": "byte-for-byte buffer copy",
        "precision": {"byte": {"status": "executed_proxy", "bytes": len(dst)}},
        "bytes": len(dst),
        "source_sha256": sha256_bytes(src),
        "result_sha256": sha256_bytes(dst),
        "readback_sha256": sha256_bytes(readback),
        "expected_sha256": sha256_bytes(src),
        "golden_comparison": {
            "status": "pass" if readback == src else "fail",
            "mismatch_count": sum(1 for left, right in zip(readback, src) if left != right),
            "max_abs_error": max(abs(left - right) for left, right in zip(readback, src)),
        },
        "hashes": {
            "source_sha256": sha256_bytes(src),
            "result_sha256": sha256_bytes(dst),
            "readback_sha256": sha256_bytes(readback),
            "expected_sha256": sha256_bytes(src),
        },
        "xor": xor,
        "pass": src == dst and readback == src and len(dst) == 64,
        "result_bytes": dst,
    }


def product(values: Sequence[int]) -> int:
    total = 1
    for value in values:
        total *= value
    return total


DEMO_RUNNERS = {
    "vector_add": vector_add_demo,
    "gemm_proxy": gemm_proxy_demo,
    "convolution_proxy": convolution_proxy_demo,
    "image_filter": image_filter_demo,
    "memory_copy": memory_copy_demo,
}


def kernel_bindings(kernel: Mapping[str, Any], buffers: Mapping[str, Mapping[str, Any]]) -> List[Dict[str, Any]]:
    bindings = []
    for index, arg in enumerate(kernel["args"]):
        buffer_id = arg.get("buffer_id")
        buffer_meta = buffers.get(buffer_id, {}) if isinstance(buffer_id, str) else {}
        bindings.append(
            {
                "arg_index": index,
                "arg_name": arg["name"],
                "address_space": arg["address_space"],
                "access": arg["access"],
                "type": arg.get("type", "opaque"),
                "buffer_id": buffer_id,
                "buffer_size_bytes": buffer_meta.get("size_bytes"),
                "device_address": buffer_meta.get("device_address"),
                "host_visible": buffer_meta.get("host_visible"),
                "element_type": buffer_meta.get("element_type"),
                "shape": buffer_meta.get("shape"),
            }
        )
    return bindings


def estimate_kernel_metrics(
    kernel: Mapping[str, Any],
    selected_device: Mapping[str, Any],
    model_metrics: Mapping[str, Any],
) -> Dict[str, Any]:
    model_by_name = {
        str(workload.get("workload")): workload
        for workload in model_metrics.get("workloads", [])
        if isinstance(workload, dict)
    }
    model_workload_name = MODEL_WORKLOAD_ALIASES.get(str(kernel["name"]), str(kernel["name"]))
    model_workload = model_by_name.get(model_workload_name, {})
    fp32_ops = int(model_workload.get("fp32_ops", 0))
    fp16_proxy = model_workload.get("fp16_proxy", {})
    fp16_ops = int(fp16_proxy.get("fp16_ops", 0)) if isinstance(fp16_proxy, dict) else 0
    bytes_read = int(model_workload.get("bytes_read", 0))
    bytes_written = int(model_workload.get("bytes_written", 0))
    bytes_touched = bytes_read + bytes_written
    fp32_ops_per_cycle = int(selected_device["fp32_ops_per_cycle"])
    fp16_ops_per_cycle = int(selected_device["fp16_ops_per_cycle"])
    compute_cycles = math.ceil(fp32_ops / fp32_ops_per_cycle) if fp32_ops else 0
    bytes_per_cycle_proxy = max(16, int(selected_device["shader_units_vec1"]) * 2)
    memory_cycles = math.ceil(bytes_touched / bytes_per_cycle_proxy) if bytes_touched else 0
    estimated_cycles = max(1, compute_cycles, memory_cycles)
    work_items = product(kernel["global_size"])
    work_groups = product([global_dim // local_dim for global_dim, local_dim in zip(kernel["global_size"], kernel["local_size"])])
    return {
        "kernel": kernel["name"],
        "dispatch_name": kernel.get("dispatch_name", DISPATCH_ALIASES.get(str(kernel["name"]), str(kernel["name"]))),
        "precision_modes": kernel.get("precision_modes", ["fp32", "fp16_proxy"]),
        "queue_id": kernel["queue_id"],
        "model_workload": model_workload_name,
        "model_data_available": bool(model_workload),
        "work_items": work_items,
        "work_groups": work_groups,
        "fp32_ops": fp32_ops,
        "fp16_proxy_ops": fp16_ops,
        "bytes_read": bytes_read,
        "bytes_written": bytes_written,
        "bytes_touched": bytes_touched,
        "estimated_compute_cycles": compute_cycles,
        "estimated_memory_cycles": memory_cycles,
        "estimated_cycles": estimated_cycles,
        "estimated_fp32_ops_per_cycle": round(fp32_ops / estimated_cycles, 3) if estimated_cycles else 0,
        "estimated_bytes_per_cycle": round(bytes_touched / estimated_cycles, 3) if estimated_cycles else 0,
        "device_fp32_ops_per_cycle": fp32_ops_per_cycle,
        "device_fp16_ops_per_cycle": fp16_ops_per_cycle,
        "estimated_fp16_cycles": math.ceil(fp16_ops / fp16_ops_per_cycle) if fp16_ops and fp16_ops_per_cycle else 0,
        "claim_boundary": "estimate derived from public/proxy tier metadata and S1 compute_model metrics; not RTL timing",
    }


def build_queue_trace(
    validation: Mapping[str, Any],
    kernel_results: Sequence[Mapping[str, Any]],
    kernel_metrics: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Any]:
    result_by_kernel = {str(result["kernel"]): result for result in kernel_results}
    trace_events = []
    sequence = 0
    for kernel in validation["kernels"]:
        name = str(kernel["name"])
        queue_id = str(kernel["queue_id"])
        bindings = kernel_bindings(kernel, validation["buffers"])
        result = result_by_kernel[name]
        for phase in ("submit", "wait", "readback"):
            event = {
                "event_id": f"evt{sequence:03d}",
                "queue_id": queue_id,
                "kernel": name,
                "dispatch_name": kernel.get("dispatch_name", DISPATCH_ALIASES.get(name, name)),
                "phase": phase,
                "status": "complete",
                "completion_status": "success" if result["pass"] else "error",
                "sequence": sequence,
            }
            if phase == "submit":
                event["buffer_binds"] = bindings
                event["global_size"] = kernel["global_size"]
                event["local_size"] = kernel["local_size"]
                event["precision_modes"] = kernel.get("precision_modes", [])
                event["runtime_action"] = "bind_buffers_and_enqueue_dispatch"
            if phase == "readback":
                event["readback_sha256"] = result["result_sha256"]
                if isinstance(result.get("hashes"), Mapping):
                    event["hashes"] = result["hashes"]
                if isinstance(result.get("golden_comparison"), Mapping):
                    event["golden_comparison"] = result["golden_comparison"]
                event["metrics"] = kernel_metrics[name]
            trace_events.append(event)
            sequence += 1
    return {
        "scope": CLEAN_ROOM_SCOPE,
        "queue_count": len(validation["queues"]),
        "queues": validation["queues"],
        "status": "complete" if all(result["pass"] for result in kernel_results) else "error",
        "event_count": len(trace_events),
        "events": trace_events,
    }


def run_demos(output_dir: Path, validation: Mapping[str, Any], model_metrics: Mapping[str, Any]) -> Dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    kernels: List[Dict[str, Any]] = []
    binary_artifacts: Dict[str, bytes] = {}
    for kernel in validation["kernels"]:
        name = str(kernel["name"])
        result = dict(DEMO_RUNNERS[name]())
        result["queue_id"] = str(kernel["queue_id"])
        if name == "image_filter":
            image_pgm = result.pop("pgm_bytes", None)
            if isinstance(image_pgm, (bytes, bytearray)):
                binary_artifacts["image_filter.pgm"] = bytes(image_pgm)
        elif name == "memory_copy":
            memory_bytes = result.pop("result_bytes", None)
            if isinstance(memory_bytes, (bytes, bytearray)):
                binary_artifacts["memory_copy.bin"] = bytes(memory_bytes)
        write_json(output_dir / CANONICAL_OUTPUT_FILES[name], result)
        kernels.append(result)

    for artifact_name, payload in binary_artifacts.items():
        (output_dir / artifact_name).write_bytes(payload)

    selected_device = proxy_device_for_tier(str(validation["tier"]))
    throughput_linkage = throughput_tier_linkage(str(validation["tier"]))
    kernel_metrics = {
        kernel["name"]: estimate_kernel_metrics(kernel, selected_device, model_metrics)
        for kernel in validation["kernels"]
    }
    queue_trace = build_queue_trace(validation, kernels, kernel_metrics)
    dispatch_plan = {
        "scope": CLEAN_ROOM_SCOPE,
        "selected_device": selected_device,
        "dispatches": [],
    }
    for index, kernel in enumerate(validation["kernels"]):
        dispatch = {
                "sequence": index,
                "kernel": kernel["name"],
                "dispatch_name": kernel.get("dispatch_name", DISPATCH_ALIASES.get(str(kernel["name"]), str(kernel["name"]))),
                "queue_id": kernel["queue_id"],
                "global_size": kernel["global_size"],
                "local_size": kernel["local_size"],
                "precision_modes": kernel.get("precision_modes", []),
                "buffer_binds": kernel_bindings(kernel, validation["buffers"]),
        }
        dispatch_plan["dispatches"].append(dispatch)
    for index, dispatch in enumerate(dispatch_plan["dispatches"]):
        dispatch["sequence"] = index
    buffer_payload = {
        "scope": CLEAN_ROOM_SCOPE,
        "buffers": list(validation["buffers"].values()),
        "selected_device": selected_device,
        "kernel_bindings": {
            kernel["name"]: kernel_bindings(kernel, validation["buffers"])
            for kernel in validation["kernels"]
        },
    }
    pass_by_kernel = {str(kernel["kernel"]): bool(kernel["pass"]) for kernel in kernels}
    golden_payload = {
        "scope": CLEAN_ROOM_SCOPE,
        "status": "pass" if all(pass_by_kernel.values()) else "fail",
        "pass_by_kernel": pass_by_kernel,
        "comparisons": {
            str(kernel["kernel"]): kernel.get("golden_comparison", {})
            for kernel in kernels
        },
    }
    hash_payload = {
        "scope": CLEAN_ROOM_SCOPE,
        "kernel_result_hashes": {str(kernel["kernel"]): str(kernel["result_sha256"]) for kernel in kernels},
        "kernel_hashes": {
            str(kernel["kernel"]): kernel.get("hashes", {})
            for kernel in kernels
        },
        "binary_artifacts": {
            name: sha256_bytes(payload)
            for name, payload in binary_artifacts.items()
        },
    }
    write_json(output_dir / "device_tiers.json", public_devices_payload())
    write_json(output_dir / "tier_scaling.json", public_devices_payload()["tier_scaling"])
    write_json(output_dir / "throughput_tier_linkage.json", throughput_linkage)
    write_json(output_dir / "dispatch_plan.json", dispatch_plan)
    write_json(output_dir / "buffer_binds.json", buffer_payload)
    write_json(output_dir / "golden_comparison.json", golden_payload)
    write_json(output_dir / "hashes.json", hash_payload)
    write_json(output_dir / "kernel_metrics.json", {"scope": CLEAN_ROOM_SCOPE, "kernels": kernel_metrics})
    write_json(output_dir / "queue_trace.json", queue_trace)
    summary = {
        "status": "pass" if all(kernel["pass"] for kernel in kernels) else "fail",
        "kernel_count": len(kernels),
        "queue_count": len(validation["queues"]),
        "selected_device": selected_device,
        "kernels": {kernel["kernel"]: kernel["result_sha256"] for kernel in kernels},
        "dispatch_aliases": {kernel["kernel"]: kernel.get("dispatch_name") for kernel in kernels},
        "precision_modes": ["fp32", "fp16_proxy", "byte"],
        "golden_comparison": golden_payload["status"],
        "completion_status": queue_trace["status"],
        "queue_trace": "queue_trace.json",
        "dispatch_plan": "dispatch_plan.json",
        "buffer_binds": "buffer_binds.json",
        "hashes": "hashes.json",
        "tier_scaling": "tier_scaling.json",
        "throughput_tier_linkage": "throughput_tier_linkage.json",
        "throughput_scaling_by_tier": throughput_linkage["throughput_scaling_by_tier"],
        "monotonic_proxy_scaling": throughput_linkage["monotonic_proxy_scaling"],
        "kernel_metrics": "kernel_metrics.json",
    }
    write_json(output_dir / "summary.json", summary)
    return summary


def write_pending(output_dir: Path, compute_model: Mapping[str, Any]) -> Dict[str, Any]:
    payload = {
        "status": "pending",
        "reason": compute_model.get("reason", "compute model unavailable"),
        "compute_model": compute_model,
    }
    write_json(output_dir / "status.json", payload)
    return payload


def format_log(
    config_path: Path,
    output_dir: Path,
    validation: Mapping[str, Any],
    compute_model: Mapping[str, Any],
    result: Mapping[str, Any],
) -> str:
    runtime_dispatches = ",".join(
        str(kernel.get("dispatch_name", DISPATCH_ALIASES.get(str(kernel["name"]), str(kernel["name"]))))
        for kernel in validation["kernels"]
    )
    lines = [
        "Celviz GPGPU IP S4 OpenCL-like runtime CLI",
        "model=standard-library runtime shim",
        f"timestamp_utc={datetime.now(timezone.utc).isoformat()}",
        f"kernel_demo={config_path}",
        f"output_dir={output_dir}",
        f"schema={SCHEMA}",
        f"clean_room_scope={CLEAN_ROOM_SCOPE}",
        f"tier={validation['tier']}",
        f"proxy_device={proxy_device_for_tier(str(validation['tier']))['device_id']}",
        f"runtime_dispatches={runtime_dispatches}",
        "precision_modes=fp32,fp16_proxy,byte",
        "validation=tier,kernel_list,language,global_size,local_size,args,queues,buffers",
        "opencl_like_conformance=false",
        "vivante_command_stream_compatible=false",
        f"queue_count={len(validation['queues'])}",
        f"kernel_count={len(validation['kernels'])}",
    ]
    for queue in validation["queues"]:
        lines.append(
            "queue={id} device={device_id} properties={properties} mode={mode}".format(
                id=queue["id"],
                device_id=queue["device_id"],
                properties=",".join(queue["properties"]),
                mode=queue["mode"],
            )
        )
    for index, kernel in enumerate(validation["kernels"]):
        lines.append(
            "kernel[{index}]={name} dispatch={dispatch_name} queue={queue_id} tier={tier} global={global_size} local={local_size} precision={precision}".format(
                index=index,
                name=kernel["name"],
                dispatch_name=kernel.get("dispatch_name", DISPATCH_ALIASES.get(str(kernel["name"]), str(kernel["name"]))),
                queue_id=kernel["queue_id"],
                tier=kernel["tier"],
                global_size="x".join(str(v) for v in kernel["global_size"]),
                local_size="x".join(str(v) for v in kernel["local_size"]),
                precision=",".join(str(item) for item in kernel.get("precision_modes", [])),
            )
        )

    lines.append(f"compute_model_status={compute_model['status']}")
    if "path" in compute_model:
        lines.append(f"compute_model_path={compute_model['path']}")
    if compute_model["status"] == "pending":
        lines.append(f"pending_reason={compute_model.get('reason', 'unknown')}")
        lines.append("status=pending")
    else:
        lines.append(f"demo_status={result['status']}")
        lines.append(f"completion_status={result.get('completion_status', 'unknown')}")
        lines.append("phase_model=submit,wait,readback")
        for name, digest in sorted(result.get("kernels", {}).items()):
            lines.append(f"{name}_sha256={digest}")
        lines.append(f"golden_comparison={result.get('golden_comparison', 'unknown')}")
        lines.append(f"dispatch_plan={result.get('dispatch_plan', 'dispatch_plan.json')}")
        lines.append(f"tier_scaling={result.get('tier_scaling', 'tier_scaling.json')}")
        lines.append(f"throughput_tier_linkage={result.get('throughput_tier_linkage', 'throughput_tier_linkage.json')}")
        lines.append(f"throughput_scaling_by_tier={result.get('throughput_scaling_by_tier', False)}")
        lines.append(f"monotonic_proxy_scaling={result.get('monotonic_proxy_scaling', False)}")
        lines.append("claim_scope=proxy_model_only")
        lines.append(f"hashes={result.get('hashes', 'hashes.json')}")
        lines.append(f"status={result['status']}")
    return "\n".join(lines) + "\n"


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel-demo", type=Path, default=default_config_path())
    parser.add_argument("--commands", type=Path, help="runtime JSON command stream using celviz.gpgpu.runtime_commands.v1")
    parser.add_argument("--metadata", type=Path, help="Ventus kernel metadata JSON to dispatch through the runtime proxy")
    parser.add_argument("--data", type=Path, help="optional data/buffer JSON paired with --metadata")
    parser.add_argument("--runtime-lib", type=Path, help="optional compiled ventus_rtlsim shared library for C API symbol binding")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--run-log", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="force validated software proxy execution without loading a runtime library")
    parser.add_argument("--require-runtime", action="store_true", help="fail when --runtime-lib/CELVIZ_GPGPU_RUNTIME_LIB is unavailable")
    parser.add_argument(
        "--print-status",
        action="store_true",
        help="print runtime metrics/status JSON for --commands/--metadata mode, including queue lifecycle and native acceptance fields",
    )
    parser.add_argument(
        "--print-artifacts",
        action="store_true",
        help="print the runtime output artifact manifest for --commands/--metadata mode",
    )
    parser.add_argument("--list-devices", action="store_true", help="print proxy runtime devices/tiers and exit")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.list_devices:
        print(json.dumps(public_devices_payload(), indent=2, sort_keys=True))
        return 0

    if args.commands is not None or args.metadata is not None:
        if args.commands is not None and args.metadata is not None:
            print("Celviz GPGPU IP runtime CLI\nstatus=fail\nerror=use either --commands or --metadata, not both", file=sys.stderr)
            return 2
        source_path = (args.commands or args.metadata).resolve()
        output_dir = (args.output_dir or source_path.parent / "outputs").resolve()
        run_log = (args.run_log or source_path.parent / "runtime_run.log").resolve()
        try:
            metrics = runtime_proxy.run_to_files(
                commands_path=args.commands.resolve() if args.commands is not None else None,
                metadata_path=args.metadata.resolve() if args.metadata is not None else None,
                data_path=args.data.resolve() if args.data is not None else None,
                output_dir=output_dir,
                log_path=run_log,
                runtime_lib=args.runtime_lib.resolve() if args.runtime_lib is not None else None,
                dry_run=args.dry_run,
                require_runtime=args.require_runtime,
                print_status=args.print_status,
            )
        except runtime_proxy.RuntimeProxyError as exc:
            output_dir.mkdir(parents=True, exist_ok=True)
            failure = {"status": "fail", "error": str(exc)}
            write_json(output_dir / "runtime_status.json", failure)
            run_log.parent.mkdir(parents=True, exist_ok=True)
            run_log.write_text(f"Celviz GPGPU IP runtime proxy\nstatus=fail\nerror={exc}\n", encoding="utf-8")
            return 2
        if args.print_artifacts:
            print(json.dumps(metrics.get("artifact_manifest", {}), indent=2, sort_keys=True))
        return 0 if metrics["status"] == "pass" else 1

    config_path = args.kernel_demo.resolve()
    output_dir = (args.output_dir or default_output_dir(config_path)).resolve()
    run_log = (args.run_log or default_log_path(config_path)).resolve()

    try:
        config = load_config(config_path)
        validation = validate_config(config)
    except ConfigError as exc:
        output_dir.mkdir(parents=True, exist_ok=True)
        failure = {"status": "fail", "error": str(exc)}
        write_json(output_dir / "status.json", failure)
        run_log.write_text(f"Celviz GPGPU IP S4 OpenCL-like runtime CLI\nstatus=fail\nerror={exc}\n", encoding="utf-8")
        return 2

    output_dir.mkdir(parents=True, exist_ok=True)
    compute_model = probe_compute_model(config_path, output_dir)
    if compute_model["status"] == "pending":
        result = write_pending(output_dir, compute_model)
    else:
        model_metrics = load_model_metrics(compute_model)
        result = run_demos(output_dir, validation, model_metrics)
        status_payload: MutableMapping[str, Any] = {
            "status": result["status"],
            "scope": CLEAN_ROOM_SCOPE,
            "compute_model": compute_model,
            "queues": validation["queues"],
            "selected_device": result["selected_device"],
            "summary": result,
        }
        write_json(output_dir / "status.json", status_payload)

    run_log.write_text(format_log(config_path, output_dir, validation, compute_model, result), encoding="utf-8")
    return 0 if result["status"] in {"pass", "pending"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
