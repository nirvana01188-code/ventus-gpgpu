#!/usr/bin/env python3
"""Clean-room OpenCL C subset compiler and runtime ABI evidence generator.

This tool intentionally implements a small, non-conformant OpenCL-like subset
for first-stage Celviz GPGPU IP ABI evidence.  It parses known-safe kernel
signatures, validates address spaces and launch metadata, emits Ventus-style
kernel ABI JSON, and builds runtime command JSON consumable by runtime_proxy.py.
It does not implement OpenCL 3.0, SPIR-V, a vendor compiler, or a proprietary
driver ABI.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, MutableMapping, Sequence

try:
    from . import runtime_proxy
except ImportError:  # pragma: no cover - direct script fallback
    import runtime_proxy  # type: ignore


SCHEMA = "celviz.gpgpu.opencl_subset.v1"
ABI_SCHEMA = "celviz.gpgpu.opencl_subset.kernel_abi.v1"
EVIDENCE_SCHEMA = "celviz.gpgpu.opencl_subset.evidence.v1"
CLEAN_ROOM_SCOPE = (
    "clean-room OpenCL C subset only; non-conformant and not OpenCL 3.0, SPIR-V, "
    "Vivante compiler, proprietary command stream, SDK, firmware, or driver ABI"
)
SUPPORTED_ADDRESS_SPACES = {"__global", "__local", "__constant", "__private"}
SUPPORTED_SCALAR_TYPES = {"char", "uchar", "short", "ushort", "int", "uint", "long", "ulong", "float", "half"}
SUPPORTED_VECTOR_WIDTHS = {2, 3, 4, 8, 16}
SUPPORTED_BUILTINS = {"get_global_id", "get_local_id", "get_group_id", "get_global_size", "get_local_size", "barrier"}
UNSUPPORTED_TOKENS = (
    "image2d_t",
    "image3d_t",
    "sampler_t",
    "pipe",
    "queue_t",
    "clk_event_t",
    "event_t",
    "async_work_group_copy",
    "read_image",
    "write_image",
    "atom_",
    "atomic_",
    "sub_group",
    "work_group_reduce",
    "printf",
    "double",
)
TYPE_SIZES = {
    "char": 1,
    "uchar": 1,
    "short": 2,
    "ushort": 2,
    "half": 2,
    "int": 4,
    "uint": 4,
    "float": 4,
    "long": 8,
    "ulong": 8,
}
ADDRESS_SPACE_FLAGS = {
    "__global": "global",
    "__local": "local",
    "__constant": "constant",
    "__private": "private",
}
PRECISION_BY_TYPE = {"half": "fp16", "float": "fp32"}
DEFAULT_OUTPUT = Path("artifacts/rank_01_vivante_3d_gpgpu_ip/demo/opencl_subset")


class SubsetError(ValueError):
    """Raised when source or launch metadata leaves the supported subset."""


@dataclass(frozen=True)
class ArgInfo:
    name: str
    type_name: str
    base_type: str
    vector_width: int
    pointer: bool
    address_space: str
    access: str
    size_bytes: int
    abi_offset: int

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type_name,
            "base_type": self.base_type,
            "vector_width": self.vector_width,
            "pointer": self.pointer,
            "address_space": ADDRESS_SPACE_FLAGS[self.address_space],
            "opencl_address_space": self.address_space,
            "access": self.access,
            "size_bytes": self.size_bytes,
            "abi_offset": self.abi_offset,
        }


@dataclass(frozen=True)
class KernelSpec:
    name: str
    source: str
    global_size: tuple[int, int, int]
    local_size: tuple[int, int, int]
    buffers: tuple[dict[str, Any], ...]
    scalar_args: Mapping[str, int | float]
    precision: str
    workgroup_local_bytes: int = 0
    private_bytes_per_thread: int = 0
    sgpr_count: int = 16
    vgpr_count: int = 24
    kernel_entry: int = 0
    description: str = ""


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def strip_comments(source: str) -> str:
    no_block = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return re.sub(r"//.*", "", no_block)


def split_args(arg_text: str) -> list[str]:
    result: list[str] = []
    depth = 0
    start = 0
    for index, char in enumerate(arg_text):
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif char == "," and depth == 0:
            result.append(arg_text[start:index].strip())
            start = index + 1
    tail = arg_text[start:].strip()
    if tail:
        result.append(tail)
    return result


def align(value: int, boundary: int) -> int:
    return int(math.ceil(value / boundary) * boundary)


def parse_type(type_text: str) -> tuple[str, int]:
    match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*?)(\d+)?", type_text)
    if not match:
        raise SubsetError(f"unsupported type syntax: {type_text}")
    base = match.group(1)
    vector_width = int(match.group(2) or "1")
    if base not in SUPPORTED_SCALAR_TYPES:
        raise SubsetError(f"unsupported scalar type: {base}")
    if vector_width != 1 and vector_width not in SUPPORTED_VECTOR_WIDTHS:
        raise SubsetError(f"unsupported vector width for {type_text}")
    return base, vector_width


def parse_access(tokens: Sequence[str], pointer: bool) -> str:
    lowered = set(tokens)
    if not pointer:
        return "by_value"
    if "const" in lowered:
        return "read_only"
    if "restrict" in lowered:
        return "read_write_restrict"
    return "read_write"


def parse_arg(arg_text: str, offset: int) -> ArgInfo:
    normalized = " ".join(arg_text.replace("*", " * ").split())
    tokens = normalized.split()
    if not tokens:
        raise SubsetError("empty argument")
    name = tokens[-1]
    if name == "*":
        raise SubsetError(f"missing argument name in: {arg_text}")
    if name.startswith("*"):
        name = name[1:]
    pointer = "*" in tokens
    address_spaces = [token for token in tokens if token in SUPPORTED_ADDRESS_SPACES]
    address_space = address_spaces[0] if address_spaces else "__private"
    if len(address_spaces) > 1:
        raise SubsetError(f"multiple address spaces in argument {name}")
    if pointer and address_space == "__private":
        raise SubsetError(f"pointer argument {name} must declare an address space")
    type_candidates = [
        token
        for token in tokens[:-1]
        if token not in SUPPORTED_ADDRESS_SPACES and token not in {"const", "volatile", "restrict", "*"}
    ]
    if len(type_candidates) != 1:
        raise SubsetError(f"argument {name} must have one supported value type")
    type_name = type_candidates[0]
    base, vector_width = parse_type(type_name)
    if pointer:
        size = 8
        abi_offset = align(offset, 8)
    else:
        size = TYPE_SIZES[base] * vector_width
        abi_offset = align(offset, min(size, 8))
    return ArgInfo(
        name=name,
        type_name=type_name,
        base_type=base,
        vector_width=vector_width,
        pointer=pointer,
        address_space=address_space,
        access=parse_access(tokens, pointer),
        size_bytes=size,
        abi_offset=abi_offset,
    )


def parse_kernel_source(source: str) -> tuple[str, list[ArgInfo], set[str], list[str]]:
    cleaned = strip_comments(source)
    for token in UNSUPPORTED_TOKENS:
        if token in cleaned:
            raise SubsetError(f"unsupported OpenCL feature token: {token}")
    match = re.search(r"__kernel\s+void\s+([A-Za-z_][A-Za-z0-9_]*)\s*\((.*?)\)\s*\{", cleaned, flags=re.S)
    if not match:
        raise SubsetError("source must contain one '__kernel void name(...) {' declaration")
    if len(re.findall(r"__kernel\s+void\s+", cleaned)) != 1:
        raise SubsetError("exactly one kernel per source is supported")
    name = match.group(1)
    offset = 0
    args: list[ArgInfo] = []
    for raw_arg in split_args(match.group(2)):
        arg = parse_arg(raw_arg, offset)
        args.append(arg)
        offset = arg.abi_offset + arg.size_bytes
    builtins = set(re.findall(r"\b(get_global_id|get_local_id|get_group_id|get_global_size|get_local_size|barrier)\s*\(", cleaned))
    unsupported_calls = sorted(
        set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", cleaned))
        - builtins
        - {name, "if", "for", "while", "sizeof"}
    )
    # Allow ordinary C casts/functions only when they are not lower-case OpenCL-ish builtins.
    unsupported_calls = [call for call in unsupported_calls if call.startswith("get_") or call.startswith("work_")]
    if unsupported_calls:
        raise SubsetError(f"unsupported builtin/function calls: {', '.join(unsupported_calls)}")
    return name, args, builtins, []


def product(values: Sequence[int]) -> int:
    result = 1
    for value in values:
        result *= int(value)
    return result


def infer_precision(args: Sequence[ArgInfo], explicit: str | None = None) -> str:
    if explicit:
        return explicit
    precisions = {PRECISION_BY_TYPE[arg.base_type] for arg in args if arg.base_type in PRECISION_BY_TYPE}
    if precisions == {"fp16"}:
        return "fp16"
    if "fp16" in precisions and "fp32" in precisions:
        return "mixed_fp16_fp32"
    return "fp32"


def buffer_maps(spec: KernelSpec, args: Sequence[ArgInfo]) -> tuple[list[int], list[int], list[int], list[dict[str, Any]]]:
    by_name = {str(buf["arg"]): buf for buf in spec.buffers}
    bases: list[int] = []
    sizes: list[int] = []
    allocs: list[int] = []
    records: list[dict[str, Any]] = []
    for arg in args:
        if not arg.pointer:
            continue
        if arg.name not in by_name:
            raise SubsetError(f"missing buffer metadata for pointer argument {arg.name}")
        raw = by_name[arg.name]
        base = int(str(raw["device_address"]), 0) if isinstance(raw["device_address"], str) else int(raw["device_address"])
        size = int(raw["size_bytes"])
        alloc = int(raw.get("alloc_size_bytes", align(size, 64)))
        bases.append(base)
        sizes.append(size)
        allocs.append(alloc)
        records.append(
            {
                "id": str(raw.get("id", arg.name)),
                "arg": arg.name,
                "device_address": hex(base),
                "size_bytes": size,
                "alloc_size_bytes": alloc,
                "address_space": ADDRESS_SPACE_FLAGS[arg.address_space],
                "access": str(raw.get("access", arg.access)),
            }
        )
    return bases, sizes, allocs, records


def scalar_arg_records(spec: KernelSpec, args: Sequence[ArgInfo]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for arg in args:
        if arg.pointer:
            continue
        if arg.name not in spec.scalar_args:
            raise SubsetError(f"missing scalar metadata for argument {arg.name}")
        records.append({**arg.to_json(), "value": spec.scalar_args[arg.name]})
    return records


def compile_kernel(spec: KernelSpec, kernel_id: int) -> dict[str, Any]:
    parsed_name, args, builtins, _warnings = parse_kernel_source(spec.source)
    if parsed_name != spec.name:
        raise SubsetError(f"kernel name mismatch: spec={spec.name} source={parsed_name}")
    if len(spec.global_size) != 3 or len(spec.local_size) != 3:
        raise SubsetError("global_size and local_size must be 3D tuples")
    if any(dim <= 0 for dim in spec.global_size + spec.local_size):
        raise SubsetError("global_size and local_size dimensions must be positive")
    if any(spec.global_size[i] % spec.local_size[i] != 0 for i in range(3)):
        raise SubsetError(f"{spec.name}: global_size must be divisible by local_size")
    if product(spec.local_size) > 256:
        raise SubsetError(f"{spec.name}: local workgroup size exceeds first-stage limit 256")
    bases, sizes, allocs, buffers = buffer_maps(spec, args)
    scalars = scalar_arg_records(spec, args)
    arg_bytes = align(max((arg.abi_offset + arg.size_bytes for arg in args), default=0), 16)
    precision = infer_precision(args, spec.precision)
    local_bytes = int(spec.workgroup_local_bytes)
    if any(arg.address_space == "__local" for arg in args) and local_bytes == 0:
        local_bytes = 1024
    metadata = {
        "schema": ABI_SCHEMA,
        "source_schema": SCHEMA,
        "generated_at": utc_now(),
        "scope": CLEAN_ROOM_SCOPE,
        "name": spec.name,
        "description": spec.description,
        "kernel_id": kernel_id,
        "source_sha256": sha256_text(spec.source),
        "subset": {
            "language": "OpenCL C clean-room subset",
            "conformant_opencl": False,
            "supported_builtins": sorted(SUPPORTED_BUILTINS),
            "used_builtins": sorted(builtins),
            "unsupported_non_goals": list(UNSUPPORTED_TOKENS),
        },
        "args": [arg.to_json() for arg in args],
        "scalar_args": scalars,
        "buffers": buffers,
        "address_spaces": sorted({ADDRESS_SPACE_FLAGS[arg.address_space] for arg in args}),
        "precision": precision,
        "required_fp_mode": precision,
        "global_size": list(spec.global_size),
        "local_size": list(spec.local_size),
        "workgroup_count": [spec.global_size[i] // spec.local_size[i] for i in range(3)],
        "work_items": product(spec.global_size),
        "arg_size_bytes": arg_bytes,
        "metadata": {
            "name": spec.name,
            "startaddr": int(spec.kernel_entry),
            "kernel_id": kernel_id,
            "kernel_size": list(spec.global_size),
            "wf_size": 32,
            "wg_size": max(1, product(spec.local_size) // 32),
            "metaDataBaseAddr": 0x80000000 + kernel_id * 0x10000,
            "ldsSize": local_bytes,
            "pdsSize": int(spec.private_bytes_per_thread),
            "sgprUsage": int(spec.sgpr_count),
            "vgprUsage": int(spec.vgpr_count),
            "pdsBaseAddr": 0,
            "num_buffer": len(bases),
            "buffer_base": bases,
            "buffer_size": sizes,
            "buffer_allocsize": allocs,
        },
    }
    return metadata


def runtime_commands_from_abis(abis: Sequence[Mapping[str, Any]], tier: str) -> dict[str, Any]:
    memory_regions: list[dict[str, Any]] = []
    commands: list[dict[str, Any]] = []
    sequence = 1
    seen_regions: set[tuple[str, str]] = set()
    for abi in abis:
        metadata = dict(abi["metadata"])
        arg_region = ("arg_" + str(abi["name"]), hex(int(metadata["metaDataBaseAddr"])))
        if arg_region not in seen_regions:
            memory_regions.append(
                {
                    "name": arg_region[0],
                    "base": arg_region[1],
                    "size": max(4096, int(abi["arg_size_bytes"]) + 64),
                    "readable": True,
                    "writable": True,
                }
            )
            seen_regions.add(arg_region)
        for buffer in abi["buffers"]:
            region = (str(buffer["id"]), str(buffer["device_address"]))
            if region in seen_regions:
                continue
            memory_regions.append(
                {
                    "name": region[0],
                    "base": region[1],
                    "size": int(buffer["alloc_size_bytes"]),
                    "readable": str(buffer.get("access")) != "write_only",
                    "writable": str(buffer.get("access")) != "read_only",
                }
            )
            seen_regions.add(region)
        commands.append(
            {
                "opcode": "kernel_dispatch",
                "sequence": sequence,
                "queue_id": 0,
                "submit_tag": f"opencl-subset-{abi['name']}",
                "kernel": abi["name"],
                "kernel_entry": hex(int(metadata["startaddr"])),
                "arg_buffer": hex(int(metadata["metaDataBaseAddr"])),
                "arg_bytes": int(abi["arg_size_bytes"]),
                "grid": list(abi["global_size"]),
                "local": list(abi["local_size"]),
                "required_fp_mode": abi["required_fp_mode"],
                "shared_bytes": int(metadata["ldsSize"]),
                "private_bytes_per_thread": int(metadata["pdsSize"]),
                "sgpr_count": int(metadata["sgprUsage"]),
                "vgpr_count": int(metadata["vgprUsage"]),
                "flags": ["INT_ON_COMPLETE", "CAPTURE_COUNTERS"],
                "completion_addr": "0x90000000",
                "ventus_metadata": metadata,
            }
        )
        sequence += 1
    memory_regions.append({"name": "runtime_completion", "base": "0x90000000", "size": 0x10000, "readable": True, "writable": True})
    return {
        "schema": runtime_proxy.RUNTIME_SCHEMA,
        "ip_name": "Celviz GPGPU IP",
        "tier": tier,
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "queues": runtime_proxy.default_queues(runtime_proxy.normalize_tier(tier))[:1],
        "memory_regions": memory_regions,
        "commands": commands,
    }


def validate_evidence(abis: Sequence[Mapping[str, Any]], runtime_data: Mapping[str, Any], runtime_metrics: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    expected = {"vector_add", "gemm", "conv2d", "image_filter"}
    names = {str(abi["name"]) for abi in abis}
    checks.append({"name": "required_kernels_present", "pass": expected <= names, "observed": sorted(names)})
    for abi in abis:
        args = abi.get("args", [])
        checks.append({"name": f"{abi['name']}_has_args", "pass": bool(args), "arg_count": len(args)})
        checks.append({"name": f"{abi['name']}_has_global_address_space", "pass": "global" in abi.get("address_spaces", [])})
        checks.append({"name": f"{abi['name']}_global_local_divisible", "pass": all(int(abi["global_size"][i]) % int(abi["local_size"][i]) == 0 for i in range(3))})
        checks.append({"name": f"{abi['name']}_abi_metadata_complete", "pass": all(key in abi["metadata"] for key in ("kernel_size", "wf_size", "wg_size", "buffer_base", "buffer_size"))})
        checks.append({"name": f"{abi['name']}_precision_declared", "pass": abi.get("precision") in {"fp16", "fp32", "mixed_fp16_fp32"}})
    dispatches = [cmd for cmd in runtime_data.get("commands", []) if cmd.get("opcode") == "kernel_dispatch"]
    checks.append({"name": "runtime_dispatch_count_matches_kernel_count", "pass": len(dispatches) == len(abis), "dispatch_count": len(dispatches)})
    checks.append({"name": "runtime_schema_matches_proxy", "pass": runtime_data.get("schema") == runtime_proxy.RUNTIME_SCHEMA})
    if runtime_metrics is not None:
        summary = runtime_metrics.get("summary", {})
        checks.append({"name": "runtime_proxy_completed_all_subset_dispatches", "pass": int(summary.get("commands_completed", -1)) == len(abis), "summary": summary})
        checks.append({"name": "runtime_proxy_no_failed_subset_dispatches", "pass": int(summary.get("commands_failed", -1)) == 0, "summary": summary})
    return checks


def builtin_specs() -> list[KernelSpec]:
    return [
        KernelSpec(
            name="vector_add",
            description="1D FP32 vector add using global buffers and scalar element count.",
            source="""
