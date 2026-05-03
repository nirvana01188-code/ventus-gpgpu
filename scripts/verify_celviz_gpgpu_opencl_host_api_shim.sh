#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

output="artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_host_api_shim_report.json"
doc="docs/celviz-gpgpu-ip/OPENCL_HOST_API_SHIM.md"

python3 tools/celviz_gpgpu_ip/opencl_host_api_shim.py --output "$output" --doc "$doc"

python3 - "$output" "$doc" <<'PY'
import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
doc_path = Path(sys.argv[2])
report = json.loads(report_path.read_text(encoding="utf-8"))
doc = doc_path.read_text(encoding="utf-8")
errors = []

def require(condition, message):
    if not condition:
        errors.append(message)

require(report.get("schema") == "celviz.gpgpu.opencl_host_api_shim.v1", "schema mismatch")
require(report.get("status") == "pass", "status is not pass")
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
observed = {item.get("api") for item in report.get("api_call_trace", [])}
require(required_apis <= observed, f"missing host APIs: {sorted(required_apis - observed)}")
summary = report.get("runtime_proxy_summary", {})
require(summary.get("status") == "pass", "runtime proxy did not pass")
require(int(summary.get("commands_completed", -1)) == 1, "runtime dispatch completion count mismatch")
require(int(summary.get("commands_failed", -1)) == 0, "runtime dispatch had failures")
require(int(summary.get("pending_count", -1)) == 0, "runtime pending count is not zero")
require(report.get("handle_lifecycle", {}).get("live_after_release") == {}, "handles leaked after release")
require(len(report.get("negative_tests", [])) >= 5, "negative tests too shallow")
for case in report.get("negative_tests", []):
    require(case.get("pass") is True, f"negative case failed: {case.get('name')}")
device_info = report.get("device_info_matrix", {})
require(device_info.get("status") == "pass", "device info matrix did not pass")
require(len(device_info.get("supported_queries", [])) >= 16, "device info query depth too shallow")
build_matrix = report.get("build_log_error_matrix", {})
require(build_matrix.get("status") == "pass", "build log error matrix did not pass")
require(len(build_matrix.get("cases", [])) >= 3, "build log error matrix too shallow")
event_matrix = report.get("event_profiling_matrix", {})
require(event_matrix.get("status") == "pass", "event profiling matrix did not pass")
require(len(event_matrix.get("events", [])) >= 4, "event profiling events too shallow")
for event in event_matrix.get("events", []):
    profile = event.get("profiling", {})
    require(
        int(profile.get("queued", -1)) <= int(profile.get("submit", -1)) <= int(profile.get("start", -1)) <= int(profile.get("end", -1)),
        f"event profile not monotonic: {event.get('event')}",
    )
scope = report.get("clean_room_scope", "")
scope_lower = scope.lower()
for token in ("not a Khronos ICD", "not official OpenCL conformance", "not CTS pass evidence"):
    require(token.lower() in scope_lower, f"scope token missing: {token}")
for token in ("OpenCL Host API Shim", "Runtime Evidence", "Negative Error-Code Tests", "Device Info Matrix", "Build Log / Error Matrix", "Event Profiling Matrix"):
    require(token in doc, f"doc token missing: {token}")

if errors:
    for error in errors:
        print(f"[FAIL] {error}", file=sys.stderr)
    raise SystemExit(1)

print(
    "celviz_gpgpu_opencl_host_api_shim_verify: pass "
    f"calls={report.get('api_call_count')} negative={len(report.get('negative_tests', []))} "
    f"device_info={len(device_info.get('supported_queries', []))} "
    f"events={len(event_matrix.get('events', []))} "
    f"completed={summary.get('commands_completed')}"
)
PY
