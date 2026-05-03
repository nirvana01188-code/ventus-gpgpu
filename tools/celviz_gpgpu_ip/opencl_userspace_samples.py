#!/usr/bin/env python3
"""Executable OpenCL userspace sample runner for Celviz GPGPU IP readiness.

This runner stitches together the existing clean-room OpenCL host API shim,
OpenCL C subset compiler, runtime proxy, and microop evidence for four
userspace-shaped samples. It is not Khronos CTS, not official OpenCL
conformance, and not evidence of a production ICD.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from . import opencl_host_api_shim, opencl_subset, runtime_proxy
except ImportError:  # pragma: no cover - direct script fallback
    import opencl_host_api_shim  # type: ignore
    import opencl_subset  # type: ignore
    import runtime_proxy  # type: ignore


SCHEMA = "celviz.gpgpu.opencl_userspace_samples.v1"
DEFAULT_OUTPUT = Path("artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_userspace_samples.json")
DEFAULT_DOC = Path("docs/celviz-gpgpu-ip/OPENCL_USERSPACE_SAMPLES.md")
DEFAULT_MICROOP_ROOT = Path("artifacts/rank_01_vivante_3d_gpgpu_ip/microop_execution")
SAMPLE_NAMES = ("vector_add", "gemm", "conv2d", "image_filter")
CLEAN_ROOM_SCOPE = (
    "clean-room executable userspace samples using the Celviz OpenCL host API "
    "shim, OpenCL C subset compiler, runtime proxy, and microop interpreter "
    "evidence. This is not Khronos CTS, not official OpenCL conformance, not "
    "a Khronos ICD, not libOpenCL, and not a production driver claim."
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def builtin_spec_map() -> dict[str, opencl_subset.KernelSpec]:
    specs = {spec.name: spec for spec in opencl_subset.builtin_specs()}
    missing = [name for name in SAMPLE_NAMES if name not in specs]
    if missing:
        raise RuntimeError(f"missing OpenCL subset builtin specs: {', '.join(missing)}")
    return specs


def buffer_access(spec: opencl_subset.KernelSpec) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    writes = []
    reads = []
    for buf in spec.buffers:
        record = {
            "arg": str(buf["arg"]),
            "id": str(buf["id"]),
            "device_address": str(buf["device_address"]),
            "size_bytes": int(buf["size_bytes"]),
            "access": str(buf["access"]),
        }
        if str(buf["access"]) != "write_only":
            writes.append(record)
        if str(buf["access"]) != "read_only":
            reads.append(record)
    return writes, reads


def runtime_commands_for_sample(abi: Mapping[str, Any]) -> dict[str, Any]:
    base = opencl_subset.runtime_commands_from_abis([abi], "gpgpu_nano_ultra31")
    memory_regions = []
    for region in base["memory_regions"]:
        normalized = dict(region)
        if str(normalized.get("name", "")).startswith("arg_") or any(
            str(buf.get("id")) == str(normalized.get("name")) for buf in abi["buffers"]
        ):
            # Kernel buffer access remains recorded in the ABI. The userspace
            # sample also needs host-side write/read staging for enqueue APIs.
            normalized["readable"] = True
            normalized["writable"] = True
        memory_regions.append(normalized)
    commands: list[dict[str, Any]] = []
    sequence = 1

    for buf in abi["buffers"]:
        if str(buf.get("access")) == "write_only":
            continue
        commands.append(
            {
                "opcode": "write_buffer",
                "sequence": sequence,
                "queue_id": 0,
                "submit_tag": f"{abi['name']}-write-{buf['arg']}",
                "dst_addr": buf["device_address"],
                "byte_count": int(buf["size_bytes"]),
                "data_pattern": "deterministic_sample_fixture",
            }
        )
        sequence += 1

    dispatch = dict(base["commands"][0])
    dispatch["sequence"] = sequence
    dispatch["submit_tag"] = f"{abi['name']}-ndrange"
    commands.append(dispatch)
    sequence += 1

    for buf in abi["buffers"]:
        if str(buf.get("access")) == "read_only":
            continue
        commands.append(
            {
                "opcode": "read_buffer",
                "sequence": sequence,
                "queue_id": 0,
                "submit_tag": f"{abi['name']}-read-{buf['arg']}",
                "src_addr": buf["device_address"],
                "byte_count": int(buf["size_bytes"]),
            }
        )
        sequence += 1

    return {
        **base,
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "memory_regions": memory_regions,
        "commands": commands,
    }


def run_host_lifecycle(spec: opencl_subset.KernelSpec, abi: Mapping[str, Any]) -> dict[str, Any]:
    shim = opencl_host_api_shim.HostShim()
    platform = shim.clGetPlatformIDs()
    device = shim.clGetDeviceIDs(platform)
    context = shim.clCreateContext(device)
    queue = shim.clCreateCommandQueueWithProperties(context, device, {"CL_QUEUE_PROFILING_ENABLE": False})
    if queue is None:
        raise RuntimeError("queue creation unexpectedly failed")

    buffers: dict[str, str] = {}
    writes, reads = buffer_access(spec)
    for buf in spec.buffers:
        buffers[str(buf["arg"])] = shim.clCreateBuffer(context, str(buf["id"]), int(buf["size_bytes"]), str(buf["access"]))
    write_events = [shim.clEnqueueWriteBuffer(queue, buffers[item["arg"]], int(item["size_bytes"])) for item in writes]
    program = shim.clCreateProgramWithSource(context, spec.source)
    built = shim.clBuildProgram(program, spec)
    if built is None:
        raise RuntimeError(f"{spec.name} build unexpectedly failed")
    kernel = shim.clCreateKernel(program, spec.name)
    if kernel is None:
        raise RuntimeError(f"{spec.name} kernel creation unexpectedly failed")

    arg_values: list[str | int | float] = []
    for arg in abi["args"]:
        name = str(arg["name"])
        if bool(arg["pointer"]):
            arg_values.append(buffers[name])
        else:
            arg_values.append(spec.scalar_args[name])
    for index, value in enumerate(arg_values):
        shim.clSetKernelArg(kernel, index, value)

    kernel_event, metrics = shim.clEnqueueNDRangeKernel(queue, kernel)
    read_events = [shim.clEnqueueReadBuffer(queue, buffers[item["arg"]], [kernel_event]) for item in reads]
    shim.clWaitForEvents(write_events + [kernel_event] + read_events)
    shim.clFinish(queue)

    release_order = read_events + [kernel_event] + write_events + [kernel, program] + list(buffers.values()) + [queue, context, device, platform]
    for handle in release_order:
        shim.clRelease(handle)

    return {
        "api_call_count": len(shim.trace),
        "api_call_trace": shim.trace,
        "events": shim.events,
        "runtime_proxy_summary": metrics.get("summary", {}),
        "live_handles_after_release": shim.live_handles(),
    }


def load_microop_index(microop_root: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    report_path = microop_root / "microop_execution_report.json"
    summary = load_json(report_path)
    kernels: dict[str, dict[str, Any]] = {}
    for name in SAMPLE_NAMES:
        kernels[name] = load_json(microop_root / "kernels" / f"{name}.microop_execution.json")
    return summary, kernels


def sample_checks(sample: Mapping[str, Any]) -> list[dict[str, Any]]:
    runtime_summary = sample["runtime_proxy"]["summary"]
    command_summary = sample["runtime_proxy"]["command_summary"]
    microop = sample["microop_evidence"]
    host_apis = {item["api"] for item in sample["host_api"]["api_call_trace"]}
    required_apis = {
        "clCreateBuffer",
        "clEnqueueWriteBuffer",
        "clBuildProgram",
        "clCreateKernel",
        "clSetKernelArg",
        "clEnqueueNDRangeKernel",
        "clEnqueueReadBuffer",
        "clWaitForEvents",
        "clFinish",
    }
    return [
        {"name": "host_api_lifecycle_complete", "pass": required_apis <= host_apis, "observed": sorted(host_apis)},
        {"name": "host_api_released_handles", "pass": sample["host_api"]["live_handles_after_release"] == {}},
        {"name": "buffer_write_path_executed", "pass": command_summary["write_buffer_count"] >= 1 and sample["buffer_io"]["write_count"] >= 1},
        {"name": "buffer_read_path_executed", "pass": command_summary["read_buffer_count"] >= 1 and sample["buffer_io"]["read_count"] >= 1},
        {"name": "ndrange_path_executed", "pass": command_summary["ndrange_count"] == 1},
        {"name": "runtime_proxy_completed_all_commands", "pass": int(runtime_summary.get("commands_completed", -1)) == command_summary["command_count"]},
        {"name": "runtime_proxy_no_failed_commands", "pass": int(runtime_summary.get("commands_failed", -1)) == 0},
        {"name": "microop_status_pass", "pass": microop["status"] == "pass"},
        {"name": "microop_oracle_hash_present", "pass": bool(microop["result_sha256"])},
        {"name": "microop_global_load_store_present", "pass": microop["memory_counts"].get("load", 0) > 0 and microop["memory_counts"].get("store", 0) > 0},
    ]


def run_negative_paths() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    specs = builtin_spec_map()
    spec = specs["vector_add"]

    bad_source = "__kernel void bad(__global double *p) { p[0] = 1.0; }"
    shim = opencl_host_api_shim.HostShim()
    platform = shim.clGetPlatformIDs()
    device = shim.clGetDeviceIDs(platform)
    context = shim.clCreateContext(device)
    bad_program = shim.clCreateProgramWithSource(context, bad_source)
    bad_spec = opencl_subset.KernelSpec(
        name="bad",
        source=bad_source,
        global_size=(64, 1, 1),
        local_size=(32, 1, 1),
        buffers=({"id": "bad_p", "arg": "p", "device_address": "0x88000000", "size_bytes": 4096, "access": "read_write"},),
        scalar_args={},
        precision="fp32",
    )
    build = shim.clBuildProgram(bad_program, bad_spec)
    cases.append(
        {
            "name": "build_rejects_unsupported_double",
            "path": "host_api_shim.clBuildProgram",
            "expected_error": "CL_BUILD_PROGRAM_FAILURE",
            "observed_error": shim.trace[-1]["result"],
            "pass": build is None and shim.trace[-1]["result"] == "CL_BUILD_PROGRAM_FAILURE",
        }
    )

    good_program = shim.clCreateProgramWithSource(context, spec.source)
    shim.clBuildProgram(good_program, spec)
    missing = shim.clCreateKernel(good_program, "not_vector_add")
    cases.append(
        {
            "name": "kernel_name_error_path",
            "path": "host_api_shim.clCreateKernel",
            "expected_error": "CL_INVALID_KERNEL_NAME",
            "observed_error": shim.trace[-1]["result"],
            "pass": missing is None and shim.trace[-1]["result"] == "CL_INVALID_KERNEL_NAME",
        }
    )

    bad_runtime = {
        "schema": runtime_proxy.RUNTIME_SCHEMA,
        "ip_name": "Celviz GPGPU IP",
        "tier": "gpgpu_nano_ultra31",
        "queues": runtime_proxy.default_queues("gpgpu_nano_ultra31")[:1],
        "memory_regions": [{"name": "tiny", "base": "0x80000000", "size": 64, "readable": True, "writable": True}],
        "commands": [
            {
                "opcode": "write_buffer",
                "sequence": 1,
                "queue_id": 0,
                "dst_addr": "0x80000100",
                "byte_count": 256,
                "submit_tag": "negative-oob-write",
            }
        ],
    }
    _log, metrics = runtime_proxy.execute_runtime(bad_runtime, dry_run=True, base_dir=repo_root())
    summary = metrics.get("summary", {})
    cases.append(
        {
            "name": "runtime_rejects_out_of_bounds_write_buffer",
            "path": "runtime_proxy.write_buffer",
            "expected_error": "ERR_MMU_FAULT",
            "observed_failed_commands": int(summary.get("commands_failed", -1)),
            "pass": int(summary.get("commands_failed", -1)) == 1,
        }
    )
    return cases


def build_doc(report: Mapping[str, Any]) -> str:
    lines = [
        "# OpenCL Userspace Samples",
        "",
        str(report["clean_room_scope"]),
        "",
        "## Boundary",
        "",
        "These samples are executable readiness evidence only. They are not official OpenCL conformance, not Khronos CTS, not a Khronos ICD, and not libOpenCL.",
        "",
        "## Samples",
        "",
    ]
    for sample in report["samples"]:
        lines.append(
            f"- `{sample['name']}`: status=`{sample['status']}` "
            f"writes=`{sample['buffer_io']['write_count']}` reads=`{sample['buffer_io']['read_count']}` "
            f"commands=`{sample['runtime_proxy']['command_summary']['command_count']}` "
            f"microop_hash=`{sample['microop_evidence']['result_sha256']}`"
        )
    lines.extend(["", "## Error Paths", ""])
    for case in report["negative_tests"]:
        lines.append(f"- `{case['name']}` path=`{case['path']}` pass=`{case['pass']}`")
    lines.extend(["", "## Evidence", "", f"- JSON: `{report['evidence_path']}`", ""])
    return "\n".join(lines)


def run(output: Path, doc: Path | None, microop_root: Path) -> dict[str, Any]:
    specs = builtin_spec_map()
    microop_summary, microop_kernels = load_microop_index(microop_root)
    samples: list[dict[str, Any]] = []

    for index, name in enumerate(SAMPLE_NAMES, start=1):
        spec = specs[name]
        abi = opencl_subset.compile_kernel(spec, index)
        writes, reads = buffer_access(spec)
        runtime_data = runtime_commands_for_sample(abi)
        _runtime_log, runtime_metrics = runtime_proxy.execute_runtime(runtime_data, dry_run=True, base_dir=repo_root())
        host_api = run_host_lifecycle(spec, abi)
        commands = runtime_data["commands"]
        microop = microop_kernels[name]
        execution = microop.get("execution", {})
        sample = {
            "name": name,
            "status": "unknown",
            "description": spec.description,
            "source_sha256": abi["source_sha256"],
            "global_size": abi["global_size"],
            "local_size": abi["local_size"],
            "work_items": abi["work_items"],
            "abi": {
                "schema": abi["schema"],
                "kernel_id": abi["kernel_id"],
                "arg_count": len(abi["args"]),
                "buffer_count": len(abi["buffers"]),
                "address_spaces": abi["address_spaces"],
                "precision": abi["precision"],
            },
            "buffer_io": {
                "writes": writes,
                "reads": reads,
                "write_count": len(writes),
                "read_count": len(reads),
            },
            "host_api": host_api,
            "runtime_proxy": {
                "schema": runtime_proxy.RUNTIME_SCHEMA,
                "summary": runtime_metrics.get("summary", {}),
                "command_summary": {
                    "command_count": len(commands),
                    "write_buffer_count": sum(1 for cmd in commands if cmd["opcode"] == "write_buffer"),
                    "ndrange_count": sum(1 for cmd in commands if cmd["opcode"] == "kernel_dispatch"),
                    "read_buffer_count": sum(1 for cmd in commands if cmd["opcode"] == "read_buffer"),
                },
                "commands": commands,
            },
            "microop_evidence": {
                "schema": microop.get("schema"),
                "status": microop.get("status"),
                "kernel": microop.get("kernel"),
                "oracle_workload": microop.get("oracle_workload"),
                "sha256": microop.get("sha256"),
                "result_sha256": microop.get("result", {}).get("result_sha256", microop.get("result_sha256")),
                "uops_executed": execution.get("pc_count"),
                "memory_event_count": execution.get("memory_event_count"),
                "memory_counts": execution.get("memory_counts", {}),
                "completion_written": execution.get("completion_written"),
            },
        }
        sample["checks"] = sample_checks(sample)
        sample["status"] = "pass" if all(check["pass"] for check in sample["checks"]) else "fail"
        samples.append(sample)

    negative_tests = run_negative_paths()
    report = {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "status": "unknown",
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "conformance_boundary": {
            "official_opencl_conformance": False,
            "khronos_cts": False,
            "khronos_icd": False,
            "libopencl": False,
        },
        "evidence_path": str(output),
        "sample_count": len(samples),
        "samples": samples,
        "negative_tests": negative_tests,
        "microop_summary": {
            "path": str(microop_root / "microop_execution_report.json"),
            "schema": microop_summary.get("schema"),
            "status": microop_summary.get("status"),
            "kernel_count": microop_summary.get("kernel_count"),
        },
    }
    report["checks"] = [
        {"name": "required_samples_present", "pass": {sample["name"] for sample in samples} == set(SAMPLE_NAMES)},
        {"name": "all_samples_pass", "pass": all(sample["status"] == "pass" for sample in samples)},
        {"name": "negative_error_paths_pass", "pass": all(case["pass"] for case in negative_tests)},
        {"name": "microop_summary_pass", "pass": microop_summary.get("status") == "pass"},
        {"name": "not_official_conformance_or_cts", "pass": report["conformance_boundary"]["official_opencl_conformance"] is False and report["conformance_boundary"]["khronos_cts"] is False},
    ]
    report["status"] = "pass" if all(check["pass"] for check in report["checks"]) else "fail"
    write_json(output, report)
    if doc is not None:
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text(build_doc(report), encoding="utf-8")
    return report


def verify(path: Path) -> dict[str, Any]:
    report = load_json(path)
    checks = report.get("checks", [])
    report["status"] = "pass" if checks and all(check.get("pass") is True for check in checks) else "fail"
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run executable OpenCL userspace samples through Celviz readiness shims.")
    parser.add_argument("--output", type=Path, default=repo_root() / DEFAULT_OUTPUT)
    parser.add_argument("--doc", type=Path, default=repo_root() / DEFAULT_DOC)
    parser.add_argument("--microop-root", type=Path, default=repo_root() / DEFAULT_MICROOP_ROOT)
    parser.add_argument("--verify-only", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        report = verify(args.output) if args.verify_only else run(args.output, args.doc, args.microop_root)
    except (OSError, RuntimeError, ValueError, KeyError, json.JSONDecodeError, opencl_subset.SubsetError, runtime_proxy.RuntimeProxyError) as exc:
        print(f"opencl_userspace_samples: error: {exc}", file=sys.stderr)
        return 2
    print(
        "opencl_userspace_samples: "
        f"status={report.get('status')} samples={report.get('sample_count')} "
        f"negative={len(report.get('negative_tests', []))} output={args.output}"
    )
    return 0 if report.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