__kernel void vector_add(__global const float *a,
                         __global const float *b,
                         __global float *c,
                         uint n) {
  uint gid = get_global_id(0);
  if (gid < n) {
    c[gid] = a[gid] + b[gid];
  }
}
""".strip(),
            global_size=(1024, 1, 1),
            local_size=(64, 1, 1),
            buffers=(
                {"id": "vadd_a", "arg": "a", "device_address": "0x81000000", "size_bytes": 4096, "access": "read_only"},
                {"id": "vadd_b", "arg": "b", "device_address": "0x81001000", "size_bytes": 4096, "access": "read_only"},
                {"id": "vadd_c", "arg": "c", "device_address": "0x81002000", "size_bytes": 4096, "access": "write_only"},
            ),
            scalar_args={"n": 1024},
            precision="fp32",
            kernel_entry=0x1000,
        ),
        KernelSpec(
            name="gemm",
            description="Tiled FP32 GEMM subset kernel with global matrices and scalar dimensions.",
            source="""
__kernel void gemm(__global const float *a,
                   __global const float *b,
                   __global float *c,
                   uint m,
                   uint n,
                   uint k) {
  uint row = get_global_id(1);
  uint col = get_global_id(0);
  if (row < m && col < n) {
    float acc = 0.0f;
    for (uint i = 0; i < k; ++i) {
      acc = acc + a[row * k + i] * b[i * n + col];
    }
    c[row * n + col] = acc;
  }
}
""".strip(),
            global_size=(64, 64, 1),
            local_size=(16, 16, 1),
            buffers=(
                {"id": "gemm_a", "arg": "a", "device_address": "0x81100000", "size_bytes": 16384, "access": "read_only"},
                {"id": "gemm_b", "arg": "b", "device_address": "0x81110000", "size_bytes": 16384, "access": "read_only"},
                {"id": "gemm_c", "arg": "c", "device_address": "0x81120000", "size_bytes": 16384, "access": "write_only"},
            ),
            scalar_args={"m": 64, "n": 64, "k": 64},
            precision="fp32",
            workgroup_local_bytes=0,
            private_bytes_per_thread=16,
            sgpr_count=24,
            vgpr_count=32,
            kernel_entry=0x2000,
        ),
        KernelSpec(
            name="conv2d",
            description="Direct FP32 3x3 convolution subset kernel over NCHW-like linear buffers.",
            source="""
