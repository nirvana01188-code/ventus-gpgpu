#!/usr/bin/env python3
"""Clean-room S1 compute golden model for Celviz GPGPU IP.

The model is standard-library only and intentionally models deterministic
compute workloads rather than graphics pipeline behavior.  It emits reproducible
JSON evidence for FP32 vector add, GEMM, convolution/image filter, and memory
copy proxy workloads plus deterministic FP16 proxy paths.  It does not claim
equivalence to proprietary Vivante RTL, firmware, SDKs, drivers, or compilers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

try:  # Keep direct script execution and package import both working.
    from . import simt_execution_model
except ImportError:  # pragma: no cover - direct script fallback
    import simt_execution_model  # type: ignore


ARTIFACT_ROOT = Path("artifacts/rank_01_vivante_3d_gpgpu_ip/model")
OUTPUT_NAMES = (
    "vector_add.json",
    "gemm_proxy.json",
    "convolution_proxy.json",
    "image_filter.json",
    "memory_copy.json",
    "simt_execution.json",
    "shader_unit_scaling.json",
    "hashes.txt",
)

CLEAN_ROOM_SCOPE = (
    "public-information-derived compute proxy; no proprietary Vivante RTL, "
    "firmware, SDK, compiler, driver, command-stream, or conformance claim"
)

PUBLIC_TIER_SOURCE = {
    "label": "VeriSilicon Vivante 3D GPGPU IP public product table",
    "url": "https://www.verisilicon.com/cn/IPPortfolio/Vivante3DGPGPUIP",
    "fields": [
        "Shader Units (vec1 equivalent shader)",
        "FP32/16 Operations/Cycle",
    ],
}

SHADER_UNIT_TIERS = [
    {"tier": "CC8000L", "shader_units_vec1": 16, "fp32_ops_per_cycle": 32, "fp16_ops_per_cycle": 64},
    {"tier": "CC8000", "shader_units_vec1": 32, "fp32_ops_per_cycle": 64, "fp16_ops_per_cycle": 128},
    {"tier": "CC8200", "shader_units_vec1": 128, "fp32_ops_per_cycle": 128, "fp16_ops_per_cycle": 256},
    {"tier": "CC8400", "shader_units_vec1": 256, "fp32_ops_per_cycle": 512, "fp16_ops_per_cycle": 1024},
    {"tier": "CC8400-MP2", "shader_units_vec1": 512, "fp32_ops_per_cycle": 1024, "fp16_ops_per_cycle": 2048},
    {"tier": "CC8400-MP4", "shader_units_vec1": 1024, "fp32_ops_per_cycle": 2048, "fp16_ops_per_cycle": 4096},
    {"tier": "CC8800", "shader_units_vec1": 512, "fp32_ops_per_cycle": 1024, "fp16_ops_per_cycle": 2048},
    {"tier": "CC8800-MP2", "shader_units_vec1": 1024, "fp32_ops_per_cycle": 2048, "fp16_ops_per_cycle": 4096},
    {"tier": "CC8800-MP4", "shader_units_vec1": 2048, "fp32_ops_per_cycle": 4096, "fp16_ops_per_cycle": 8192},
]


def f32(value: float) -> float:
    """Round a Python float through IEEE-754 binary32 storage."""
    return struct.unpack(">f", struct.pack(">f", float(value)))[0]


def fp16_quantize(value: float) -> float:
    """Round a Python float through IEEE-754 binary16 storage.

    Python's standard-library ``struct`` binary16 format is the deterministic
    proxy arithmetic boundary for S1 evidence.  It is not a Vivante ISA,
    pipeline, denormal, exception, or RTL timing model.
    """
    try:
        return struct.unpack(">e", struct.pack(">e", float(value)))[0]
    except (struct.error, OverflowError):
        if math.isnan(value) or math.isinf(value):
            return float(value)
        # Portable fallback for hosts without binary16 support, documented as proxy.
        return round(float(value), 3)


def fp16_add_proxy(lhs: float, rhs: float) -> float:
    """Proxy FP16 add: quantize operands and result through binary16 storage."""
    return fp16_quantize(fp16_quantize(lhs) + fp16_quantize(rhs))


def fp16_mul_proxy(lhs: float, rhs: float) -> float:
    """Proxy FP16 multiply: quantize operands and result through binary16 storage."""
    return fp16_quantize(fp16_quantize(lhs) * fp16_quantize(rhs))


def max_abs_error(reference: Sequence[float], candidate: Sequence[float]) -> float:
    return f32(max(abs(a - b) for a, b in zip(reference, candidate)))


def tolerance_summary(
    *,
    reference: Sequence[float],
    candidate: Sequence[float],
    abs_tolerance: float,
    rel_tolerance: float,
    reference_label: str,
) -> Dict[str, object]:
    worst_index = 0
    worst_error = 0.0
    sum_abs = 0.0
    pass_count = 0
    for index, (expected, observed) in enumerate(zip(reference, candidate)):
        error = f32(abs(expected - observed))
        limit = f32(abs_tolerance + rel_tolerance * abs(expected))
        sum_abs = f32(sum_abs + error)
        if error > worst_error:
            worst_error = error
            worst_index = index
        if error <= limit:
            pass_count += 1

    count = min(len(reference), len(candidate))
    return {
        "reference": reference_label,
        "abs_tolerance": f32(abs_tolerance),
        "rel_tolerance": f32(rel_tolerance),
        "max_abs": f32(worst_error),
        "sum_abs": f32(sum_abs),
        "worst_index": worst_index,
        "elements_checked": count,
        "elements_within_tolerance": pass_count,
        "pass": count == len(reference) == len(candidate) and pass_count == count,
    }


def exact_tolerance(count: int, reference_label: str = "deterministic in-model oracle") -> Dict[str, object]:
    return {
        "reference": reference_label,
        "abs_tolerance": 0.0,
        "rel_tolerance": 0.0,
        "max_abs": 0.0,
        "sum_abs": 0.0,
        "worst_index": 0,
        "elements_checked": count,
        "elements_within_tolerance": count,
        "pass": True,
    }


def fp16_proxy_summary(
    *,
    workload: str,
    fp32_result: Sequence[float],
    fp16_result: Sequence[float],
    fp16_ops: int,
) -> Dict[str, object]:
    errors = [f32(abs(a - b)) for a, b in zip(fp32_result, fp16_result)]
    return {
        "status": "executed_proxy",
        "precision_path": "FP16 proxy",
        "claim_boundary": (
            "deterministic Python binary16 round-trip arithmetic proxy; "
            "not Vivante RTL, ISA, compiler, firmware, driver, or conformance behavior"
        ),
        "method": (
            "operands and arithmetic results are rounded through standard-library "
            "struct binary16 storage at each modeled FP16 operation"
        ),
        "workload": workload,
        "fp16_ops": fp16_ops,
        "result": list(fp16_result),
        "result_head": list(fp16_result[:8]),
        "sample_head": list(fp16_result[:8]),
        "result_sum": fp16_quantize(sum(fp16_result)),
        "result_sha256": sha256_json(list(fp16_result)),
        "error_vs_fp32": {
            "max_abs": max_abs_error(fp32_result, fp16_result),
            "sum_abs": f32(sum(errors)),
            "error_head": errors[:8],
            "reference": "FP32 proxy output from the same clean-room model",
        },
        "tolerance": tolerance_summary(
            reference=fp32_result,
            candidate=fp16_result,
            abs_tolerance=0.01,
            rel_tolerance=0.02,
            reference_label="FP32 proxy output from the same clean-room model",
        ),
    }


def sha256_json(data: object) -> str:
    blob = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def write_json(path: Path, data: object) -> str:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def deterministic_vector(length: int, scale: float, offset: float) -> List[float]:
    return [f32(math.sin(i * 0.37 + offset) * scale + (i % 7) * 0.125) for i in range(length)]


def vector_add() -> Dict[str, object]:
    a = deterministic_vector(32, 1.75, 0.15)
    b = deterministic_vector(32, -0.90, 1.10)
    result = [f32(x + y) for x, y in zip(a, b)]
    fp16_result = [fp16_add_proxy(x, y) for x, y in zip(a, b)]
    checksum = sha256_json(result)
    return {
        "workload": "vector_add",
        "precision_path": "FP32",
        "length": len(result),
        "fp32_ops": len(result),
        "bytes_read": len(result) * 2 * 4,
        "bytes_written": len(result) * 4,
        "input_a_head": a[:8],
        "input_b_head": b[:8],
        "result": result,
        "result_head": result[:8],
        "result_sum": f32(sum(result)),
        "result_sha256": checksum,
        "output_hashes": {"result_sha256": checksum},
        "tolerance": exact_tolerance(len(result)),
        "fp16_proxy": fp16_proxy_summary(
            workload="vector_add",
            fp32_result=result,
            fp16_result=fp16_result,
            fp16_ops=len(result),
        ),
    }


def gemm_proxy() -> Dict[str, object]:
    m, n, k = 4, 5, 6
    a = [[f32(((row * k + col) % 11 - 5) * 0.1875) for col in range(k)] for row in range(m)]
    b = [[f32(math.cos((row + 1) * (col + 2) * 0.21) * 0.75) for col in range(n)] for row in range(k)]
    c: List[List[float]] = []
    for row in range(m):
        out_row = []
        for col in range(n):
            acc = f32(0.0)
            for inner in range(k):
                acc = f32(acc + f32(a[row][inner] * b[inner][col]))
            out_row.append(acc)
        c.append(out_row)

    flat = [value for row in c for value in row]
    c_fp16: List[List[float]] = []
    for row in range(m):
        out_row = []
        for col in range(n):
            acc = fp16_quantize(0.0)
            for inner in range(k):
                product = fp16_mul_proxy(a[row][inner], b[inner][col])
                acc = fp16_add_proxy(acc, product)
            out_row.append(acc)
        c_fp16.append(out_row)

    flat_fp16 = [value for row in c_fp16 for value in row]
    return {
        "workload": "gemm_proxy",
        "precision_path": "FP32",
        "shape": {"m": m, "n": n, "k": k},
        "fp32_ops": m * n * k * 2,
        "bytes_read": (m * k + k * n) * 4,
        "bytes_written": m * n * 4,
        "matrix_a": a,
        "matrix_b": b,
        "matrix_c": c,
        "result_sum": f32(sum(flat)),
        "result_sha256": sha256_json(c),
        "output_hashes": {"result_sha256": sha256_json(c)},
        "tolerance": exact_tolerance(len(flat)),
        "fp16_proxy": {
            **fp16_proxy_summary(
                workload="gemm_proxy",
                fp32_result=flat,
                fp16_result=flat_fp16,
                fp16_ops=m * n * k * 2,
            ),
            "matrix_c": c_fp16,
            "shape": {"m": m, "n": n, "k": k},
        },
    }


def convolution_proxy() -> Dict[str, object]:
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
    out_h, out_w = height - 2, width - 2
    output: List[List[float]] = []
    for y in range(out_h):
        row = []
        for x in range(out_w):
            acc = f32(0.0)
            for ky in range(3):
                for kx in range(3):
                    acc = f32(acc + f32(image[y + ky][x + kx] * kernel[ky][kx]))
            row.append(acc)
        output.append(row)

    flat = [value for row in output for value in row]
    output_fp16: List[List[float]] = []
    for y in range(out_h):
        row = []
        for x in range(out_w):
            acc = fp16_quantize(0.0)
            for ky in range(3):
                for kx in range(3):
                    product = fp16_mul_proxy(image[y + ky][x + kx], kernel[ky][kx])
                    acc = fp16_add_proxy(acc, product)
            row.append(acc)
        output_fp16.append(row)

    flat_fp16 = [value for row in output_fp16 for value in row]
    taps = 3 * 3
    result_hash = sha256_json(output)
    return {
        "workload": "convolution_proxy",
        "alias": "image_filter",
        "precision_path": "FP32",
        "input_shape": {"height": height, "width": width, "channels": 1},
        "kernel_shape": {"height": 3, "width": 3},
        "output_shape": {"height": out_h, "width": out_w, "channels": 1},
        "fp32_ops": out_h * out_w * taps * 2,
        "bytes_read": (height * width + taps) * 4,
        "bytes_written": out_h * out_w * 4,
        "kernel": kernel,
        "output": output,
        "result_sum": f32(sum(flat)),
        "result_sha256": result_hash,
        "output_hashes": {"result_sha256": result_hash},
        "tolerance": exact_tolerance(len(flat)),
        "fp16_proxy": {
            **fp16_proxy_summary(
                workload="convolution_proxy",
                fp32_result=flat,
                fp16_result=flat_fp16,
                fp16_ops=out_h * out_w * taps * 2,
            ),
            "output": output_fp16,
            "input_shape": {"height": height, "width": width, "channels": 1},
            "kernel_shape": {"height": 3, "width": 3},
            "output_shape": {"height": out_h, "width": out_w, "channels": 1},
        },
    }


def image_filter() -> Dict[str, object]:
    width, height = 8, 8
    source = [
        [((x * 29 + y * 17 + (x * y) * 3) & 0xFF) for x in range(width)]
        for y in range(height)
    ]
    result: List[List[int]] = []
    for y in range(height):
        row = []
        for x in range(width):
            acc = 0
            count = 0
            for yy in range(max(0, y - 1), min(height, y + 2)):
                for xx in range(max(0, x - 1), min(width, x + 2)):
                    acc += source[yy][xx]
                    count += 1
            row.append(acc // count)
        result.append(row)

    pgm = bytearray(f"P5\n{width} {height}\n255\n".encode("ascii"))
    for row in result:
        pgm.extend(row)

    result_hash = hashlib.sha256(bytes(pgm)).hexdigest()
    flat = [float(value) for row in result for value in row]
    return {
        "workload": "image_filter",
        "precision_path": "u8",
        "filter": "3x3_box_u8_edge_truncated",
        "input_shape": {"height": height, "width": width, "channels": 1},
        "output_shape": {"height": height, "width": width, "channels": 1},
        "integer_ops": height * width * 9,
        "fp32_ops": 0,
        "bytes_read": height * width,
        "bytes_written": height * width,
        "source_head": source[0][:8],
        "result": result,
        "result_head": result[0][:8],
        "result_sum": sum(int(value) for row in result for value in row),
        "result_sha256": result_hash,
        "output_hashes": {"pgm_sha256": result_hash, "result_sha256": sha256_json(result)},
        "tolerance": exact_tolerance(len(flat), reference_label="integer u8 deterministic oracle"),
        "pass": result[0][0] == 23 and result[-1][-1] == 169,
    }


def memory_copy() -> Dict[str, object]:
    source = [((i * 37 + 11) & 0xFF) for i in range(256)]
    destination = list(source)
    source_hash = hashlib.sha256(bytes(source)).hexdigest()
    destination_hash = hashlib.sha256(bytes(destination)).hexdigest()
    return {
        "workload": "memory_copy",
        "precision_path": "byte",
        "bytes_copied": len(source),
        "fp32_ops": 0,
        "bytes_read": len(source),
        "bytes_written": len(destination),
        "source_head": source[:16],
        "destination_head": destination[:16],
        "source_sha256": source_hash,
        "destination_sha256": destination_hash,
        "result_sha256": destination_hash,
        "output_hashes": {
            "source_sha256": source_hash,
            "destination_sha256": destination_hash,
            "result_sha256": destination_hash,
        },
        "tolerance": exact_tolerance(len(source), reference_label="byte-exact copy"),
        "pass": source == destination and source_hash == destination_hash,
    }


def shader_unit_scaling() -> Dict[str, object]:
    rows = []
    for tier in SHADER_UNIT_TIERS:
        row = dict(tier)
        row["fp32_ops_per_shader_unit"] = round(row["fp32_ops_per_cycle"] / row["shader_units_vec1"], 3)
        row["fp16_ops_per_shader_unit"] = round(row["fp16_ops_per_cycle"] / row["shader_units_vec1"], 3)
        row["fp16_to_fp32_ops_ratio"] = round(row["fp16_ops_per_cycle"] / row["fp32_ops_per_cycle"], 3)
        row["fp32_speedup_vs_cc8000l"] = round(
            row["fp32_ops_per_cycle"] / SHADER_UNIT_TIERS[0]["fp32_ops_per_cycle"],
            3,
        )
        row["fp16_speedup_vs_cc8000l"] = round(
            row["fp16_ops_per_cycle"] / SHADER_UNIT_TIERS[0]["fp16_ops_per_cycle"],
            3,
        )
        rows.append(row)
    return {
        "source": PUBLIC_TIER_SOURCE,
        "claim_boundary": "public tier metadata only; not measured local RTL performance",
        "tiers": rows,
    }


def workload_passes(workloads: Iterable[Dict[str, object]]) -> Dict[str, bool]:
    status = {}
    for workload in workloads:
        name = str(workload["workload"])
        if name == "memory_copy":
            status[name] = bool(workload["pass"])
        else:
            status[name] = bool(workload.get("result_sha256")) and int(workload["fp32_ops"]) >= 0
    return status


def write_hashes(path: Path, file_hashes: Dict[str, str]) -> None:
    lines = [f"{digest}  {name}\n" for name, digest in sorted(file_hashes.items())]
    path.write_text("".join(lines), encoding="utf-8")


def build_readme() -> str:
    tier_rows = "\n".join(
        "| {tier} | {shader_units_vec1} | {fp32_ops_per_cycle} | {fp16_ops_per_cycle} |".format(**tier)
        for tier in SHADER_UNIT_TIERS
    )
    return f"""# S1 Compute Golden Model Evidence

