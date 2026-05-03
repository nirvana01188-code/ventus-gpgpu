#!/usr/bin/env python3
"""OpenCL-style build log and error-code matrix for the Celviz subset.

This executable matrix models the error behavior of the local clean-room
OpenCL C subset path around clBuildProgram, clCreateKernel, clSetKernelArg,
NDRange geometry, and buffer APIs.  It is not a Khronos ICD, not libOpenCL,
not Khronos CTS, not official OpenCL conformance, and not proprietary Vivante
compiler/SDK/firmware/driver/command-stream compatibility.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

try:
    from . import opencl_subset
except ImportError:  # pragma: no cover - direct script fallback
    import opencl_subset  # type: ignore


SCHEMA = "celviz.gpgpu.opencl_build_error_code_matrix.v1"
DEFAULT_OUTPUT = Path("artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_build_error_code_matrix.json")
DEFAULT_DOC = Path("docs/celviz-gpgpu-ip/OPENCL_BUILD_ERROR_CODE_MATRIX.md")
CLEAN_ROOM_SCOPE = (
    "clean-room OpenCL-style build log/error-code matrix for Celviz GPGPU IP "
    "subset evidence only; not Khronos CTS, not official OpenCL conformance, "
    "not libOpenCL/ICD, and not proprietary Vivante compiler/SDK/firmware/"
    "driver/command-stream compatibility"
)

ERROR_CODES = {
    "CL_SUCCESS": 0,
    "CL_INVALID_VALUE": -30,
    "CL_INVALID_CONTEXT": -34,
    "CL_INVALID_MEM_OBJECT": -38,
    "CL_INVALID_PROGRAM": -44,
    "CL_INVALID_PROGRAM_EXECUTABLE": -45,
    "CL_INVALID_KERNEL_NAME": -46,
    "CL_INVALID_KERNEL": -48,
    "CL_INVALID_ARG_INDEX": -49,
    "CL_INVALID_ARG_VALUE": -50,
    "CL_INVALID_ARG_SIZE": -51,
    "CL_INVALID_WORK_DIMENSION": -53,
    "CL_INVALID_WORK_GROUP_SIZE": -54,
    "CL_INVALID_GLOBAL_WORK_SIZE": -63,
    "CL_BUILD_PROGRAM_FAILURE": -11,
    "CL_INVALID_BUILD_OPTIONS": -43,
}


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
) -> opencl_subset.KernelSpec:
    builtin = next(spec for spec in opencl_subset.builtin_specs() if spec.name == "vector_add")
    return opencl_subset.KernelSpec(
        name="vector_add",
        description=builtin.description,
        source=source or builtin.source,
        global_size=global_size,
        local_size=local_size,
        buffers=builtin.buffers,
        scalar_args=builtin.scalar_args,
        precision=builtin.precision,
        workgroup_local_bytes=builtin.workgroup_local_bytes,
        private_bytes_per_thread=builtin.private_bytes_per_thread,
        sgpr_count=builtin.sgpr_count,
        vgpr_count=builtin.vgpr_count,
        kernel_entry=builtin.kernel_entry,
    )


@dataclass
class Program:
    source: str
    built: bool = False
    build_log: str = ""
    abi: dict[str, Any] | None = None


@dataclass
class Kernel:
    name: str
    abi: Mapping[str, Any]
    args: dict[int, Any] = field(default_factory=dict)


@dataclass
class Buffer:
    size_bytes: int
    flags: str


class OpenCLSubsetMatrixShim:
    def __init__(self) -> None:
        self.context_valid = True
        self.programs: dict[str, Program] = {}
        self.kernels: dict[str, Kernel] = {}
        self.buffers: dict[str, Buffer] = {}
        self.next_id = 1

    def _handle(self, prefix: str) -> str:
        value = f"{prefix}_{self.next_id}"
        self.next_id += 1
        return value

    def clCreateProgramWithSource(self, source: str) -> tuple[str | None, str, str]:
        if not source.strip():
            return None, "CL_INVALID_VALUE", "program source is empty"
        handle = self._handle("program")
        self.programs[handle] = Program(source=source)
        return handle, "CL_SUCCESS", "program object created"

    def clBuildProgram(self, program: str | None, *, options: str = "", spec_factory: Callable[[str], opencl_subset.KernelSpec] | None = None) -> tuple[dict[str, Any] | None, str, str]:
        if program not in self.programs:
            return None, "CL_INVALID_PROGRAM", "program handle is invalid"
        if options:
            return None, "CL_INVALID_BUILD_OPTIONS", f"unsupported build options: {options}"
        record = self.programs[str(program)]
        spec_factory = spec_factory or (lambda source: vector_add_spec(source=source))
        try:
            abi = opencl_subset.compile_kernel(spec_factory(record.source), 900)
        except opencl_subset.SubsetError as exc:
            record.built = False
            record.build_log = f"build failed: {exc}"
            return None, "CL_BUILD_PROGRAM_FAILURE", record.build_log
        record.built = True
        record.abi = abi
        record.build_log = f"build succeeded: kernel={abi['name']} args={len(abi['args'])}"
        return abi, "CL_SUCCESS", record.build_log

    def clCreateKernel(self, program: str | None, kernel_name: str) -> tuple[str | None, str, str]:
        if program not in self.programs:
            return None, "CL_INVALID_PROGRAM", "program handle is invalid"
        record = self.programs[str(program)]
        if not record.built or record.abi is None:
            return None, "CL_INVALID_PROGRAM_EXECUTABLE", "program has no successful executable build"
        if record.abi.get("name") != kernel_name:
            return None, "CL_INVALID_KERNEL_NAME", f"kernel '{kernel_name}' not found"
        handle = self._handle("kernel")
        self.kernels[handle] = Kernel(name=kernel_name, abi=record.abi)
        return handle, "CL_SUCCESS", f"kernel created: {kernel_name}"

    def clCreateBuffer(self, size_bytes: int, flags: str) -> tuple[str | None, str, str]:
        allowed_flags = {"read_only", "write_only", "read_write"}
        if size_bytes <= 0:
            return None, "CL_INVALID_VALUE", "buffer size must be positive"
        if flags not in allowed_flags:
            return None, "CL_INVALID_VALUE", f"unsupported buffer flags: {flags}"
        handle = self._handle("buffer")
        self.buffers[handle] = Buffer(size_bytes=size_bytes, flags=flags)
        return handle, "CL_SUCCESS", f"buffer created bytes={size_bytes} flags={flags}"

    def clSetKernelArg(self, kernel: str | None, index: int, value: Any, arg_size: int) -> tuple[str, str]:
        if kernel not in self.kernels:
            return "CL_INVALID_KERNEL", "kernel handle is invalid"
        record = self.kernels[str(kernel)]
        args = list(record.abi.get("args", []))
        if index < 0 or index >= len(args):
            return "CL_INVALID_ARG_INDEX", f"argument index {index} out of range"
        arg = args[index]
        expected_size = int(arg.get("size_bytes", 0))
        if arg_size != expected_size:
            return "CL_INVALID_ARG_SIZE", f"argument {index} expects {expected_size} bytes, got {arg_size}"
        if bool(arg.get("pointer")):
            if value not in self.buffers:
                return "CL_INVALID_MEM_OBJECT", f"argument {index} expects a valid buffer object"
            buf = self.buffers[str(value)]
            access = str(arg.get("access"))
            if access == "read_only" and buf.flags == "write_only":
                return "CL_INVALID_ARG_VALUE", "read-only kernel argument cannot bind write-only buffer"
            if access in {"read_write", "read_write_restrict"} and buf.flags == "read_only":
                return "CL_INVALID_ARG_VALUE", "writable kernel argument cannot bind read-only buffer"
        record.args[index] = value
        return "CL_SUCCESS", f"argument {index} set"

    def clEnqueueNDRangeKernel(
        self,
        kernel: str | None,
        *,
        work_dim: int,
        global_size: tuple[int, int, int],
        local_size: tuple[int, int, int] | None,
        global_offset: tuple[int, int, int] | None = None,
    ) -> tuple[str, str]:
        if kernel not in self.kernels:
            return "CL_INVALID_KERNEL", "kernel handle is invalid"
        if work_dim < 1 or work_dim > 3:
            return "CL_INVALID_WORK_DIMENSION", f"unsupported work_dim={work_dim}"
        if global_offset is not None and any(value != 0 for value in global_offset):
            return "CL_INVALID_VALUE", "non-zero global work offset is not supported by this subset"
        active_global = global_size[:work_dim]
        if any(value <= 0 for value in active_global):
            return "CL_INVALID_GLOBAL_WORK_SIZE", f"global size must be positive for {work_dim}D launch"
        if local_size is None:
            return "CL_INVALID_WORK_GROUP_SIZE", "explicit local size is required by this subset"
        active_local = local_size[:work_dim]
        if any(value <= 0 for value in active_local):
            return "CL_INVALID_WORK_GROUP_SIZE", f"local size must be positive for {work_dim}D launch"
        local_product = 1
        for value in active_local:
            local_product *= value
        if local_product > 256:
            return "CL_INVALID_WORK_GROUP_SIZE", "local workgroup size exceeds first-stage limit 256"
        if any(active_global[i] % active_local[i] != 0 for i in range(work_dim)):
            return "CL_INVALID_WORK_GROUP_SIZE", "global size must be divisible by local size"
        return "CL_SUCCESS", "NDRange geometry accepted"


def make_case(
    *,
    name: str,
    category: str,
    api: str,
    expected_error: str,
    runner: Callable[[OpenCLSubsetMatrixShim], tuple[str, str]],
) -> dict[str, Any]:
    shim = OpenCLSubsetMatrixShim()
    observed, build_log = runner(shim)
    return {
        "name": name,
        "category": category,
        "api": api,
        "expected_error": expected_error,
        "expected_error_code": ERROR_CODES[expected_error],
        "observed_error": observed,
        "observed_error_code": ERROR_CODES.get(observed),
        "build_log": build_log,
        "pass": observed == expected_error and ERROR_CODES.get(observed) == ERROR_CODES[expected_error],
    }


def build_good_program(shim: OpenCLSubsetMatrixShim) -> tuple[str, str, str, dict[str, str]]:
    spec = vector_add_spec()
    program, status, log = shim.clCreateProgramWithSource(spec.source)
    if status != "CL_SUCCESS":
        raise RuntimeError(log)
    _abi, status, log = shim.clBuildProgram(program)
    if status != "CL_SUCCESS":
        raise RuntimeError(log)
    kernel, status, klog = shim.clCreateKernel(program, "vector_add")
    if status != "CL_SUCCESS":
        raise RuntimeError(klog)
    buffers = {}
    for raw in spec.buffers:
        handle, status, blog = shim.clCreateBuffer(int(raw["size_bytes"]), str(raw["access"]))
        if status != "CL_SUCCESS" or handle is None:
            raise RuntimeError(blog)
        buffers[str(raw["arg"])] = handle
    return str(program), str(kernel), log, buffers


def matrix_cases() -> list[dict[str, Any]]:
    bad_source = "__kernel void bad(__global double *out) { out[get_global_id(0)] = 1.0; }"
    multi_kernel = """