__kernel void conv2d(__global const float *input,
                     __global const float *filter,
                     __global float *output,
                     uint width,
                     uint height) {
  uint x = get_global_id(0);
  uint y = get_global_id(1);
  if (x > 0 && y > 0 && x + 1 < width && y + 1 < height) {
    float acc = 0.0f;
    for (uint fy = 0; fy < 3; ++fy) {
      for (uint fx = 0; fx < 3; ++fx) {
        uint ix = x + fx - 1;
        uint iy = y + fy - 1;
        acc = acc + input[iy * width + ix] * filter[fy * 3 + fx];
      }
    }
    output[y * width + x] = acc;
  }
}
""".strip(),
            global_size=(128, 128, 1),
            local_size=(16, 16, 1),
            buffers=(
                {"id": "conv_input", "arg": "input", "device_address": "0x81200000", "size_bytes": 65536, "access": "read_only"},
                {"id": "conv_filter", "arg": "filter", "device_address": "0x81220000", "size_bytes": 36, "alloc_size_bytes": 64, "access": "read_only"},
                {"id": "conv_output", "arg": "output", "device_address": "0x81230000", "size_bytes": 65536, "access": "write_only"},
            ),
            scalar_args={"width": 128, "height": 128},
            precision="fp32",
            private_bytes_per_thread=24,
            sgpr_count=24,
            vgpr_count=36,
            kernel_entry=0x3000,
        ),
        KernelSpec(
            name="image_filter",
            description="Image-filter subset expressed as buffer math, not OpenCL image objects/samplers.",
            source="""
