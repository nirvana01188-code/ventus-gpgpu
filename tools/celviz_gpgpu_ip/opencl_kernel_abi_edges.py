#!/usr/bin/env python3
"""OpenCL kernel ABI negative/edge runner for the Celviz subset.

This runner exercises ABI-facing negative and edge behavior around the local
clean-room OpenCL C subset compiler plus the existing OpenCL-style error-code
matrix shim.  It is intentionally narrow evidence: not Khronos CTS, not
official OpenCL conformance, not libOpenCL/ICD behavior, and not Vivante
compiler/runtime/driver compatibility.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

try:
    from . import opencl_build_error_code_matrix as error_matrix
    from . import opencl_subset
except ImportError:  # pragma: no cover - direct script fallback
    import opencl_build_error_code_matrix as error_matrix  # type: ignore
    import opencl_subset  # type: ignore


SCHEMA = "celviz.gpgpu.opencl_kernel_abi_edges.v1"
DEFAULT_OUTPUT = Path("artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_kernel_abi_edges.json")
DEFAULT_DOC = Path("docs/celviz-gpgpu-ip/OPENCL_KERNEL_ABI_EDGES.md")
CLEAN_ROOM_SCOPE = (
    "OpenCL kernel ABI negative/edge evidence for the local clean-room Celviz "
    "GPGPU IP subset only; not Khronos CTS, not official OpenCL conformance, "
    "not libOpenCL/ICD behavior, and not proprietary Vivante compiler/runtime/"
    "driver/firmware/command-stream compatibility"
)


@dataclass(frozen=True)
class AbiEdgeCase:
    name: str
    category: str
    requirement: str
    capability: str
    expected_status: str
    runner: Callable[[], dict[str, Any]]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def vector_add_spec(
    *,
    source: str | None = None,
    global_size: tuple[int, int, int] = (1024, 1, 1),
    local_size: tuple[int, int, int] = (64, 1, 1),
    buffers: tuple[dict[str, Any], ...] | None = None,
    scalar_args: Mapping[str, int | float] | None = None,
) -> opencl_subset.KernelSpec:
    builtin = next(spec for spec in opencl_subset.builtin_specs() if spec.name == "vector_add")
    return opencl_subset.KernelSpec(
        name="vector_add",
        description=builtin.description,
        source=source or builtin.source,
        global_size=global_size,
        local_size=local_size,
        buffers=buffers if buffers is not None else builtin.buffers,
        scalar_args=scalar_args if scalar_args is not None else builtin.scalar_args,
        precision=builtin.precision,
        workgroup_local_bytes=builtin.workgroup_local_bytes,
        private_bytes_per_thread=builtin.private_bytes_per_thread,
        sgpr_count=builtin.sgpr_count,
        vgpr_count=builtin.vgpr_count,
        kernel_entry=builtin.kernel_entry,
    )


def compile_success(spec: opencl_subset.KernelSpec, kernel_id: int = 1200) -> dict[str, Any]:
    abi = opencl_subset.compile_kernel(spec, kernel_id)
    return {
        "status": "CL_SUCCESS",
        "observed_error": "CL_SUCCESS",
        "observed_error_code": error_matrix.ERROR_CODES["CL_SUCCESS"],
        "message": f"compiled kernel={abi['name']} args={len(abi['args'])}",
        "abi_excerpt": {
            "name": abi["name"],
            "arg_size_bytes": abi["arg_size_bytes"],
            "global_size": abi["global_size"],
            "local_size": abi["local_size"],
            "workgroup_count": abi["workgroup_count"],
            "args": [
                {
                    "name": arg["name"],
                    "type": arg["type"],
                    "pointer": arg["pointer"],
                    "address_space": arg["address_space"],
                    "access": arg["access"],
                    "size_bytes": arg["size_bytes"],
                    "abi_offset": arg["abi_offset"],
                }
                for arg in abi["args"]
            ],
        },
    }


def compile_failure(spec: opencl_subset.KernelSpec) -> dict[str, Any]:
    try:
        opencl_subset.compile_kernel(spec, 1300)
    except opencl_subset.SubsetError as exc:
        return {
            "status": "CL_BUILD_PROGRAM_FAILURE",
            "observed_error": "CL_BUILD_PROGRAM_FAILURE",
            "observed_error_code": error_matrix.ERROR_CODES["CL_BUILD_PROGRAM_FAILURE"],
            "message": str(exc),
        }
    return {
        "status": "CL_SUCCESS",
        "observed_error": "CL_SUCCESS",
        "observed_error_code": error_matrix.ERROR_CODES["CL_SUCCESS"],
        "message": "compile unexpectedly succeeded",
    }


def build_failure_via_matrix(source: str) -> dict[str, Any]:
    shim = error_matrix.OpenCLSubsetMatrixShim()
    program, create_status, create_log = shim.clCreateProgramWithSource(source)
    if create_status != "CL_SUCCESS":
        return {
            "status": create_status,
            "observed_error": create_status,
            "observed_error_code": error_matrix.ERROR_CODES[create_status],
            "message": create_log,
        }
    _abi, status, log = shim.clBuildProgram(program, spec_factory=lambda text: vector_add_spec(source=text))
    return {
        "status": status,
        "observed_error": status,
        "observed_error_code": error_matrix.ERROR_CODES.get(status),
        "message": log,
    }


def with_good_kernel(fn: Callable[[error_matrix.OpenCLSubsetMatrixShim, str, dict[str, str]], tuple[str, str]]) -> dict[str, Any]:
    shim = error_matrix.OpenCLSubsetMatrixShim()
    _program, kernel, _log, buffers = error_matrix.build_good_program(shim)
    status, log = fn(shim, kernel, buffers)
    return {
        "status": status,
        "observed_error": status,
        "observed_error_code": error_matrix.ERROR_CODES.get(status),
        "message": log,
    }


def edge_cases() -> list[AbiEdgeCase]:
    unsupported_generic = """
