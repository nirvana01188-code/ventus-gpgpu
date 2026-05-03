#!/usr/bin/env python3
"""Executable OpenCL host API shim for Celviz GPGPU IP readiness.

This is a clean-room API lifecycle simulator that drives the existing OpenCL C
subset compiler and runtime proxy. It is not a Khronos ICD, not libOpenCL, and
not official conformance evidence.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

try:
    from . import opencl_subset, runtime_proxy
except ImportError:  # pragma: no cover - direct script fallback
    import opencl_subset  # type: ignore
    import runtime_proxy  # type: ignore


SCHEMA = "celviz.gpgpu.opencl_host_api_shim.v1"
DEFAULT_ARTIFACT_ROOT = Path("artifacts/rank_01_vivante_3d_gpgpu_ip")
DEFAULT_OUTPUT = DEFAULT_ARTIFACT_ROOT / "verification/opencl_host_api_shim_report.json"
DEFAULT_DOC = Path("docs/celviz-gpgpu-ip/OPENCL_HOST_API_SHIM.md")
CLEAN_ROOM_SCOPE = (
    "clean-room OpenCL host API shim for Celviz GPGPU IP readiness; executes "
    "a local subset lifecycle through the compiler ABI and runtime proxy. Not "
    "a Khronos ICD, not libOpenCL, not official OpenCL conformance, not CTS "
    "pass evidence, not a production Linux driver, and not Vivante proprietary "
    "compatibility."
)

ERROR_CODES = {
    "CL_SUCCESS": 0,
    "CL_INVALID_VALUE": -30,
    "CL_INVALID_DEVICE": -33,
    "CL_INVALID_CONTEXT": -34,
    "CL_INVALID_QUEUE_PROPERTIES": -35,
    "CL_INVALID_COMMAND_QUEUE": -36,
    "CL_INVALID_MEM_OBJECT": -38,
    "CL_INVALID_PROGRAM": -44,
    "CL_INVALID_KERNEL_NAME": -46,
    "CL_INVALID_KERNEL": -48,
    "CL_INVALID_ARG_INDEX": -49,
    "CL_INVALID_WORK_GROUP_SIZE": -54,
    "CL_BUILD_PROGRAM_FAILURE": -11,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_doc(path: Path, report: Mapping[str, Any]) -> None:
    lines = [
        "# OpenCL Host API Shim",
        "",
        str(report["clean_room_scope"]),
        "",
        "## Executed Lifecycle",
        "",
    ]
    for call in report["api_call_trace"]:
        lines.append(f"- `{call['api']}` -> `{call['result']}` handle=`{call.get('handle', '')}`")
    lines.extend(["", "## Negative Error-Code Tests", ""])
    for case in report["negative_tests"]:
        lines.append(f"- `{case['name']}`: `{case['observed_error']}` expected `{case['expected_error']}`")
    lines.extend(
        [
            "",
            "## Runtime Evidence",
            "",
            f"- Runtime status: `{report['runtime_proxy_summary']['status']}`",
            f"- Commands completed: `{report['runtime_proxy_summary']['commands_completed']}`",
            f"- Commands failed: `{report['runtime_proxy_summary']['commands_failed']}`",
            f"- Pending count: `{report['runtime_proxy_summary']['pending_count']}`",
            "",
            "Boundary: this is an executable readiness shim, not a Khronos ICD or official CTS result.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


@dataclass
class Handle:
    kind: str
    name: str
    refcount: int = 1
    payload: dict[str, Any] = field(default_factory=dict)


class HostShim:
    def __init__(self) -> None:
        self.next_id = 1
        self.handles: dict[str, Handle] = {}
        self.trace: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []

    def _new_handle(self, kind: str, name: str, payload: Mapping[str, Any] | None = None) -> str:
        handle = f"{kind}_{self.next_id}"
        self.next_id += 1
        self.handles[handle] = Handle(kind=kind, name=name, payload=dict(payload or {}))
        return handle

    def _trace(self, api: str, result: str = "CL_SUCCESS", handle: str | None = None, **details: Any) -> None:
        self.trace.append(
            {
                "index": len(self.trace) + 1,
                "api": api,
                "result": result,
                "error_code": ERROR_CODES[result],
                **({"handle": handle} if handle else {}),
                **details,
            }
        )

    def _require(self, handle: str, kind: str, error: str) -> Handle:
        item = self.handles.get(handle)
        if item is None or item.kind != kind or item.refcount <= 0:
            raise KeyError(error)
        return item

    def clGetPlatformIDs(self) -> str:
        handle = self._new_handle("platform", "Celviz Clean-room Platform", {"profile": "EMBEDDED_PROFILE_PROXY"})
        self._trace("clGetPlatformIDs", handle=handle)
        return handle

    def clGetDeviceIDs(self, platform: str) -> str:
        self._require(platform, "platform", "CL_INVALID_VALUE")
        handle = self._new_handle(
            "device",
            "celviz-gpgpu-proxy",
            {
                "type": "CL_DEVICE_TYPE_GPU",
                "opencl_c_version": "OpenCL C subset",
                "max_work_group_size": 256,
                "address_bits": 40,
            },
        )
        self._trace("clGetDeviceIDs", handle=handle, platform=platform)
        return handle

    def clGetDeviceInfo(self, device: str, param: str) -> Any:
        item = self._require(device, "device", "CL_INVALID_DEVICE")
        supported = {"CL_DEVICE_TYPE", "CL_DEVICE_MAX_WORK_GROUP_SIZE", "CL_DEVICE_ADDRESS_BITS", "CL_DEVICE_OPENCL_C_VERSION"}
        if param not in supported:
            self._trace("clGetDeviceInfo", "CL_INVALID_VALUE", device=device, param=param)
            return None
        self._trace("clGetDeviceInfo", device=device, param=param)
        return item.payload.get(param.lower().replace("cl_device_", ""))

    def clCreateContext(self, device: str) -> str:
        self._require(device, "device", "CL_INVALID_DEVICE")
        handle = self._new_handle("context", "context0", {"device": device})
        self._trace("clCreateContext", handle=handle, device=device)
        return handle

    def clCreateCommandQueueWithProperties(self, context: str, device: str, properties: Mapping[str, Any] | None = None) -> str | None:
        self._require(context, "context", "CL_INVALID_CONTEXT")
        self._require(device, "device", "CL_INVALID_DEVICE")
        properties = dict(properties or {})
        if properties.get("CL_QUEUE_OUT_OF_ORDER_EXEC_MODE_ENABLE"):
            self._trace("clCreateCommandQueueWithProperties", "CL_INVALID_QUEUE_PROPERTIES", context=context, device=device, properties=properties)
            return None
        handle = self._new_handle("queue", "queue0", {"context": context, "device": device, "properties": properties})
        self._trace("clCreateCommandQueueWithProperties", handle=handle, context=context, device=device, properties=properties)
        return handle

    def clCreateBuffer(self, context: str, name: str, size_bytes: int, flags: str) -> str:
        self._require(context, "context", "CL_INVALID_CONTEXT")
        if size_bytes <= 0:
            self._trace("clCreateBuffer", "CL_INVALID_VALUE", context=context, name=name, size_bytes=size_bytes, flags=flags)
            raise ValueError("CL_INVALID_VALUE")
        handle = self._new_handle("buffer", name, {"context": context, "size_bytes": size_bytes, "flags": flags})
        self._trace("clCreateBuffer", handle=handle, context=context, name=name, size_bytes=size_bytes, flags=flags)
        return handle

    def clEnqueueWriteBuffer(self, queue: str, buffer_handle: str, size_bytes: int) -> str:
        self._require(queue, "queue", "CL_INVALID_COMMAND_QUEUE")
        buffer = self._require(buffer_handle, "buffer", "CL_INVALID_MEM_OBJECT")
        if size_bytes > int(buffer.payload["size_bytes"]):
            self._trace("clEnqueueWriteBuffer", "CL_INVALID_VALUE", queue=queue, buffer=buffer_handle, size_bytes=size_bytes)
            raise ValueError("CL_INVALID_VALUE")
        event = self._new_handle("event", f"write_{buffer.name}", {"queue": queue, "status": "complete"})
        self.events.append({"event": event, "command": "write_buffer", "status": "complete", "buffer": buffer_handle})
        self._trace("clEnqueueWriteBuffer", handle=event, queue=queue, buffer=buffer_handle, size_bytes=size_bytes)
        return event

    def clCreateProgramWithSource(self, context: str, source: str) -> str:
        self._require(context, "context", "CL_INVALID_CONTEXT")
        handle = self._new_handle("program", "program0", {"context": context, "source": source, "build_status": "none"})
        self._trace("clCreateProgramWithSource", handle=handle, context=context, source_sha256=opencl_subset.sha256_text(source))
        return handle

    def clBuildProgram(self, program: str, spec: opencl_subset.KernelSpec) -> dict[str, Any] | None:
        handle = self._require(program, "program", "CL_INVALID_PROGRAM")
        try:
            abi = opencl_subset.compile_kernel(spec, 300)
        except opencl_subset.SubsetError as exc:
            handle.payload["build_status"] = "failed"
            handle.payload["build_log"] = str(exc)
            self._trace("clBuildProgram", "CL_BUILD_PROGRAM_FAILURE", program=program, build_log=str(exc))
            return None
        handle.payload["build_status"] = "success"
        handle.payload["abi"] = abi
        self._trace("clBuildProgram", program=program, kernel=abi["name"], abi_schema=abi["schema"])
        return abi

    def clCreateKernel(self, program: str, kernel_name: str) -> str | None:
        handle = self._require(program, "program", "CL_INVALID_PROGRAM")
        abi = handle.payload.get("abi", {})
        if abi.get("name") != kernel_name:
            self._trace("clCreateKernel", "CL_INVALID_KERNEL_NAME", program=program, kernel_name=kernel_name)
            return None
        kernel = self._new_handle("kernel", kernel_name, {"program": program, "abi": abi, "args": {}})
        self._trace("clCreateKernel", handle=kernel, program=program, kernel_name=kernel_name)
        return kernel

    def clSetKernelArg(self, kernel: str, index: int, value: str | int | float) -> None:
        handle = self._require(kernel, "kernel", "CL_INVALID_KERNEL")
        arg_count = len(handle.payload.get("abi", {}).get("args", []))
        if index < 0 or index >= arg_count:
            self._trace("clSetKernelArg", "CL_INVALID_ARG_INDEX", kernel=kernel, index=index)
            raise IndexError("CL_INVALID_ARG_INDEX")
        handle.payload["args"][index] = value
        self._trace("clSetKernelArg", kernel=kernel, index=index, value=str(value))

    def clEnqueueNDRangeKernel(self, queue: str, kernel: str) -> tuple[str, dict[str, Any]]:
        self._require(queue, "queue", "CL_INVALID_COMMAND_QUEUE")
        handle = self._require(kernel, "kernel", "CL_INVALID_KERNEL")
        abi = handle.payload["abi"]
        global_size = abi["global_size"]
        local_size = abi["local_size"]
        if any(int(global_size[i]) % int(local_size[i]) != 0 for i in range(3)):
            self._trace("clEnqueueNDRangeKernel", "CL_INVALID_WORK_GROUP_SIZE", queue=queue, kernel=kernel)
            raise ValueError("CL_INVALID_WORK_GROUP_SIZE")
        runtime_data = opencl_subset.runtime_commands_from_abis([abi], "gpgpu_nano_ultra31")
        _log, metrics = runtime_proxy.execute_runtime(runtime_data, dry_run=True, base_dir=Path.cwd())
        event = self._new_handle("event", f"kernel_{handle.name}", {"queue": queue, "status": "complete", "runtime_status": metrics["status"]})
        self.events.append({"event": event, "command": "ndrange_kernel", "status": "complete", "kernel": kernel})
        self._trace("clEnqueueNDRangeKernel", handle=event, queue=queue, kernel=kernel, runtime_status=metrics["status"])
        return event, metrics

    def clEnqueueReadBuffer(self, queue: str, buffer_handle: str, wait_for: list[str]) -> str:
        self._require(queue, "queue", "CL_INVALID_COMMAND_QUEUE")
        self._require(buffer_handle, "buffer", "CL_INVALID_MEM_OBJECT")
        for event in wait_for:
            self._require(event, "event", "CL_INVALID_VALUE")
        out_event = self._new_handle("event", "read_buffer", {"queue": queue, "status": "complete", "wait_for": wait_for})
        self.events.append({"event": out_event, "command": "read_buffer", "status": "complete", "wait_for": wait_for})
        self._trace("clEnqueueReadBuffer", handle=out_event, queue=queue, buffer=buffer_handle, wait_for=wait_for)
        return out_event

    def clWaitForEvents(self, events: list[str]) -> None:
        for event in events:
            self._require(event, "event", "CL_INVALID_VALUE")
        self._trace("clWaitForEvents", event_count=len(events), events=events)

    def clFinish(self, queue: str) -> None:
        self._require(queue, "queue", "CL_INVALID_COMMAND_QUEUE")
        self._trace("clFinish", queue=queue, pending_count=0)

    def clRelease(self, handle: str) -> None:
        item = self.handles.get(handle)
        if item is None or item.refcount <= 0:
            self._trace("clRelease*", "CL_INVALID_VALUE", handle=handle)
            raise KeyError("CL_INVALID_VALUE")
        item.refcount -= 1
        self._trace(f"clRelease{item.kind.capitalize()}", handle=handle, refcount=item.refcount)

    def live_handles(self) -> dict[str, dict[str, Any]]:
        return {
            handle: {"kind": item.kind, "name": item.name, "refcount": item.refcount}
            for handle, item in self.handles.items()
            if item.refcount > 0
        }


def vector_add_spec() -> opencl_subset.KernelSpec:
    for spec in opencl_subset.builtin_specs():
        if spec.name == "vector_add":
            return spec
    raise RuntimeError("missing vector_add builtin spec")


def run_lifecycle() -> dict[str, Any]:
    shim = HostShim()
    spec = vector_add_spec()

    platform = shim.clGetPlatformIDs()
    device = shim.clGetDeviceIDs(platform)
    shim.clGetDeviceInfo(device, "CL_DEVICE_TYPE")
    shim.clGetDeviceInfo(device, "CL_DEVICE_MAX_WORK_GROUP_SIZE")
    context = shim.clCreateContext(device)
    queue = shim.clCreateCommandQueueWithProperties(context, device, {"CL_QUEUE_PROFILING_ENABLE": False})
    assert queue is not None

    buffers: dict[str, str] = {}
    for buf in spec.buffers:
        buffers[str(buf["arg"])] = shim.clCreateBuffer(context, str(buf["id"]), int(buf["size_bytes"]), str(buf["access"]))
    write_events = [
        shim.clEnqueueWriteBuffer(queue, buffers["a"], 4096),
        shim.clEnqueueWriteBuffer(queue, buffers["b"], 4096),
    ]
    program = shim.clCreateProgramWithSource(context, spec.source)
    abi = shim.clBuildProgram(program, spec)
    if abi is None:
        raise RuntimeError("vector_add build unexpectedly failed")
    kernel = shim.clCreateKernel(program, "vector_add")
    if kernel is None:
        raise RuntimeError("vector_add kernel lookup unexpectedly failed")
    arg_values: list[str | int] = [buffers["a"], buffers["b"], buffers["c"], int(spec.scalar_args["n"])]
    for index, value in enumerate(arg_values):
        shim.clSetKernelArg(kernel, index, value)
    kernel_event, metrics = shim.clEnqueueNDRangeKernel(queue, kernel)
    read_event = shim.clEnqueueReadBuffer(queue, buffers["c"], [kernel_event])
    shim.clWaitForEvents(write_events + [kernel_event, read_event])
    shim.clFinish(queue)

    release_order = [read_event, kernel_event, *write_events, kernel, program, *buffers.values(), queue, context, device, platform]
    for handle in release_order:
        shim.clRelease(handle)

    summary = metrics.get("summary", {})
    return {
        "shim": shim,
        "abi": abi,
        "runtime_metrics": metrics,
        "runtime_proxy_summary": {
            "status": metrics.get("status"),
            "commands_submitted": summary.get("commands_submitted"),
            "commands_completed": summary.get("commands_completed"),
            "commands_failed": summary.get("commands_failed"),
            "pending_count": summary.get("pending_count"),
            "dry_run": summary.get("dry_run"),
        },
    }


def run_negative_tests() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []

    shim = HostShim()
    platform = shim.clGetPlatformIDs()
    device = shim.clGetDeviceIDs(platform)
    context = shim.clCreateContext(device)

    shim.clGetDeviceInfo(device, "CL_DEVICE_IMAGE_SUPPORT")
    cases.append(
        {
            "name": "unsupported_device_info_query",
            "api": "clGetDeviceInfo",
            "expected_error": "CL_INVALID_VALUE",
            "observed_error": shim.trace[-1]["result"],
            "pass": shim.trace[-1]["result"] == "CL_INVALID_VALUE",
        }
    )

    queue = shim.clCreateCommandQueueWithProperties(context, device, {"CL_QUEUE_OUT_OF_ORDER_EXEC_MODE_ENABLE": True})
    cases.append(
        {
            "name": "reject_out_of_order_queue_property",
            "api": "clCreateCommandQueueWithProperties",
            "expected_error": "CL_INVALID_QUEUE_PROPERTIES",
            "observed_error": shim.trace[-1]["result"],
            "pass": queue is None and shim.trace[-1]["result"] == "CL_INVALID_QUEUE_PROPERTIES",
        }
    )

    spec = vector_add_spec()
    program = shim.clCreateProgramWithSource(context, spec.source)
    shim.clBuildProgram(program, spec)
    missing = shim.clCreateKernel(program, "missing_kernel")
    cases.append(
        {
            "name": "reject_missing_kernel_name",
            "api": "clCreateKernel",
            "expected_error": "CL_INVALID_KERNEL_NAME",
            "observed_error": shim.trace[-1]["result"],
            "pass": missing is None and shim.trace[-1]["result"] == "CL_INVALID_KERNEL_NAME",
        }
    )

    kernel = shim.clCreateKernel(program, "vector_add")
    assert kernel is not None
    try:
        shim.clSetKernelArg(kernel, 99, 0)
    except IndexError:
        pass
    cases.append(
        {
            "name": "reject_bad_kernel_arg_index",
            "api": "clSetKernelArg",
            "expected_error": "CL_INVALID_ARG_INDEX",
            "observed_error": shim.trace[-1]["result"],
            "pass": shim.trace[-1]["result"] == "CL_INVALID_ARG_INDEX",
        }
    )

    try:
        shim.clCreateBuffer(context, "zero", 0, "read_write")
    except ValueError:
        pass
    cases.append(
        {
            "name": "reject_zero_size_buffer",
            "api": "clCreateBuffer",
            "expected_error": "CL_INVALID_VALUE",
            "observed_error": shim.trace[-1]["result"],
            "pass": shim.trace[-1]["result"] == "CL_INVALID_VALUE",
        }
    )

    return cases


def build_report() -> dict[str, Any]:
    lifecycle = run_lifecycle()
    shim: HostShim = lifecycle["shim"]
    negatives = run_negative_tests()
    api_names = [item["api"] for item in shim.trace]
    required_apis = {
        "clGetPlatformIDs",
        "clGetDeviceIDs",
        "clGetDeviceInfo",
        "clCreateContext",
        "clCreateCommandQueueWithProperties",
        "clCreateBuffer",
        "clEnqueueWriteBuffer",
        "clCreateProgramWithSource",
        "clBuildProgram",
        "clCreateKernel",
        "clSetKernelArg",
        "clEnqueueNDRangeKernel",
        "clEnqueueReadBuffer",
        "clWaitForEvents",
        "clFinish",
    }
    live = shim.live_handles()
    runtime_summary = lifecycle["runtime_proxy_summary"]
    checks = [
        {"name": "required_host_api_lifecycle_executed", "pass": required_apis <= set(api_names), "observed": sorted(set(api_names))},
        {"name": "runtime_proxy_dispatch_pass", "pass": runtime_summary.get("status") == "pass", "runtime_summary": runtime_summary},
        {"name": "runtime_proxy_completed_dispatch", "pass": int(runtime_summary.get("commands_completed", -1)) == 1, "runtime_summary": runtime_summary},
        {"name": "runtime_proxy_no_failures", "pass": int(runtime_summary.get("commands_failed", -1)) == 0, "runtime_summary": runtime_summary},
        {"name": "runtime_proxy_pending_zero", "pass": int(runtime_summary.get("pending_count", -1)) == 0, "runtime_summary": runtime_summary},
        {"name": "handles_released", "pass": live == {}, "live_handles": live},
        {"name": "negative_error_code_tests_pass", "pass": all(item["pass"] for item in negatives), "negative_count": len(negatives)},
        {
            "name": "no_official_conformance_overclaim",
            "pass": "not official OpenCL conformance" in CLEAN_ROOM_SCOPE and "not CTS pass" in CLEAN_ROOM_SCOPE,
            "scope": CLEAN_ROOM_SCOPE,
        },
    ]
    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "status": "pass" if all(item["pass"] for item in checks) else "fail",
        "api_call_count": len(shim.trace),
        "api_call_trace": shim.trace,
        "event_trace": shim.events,
        "handle_lifecycle": {"live_after_release": live},
        "kernel_abi_summary": {
            "name": lifecycle["abi"].get("name"),
            "schema": lifecycle["abi"].get("schema"),
            "arg_count": len(lifecycle["abi"].get("args", [])),
            "work_items": lifecycle["abi"].get("work_items"),
        },
        "runtime_proxy_summary": runtime_summary,
        "negative_tests": negatives,
        "error_codes": ERROR_CODES,
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Celviz OpenCL host API shim lifecycle tests.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    args = parser.parse_args()
    report = build_report()
    write_json(args.output, report)
    write_doc(args.doc, report)
    passed = sum(1 for check in report["checks"] if check["pass"])
    total = len(report["checks"])
    print(f"celviz_gpgpu_opencl_host_api_shim: {report['status']} checks={passed}/{total} calls={report['api_call_count']} output={args.output}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
