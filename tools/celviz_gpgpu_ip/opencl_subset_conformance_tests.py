#!/usr/bin/env python3
"""OpenCL C subset conformance-readiness tests for Celviz GPGPU IP.

These tests are deliberately local subset tests. They exercise the current
clean-room compiler/ABI parser with CTS-shaped positive and negative cases, but
they are not Khronos CTS and not official OpenCL conformance evidence.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

try:
    from . import opencl_subset
except ImportError:  # pragma: no cover - direct script fallback
    import opencl_subset  # type: ignore


SCHEMA = "celviz.gpgpu.opencl_subset_conformance_tests.v1"
DEFAULT_OUTPUT = Path("artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_subset_conformance_tests.json")
CLEAN_ROOM_SCOPE = (
    "CTS-shaped OpenCL C subset readiness tests for the clean-room Celviz GPGPU "
    "IP compiler/ABI path only; not Khronos CTS, not official OpenCL "
    "conformance, not a complete OpenCL C implementation, and not a production "
    "ICD/runtime claim"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def buffer(arg: str, index: int, access: str = "read_write", address: int | None = None) -> dict[str, Any]:
    base = 0x86000000 + index * 0x10000 if address is None else address
    return {
        "id": f"{arg}_buf",
        "arg": arg,
        "device_address": hex(base),
        "size_bytes": 4096,
        "alloc_size_bytes": 4096,
        "access": access,
    }


def spec(
    name: str,
    source: str,
    *,
    buffers: tuple[dict[str, Any], ...] = (),
    scalars: Mapping[str, int | float] | None = None,
    global_size: tuple[int, int, int] = (64, 1, 1),
    local_size: tuple[int, int, int] = (32, 1, 1),
    local_bytes: int = 0,
) -> opencl_subset.KernelSpec:
    return opencl_subset.KernelSpec(
        name=name,
        source=source.strip(),
        global_size=global_size,
        local_size=local_size,
        buffers=buffers,
        scalar_args=dict(scalars or {}),
        precision="fp32",
        workgroup_local_bytes=local_bytes,
        kernel_entry=0x9000,
        description="OpenCL subset conformance-readiness fixture",
    )


def positive_cases() -> list[opencl_subset.KernelSpec]:
    return [
        spec(
            "scalar_arg_layout",
            """
__kernel void scalar_arg_layout(__global float *out, uint n, float scale, int bias) {
  uint gid = get_global_id(0);
  if (gid < n) out[gid] = scale + (float)bias;
}
""",
            buffers=(buffer("out", 0, "write_only"),),
            scalars={"n": 64, "scale": 2.0, "bias": 3},
        ),
        spec(
            "vector_type_float2",
            "__kernel void vector_type_float2(__global const float2 *a, __global float2 *b) { uint gid = get_global_id(0); b[gid] = a[gid]; }",
            buffers=(buffer("a", 1, "read_only"), buffer("b", 2, "write_only")),
        ),
        spec(
            "vector_type_float4",
            "__kernel void vector_type_float4(__global const float4 *a, __global float4 *b) { uint gid = get_global_id(0); b[gid] = a[gid]; }",
            buffers=(buffer("a", 3, "read_only"), buffer("b", 4, "write_only")),
        ),
        spec(
            "vector_type_float8",
            "__kernel void vector_type_float8(__global const float8 *a, __global float8 *b) { uint gid = get_global_id(0); b[gid] = a[gid]; }",
            buffers=(buffer("a", 5, "read_only"), buffer("b", 6, "write_only")),
        ),
        spec(
            "vector_type_float16",
            "__kernel void vector_type_float16(__global const float16 *a, __global float16 *b) { uint gid = get_global_id(0); b[gid] = a[gid]; }",
            buffers=(buffer("a", 7, "read_only"), buffer("b", 8, "write_only")),
        ),
        spec(
            "vector_type_uchar4",
            "__kernel void vector_type_uchar4(__global const uchar4 *a, __global uchar4 *b) { uint gid = get_global_id(0); b[gid] = a[gid]; }",
            buffers=(buffer("a", 9, "read_only"), buffer("b", 10, "write_only")),
        ),
        spec(
            "address_spaces_global_local_constant",
            """
__kernel void address_spaces_global_local_constant(__global float *out,
                                                  __local float *scratch,
                                                  __constant float *coef,
                                                  uint n) {
  uint lid = get_local_id(0);
  uint gid = get_global_id(0);
  scratch[lid] = coef[0];
  barrier(CLK_LOCAL_MEM_FENCE);
  if (gid < n) out[gid] = scratch[lid];
}
""",
            buffers=(buffer("out", 11, "write_only"), buffer("scratch", 12), buffer("coef", 13, "read_only")),
            scalars={"n": 64},
            local_bytes=1024,
        ),
        spec(
            "builtins_geometry",
            """
__kernel void builtins_geometry(__global uint *out) {
  uint gid = get_global_id(0);
  uint lid = get_local_id(0);
  uint group = get_group_id(0);
  uint gsz = get_global_size(0);
  uint lsz = get_local_size(0);
  out[gid] = gid + lid + group + gsz + lsz;
}
""",
            buffers=(buffer("out", 14, "write_only"),),
            global_size=(128, 1, 1),
            local_size=(64, 1, 1),
        ),
        spec(
            "launch_geometry_2d",
            """