__kernel void image_filter(__global const uchar4 *src,
                           __global uchar4 *dst,
                           uint width,
                           uint height,
                           float gain) {
  uint x = get_global_id(0);
  uint y = get_global_id(1);
  if (x < width && y < height) {
    uint idx = y * width + x;
    uchar4 px = src[idx];
    dst[idx] = (uchar4)(px.x * gain, px.y * gain, px.z * gain, px.w);
  }
}
""".strip(),
            global_size=(256, 128, 1),
            local_size=(16, 16, 1),
            buffers=(
                {"id": "filter_src_rgba", "arg": "src", "device_address": "0x81300000", "size_bytes": 131072, "access": "read_only"},
                {"id": "filter_dst_rgba", "arg": "dst", "device_address": "0x81340000", "size_bytes": 131072, "access": "write_only"},
            ),
            scalar_args={"width": 256, "height": 128, "gain": 1.25},
            precision="fp32",
            private_bytes_per_thread=8,
            sgpr_count=18,
            vgpr_count=28,
            kernel_entry=0x4000,
        ),
    ]


def compile_builtin(output_dir: Path, tier: str) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    abi_dir = output_dir / "abi"
    source_dir = output_dir / "src"
    abis = []
    for index, spec in enumerate(builtin_specs(), start=1):
        source_path = source_dir / f"{spec.name}.cl"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(spec.source + "\n", encoding="utf-8")
        abi = compile_kernel(spec, index)
        abi["source_path"] = str(source_path)
        write_json(abi_dir / f"{spec.name}.kernel_abi.json", abi)
        abis.append(abi)
    runtime_data = runtime_commands_from_abis(abis, tier)
    write_json(output_dir / "runtime_commands.json", runtime_data)
    evidence = {
        "schema": EVIDENCE_SCHEMA,
        "generated_at": utc_now(),
        "scope": CLEAN_ROOM_SCOPE,
        "tier": tier,
        "kernel_count": len(abis),
        "kernels": [
            {
                "name": abi["name"],
                "abi": str(abi_dir / f"{abi['name']}.kernel_abi.json"),
                "source_sha256": abi["source_sha256"],
                "global_size": abi["global_size"],
                "local_size": abi["local_size"],
                "precision": abi["precision"],
                "address_spaces": abi["address_spaces"],
            }
            for abi in abis
        ],
        "runtime_commands_path": str(output_dir / "runtime_commands.json"),
        "checks": validate_evidence(abis, runtime_data),
        "status": "pass",
    }
    evidence["status"] = "pass" if all(check["pass"] for check in evidence["checks"]) else "fail"
    write_json(output_dir / "opencl_subset_evidence.json", evidence)
    return abis, runtime_data, evidence


def run_demo(output_dir: Path, tier: str) -> dict[str, Any]:
    abis, runtime_data, evidence = compile_builtin(output_dir, tier)
    runtime_out = output_dir / "runtime_proxy"
    runtime_log = output_dir / "runtime_proxy.log"
    metrics = runtime_proxy.run_to_files(
        commands_path=output_dir / "runtime_commands.json",
        metadata_path=None,
        data_path=None,
        output_dir=runtime_out,
        log_path=runtime_log,
        dry_run=True,
    )
    evidence["runtime_proxy"] = {
        "metrics_path": str(runtime_out / "runtime_metrics.json"),
        "status_path": str(runtime_out / "runtime_status.json"),
        "log_path": str(runtime_log),
        "summary": metrics.get("summary", {}),
    }
    evidence["checks"] = validate_evidence(abis, runtime_data, metrics)
    evidence["status"] = "pass" if all(check["pass"] for check in evidence["checks"]) else "fail"
    write_json(output_dir / "opencl_subset_evidence.json", evidence)
    log_lines = [
        f"opencl_subset status={evidence['status']}",
        f"kernels={','.join(str(abi['name']) for abi in abis)}",
        f"runtime_commands={output_dir / 'runtime_commands.json'}",
        f"runtime_summary={json.dumps(metrics.get('summary', {}), sort_keys=True)}",
        f"scope={CLEAN_ROOM_SCOPE}",
    ]
    (output_dir / "opencl_subset_check.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    return evidence


def load_single_source(path: Path, output_dir: Path, tier: str, name: str | None, global_size: Sequence[int], local_size: Sequence[int]) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8")
    parsed_name, args, _builtins, _warnings = parse_kernel_source(source)
    kernel_name = name or parsed_name
    buffers = []
    scalar_args: dict[str, int | float] = {}
    base = 0x82000000
    for index, arg in enumerate(args):
        if arg.pointer:
            buffers.append(
                {
                    "id": arg.name,
                    "arg": arg.name,
                    "device_address": hex(base + index * 0x10000),
                    "size_bytes": 4096,
                    "access": arg.access,
                }
            )
        else:
            scalar_args[arg.name] = 1.0 if arg.base_type in {"float", "half"} else 1
    spec = KernelSpec(
        name=kernel_name,
        source=source,
        global_size=tuple(int(v) for v in global_size),  # type: ignore[arg-type]
        local_size=tuple(int(v) for v in local_size),  # type: ignore[arg-type]
        buffers=tuple(buffers),
        scalar_args=scalar_args,
        precision="",
        kernel_entry=0x5000,
        description=f"Single-source subset compile from {path}",
    )
    abi = compile_kernel(spec, 1)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / f"{kernel_name}.kernel_abi.json", abi)
    runtime_data = runtime_commands_from_abis([abi], tier)
    write_json(output_dir / f"{kernel_name}.runtime_commands.json", runtime_data)
    evidence = {
        "schema": EVIDENCE_SCHEMA,
        "generated_at": utc_now(),
        "scope": CLEAN_ROOM_SCOPE,
        "tier": tier,
        "kernel_count": 1,
        "kernels": [{"name": kernel_name, "source": str(path), "global_size": list(global_size), "local_size": list(local_size)}],
        "runtime_commands_path": str(output_dir / f"{kernel_name}.runtime_commands.json"),
        "checks": validate_evidence([abi], runtime_data),
    }
    # Single-source mode is exploratory, so it does not require all built-in demo kernels.
    evidence["checks"] = [check for check in evidence["checks"] if check["name"] != "required_kernels_present"]
    evidence["status"] = "pass" if all(check["pass"] for check in evidence["checks"]) else "fail"
    write_json(output_dir / f"{kernel_name}.opencl_subset_evidence.json", evidence)
    return evidence


def parse_size3(values: Sequence[str], field: str) -> tuple[int, int, int]:
    if len(values) not in {1, 2, 3}:
        raise SubsetError(f"{field} expects one to three integers")
    parsed = [int(value, 0) for value in values]
    while len(parsed) < 3:
        parsed.append(1)
    return (parsed[0], parsed[1], parsed[2])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compile/verify a clean-room OpenCL C subset to Celviz runtime ABI evidence.")
    parser.add_argument("--output-dir", type=Path, default=repo_root() / DEFAULT_OUTPUT)
    parser.add_argument("--tier", default="gpgpu_nano_ultra31", help="Runtime proxy tier alias.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("compile-builtins", help="Compile vector_add, GEMM, conv2d, and image_filter subset kernels.")
    sub.add_parser("demo", help="Compile built-ins and run runtime_proxy dry-run evidence.")
    verify = sub.add_parser("verify", help="Verify existing generated evidence JSON.")
    verify.add_argument("--evidence", type=Path, default=None)
    single = sub.add_parser("compile", help="Compile one standalone subset .cl file with inferred placeholder buffers.")
    single.add_argument("source", type=Path)
    single.add_argument("--name", default=None)
    single.add_argument("--global-size", nargs="+", default=["1"])
    single.add_argument("--local-size", nargs="+", default=["1"])
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "compile-builtins":
            _abis, _runtime_data, evidence = compile_builtin(args.output_dir, args.tier)
        elif args.command == "demo":
            evidence = run_demo(args.output_dir, args.tier)
        elif args.command == "compile":
            evidence = load_single_source(
                args.source,
                args.output_dir,
                args.tier,
                args.name,
                parse_size3(args.global_size, "global-size"),
                parse_size3(args.local_size, "local-size"),
            )
        elif args.command == "verify":
            evidence_path = args.evidence or (args.output_dir / "opencl_subset_evidence.json")
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            checks = evidence.get("checks", [])
            evidence["status"] = "pass" if checks and all(check.get("pass") is True for check in checks) else "fail"
        else:  # pragma: no cover
            parser.error(f"unknown command: {args.command}")
        print(json.dumps({"status": evidence["status"], "evidence": str(args.output_dir), "schema": evidence.get("schema")}, sort_keys=True))
        return 0 if evidence["status"] == "pass" else 1
    except (OSError, SubsetError, runtime_proxy.RuntimeProxyError, json.JSONDecodeError) as exc:
        print(f"opencl_subset: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
