#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

output="artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_cts_smoke_runner.json"
doc="docs/celviz-gpgpu-ip/OPENCL_CTS_SMOKE_RUNNER.md"

PYTHONDONTWRITEBYTECODE=1 python3 tools/celviz_gpgpu_ip/opencl_cts_smoke_runner.py \
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


required_categories = {"device_info", "build_errors", "buffer_flags", "events", "queue", "kernels"}
required_kernel_names = {"vector_add", "gemm", "conv2d", "image_filter"}

require(report.get("schema") == "celviz.gpgpu.opencl_cts_smoke_runner.v1", "schema mismatch")
require(report.get("runner_kind") == "cts_oriented_smoke_manifest", "runner kind mismatch")
require(report.get("khronos_cts_executed") is False, "runner must not claim Khronos CTS execution")
require(report.get("official_cts_pass") is False, "official CTS pass must remain false")
require(report.get("official_opencl_conformance_claimed") is False, "official conformance must not be claimed")
require(report.get("status") == "pass", "smoke manifest status is not pass")

items = report.get("items", [])
require(len(items) == 6, f"expected 6 smoke items, got {len(items)}")
categories = {item.get("category") for item in items}
require(required_categories == categories, f"category mismatch: {sorted(required_categories - categories)}")
require(all(item.get("pass") is True and item.get("fail") is False for item in items), "not every item has pass=true/fail=false")

for item in items:
    evidence = item.get("evidence", [])
    require(evidence, f"{item.get('id')} has no evidence binding")
    require(item.get("gate_binding"), f"{item.get('id')} missing gate binding")
    require(item.get("requirement") in {"device info", "build errors", "buffer flags", "events", "queue", "four kernels"}, f"{item.get('id')} has unexpected requirement")
    require("official CTS pass remains false" in item.get("claim_boundary", ""), f"{item.get('id')} missing CTS boundary")
    for row in evidence:
        require(row.get("pass") is True, f"{item.get('id')} evidence did not pass: {row.get('path')}")
        require(row.get("exists") is True, f"{item.get('id')} evidence missing: {row.get('path')}")

kernel_item = next(item for item in items if item.get("category") == "kernels")
kernels = kernel_item.get("details", {}).get("kernels", [])
kernel_names = {kernel.get("name") for kernel in kernels}
require(kernel_names == required_kernel_names, f"kernel names mismatch: {sorted(required_kernel_names - kernel_names)}")
require(all(kernel.get("pass") is True for kernel in kernels), "not all kernel smoke rows passed")

for token in (
    "OpenCL CTS Smoke Runner",
    "does not run Khronos OpenCL CTS",
    "`official_cts_pass`: `False`",
    "vector_add",
    "gemm",
    "conv2d",
    "image_filter",
):
    require(token in doc, f"doc token missing: {token}")

if errors:
    for error in errors:
        print(f"[FAIL] {error}", file=sys.stderr)
    raise SystemExit(1)

summary = report["summary"]
print(
    "celviz_gpgpu_opencl_cts_smoke_verify: pass "
    f"items={summary['item_count']} kernels={summary['kernel_count']} "
    f"official_cts_pass={summary['official_cts_pass']}"
)
PY
