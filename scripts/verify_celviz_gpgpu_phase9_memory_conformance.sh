#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

report="artifacts/rank_01_vivante_3d_gpgpu_ip/verification/phase9_memory_conformance_readiness_gate.json"
completion="artifacts/rank_01_vivante_3d_gpgpu_ip/verification/phase9_memory_conformance_completion_columns.json"
doc="docs/celviz-gpgpu-ip/PHASE9_MEMORY_CONFORMANCE_GATES.md"
log="artifacts/rank_01_vivante_3d_gpgpu_ip/verification/phase9_memory_conformance_gate.log"

python3 tools/celviz_gpgpu_ip/phase9_memory_conformance_gate.py \
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


required_surfaces = {
    "global",
    "local",
    "constant",
    "private",
    "image",
    "sampler",
    "atomics",
    "coalescing",
    "cache",
    "scratchpad",
    "DMA",
}
require(report.get("schema") == "celviz.gpgpu.phase9_memory_conformance_gate.v1", "report schema mismatch")
require(completion.get("schema") == "celviz.gpgpu.phase9_memory_completion_columns.v1", "completion schema mismatch")
require(report.get("status") == "pass", "report status is not pass")
require(completion.get("status") == "pass", "completion status is not pass")
surfaces = report.get("surfaces", [])
surface_names = {row.get("surface") for row in surfaces}
require(surface_names == required_surfaces, f"surface set mismatch: {sorted(surface_names)}")
require(len(completion.get("rows", [])) == len(surfaces), "completion rows do not match report surfaces")
for column in (
    "surface",
    "readiness",
    "completion",
    "unified_access_model",
    "current_evidence",
    "productization_gate",
    "blockers",
    "next_actions",
):
    require(column in completion.get("columns", []), f"missing completion column: {column}")

summary = report.get("completion_summary", {})
require(summary.get("official_conformance_claim") is False, "official conformance claim must be false")
require(int(summary.get("complete_for_proxy_gate", 0)) >= 7, "too few proxy-complete surfaces")
require({"private", "sampler", "atomics"}.issubset(set(summary.get("gap_or_partial_surfaces", []))), "required gap surfaces not listed")
for row in surfaces:
    if row.get("completion") != "complete_for_proxy_gate":
        require(row.get("readiness") != "ready_proxy", f"gap row claims ready_proxy: {row.get('surface')}")
        require(row.get("blockers"), f"gap row missing blockers: {row.get('surface')}")
    require(row.get("unified_access_model"), f"missing unified model: {row.get('surface')}")
    require(row.get("productization_gate"), f"missing productization gate: {row.get('surface')}")

for check in report.get("checks", []):
    require(check.get("pass") is True, f"check failed: {check.get('name')}")

for token in (
    "Phase 9 Memory Conformance Gates",
    "global",
    "local",
    "constant",
    "private",
    "image",
    "sampler",
    "atomics",
    "coalescing",
    "cache",
    "scratchpad",
    "DMA",
    "Official conformance claim: `false`",
):
    require(token in doc, f"doc token missing: {token}")

if errors:
    for error in errors:
        print(f"[FAIL] {error}", file=sys.stderr)
    raise SystemExit(1)

print(
    "celviz_gpgpu_phase9_memory_conformance_verify: pass "
    f"surfaces={summary.get('surface_count')} "
    f"complete={summary.get('complete_for_proxy_gate')} "
    f"gaps={summary.get('gap_or_partial')} "
    f"ready={','.join(summary.get('ready_proxy_surfaces', []))} "
    f"gap_surfaces={','.join(summary.get('gap_or_partial_surfaces', []))}"
)
PY