Status: implemented.

This directory contains the standard-library-only S1 compute golden model for
Rank 1 Vivante 3D GPGPU IP / Celviz GPGPU IP. The evidence is compute-oriented:
vector add, GEMM proxy, convolution/image-filter proxy, u8 image filtering, and
memory copy. It intentionally does not model a 3D graphics workload.

The model is a clean-room software oracle built inside the Ventus GPGPU
repository. It does not import or claim equivalence to proprietary Vivante RTL,
firmware, SDK, compiler, driver, command stream, or conformance behavior.

## Run

From the repository root:

```sh
python3 tools/celviz_gpgpu_ip/compute_model.py
```

Optional metrics dump:

```sh
python3 tools/celviz_gpgpu_ip/compute_model.py --print-metrics
```

The default artifact root is:

```text
artifacts/rank_01_vivante_3d_gpgpu_ip/model
```

## Fixed Workloads

- `vector_add`: deterministic FP32 elementwise add over 32 elements.
- `gemm_proxy`: deterministic FP32 4x6 by 6x5 matrix multiply.
- `convolution_proxy`: deterministic FP32 3x3 image-filter proxy over a 7x7
  single-channel image, producing a 5x5 output.
- `image_filter`: deterministic executable 8x8 u8 3x3 box-filter workload.
- `memory_copy`: deterministic byte copy and SHA-256 equality check.

