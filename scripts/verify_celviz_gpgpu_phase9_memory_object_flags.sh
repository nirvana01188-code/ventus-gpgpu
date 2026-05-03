#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

report="artifacts/rank_01_vivante_3d_gpgpu_ip/verification/phase9_memory_object_flags_map_gate.json"
completion="artifacts/rank_01_vivante_3d_gpgpu_ip/verification/phase9_memory_object_flags_completion_columns.json"
doc="docs/celviz-gpgpu-ip/PHASE9_MEMORY_OBJECT_FLAGS_GATES.md"
log="artifacts/rank_01_vivante_3d_gpgpu_ip/verification/phase9_memory_object_flags_gate.log"

python3 tools/celviz_gpgpu_ip/phase9_memory_object_flags_gate.py \
  --report "$report" \
  --completion "$completion" \
  --doc "$doc" \
  --log "$log"

python3 - "$report" "$completion" "$doc" <<'PY'
import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
completion_path = Path(sys.argv[2])
doc_path = Path(sys.argv[3])
report = json.loads(report_path.read_text(encoding="utf-8"))
completion = json.loads(completion_path.read_text(encoding="utf-8"))
doc = doc_path.read_text(encoding="utf-8")
errors = []


def require(condition, message):
    if not condition:
        errors.append(message)


required_flags = {
    "CL_MEM_READ_WRITE",
    "CL_MEM_READ_ONLY",
    "CL_MEM_WRITE_ONLY",
    "CL_MEM_COPY_HOST_PTR",
    "CL_MEM_USE_HOST_PTR",
}
required_ops = {"map/unmap", "sub-buffer", "bounds negative tests"}

require(report.get("schema") == "celviz.gpgpu.phase9_memory_object_flags_gate.v1", "report schema mismatch")
require(completion.get("schema") == "celviz.gpgpu.phase9_memory_object_completion_columns.v1", "completion schema mismatch")
require(report.get("status") == "pass", "report status is not pass")
require(completion.get("status") == "pass", "completion status is not pass")
require(report.get("summary", {}).get("official_conformance_claim") is False, "report overclaims conformance")
require(completion.get("summary", {}).get("official_conformance_claim") is False, "completion overclaims conformance")

flags = {row.get("flag") for row in report.get("flag_gates", [])}
ops = {row.get("operation") for row in report.get("operation_gates", [])}
require(flags == required_flags, f"flag set mismatch: {sorted(flags)}")
require(ops == required_ops, f"operation gate mismatch: {sorted(ops)}")
for row in report.get("flag_gates", []):
    require(row.get("completion") == "complete_for_proxy_gate", f"flag not complete: {row.get('flag')}")
    require(row.get("covered_by"), f"flag lacks coverage event ids: {row.get('flag')}")
for row in report.get("operation_gates", []):
    require(row.get("completion") == "complete_for_proxy_gate", f"operation not complete: {row.get('operation')}")
    require(row.get("covered_by"), f"operation lacks coverage event ids: {row.get('operation')}")

rows = completion.get("rows", [])
require(len(rows) == len(required_flags) + len(required_ops), "completion row count mismatch")
for column in ("kind", "name", "readiness", "completion", "covered_by", "blockers", "next_actions"):
    require(column in completion.get("columns", []), f"missing completion column: {column}")

negative_events = [
    event for event in report.get("events", [])
    if event.get("status") == "expected_error"
]
require(len(negative_events) >= 8, "too few negative cases")
for scenario in (
    "negative_read_write_missing_access_flag",
    "negative_copy_and_use_host_ptr",
    "negative_copy_host_ptr_missing_ptr",
    "negative_read_only_kernel_write",
    "negative_write_only_kernel_read",
    "negative_map_bounds",
    "negative_unmap_unknown",
    "negative_sub_buffer_bounds",
    "negative_sub_buffer_broaden_flags",
):
    require(any(event.get("scenario") == scenario and event.get("passed") is True for event in negative_events), f"missing negative scenario: {scenario}")

for check in report.get("checks", []):
    require(check.get("pass") is True, f"check failed: {check.get('name')}")

for token in (
    "Phase 9 Memory Object Flags Gates",
    "CL_MEM_READ_WRITE",
    "CL_MEM_READ_ONLY",
    "CL_MEM_WRITE_ONLY",
    "CL_MEM_COPY_HOST_PTR",
    "CL_MEM_USE_HOST_PTR",
    "map/unmap",
    "sub-buffer",
    "bounds negative tests",
    "Official conformance claim: `false`",
):
    require(token in doc, f"doc token missing: {token}")

if errors:
    for error in errors:
        print(f"[FAIL] {error}", file=sys.stderr)
    raise SystemExit(1)

summary = report.get("summary", {})
print(
    "celviz_gpgpu_phase9_memory_object_flags_verify: pass "
    f"flags={summary.get('flag_count')} "
    f"ops={summary.get('operation_gate_count')} "
    f"negatives={summary.get('negative_case_count')} "
    f"events={summary.get('event_count')}"
)
PY