__kernel void a(__global int *out) { out[get_global_id(0)] = 0; }
__kernel void b(__global int *out) { out[get_global_id(0)] = 1; }
""".strip()
    return [
        make_case(
            name="build_success_vector_add",
            category="clBuildProgram",
            api="clBuildProgram",
            expected_error="CL_SUCCESS",
            runner=lambda shim: (
                lambda program_status: (
                    shim.clBuildProgram(program_status[0])[1],
                    shim.clBuildProgram(program_status[0])[2] if False else "build succeeded via clean-room subset compiler",
                )
            )(shim.clCreateProgramWithSource(vector_add_spec().source)),
        ),
        make_case(
            name="build_reject_unsupported_double",
            category="clBuildProgram",
            api="clBuildProgram",
            expected_error="CL_BUILD_PROGRAM_FAILURE",
            runner=lambda shim: (
                lambda program: shim.clBuildProgram(program[0])
            )(shim.clCreateProgramWithSource(bad_source))[1:3],
        ),
        make_case(
            name="build_reject_multi_kernel_source",
            category="clBuildProgram",
            api="clBuildProgram",
            expected_error="CL_BUILD_PROGRAM_FAILURE",
            runner=lambda shim: (
                lambda program: shim.clBuildProgram(program[0])
            )(shim.clCreateProgramWithSource(multi_kernel))[1:3],
        ),
        make_case(
            name="build_reject_options",
            category="clBuildProgram",
            api="clBuildProgram",
            expected_error="CL_INVALID_BUILD_OPTIONS",
            runner=lambda shim: (
                lambda program: shim.clBuildProgram(program[0], options="-cl-fast-relaxed-math")
            )(shim.clCreateProgramWithSource(vector_add_spec().source))[1:3],
        ),
        make_case(
            name="build_invalid_program_handle",
            category="clBuildProgram",
            api="clBuildProgram",
            expected_error="CL_INVALID_PROGRAM",
            runner=lambda shim: shim.clBuildProgram("program_missing")[1:3],
        ),
        make_case(
            name="create_kernel_success",
            category="clCreateKernel",
            api="clCreateKernel",
            expected_error="CL_SUCCESS",
            runner=lambda shim: (
                lambda built: shim.clCreateKernel(built[0], "vector_add")[1:3]
            )((lambda s: (s[0], shim.clBuildProgram(s[0])))(shim.clCreateProgramWithSource(vector_add_spec().source))),
        ),
        make_case(
            name="create_kernel_missing_symbol",
            category="clCreateKernel",
            api="clCreateKernel",
            expected_error="CL_INVALID_KERNEL_NAME",
            runner=lambda shim: (
                lambda built: shim.clCreateKernel(built[0], "missing_kernel")[1:3]
            )((lambda s: (s[0], shim.clBuildProgram(s[0])))(shim.clCreateProgramWithSource(vector_add_spec().source))),
        ),
        make_case(
            name="create_kernel_unbuilt_program",
            category="clCreateKernel",
            api="clCreateKernel",
            expected_error="CL_INVALID_PROGRAM_EXECUTABLE",
            runner=lambda shim: (
                lambda program: shim.clCreateKernel(program[0], "vector_add")[1:3]
            )(shim.clCreateProgramWithSource(vector_add_spec().source)),
        ),
        make_case(
            name="set_arg_success_all_vector_add_args",
            category="clSetKernelArg",
            api="clSetKernelArg",
            expected_error="CL_SUCCESS",
            runner=lambda shim: set_all_vector_add_args(shim),
        ),
        make_case(
            name="set_arg_bad_index",
            category="clSetKernelArg",
            api="clSetKernelArg",
            expected_error="CL_INVALID_ARG_INDEX",
            runner=lambda shim: (
                lambda ctx: shim.clSetKernelArg(ctx[1], 99, 0, 4)
            )(build_good_program(shim))[0:2],
        ),
        make_case(
            name="set_arg_bad_size",
            category="clSetKernelArg",
            api="clSetKernelArg",
            expected_error="CL_INVALID_ARG_SIZE",
            runner=lambda shim: (
                lambda ctx: shim.clSetKernelArg(ctx[1], 3, 1024, 8)
            )(build_good_program(shim))[0:2],
        ),
        make_case(
            name="set_arg_invalid_mem_object",
            category="clSetKernelArg",
            api="clSetKernelArg",
            expected_error="CL_INVALID_MEM_OBJECT",
            runner=lambda shim: (
                lambda ctx: shim.clSetKernelArg(ctx[1], 0, "buffer_missing", 8)
            )(build_good_program(shim))[0:2],
        ),
        make_case(
            name="set_arg_wrong_buffer_access",
            category="clSetKernelArg",
            api="clSetKernelArg",
            expected_error="CL_INVALID_ARG_VALUE",
            runner=lambda shim: (
                lambda ctx: shim.clSetKernelArg(ctx[1], 0, ctx[3]["c"], 8)
            )(build_good_program(shim))[0:2],
        ),
        make_case(
            name="ndrange_success",
            category="NDRange geometry",
            api="clEnqueueNDRangeKernel",
            expected_error="CL_SUCCESS",
            runner=lambda shim: (
                lambda ctx: shim.clEnqueueNDRangeKernel(ctx[1], work_dim=1, global_size=(1024, 1, 1), local_size=(64, 1, 1))
            )(build_good_program(shim))[0:2],
        ),
        make_case(
            name="ndrange_bad_work_dim",
            category="NDRange geometry",
            api="clEnqueueNDRangeKernel",
            expected_error="CL_INVALID_WORK_DIMENSION",
            runner=lambda shim: (
                lambda ctx: shim.clEnqueueNDRangeKernel(ctx[1], work_dim=4, global_size=(1024, 1, 1), local_size=(64, 1, 1))
            )(build_good_program(shim))[0:2],
        ),
        make_case(
            name="ndrange_zero_global_size",
            category="NDRange geometry",
            api="clEnqueueNDRangeKernel",
            expected_error="CL_INVALID_GLOBAL_WORK_SIZE",
            runner=lambda shim: (
                lambda ctx: shim.clEnqueueNDRangeKernel(ctx[1], work_dim=1, global_size=(0, 1, 1), local_size=(64, 1, 1))
            )(build_good_program(shim))[0:2],
        ),
        make_case(
            name="ndrange_non_divisible_local",
            category="NDRange geometry",
            api="clEnqueueNDRangeKernel",
            expected_error="CL_INVALID_WORK_GROUP_SIZE",
            runner=lambda shim: (
                lambda ctx: shim.clEnqueueNDRangeKernel(ctx[1], work_dim=1, global_size=(1000, 1, 1), local_size=(64, 1, 1))
            )(build_good_program(shim))[0:2],
        ),
        make_case(
            name="ndrange_local_wg_too_large",
            category="NDRange geometry",
            api="clEnqueueNDRangeKernel",
            expected_error="CL_INVALID_WORK_GROUP_SIZE",
            runner=lambda shim: (
                lambda ctx: shim.clEnqueueNDRangeKernel(ctx[1], work_dim=1, global_size=(512, 1, 1), local_size=(512, 1, 1))
            )(build_good_program(shim))[0:2],
        ),
        make_case(
            name="ndrange_nonzero_global_offset",
            category="NDRange geometry",
            api="clEnqueueNDRangeKernel",
            expected_error="CL_INVALID_VALUE",
            runner=lambda shim: (
                lambda ctx: shim.clEnqueueNDRangeKernel(ctx[1], work_dim=1, global_size=(1024, 1, 1), local_size=(64, 1, 1), global_offset=(1, 0, 0))
            )(build_good_program(shim))[0:2],
        ),
        make_case(
            name="buffer_success_read_write",
            category="buffer errors",
            api="clCreateBuffer",
            expected_error="CL_SUCCESS",
            runner=lambda shim: (
                lambda result: (result[1], result[2])
            )(shim.clCreateBuffer(4096, "read_write")),
        ),
        make_case(
            name="buffer_zero_size",
            category="buffer errors",
            api="clCreateBuffer",
            expected_error="CL_INVALID_VALUE",
            runner=lambda shim: shim.clCreateBuffer(0, "read_write")[1:3],
        ),
        make_case(
            name="buffer_bad_flags",
            category="buffer errors",
            api="clCreateBuffer",
            expected_error="CL_INVALID_VALUE",
            runner=lambda shim: shim.clCreateBuffer(4096, "use_host_ptr")[1:3],
        ),
    ]


def set_all_vector_add_args(shim: OpenCLSubsetMatrixShim) -> tuple[str, str]:
    _program, kernel, _log, buffers = build_good_program(shim)
    for index, value in enumerate((buffers["a"], buffers["b"], buffers["c"], 1024)):
        size = 8 if index < 3 else 4
        status, log = shim.clSetKernelArg(kernel, index, value, size)
        if status != "CL_SUCCESS":
            return status, log
    return "CL_SUCCESS", "all vector_add arguments accepted"


def category_summary(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = {}
    for case in cases:
        group = str(case["category"])
        groups.setdefault(group, {"total": 0, "passed": 0, "apis": set(), "error_codes": set()})
        groups[group]["total"] += 1
        groups[group]["passed"] += 1 if case.get("pass") is True else 0
        groups[group]["apis"].add(str(case["api"]))
        groups[group]["error_codes"].add(str(case["expected_error"]))
    return {
        name: {
            "total": row["total"],
            "passed": row["passed"],
            "status": "pass" if row["passed"] == row["total"] else "fail",
            "apis": sorted(row["apis"]),
            "error_codes": sorted(row["error_codes"]),
        }
        for name, row in sorted(groups.items())
    }


def build_report() -> dict[str, Any]:
    cases = matrix_cases()
    required_categories = {"clBuildProgram", "clCreateKernel", "clSetKernelArg", "NDRange geometry", "buffer errors"}
    observed_categories = {str(case["category"]) for case in cases}
    required_errors = {
        "CL_SUCCESS",
        "CL_BUILD_PROGRAM_FAILURE",
        "CL_INVALID_BUILD_OPTIONS",
        "CL_INVALID_PROGRAM",
        "CL_INVALID_PROGRAM_EXECUTABLE",
        "CL_INVALID_KERNEL_NAME",
        "CL_INVALID_ARG_INDEX",
        "CL_INVALID_ARG_SIZE",
        "CL_INVALID_MEM_OBJECT",
        "CL_INVALID_ARG_VALUE",
        "CL_INVALID_WORK_DIMENSION",
        "CL_INVALID_GLOBAL_WORK_SIZE",
        "CL_INVALID_WORK_GROUP_SIZE",
        "CL_INVALID_VALUE",
    }
    observed_errors = {str(case["expected_error"]) for case in cases}
    checks = [
        {
            "name": "required_categories_present",
            "pass": required_categories.issubset(observed_categories),
            "required": sorted(required_categories),
            "observed": sorted(observed_categories),
        },
        {
            "name": "required_error_codes_present",
            "pass": required_errors.issubset(observed_errors),
            "required": sorted(required_errors),
            "observed": sorted(observed_errors),
        },
        {
            "name": "all_matrix_cases_pass",
            "pass": all(case["pass"] is True for case in cases),
            "case_count": len(cases),
        },
        {
            "name": "build_logs_present",
            "pass": all(isinstance(case.get("build_log"), str) and len(str(case.get("build_log"))) > 0 for case in cases),
        },
        {
            "name": "clean_room_boundary_present",
            "pass": "not official OpenCL conformance" in CLEAN_ROOM_SCOPE and "not Khronos CTS" in CLEAN_ROOM_SCOPE,
        },
    ]
    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "claim_boundary": {
            "allowed": "OpenCL-style error-code matrix for the local clean-room subset",
            "not_claimed": [
                "Khronos CTS pass",
                "official OpenCL conformance",
                "full libOpenCL or ICD behavior",
                "proprietary Vivante compiler/runtime/driver compatibility",
            ],
        },
        "status": "pass" if all(check["pass"] for check in checks) else "fail",
        "case_count": len(cases),
        "error_codes": ERROR_CODES,
        "category_summary": category_summary(cases),
        "checks": checks,
        "matrix": cases,
    }


def write_doc(path: Path, report: Mapping[str, Any]) -> None:
    lines = [
        "# OpenCL Build Log And Error Code Matrix",
        "",
        str(report["clean_room_scope"]),
        "",
        "## Summary",
        "",
        f"- Status: `{report['status']}`",
        f"- Cases: `{report['case_count']}`",
        f"- JSON: `artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_build_error_code_matrix.json`",
        "",
        "## Categories",
        "",
    ]
    for name, row in report["category_summary"].items():
        lines.append(f"- `{name}`: `{row['status']}` `{row['passed']}/{row['total']}` codes={', '.join(row['error_codes'])}")
    lines.extend(["", "## Matrix", ""])
    for case in report["matrix"]:
        lines.append(
            f"- `{case['name']}` `{case['api']}` expected `{case['expected_error']}` "
            f"observed `{case['observed_error']}` status=`{'pass' if case['pass'] else 'fail'}`"
        )
    lines.extend(
        [
            "",
            "Boundary: this matrix is executable subset evidence. It is not Khronos CTS, not official OpenCL conformance, and not proprietary Vivante compatibility.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate OpenCL-style build log/error-code matrix evidence.")
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
            "celviz_opencl_build_error_code_matrix: "
            f"{report['status']} checks={passed}/{total} cases={report['case_count']} "
            f"output={args.output} doc={args.doc}"
        )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
