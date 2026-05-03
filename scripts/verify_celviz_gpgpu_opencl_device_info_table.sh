#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

output="artifacts/rank_01_vivante_3d_gpgpu_ip/opencl_conformance/opencl_device_info_table.json"
doc="docs/celviz-gpgpu-ip/PHASE9_OPENCL_DEVICE_INFO_TABLE.md"

python3 tools/celviz_gpgpu_ip/opencl_device_info_table.py --output "$output" --doc "$doc"

python3 - "$output" "$doc" <<'PY'
import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
doc_path = Path(sys.argv[2])
report = json.loads(report_path.read_text(encoding="utf-8"))
doc = doc_path.read_text(encoding="utf-8")
if report.get("schema") != "celviz.gpgpu.opencl_device_info_table.v1":
    raise SystemExit(f"bad schema: {report.get('schema')}")
if report.get("status") != "pass":
    raise SystemExit(f"report status is {report.get('status')}")
queries = report.get("queries", [])
names = {row.get("name") for row in queries}
required = {
    "CL_DEVICE_PROFILE",
    "CL_DEVICE_VERSION",
    "CL_DEVICE_EXTENSIONS",
    "CL_DEVICE_MAX_COMPUTE_UNITS",
    "CL_DEVICE_GLOBAL_MEM_SIZE",
    "CL_DEVICE_IMAGE_SUPPORT",
    "CL_DEVICE_ATOMIC_MEMORY_CAPABILITIES",
    "CL_DEVICE_SVM_CAPABILITIES",
}
missing = sorted(required - names)
if missing:
    raise SystemExit(f"missing required CL_DEVICE rows: {missing}")
if len(queries) < 50:
    raise SystemExit(f"too few CL_DEVICE rows: {len(queries)}")
bad = [row for row in queries if "not official OpenCL conformance" not in row.get("claim_boundary", "")]
if bad:
    raise SystemExit(f"rows missing overclaim boundary: {[row.get('name') for row in bad[:5]]}")
if "not official OpenCL conformance" not in doc or "CL_DEVICE_SVM_CAPABILITIES" not in doc:
    raise SystemExit("doc missing claim boundary or SVM row")
summary = report["summary"]
print(
    "celviz_gpgpu_opencl_device_info_table_verify: pass "
    f"queries={summary['query_count']} "
    f"categories={len(summary['categories'])} "
    f"statuses={len(summary['support_status'])}"
)
PY
