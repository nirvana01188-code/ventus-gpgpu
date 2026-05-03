#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

output="artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_build_error_code_matrix.json"
doc="docs/celviz-gpgpu-ip/OPENCL_BUILD_ERROR_CODE_MATRIX.md"

PYTHONDONTWRITEBYTECODE=1 python3 tools/celviz_gpgpu_ip/opencl_build_error_code_matrix.py \
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


required_categories = {
    "clBuildProgram",
    "clCreateKernel",
    "clSetKernelArg",
    "NDRange geometry",
    "buffer errors",
}
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

require(report.get("schema") == "celviz.gpgpu.opencl_build_error_code_matrix.v1", "schema mismatch")
require(report.get("status") == "pass", "status is not pass")
require(report.get("case_count", 0) >= 22, "case depth is too shallow")
require(all(check.get("pass") is True for check in report.get("checks", [])), "not all checks passed")

categories = set(report.get("category_summary", {}).keys())
require(required_categories.issubset(categories), f"missing categories: {sorted(required_categories - categories)}")
observed_errors = {case.get("expected_error") for case in report.get("matrix", [])}
require(required_errors.issubset(observed_errors), f"missing errors: {sorted(required_errors - observed_errors)}")
require(
    all(case.get("expected_error") == case.get("observed_error") and case.get("pass") is True for case in report.get("matrix", [])),
    "matrix contains failing case",
)

scope = str(report.get("clean_room_scope", ""))
require("not official OpenCL conformance" in scope, "official conformance boundary missing")
require("not Khronos CTS" in scope, "CTS boundary missing")
for token in (
    "OpenCL Build Log And Error Code Matrix",
    "clBuildProgram",
    "clCreateKernel",
    "clSetKernelArg",
    "NDRange geometry",
    "not official OpenCL conformance",
):
    require(token in doc, f"doc token missing: {token}")

if errors:
    for error in errors:
        print(f"[FAIL] {error}", file=sys.stderr)
    raise SystemExit(1)

print(
    "celviz_gpgpu_opencl_build_error_code_matrix_verify: pass "
    f"cases={report.get('case_count')} categories={len(categories)} "
    f"errors={len(observed_errors)}"
)
PY
