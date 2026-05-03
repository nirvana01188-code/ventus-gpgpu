#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

output="artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_rtl_cts_cross_check.json"
doc="docs/celviz-gpgpu-ip/OPENCL_RTL_CTS_CROSS_CHECK.md"

PYTHONDONTWRITEBYTECODE=1 python3 tools/celviz_gpgpu_ip/opencl_rtl_cts_cross_check.py \
  --output "$output" \
  --doc-output "$doc" \
  --print-summary

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

require(report.get("schema") == "celviz.gpgpu.opencl_rtl_cts_cross_check.v1", "schema mismatch")
require(report.get("status") == "pass", "status is not pass")
require(report.get("cts_ready") is False, "cts_ready must remain false")
require(report.get("structural_coverage_closed") is False, "structural_coverage_closed must remain false")
boundaries = report.get("claim_boundaries", {})
for key in (
    "khronos_cts_pass",
    "official_opencl_conformance",
    "product_icd",
    "rtl_structural_coverage_100",
    "silicon_signoff",
):
    require(boundaries.get(key) is False, f"claim boundary not false: {key}")

checks = report.get("checks", [])
require(checks and all(item.get("pass") is True for item in checks), "not all checks passed")
mappings = {item.get("path_id"): item for item in report.get("path_mappings", [])}
for key in (
    "host_dispatch_to_kernel_dispatch",
    "host_events_to_interrupt_fence_paths",
    "host_buffers_to_dma_and_axi_paths",
    "host_negative_api_to_fault_bins",
):
    require(mappings.get(key, {}).get("pass") is True, f"mapping did not pass: {key}")

structural = report.get("observed", {}).get("structural_metrics", {})
require(structural.get("status") == "reported_separately_not_a_closure_claim", "structural metrics boundary missing")
for token in (
    "OpenCL RTL/CTS Readiness Cross-Check",
    "Path Mappings",
    "Structural Metrics",
    "Claim Boundaries",
    "not a structural coverage closure",
):
    require(token in doc, f"doc token missing: {token}")

if errors:
    for error in errors:
        print(f"[FAIL] {error}", file=sys.stderr)
    raise SystemExit(1)

print(
    "celviz_gpgpu_opencl_rtl_cts_cross_check_verify: pass "
    f"checks={len(checks)} mappings={len(mappings)}"
)
PY