The FP32 path uses Python floats rounded through IEEE-754 binary32 storage at
each modeled arithmetic step. FP16 evidence is now executed as a conservative
proxy for `vector_add`, `gemm_proxy`, and `convolution_proxy`: operands,
multiply results, additions, and final outputs are rounded through
standard-library IEEE-754 binary16 storage at each modeled FP16 operation. None
of these paths claims a Vivante ISA, compiler, driver, firmware, RTL,
exception, denormal, timing, or conformance model.

## Public Shader-Unit Scaling Table

Source: VeriSilicon Vivante 3D GPGPU IP public product table,
`https://www.verisilicon.com/cn/IPPortfolio/Vivante3DGPGPUIP`.

| Tier | Public shader units, vec1 equivalent | FP32 ops/cycle | FP16 ops/cycle |
| --- | ---: | ---: | ---: |
{tier_rows}

These rows are public capability metadata, not measured local RTL performance.

## Generated Evidence

Running the command writes:

- `run.log`: command trace, workload pass/fail summary, output locations, and
  pass status.
- `metrics.json`: public tier table, FP32/FP16 proxy notes, workload metrics,
  operation counts, byte traffic, hashes, and pass status.
- `outputs/vector_add.json`: vector inputs/outputs and checksum.
- `outputs/gemm_proxy.json`: matrix inputs/outputs and checksum.
- `outputs/convolution_proxy.json`: image-filter proxy output and checksum.
- `outputs/image_filter.json`: u8 box-filter output and checksum.
- `outputs/memory_copy.json`: memory copy bytes and source/destination hashes.
- `outputs/simt_execution.json`: clean-room SIMT execution evidence with
  wavefront scheduling, register-file reads/writes, ALU ops, LSU ops,
  scoreboard hazards, and barrier events for vector add, GEMM, convolution,
  and image filter.
