#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

output="artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_kernel_abi_edges.json"
doc="docs/celviz-gpgpu-ip/OPENCL_KERNEL_ABI_EDGES.md"

PYTHONDONTWRITEBYTECODE=1 python3 tools/celviz_gpgpu_ip/opencl_kernel_abi_edges.py \
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
    "arg size/index/type",
    "global/local size",
    "unsupported address spaces/builtins/double",
    "buffer access mismatch",
}
required_case_tokens = {
    "bad_index": "CL_INVALID_ARG_INDEX",
    "bad_size": "CL_INVALID_ARG_SIZE",
    "pointer_type_mismatch": "CL_INVALID_MEM_OBJECT",
    "access_mismatch": "CL_INVALID_ARG_VALUE",
    "zero_global": "CL_BUILD_PROGRAM_FAILURE",
    "non_divisible": "CL_BUILD_PROGRAM_FAILURE",
    "generic_address": "CL_BUILD_PROGRAM_FAILURE",
    "unsupported_builtin": "CL_BUILD_PROGRAM_FAILURE",
    "double": "CL_BUILD_PROGRAM_FAILURE",
}

require(report.get("schema") == "celviz.gpgpu.opencl_kernel_abi_edges.v1", "schema mismatch")
require(report.get("status") == "pass", "status is not pass")
require(report.get("case_count", 0) >= 14, "case depth is too shallow")
require(all(check.get("pass") is True for check in report.get("checks", [])), "not all checks passed")

categories = set(report.get("category_summary", {}).keys())
require(required_categories.issubset(categories), f"missing categories: {sorted(required_categories - categories)}")
cases = report.get("cases", [])
require(all(case.get("pass") is True for case in cases), "cases contain a failure")
require(
    any("opencl_subset" in str(case.get("capability")) for case in cases),
    "opencl_subset capability not used",
)
require(
    any("opencl_build_error_code_matrix" in str(case.get("capability")) for case in cases),
    "opencl_build_error_code_matrix capability not used",
)
for name_token, expected_status in required_case_tokens.items():
    require(
        any(name_token in str(case.get("name")) and case.get("observed_status") == expected_status for case in cases),
        f"missing case/status for {name_token} -> {expected_status}",
    )

scope = str(report.get("clean_room_scope", ""))
require("not official OpenCL conformance" in scope, "official conformance boundary missing")
require("not Khronos CTS" in scope, "CTS boundary missing")
for token in (
    "OpenCL Kernel ABI Negative/Edge Runner",
    "arg size/index/type",
    "global/local",
    "unsupported address spaces",
    "unsupported builtins",
    "double precision",
    "buffer access mismatch",
    "not Khronos CTS",
):
    require(token in doc, f"doc token missing: {token}")

if errors:
    for error in errors:
        print(f"[FAIL] {error}", file=sys.stderr)
    raise SystemExit(1)

print(
    "celviz_gpgpu_opencl_kernel_abi_edges_verify: pass "
    f"cases={report.get('case_count')} categories={len(categories)}"
)
PY