__kernel void launch_geometry_2d(__global float *out, uint width) {
  uint x = get_global_id(0);
  uint y = get_global_id(1);
  out[y * width + x] = (float)(x + y);
}
""",
            buffers=(buffer("out", 15, "write_only"),),
            scalars={"width": 16},
            global_size=(16, 16, 1),
            local_size=(8, 8, 1),
        ),
    ]


def negative_cases() -> list[dict[str, Any]]:
    base = "__kernel void bad(__global float *p) { p[get_global_id(0)] = 0.0f; }"
    return [
        {"name": "reject_image_object", "source": "__kernel void bad(image2d_t img) { }", "expect": "unsupported OpenCL feature token"},
        {"name": "reject_sampler_object", "source": "__kernel void bad(sampler_t s) { }", "expect": "unsupported OpenCL feature token"},
        {"name": "reject_atomic_builtin", "source": "__kernel void bad(__global int *p) { atomic_inc(p); }", "expect": "unsupported OpenCL feature token"},
        {"name": "reject_double_precision", "source": "__kernel void bad(__global double *p) { p[0] = 1.0; }", "expect": "unsupported OpenCL feature token"},
        {"name": "reject_subgroup_builtin", "source": "__kernel void bad(__global uint *p) { p[0] = get_sub_group_id(); }", "expect": "unsupported OpenCL feature token"},
        {"name": "reject_device_side_enqueue", "source": "__kernel void bad(queue_t q) { }", "expect": "unsupported OpenCL feature token"},
        {"name": "reject_printf", "source": "__kernel void bad(__global int *p) { printf(\"x\"); }", "expect": "unsupported OpenCL feature token"},
        {"name": "reject_pipes", "source": "__kernel void bad(pipe int p) { }", "expect": "unsupported OpenCL feature token"},
        {"name": "reject_multiple_kernels", "source": base + "\n__kernel void bad2(__global float *p) { }", "expect": "exactly one kernel"},
        {"name": "reject_pointer_missing_address_space", "source": "__kernel void bad(float *p) { p[0] = 0.0f; }", "expect": "must declare an address space"},
        {"name": "reject_bad_launch_geometry", "source": base, "expect": "global_size must be divisible by local_size", "global_size": (100, 1, 1), "local_size": (64, 1, 1)},
        {"name": "reject_local_workgroup_too_large", "source": base, "expect": "local workgroup size exceeds", "global_size": (512, 1, 1), "local_size": (512, 1, 1)},
    ]


def run_positive() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for index, case in enumerate(positive_cases(), start=1):
        try:
            abi = opencl_subset.compile_kernel(case, 100 + index)
            results.append(
                {
                    "name": case.name,
                    "status": "pass",
                    "used_builtins": abi.get("subset", {}).get("used_builtins", []),
                    "address_spaces": abi.get("address_spaces", []),
                    "arg_count": len(abi.get("args", [])),
                    "work_items": abi.get("work_items"),
                    "claim": "local subset compile/ABI pass only",
                }
            )
        except Exception as exc:  # pragma: no cover - report path
            results.append({"name": case.name, "status": "fail", "error": str(exc)})
    return results


def run_negative() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for index, case in enumerate(negative_cases(), start=1):
        try:
            kernel = spec(
                "bad",
                str(case["source"]),
                buffers=(buffer("p", 200 + index),),
                global_size=tuple(case.get("global_size", (64, 1, 1))),
                local_size=tuple(case.get("local_size", (32, 1, 1))),
            )
            opencl_subset.compile_kernel(kernel, 200 + index)
            results.append(
                {
                    "name": case["name"],
                    "status": "fail",
                    "expected_rejection": case["expect"],
                    "observed_error": None,
                }
            )
        except opencl_subset.SubsetError as exc:
            observed = str(exc)
            results.append(
                {
                    "name": case["name"],
                    "status": "pass" if str(case["expect"]) in observed else "fail",
                    "expected_rejection": case["expect"],
                    "observed_error": observed,
                }
            )
    return results


def build_report() -> dict[str, Any]:
    positive = run_positive()
    negative = run_negative()
    checks = [
        {
            "name": "positive_subset_cases_pass",
            "pass": all(item["status"] == "pass" for item in positive),
            "count": len(positive),
        },
        {
            "name": "negative_subset_cases_rejected",
            "pass": all(item["status"] == "pass" for item in negative),
            "count": len(negative),
        },
        {
            "name": "cts_boundary_declared",
            "pass": "not Khronos CTS" in CLEAN_ROOM_SCOPE and "not official OpenCL conformance" in CLEAN_ROOM_SCOPE,
            "scope": CLEAN_ROOM_SCOPE,
        },
    ]
    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "status": "pass" if all(item["pass"] for item in checks) else "fail",
        "positive_tests": positive,
        "negative_tests": negative,
        "positive_count": len(positive),
        "negative_count": len(negative),
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Celviz OpenCL subset conformance-readiness tests.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = build_report()
    write_json(args.output, report)
    print(
        "celviz_gpgpu_opencl_subset_conformance_tests: "
        f"{report['status']} positive={report['positive_count']} negative={report['negative_count']} "
        f"output={args.output}"
    )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