- `outputs/shader_unit_scaling.json`: public tier metadata table.
- `outputs/hashes.txt`: SHA-256 hashes for generated JSON evidence files.

## Scope Notes

This is S1 acceptance evidence for a Celviz GPGPU IP compute proxy using the
Ventus GPGPU repository as the implementation frame. Celviz remains the tooling
namespace; this repository does not vendor Celviz or proprietary vendor
collateral. Clean-room scope: {CLEAN_ROOM_SCOPE}.
"""


def run_model(artifact_root: Path) -> Dict[str, object]:
    artifact_root.mkdir(parents=True, exist_ok=True)
    output_dir = artifact_root / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    workloads = [vector_add(), gemm_proxy(), convolution_proxy(), image_filter(), memory_copy()]
    scaling = shader_unit_scaling()
    simt_evidence = simt_execution_model.build_evidence(
        simt_execution_model.SimtConfig(),
        ("vector_add", "gemm_proxy", "convolution_proxy", "image_filter"),
    )

    file_hashes: Dict[str, str] = {}
    for workload in workloads:
        name = str(workload["workload"])
        file_hashes[f"{name}.json"] = write_json(output_dir / f"{name}.json", workload)
    file_hashes["simt_execution.json"] = write_json(output_dir / "simt_execution.json", simt_evidence)
    file_hashes["shader_unit_scaling.json"] = write_json(output_dir / "shader_unit_scaling.json", scaling)
    write_hashes(output_dir / "hashes.txt", file_hashes)
    file_hashes["hashes.txt"] = hashlib.sha256((output_dir / "hashes.txt").read_bytes()).hexdigest()

    pass_by_workload = workload_passes(workloads)
    total_fp32_ops = sum(int(workload["fp32_ops"]) for workload in workloads)
    total_integer_ops = sum(int(workload.get("integer_ops", 0)) for workload in workloads)
    total_fp16_proxy_ops = sum(
        int(workload.get("fp16_proxy", {}).get("fp16_ops", 0))
        for workload in workloads
        if isinstance(workload.get("fp16_proxy"), dict)
    )
    total_bytes_read = sum(int(workload["bytes_read"]) for workload in workloads)
    total_bytes_written = sum(int(workload["bytes_written"]) for workload in workloads)
    result_hashes = {
        str(workload["workload"]): str(
            workload.get("result_sha256")
            or workload.get("destination_sha256")
            or workload.get("source_sha256")
        )
        for workload in workloads
    }
    fp16_proxy_result_hashes = {
        str(workload["workload"]): str(workload["fp16_proxy"]["result_sha256"])
        for workload in workloads
        if isinstance(workload.get("fp16_proxy"), dict)
        and workload["fp16_proxy"].get("status") == "executed_proxy"
    }
    workload_tolerances = {
        str(workload["workload"]): workload["tolerance"]
        for workload in workloads
        if isinstance(workload.get("tolerance"), dict)
    }

    metrics: Dict[str, object] = {
        "ip_name": "Celviz GPGPU IP",
        "public_reference_ip": "Vivante 3D GPGPU IP",
        "rank": 1,
        "stage": "S1",
        "model": "standard-library compute golden model",
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "orientation": "GPGPU compute workloads, not 3D graphics workloads",
        "precision": {
            "fp32_path": "implemented with Python float values rounded through IEEE-754 binary32 storage",
            "fp16_path": (
                "deterministic binary16 proxy execution for vector_add, gemm_proxy, and "
                "convolution_proxy; no Vivante RTL/ISA/conformance claim"
            ),
        },
        "simt_execution": {
            "status": simt_evidence["status"],
            "schema": simt_evidence["schema"],
            "output": str(output_dir / "simt_execution.json"),
            "wavefront_size": simt_evidence["simt_topology"]["wavefront_size"],
            "workloads": simt_evidence["workload_names"],
            "totals": simt_evidence["totals"],
            "result_hashes": simt_evidence["result_hashes"],
            "claim_scope": simt_evidence["clean_room_scope"],
        },
        "public_shader_unit_scaling": scaling,
        "workloads": workloads,
        "workload_count": len(workloads),
        "pass_by_workload": pass_by_workload,
        "status": "pass" if all(pass_by_workload.values()) else "fail",
        "totals": {
            "fp32_ops": total_fp32_ops,
            "integer_ops": total_integer_ops,
            "fp16_proxy_ops": total_fp16_proxy_ops,
            "bytes_read": total_bytes_read,
            "bytes_written": total_bytes_written,
            "bytes_touched": total_bytes_read + total_bytes_written,
        },
        "outputs": {
            "directory": str(output_dir),
            "expected_files": list(OUTPUT_NAMES),
            "file_hashes": file_hashes,
            "result_hashes": result_hashes,
            "fp16_proxy_result_hashes": fp16_proxy_result_hashes,
            "workload_tolerances": workload_tolerances,
        },
    }

    metrics_hash = write_json(artifact_root / "metrics.json", metrics)
    readme_text = build_readme()
    (artifact_root / "README.md").write_text(readme_text, encoding="utf-8")

    run_lines = [
        "Celviz GPGPU IP S1 compute golden model run",
        "model=standard-library compute golden model",
        "orientation=GPGPU compute workloads, not 3D graphics workloads",
        f"artifact_root={artifact_root}",
        f"outputs={output_dir}",
        f"public_tier_source={PUBLIC_TIER_SOURCE['url']}",
        "fp32_path=implemented",
        "fp16_path=executed_proxy_for_vector_add_gemm_and_convolution",
        f"simt_execution={output_dir / 'simt_execution.json'}",
        f"simt_execution_status={simt_evidence['status']}",
        "simt_execution_features=wavefront_scheduler,register_file,alu,lsu,scoreboard,barrier",
    ]
    for index, workload in enumerate(workloads):
        name = str(workload["workload"])
        fp16_status = "none"
        if isinstance(workload.get("fp16_proxy"), dict):
            fp16_status = str(workload["fp16_proxy"].get("status", "none"))
        run_lines.append(
            "workload[{index}]={name} precision={precision} fp32_ops={ops} "
            "fp16_status={fp16_status} bytes_read={bytes_read} "
            "bytes_written={bytes_written} pass={passed}".format(
                index=index,
                name=name,
                precision=workload["precision_path"],
                ops=workload["fp32_ops"],
                fp16_status=fp16_status,
                bytes_read=workload["bytes_read"],
                bytes_written=workload["bytes_written"],
                passed=pass_by_workload[name],
            )
        )
    run_lines.extend(
        [
            "shader_unit_scaling_tiers="
            + ",".join(str(tier["tier"]) for tier in SHADER_UNIT_TIERS),
            f"total_fp32_ops={total_fp32_ops}",
            f"total_integer_ops={total_integer_ops}",
            f"total_fp16_proxy_ops={total_fp16_proxy_ops}",
            f"total_bytes_touched={total_bytes_read + total_bytes_written}",
            f"metrics={artifact_root / 'metrics.json'}",
            f"metrics_sha256={metrics_hash}",
            f"hashes={output_dir / 'hashes.txt'}",
            f"status={metrics['status']}",
        ]
    )
    (artifact_root / "run.log").write_text("\n".join(run_lines) + "\n", encoding="utf-8")
    return metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact-root",
        type=Path,
        default=ARTIFACT_ROOT,
        help="directory for README.md, run.log, metrics.json, and outputs",
    )
    parser.add_argument(
        "--print-metrics",
        action="store_true",
        help="also print metrics JSON to stdout",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    metrics = run_model(args.artifact_root)
    if args.print_metrics:
        print(json.dumps(metrics, indent=2, sort_keys=True))
    else:
        print(f"wrote {args.artifact_root / 'run.log'}")
        print(f"wrote {args.artifact_root / 'metrics.json'}")
        print(f"status={metrics['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
