#!/usr/bin/env python3
"""OpenCL ICD/runtime API contract map for the Celviz proxy stack.

This records the host API surface needed before official CTS can be attempted.
It is a contract and gap map, not a production ICD implementation.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "celviz.gpgpu.opencl_icd_runtime_contract.v1"
DEFAULT_OUTPUT = Path("artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_icd_runtime_contract.json")
CLEAN_ROOM_SCOPE = (
    "clean-room OpenCL host API contract for Celviz proxy/runtime alignment; "
    "not a Khronos ICD loader integration, not an official OpenCL conformance "
    "claim, not a production Linux driver, and not a stable public ABI"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def api(
    name: str,
    status: str,
    proxy_mapping: str,
    evidence: list[str],
    blocker: str,
    next_test: str,
) -> dict[str, Any]:
    return {
        "api": name,
        "current_status": status,
        "proxy_mapping": proxy_mapping,
        "local_evidence": evidence,
        "blocker_to_official_conformance": blocker,
        "next_executable_test": next_test,
    }


def build_contract() -> dict[str, Any]:
    entries = [
        api(
            "clGetPlatformIDs",
            "proxy",
            "single Celviz clean-room platform descriptor",
            ["docs/celviz-gpgpu-ip/OPENCL_SUBSET_ABI.md"],
            "No Khronos ICD vendor library or platform enumeration ABI is implemented.",
            "Add a mock ICD loader fixture that enumerates exactly one Celviz platform.",
        ),
        api(
            "clGetDeviceIDs",
            "proxy",
            "device_tiers.json models tiered GPU-like devices",
            ["artifacts/rank_01_vivante_3d_gpgpu_ip/demo/outputs/device_tiers.json"],
            "Device type/profile/extensions/limits are not spec-complete.",
            "Validate CL_DEVICE_TYPE_GPU, work-item limits, memory sizes, and feature queries.",
        ),
        api(
            "clGetDeviceInfo",
            "partial",
            "proxy metrics expose tiers, ops/cycle proxies, and memory metadata",
            ["artifacts/rank_01_vivante_3d_gpgpu_ip/demo/outputs/kernel_metrics.json"],
            "OpenCL 3.0 device-info table and optional feature query semantics are incomplete.",
            "Create a device-info golden table and negative tests for unsupported queries.",
        ),
        api(
            "clCreateContext",
            "proxy",
            "linux_runtime_proxy context/device lifecycle",
            ["artifacts/rank_01_vivante_3d_gpgpu_ip/os_runtime/linux_runtime_evidence.json"],
            "No real ICD context handles, callback semantics, or multi-device context validation.",
            "Add handle lifetime tests for create/release/error callback cases.",
        ),
        api(
            "clCreateCommandQueueWithProperties",
            "partial",
            "driver_submission_model queue lifecycle and ordered completion",
            ["artifacts/rank_01_vivante_3d_gpgpu_ip/driver_submission/queue_lifecycle.json"],
            "Out-of-order queues, profiling properties, and full error behavior are absent.",
            "Map in-order queue semantics to fence/event traces and reject unsupported properties.",
        ),
        api(
            "clCreateBuffer",
            "partial",
            "runtime_proxy memory_regions and buffer_binds",
            ["artifacts/rank_01_vivante_3d_gpgpu_ip/demo/outputs/buffer_binds.json"],
            "OpenCL flags, host pointer import, sub-buffers, and map/unmap semantics are incomplete.",
            "Add flag matrix tests for read/write/copy-host-ptr unsupported cases.",
        ),
        api(
            "clEnqueueWriteBuffer",
            "proxy",
            "host_to_device/dma_copy command category",
            ["artifacts/rank_01_vivante_3d_gpgpu_ip/rtl/control_plane_demo.json"],
            "Blocking/non-blocking, offset bounds, event wait lists, and map coherency are not complete.",
            "Add offset/bounds/event-wait directed tests through runtime_proxy.",
        ),
        api(
            "clEnqueueReadBuffer",
            "proxy",
            "device_to_host/dma_copy readback and golden hashes",
            ["artifacts/rank_01_vivante_3d_gpgpu_ip/demo/outputs/queue_trace.json"],
            "Blocking/non-blocking and event wait-list behavior needs CTS-shaped validation.",
            "Add event-order and negative bounds tests for readback commands.",
        ),
        api(
            "clCreateProgramWithSource",
            "partial",
            "opencl_subset.py parses one-kernel OpenCL C subset sources",
            ["tools/celviz_gpgpu_ip/opencl_subset.py"],
            "Multi-kernel programs, include options, diagnostics, and full OpenCL C grammar are absent.",
            "Add source program object tests for one-kernel accepted and multi-kernel rejected cases.",
        ),
        api(
            "clBuildProgram",
            "partial",
            "opencl_subset.py compile_kernel emits ABI JSON",
            ["artifacts/rank_01_vivante_3d_gpgpu_ip/demo/opencl_subset/opencl_subset_evidence.json"],
            "Build options, binaries, SPIR-V ingestion, logs, and specialization are absent.",
            "Add build-log and unsupported-option negative tests.",
        ),
        api(
            "clCreateKernel",
            "partial",
            "kernel ABI names and metadata map to runtime dispatch",
            ["artifacts/rank_01_vivante_3d_gpgpu_ip/demo/opencl_subset/abi/vector_add.kernel_abi.json"],
            "Program-owned kernel handle lifecycle and symbol lookup errors are incomplete.",
            "Add kernel name lookup tests for valid and missing symbols.",
        ),
        api(
            "clSetKernelArg",
            "partial",
            "ABI scalar_args and buffer metadata bind kernel arguments",
            ["docs/celviz-gpgpu-ip/OPENCL_SUBSET_ABI.md"],
            "Argument type checking, local memory arg sizing, and retained object lifetime are incomplete.",
            "Add scalar/vector/pointer/local argument layout tests.",
        ),
        api(
            "clEnqueueNDRangeKernel",
            "partial",
            "runtime kernel_dispatch command models NDRange and local geometry",
            ["artifacts/rank_01_vivante_3d_gpgpu_ip/demo/opencl_subset/runtime_commands.json"],
            "Work dimension validation, offsets, event wait lists, and unsupported local sizes need full coverage.",
            "Add NDRange geometry matrix tests and map failures to OpenCL-style error codes.",
        ),
        api(
            "clFinish",
            "proxy",
            "runtime pending_count reaches zero",
            ["artifacts/rank_01_vivante_3d_gpgpu_ip/demo/opencl_subset/runtime_proxy/runtime_metrics.json"],
            "Per-queue blocking semantics and error propagation are modeled but not API-stable.",
            "Add queue drain tests with success and injected fault cases.",
        ),
        api(
            "clWaitForEvents",
            "proxy",
            "driver fence/event lifecycle",
            ["artifacts/rank_01_vivante_3d_gpgpu_ip/driver_submission/fence_event_lifecycle.json"],
            "Event wait-list validation, status transitions, callbacks, and profiling are incomplete.",
            "Add event dependency graph tests including failure propagation.",
        ),
        api(
            "clRelease*",
            "partial",
            "proxy lifecycle reports close queues and releases handles conceptually",
            ["artifacts/rank_01_vivante_3d_gpgpu_ip/os_runtime/linux_runtime_evidence.json"],
            "Reference counting, use-after-release errors, and cross-object ownership are absent.",
            "Add retained/released handle lifecycle tests across context, queue, buffer, program, kernel, and event.",
        ),
    ]
    checks = [
        {"name": "api_surface_depth", "pass": len(entries) >= 16, "count": len(entries)},
        {
            "name": "all_entries_have_executable_next_test",
            "pass": all(item["next_executable_test"] for item in entries),
        },
        {
            "name": "no_official_icd_overclaim",
            "pass": "not a Khronos ICD" in CLEAN_ROOM_SCOPE and "not an official OpenCL conformance claim" in CLEAN_ROOM_SCOPE,
            "scope": CLEAN_ROOM_SCOPE,
        },
    ]
    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "status": "pass" if all(item["pass"] for item in checks) else "fail",
        "status_vocabulary": ["absent", "proxy", "partial", "ready"],
        "host_api_contract": entries,
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Celviz OpenCL ICD/runtime contract map.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = build_contract()
    write_json(args.output, report)
    print(f"celviz_gpgpu_opencl_icd_runtime_contract: {report['status']} apis={len(report['host_api_contract'])} output={args.output}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