__kernel void vector_add(__generic int *a,
                         __global const float *b,
                         __global float *c,
                         uint n) {
  uint gid = get_global_id(0);
  if (gid < n) { c[gid] = b[gid]; }
}
""".strip()
    unsupported_builtin = """
__kernel void vector_add(__global const float *a,
                         __global const float *b,
                         __global float *c,
                         uint n) {
  uint gid = get_global_id(0);
  if (gid < n) { c[gid] = work_group_reduce_add(a[gid] + b[gid]); }
}
""".strip()
    unsupported_double = """
__kernel void vector_add(__global const double *a,
                         __global const double *b,
                         __global double *c,
                         uint n) {
  uint gid = get_global_id(0);
  if (gid < n) { c[gid] = a[gid] + b[gid]; }
}
""".strip()
    unsupported_image = """
__kernel void vector_add(image2d_t img,
                         __global const float *b,
                         __global float *c,
                         uint n) {
  uint gid = get_global_id(0);
  if (gid < n) { c[gid] = b[gid]; }
}
""".strip()
    vector_arg_source = """
__kernel void vector_add(__global const float4 *a,
                         __global const float4 *b,
                         __global float4 *c,
                         uint n,
                         float gain) {
  uint gid = get_global_id(0);
  if (gid < n) { c[gid] = (a[gid] + b[gid]) * gain; }
}
""".strip()
    missing_buffer_source = """
