#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

cc_bin="${CC:-cc}"
build_dir="${TMPDIR:-/tmp}/celviz_opencl_c_abi_smoke.$$"
report="artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_c_abi_smoke.json"

cleanup() {
  rm -rf "$build_dir"
}
trap cleanup EXIT

mkdir -p "$build_dir" "$(dirname "$report")"

"$cc_bin" -std=c99 -Wall -Wextra -Werror -pedantic -Iruntime/opencl \
  -c runtime/opencl/celviz_opencl.c -o "$build_dir/celviz_opencl.o"
"$cc_bin" -std=c99 -Wall -Wextra -Werror -pedantic -Iruntime/opencl \
  -c runtime/opencl/vector_add_smoke.c -o "$build_dir/vector_add_smoke.o"
"$cc_bin" "$build_dir/celviz_opencl.o" "$build_dir/vector_add_smoke.o" -lm \
  -o "$build_dir/vector_add_smoke"

smoke_output="$("$build_dir/vector_add_smoke")"

required_symbols=(
  clGetPlatformIDs
  clGetDeviceIDs
  clCreateContext
  clCreateCommandQueueWithProperties
  clCreateBuffer
  clCreateProgramWithSource
  clBuildProgram
  clCreateKernel
  clSetKernelArg
  clEnqueueWriteBuffer
  clEnqueueNDRangeKernel
  clEnqueueReadBuffer
  clFinish
  clReleaseMemObject
  clReleaseKernel
  clReleaseProgram
  clReleaseCommandQueue
  clReleaseContext
  clReleaseEvent
)

nm_output="$(nm -g "$build_dir/celviz_opencl.o")"
for sym in "${required_symbols[@]}"; do
  if ! grep -Eq "[[:space:]]T[[:space:]]_$sym$|[[:space:]]T[[:space:]]$sym$" <<<"$nm_output"; then
    echo "[FAIL] missing exported symbol: $sym" >&2
    exit 1
  fi
done

if ! grep -q "vector_add_smoke: pass" <<<"$smoke_output"; then
  echo "[FAIL] smoke did not pass: $smoke_output" >&2
  exit 1
fi

python3 - "$report" "$cc_bin" "$smoke_output" "${required_symbols[@]}" <<'PY'
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

report = Path(sys.argv[1])
cc = sys.argv[2]
smoke_output = sys.argv[3]
symbols = sys.argv[4:]
payload = {
    "schema": "celviz.gpgpu.opencl_c_abi_smoke.v1",
    "status": "pass",
    "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "compiler": cc,
    "host": {
        "system": platform.system(),
        "machine": platform.machine(),
    },
    "scope": (
        "Clean-room userspace OpenCL-like C ABI shim for Celviz GPGPU IP smoke testing only; "
        "not Khronos ICD, not libOpenCL, not Khronos CTS, not official OpenCL conformance, "
        "not a production driver, and not Vivante proprietary compatibility."
    ),
    "artifact_inputs": [
        "runtime/opencl/celviz_opencl.h",
        "runtime/opencl/celviz_opencl.c",
        "runtime/opencl/vector_add_smoke.c",
    ],
    "build": {
        "mode": "local c99 object plus smoke binary",
        "warnings": "compiled with -Wall -Wextra -Werror -pedantic",
    },
    "exported_symbols": symbols,
    "smoke": {
        "name": "vector_add",
        "binary": "temporary local smoke binary",
        "result": "pass",
        "stdout": smoke_output,
        "elements": 256,
    },
    "release_coverage": [
        "clReleaseMemObject",
        "clReleaseKernel",
        "clReleaseProgram",
        "clReleaseCommandQueue",
        "clReleaseContext",
        "clReleaseEvent",
    ],
}
report.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(
    "celviz_gpgpu_opencl_c_abi_verify: pass "
    f"symbols={len(symbols)} smoke=vector_add elements=256"
)
PY
