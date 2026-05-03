#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

output="artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_userspace_samples.json"
doc="docs/celviz-gpgpu-ip/OPENCL_USERSPACE_SAMPLES.md"

PYTHONDONTWRITEBYTECODE=1 python3 tools/celviz_gpgpu_ip/opencl_userspace_samples.py \
  --output "$output" \
  --doc "$doc"

PYTHONDONTWRITEBYTECODE=1 python3 - "$output" "$doc" <<'PY'
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


required_samples = {"vector_add", "gemm", "conv2d", "image_filter"}
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

require(report.get("schema") == "celviz.gpgpu.opencl_userspace_samples.v1", "schema mismatch")
require(report.get("status") == "pass", "status is not pass")
require(report.get("sample_count") == 4, "sample count mismatch")
require({sample.get("name") for sample in report.get("samples", [])} == required_samples, "sample set mismatch")
require(all(check.get("pass") is True for check in report.get("checks", [])), "top-level checks contain failures")

for sample in report.get("samples", []):
    name = sample.get("name")
    require(sample.get("status") == "pass", f"{name}: sample status is not pass")
    require(all(check.get("pass") is True for check in sample.get("checks", [])), f"{name}: sample checks contain failures")
    observed_apis = {item.get("api") for item in sample.get("host_api", {}).get("api_call_trace", [])}
    require(required_apis <= observed_apis, f"{name}: missing host APIs {sorted(required_apis - observed_apis)}")
    require(sample.get("host_api", {}).get("live_handles_after_release") == {}, f"{name}: leaked shim handles")

    buffer_io = sample.get("buffer_io", {})
    require(buffer_io.get("write_count", 0) >= 1, f"{name}: no buffer write path")
    require(buffer_io.get("read_count", 0) >= 1, f"{name}: no buffer read path")

    command_summary = sample.get("runtime_proxy", {}).get("command_summary", {})
    runtime_summary = sample.get("runtime_proxy", {}).get("summary", {})
    require(command_summary.get("write_buffer_count", 0) >= 1, f"{name}: runtime write_buffer missing")
    require(command_summary.get("read_buffer_count", 0) >= 1, f"{name}: runtime read_buffer missing")
    require(command_summary.get("ndrange_count") == 1, f"{name}: NDRange dispatch count mismatch")
    require(runtime_summary.get("commands_completed") == command_summary.get("command_count"), f"{name}: runtime completion mismatch")
    require(runtime_summary.get("commands_failed") == 0, f"{name}: runtime failures observed")

    microop = sample.get("microop_evidence", {})
    require(microop.get("status") == "pass", f"{name}: microop status not pass")
    require(bool(microop.get("result_sha256")), f"{name}: microop result hash missing")
    memory_counts = microop.get("memory_counts", {})
    require(memory_counts.get("load", 0) > 0, f"{name}: microop load trace missing")
    require(memory_counts.get("store", 0) > 0, f"{name}: microop store trace missing")
    require(microop.get("completion_written") is True, f"{name}: microop completion missing")

require(len(report.get("negative_tests", [])) >= 3, "negative path depth too shallow")
require(all(case.get("pass") is True for case in report.get("negative_tests", [])), "negative paths contain failures")
scope = str(report.get("clean_room_scope", ""))
for token in ("not Khronos CTS", "not official OpenCL conformance", "not a Khronos ICD", "not libOpenCL"):
    require(token in scope, f"scope token missing: {token}")
for key, expected in {
    "official_opencl_conformance": False,
    "khronos_cts": False,
    "khronos_icd": False,
    "libopencl": False,
}.items():
    require(report.get("conformance_boundary", {}).get(key) is expected, f"boundary mismatch: {key}")
for token in ("OpenCL Userspace Samples", "Boundary", "vector_add", "gemm", "conv2d", "image_filter", "not official OpenCL conformance", "not Khronos CTS"):
    require(token in doc, f"doc token missing: {token}")

if errors:
    for error in errors:
        print(f"[FAIL] {error}", file=sys.stderr)
    raise SystemExit(1)

print(
    "celviz_gpgpu_opencl_userspace_samples_verify: pass "
    f"samples={report.get('sample_count')} negative={len(report.get('negative_tests', []))} "
    f"commands={sum(sample.get('runtime_proxy', {}).get('command_summary', {}).get('command_count', 0) for sample in report.get('samples', []))}"
)
PY