__kernel void vector_add(__global const float *a,
                         __global const float *b,
                         __global float *c,
                         __global float *extra,
                         uint n) {
  uint gid = get_global_id(0);
  if (gid < n) { c[gid] = a[gid] + b[gid] + extra[gid]; }
}
""".strip()

    return [
        AbiEdgeCase(
            name="abi_arg_layout_vector_scalar_edges",
            category="arg size/index/type",
            requirement="Emit ABI offsets and sizes for pointer, vector, uint, and float kernel args.",
            capability="opencl_subset.compile_kernel",
            expected_status="CL_SUCCESS",
            runner=lambda: compile_success(
                vector_add_spec(
                    source=vector_arg_source,
                    scalar_args={"n": 1024, "gain": 1.25},
                )
            ),
        ),
        AbiEdgeCase(
            name="set_arg_reject_bad_index",
            category="arg size/index/type",
            requirement="Reject a clSetKernelArg index outside the compiled ABI argument list.",
            capability="opencl_build_error_code_matrix.OpenCLSubsetMatrixShim.clSetKernelArg",
            expected_status="CL_INVALID_ARG_INDEX",
            runner=lambda: with_good_kernel(lambda shim, kernel, buffers: shim.clSetKernelArg(kernel, 99, 0, 4)),
        ),
        AbiEdgeCase(
            name="set_arg_reject_bad_size",
            category="arg size/index/type",
            requirement="Reject an argument byte size that does not match the compiled ABI entry.",
            capability="opencl_build_error_code_matrix.OpenCLSubsetMatrixShim.clSetKernelArg",
            expected_status="CL_INVALID_ARG_SIZE",
            runner=lambda: with_good_kernel(lambda shim, kernel, buffers: shim.clSetKernelArg(kernel, 3, 1024, 8)),
        ),
        AbiEdgeCase(
            name="set_arg_reject_pointer_type_mismatch",
            category="arg size/index/type",
            requirement="Reject non-buffer values for pointer ABI entries.",
            capability="opencl_build_error_code_matrix.OpenCLSubsetMatrixShim.clSetKernelArg",
            expected_status="CL_INVALID_MEM_OBJECT",
            runner=lambda: with_good_kernel(lambda shim, kernel, buffers: shim.clSetKernelArg(kernel, 0, "not_a_buffer", 8)),
        ),
        AbiEdgeCase(
            name="compile_reject_missing_pointer_buffer_metadata",
            category="buffer access mismatch",
            requirement="Reject pointer ABI entries that lack matching buffer metadata.",
            capability="opencl_subset.compile_kernel",
            expected_status="CL_BUILD_PROGRAM_FAILURE",
            runner=lambda: compile_failure(vector_add_spec(source=missing_buffer_source)),
        ),
        AbiEdgeCase(
            name="set_arg_reject_buffer_access_mismatch",
            category="buffer access mismatch",
            requirement="Reject binding a write-only buffer to a read-only kernel pointer argument.",
            capability="opencl_build_error_code_matrix.OpenCLSubsetMatrixShim.clSetKernelArg",
            expected_status="CL_INVALID_ARG_VALUE",
            runner=lambda: with_good_kernel(lambda shim, kernel, buffers: shim.clSetKernelArg(kernel, 0, buffers["c"], 8)),
        ),
        AbiEdgeCase(
            name="compile_accept_3d_global_local_edge",
            category="global/local size",
            requirement="Accept a 3D launch whose global dimensions are divisible by local dimensions.",
            capability="opencl_subset.compile_kernel",
            expected_status="CL_SUCCESS",
            runner=lambda: compile_success(vector_add_spec(global_size=(64, 8, 2), local_size=(16, 2, 1))),
        ),
        AbiEdgeCase(
            name="compile_reject_zero_global_size",
            category="global/local size",
            requirement="Reject zero global dimensions before ABI emission.",
            capability="opencl_subset.compile_kernel",
            expected_status="CL_BUILD_PROGRAM_FAILURE",
            runner=lambda: compile_failure(vector_add_spec(global_size=(0, 1, 1))),
        ),
        AbiEdgeCase(
            name="compile_reject_non_divisible_local_size",
            category="global/local size",
            requirement="Reject global/local geometry that cannot form integral workgroups.",
            capability="opencl_subset.compile_kernel",
            expected_status="CL_BUILD_PROGRAM_FAILURE",
            runner=lambda: compile_failure(vector_add_spec(global_size=(1000, 1, 1), local_size=(64, 1, 1))),
        ),
        AbiEdgeCase(
            name="enqueue_reject_local_workgroup_too_large",
            category="global/local size",
            requirement="Reject local workgroup sizes beyond the first-stage limit.",
            capability="opencl_build_error_code_matrix.OpenCLSubsetMatrixShim.clEnqueueNDRangeKernel",
            expected_status="CL_INVALID_WORK_GROUP_SIZE",
            runner=lambda: with_good_kernel(
                lambda shim, kernel, buffers: shim.clEnqueueNDRangeKernel(
                    kernel,
                    work_dim=1,
                    global_size=(512, 1, 1),
                    local_size=(512, 1, 1),
                )
            ),
        ),
        AbiEdgeCase(
            name="build_reject_generic_address_space",
            category="unsupported address spaces/builtins/double",
            requirement="Reject unsupported pointer address spaces such as __generic.",
            capability="opencl_build_error_code_matrix.OpenCLSubsetMatrixShim.clBuildProgram",
            expected_status="CL_BUILD_PROGRAM_FAILURE",
            runner=lambda: build_failure_via_matrix(unsupported_generic),
        ),
        AbiEdgeCase(
            name="build_reject_image_address_object",
            category="unsupported address spaces/builtins/double",
            requirement="Reject unsupported OpenCL image object/addressing surface.",
            capability="opencl_build_error_code_matrix.OpenCLSubsetMatrixShim.clBuildProgram",
            expected_status="CL_BUILD_PROGRAM_FAILURE",
            runner=lambda: build_failure_via_matrix(unsupported_image),
        ),
        AbiEdgeCase(
            name="build_reject_unsupported_builtin",
            category="unsupported address spaces/builtins/double",
            requirement="Reject unsupported work-group/subgroup-style builtins.",
            capability="opencl_build_error_code_matrix.OpenCLSubsetMatrixShim.clBuildProgram",
            expected_status="CL_BUILD_PROGRAM_FAILURE",
            runner=lambda: build_failure_via_matrix(unsupported_builtin),
        ),
        AbiEdgeCase(
            name="build_reject_double_precision",
            category="unsupported address spaces/builtins/double",
            requirement="Reject double precision in the current subset.",
            capability="opencl_build_error_code_matrix.OpenCLSubsetMatrixShim.clBuildProgram",
            expected_status="CL_BUILD_PROGRAM_FAILURE",
            runner=lambda: build_failure_via_matrix(unsupported_double),
        ),
    ]


def run_case(case: AbiEdgeCase) -> dict[str, Any]:
    observed = case.runner()
    status = str(observed.get("status"))
    expected_code = error_matrix.ERROR_CODES.get(case.expected_status)
    return {
        "name": case.name,
        "category": case.category,
        "requirement": case.requirement,
        "capability": case.capability,
        "expected_status": case.expected_status,
        "expected_error_code": expected_code,
        "observed_status": status,
        "observed_error_code": observed.get("observed_error_code"),
        "message": observed.get("message", ""),
        "pass": status == case.expected_status and observed.get("observed_error_code") == expected_code,
        "details": {key: value for key, value in observed.items() if key not in {"status", "observed_error", "observed_error_code", "message"}},
    }


def category_summary(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = {}
    for case in cases:
        category = str(case["category"])
        groups.setdefault(category, {"total": 0, "passed": 0, "capabilities": set(), "statuses": set()})
        groups[category]["total"] += 1
        groups[category]["passed"] += 1 if case.get("pass") is True else 0
        groups[category]["capabilities"].add(str(case["capability"]))
        groups[category]["statuses"].add(str(case["expected_status"]))
    return {
        name: {
            "total": row["total"],
            "passed": row["passed"],
            "status": "pass" if row["passed"] == row["total"] else "fail",
            "capabilities": sorted(row["capabilities"]),
            "statuses": sorted(row["statuses"]),
        }
        for name, row in sorted(groups.items())
    }


def build_report() -> dict[str, Any]:
    cases = [run_case(case) for case in edge_cases()]
    required_categories = {
        "arg size/index/type",
        "global/local size",
        "unsupported address spaces/builtins/double",
        "buffer access mismatch",
    }
    observed_categories = {str(case["category"]) for case in cases}
    required_capability_tokens = {"opencl_subset", "opencl_build_error_code_matrix"}
    observed_capabilities = " ".join(str(case["capability"]) for case in cases)
    checks = [
        {
            "name": "required_categories_present",
            "pass": required_categories.issubset(observed_categories),
            "required": sorted(required_categories),
            "observed": sorted(observed_categories),
        },
        {
            "name": "all_edge_cases_pass",
            "pass": all(case.get("pass") is True for case in cases),
            "case_count": len(cases),
        },
        {
            "name": "existing_capabilities_invoked",
            "pass": all(token in observed_capabilities for token in required_capability_tokens),
            "required": sorted(required_capability_tokens),
        },
        {
            "name": "negative_and_edge_mix_present",
            "pass": any(case["expected_status"] == "CL_SUCCESS" for case in cases)
            and any(case["expected_status"] != "CL_SUCCESS" for case in cases),
        },
        {
            "name": "clean_room_boundary_present",
            "pass": "not Khronos CTS" in CLEAN_ROOM_SCOPE and "not official OpenCL conformance" in CLEAN_ROOM_SCOPE,
        },
    ]
    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "claim_boundary": {
            "allowed": "local OpenCL-like kernel ABI negative/edge evidence generated from existing subset and error-matrix capabilities",
            "not_claimed": [
                "Khronos CTS pass",
                "official OpenCL conformance",
                "full OpenCL C compiler coverage",
                "full libOpenCL or ICD behavior",
                "proprietary Vivante compiler/runtime/driver compatibility",
            ],
        },
        "source_capabilities": [
            "tools/celviz_gpgpu_ip/opencl_subset.py",
            "tools/celviz_gpgpu_ip/opencl_build_error_code_matrix.py",
        ],
        "status": "pass" if all(check["pass"] for check in checks) else "fail",
        "case_count": len(cases),
        "category_summary": category_summary(cases),
        "checks": checks,
        "cases": cases,
    }


def write_doc(path: Path, report: Mapping[str, Any]) -> None:
    lines = [
        "# OpenCL Kernel ABI Negative/Edge Runner",
        "",
        str(report["clean_room_scope"]),
        "",
        "## Summary",
        "",
        f"- Status: `{report['status']}`",
        f"- Cases: `{report['case_count']}`",
        "- JSON: `artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_kernel_abi_edges.json`",
        "- Existing capabilities: `opencl_subset.compile_kernel`, `opencl_build_error_code_matrix.OpenCLSubsetMatrixShim`",
        "",
        "## Categories",
        "",
    ]
    for name, row in report["category_summary"].items():
        lines.append(f"- `{name}`: `{row['status']}` `{row['passed']}/{row['total']}` statuses={', '.join(row['statuses'])}")
    lines.extend(["", "## Cases", ""])
    for case in report["cases"]:
        lines.append(
            f"- `{case['name']}` `{case['category']}` expected `{case['expected_status']}` "
            f"observed `{case['observed_status']}` status=`{'pass' if case['pass'] else 'fail'}`"
        )
    lines.extend(
        [
            "",
            "## Coverage Boundary",
            "",
            "This is an executable negative/edge runner for the local kernel ABI path. It covers argument size/index/type handling, global/local launch geometry, unsupported address spaces, unsupported builtins, unsupported double precision, and buffer access mismatch behavior by invoking the existing subset compiler and error-code matrix shim.",
            "",
            "It is not Khronos CTS, not official OpenCL conformance, not a product ICD/libOpenCL implementation, and not proprietary Vivante compatibility evidence.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate OpenCL kernel ABI negative/edge evidence.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args(argv)
    report = build_report()
    write_json(args.output, report)
    write_doc(args.doc, report)
    passed = sum(1 for check in report["checks"] if check["pass"])
    total = len(report["checks"])
    if args.print_summary:
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "checks": f"{passed}/{total}",
                    "case_count": report["case_count"],
                    "categories": report["category_summary"],
                    "output": str(args.output),
                    "doc": str(args.doc),
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(
            "celviz_opencl_kernel_abi_edges: "
            f"{report['status']} checks={passed}/{total} cases={report['case_count']} "
            f"output={args.output} doc={args.doc}"
        )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
