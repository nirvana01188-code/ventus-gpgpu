#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

output="artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_event_waitlist_profiling_report.json"

usage() {
  cat <<'EOF'
usage: scripts/verify_celviz_gpgpu_opencl_event_waitlist_profiling.sh [--output FILE]

Runs the clean-room OpenCL event wait-list/profiling proxy gate. This validates
event dependency DAGs, queued/submit/start/end profiling timestamps, wait-list
rejection cases, and failure propagation. It is not a Khronos ICD or official
OpenCL conformance claim.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output)
      output="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

python3 tools/celviz_gpgpu_ip/opencl_event_waitlist_profiling_gate.py --output "$output"

python3 - "$output" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
report = json.loads(path.read_text(encoding="utf-8"))
errors = []

def require(condition, message):
    if not condition:
        errors.append(message)

require(report.get("schema") == "celviz.gpgpu.opencl_event_waitlist_profiling_gate.v1", "schema mismatch")
require(report.get("status") == "pass", "status is not pass")
metrics = report.get("metrics", {})
require(metrics.get("events") == 7, f"expected 7 modeled events, got {metrics.get('events')}")
require(metrics.get("edges", 0) >= 6, "expected at least six wait-list DAG edges")
require(metrics.get("completed_events") == 5, "expected five completed events")
require(metrics.get("failed_events") == 2, "expected two failed events")
require(metrics.get("validation_rejections") == 3, "expected three wait-list validation rejections")
require(metrics.get("profiling_records") == metrics.get("events"), "profiling record count mismatch")

for check in report.get("checks", []):
    require(check.get("pass") is True, f"check failed: {check.get('name')}")

dag = report.get("event_dag", {})
nodes = {node.get("handle"): node for node in dag.get("nodes", [])}
for node in nodes.values():
    profiling = node.get("profiling", {})
    require(
        profiling.get("queued") <= profiling.get("submit") <= profiling.get("start") <= profiling.get("end"),
        f"non-monotonic profiling timestamps for {node.get('handle')}",
    )
for edge in dag.get("edges", []):
    src = nodes[edge.get("from")]
    dst = nodes[edge.get("to")]
    if src.get("status") == 0:
        require(
            src["profiling"]["end"] <= dst["profiling"]["submit"],
            f"dependency timing violation {edge}",
        )

boundary = report.get("claim_boundary", {})
require(boundary.get("official_opencl_icd") is False, "official ICD boundary not false")
require(boundary.get("khronos_conformance") is False, "conformance boundary not false")
require(boundary.get("cts_evidence") is False, "CTS boundary not false")

if errors:
    for error in errors:
        print(f"[FAIL] {error}", file=sys.stderr)
    raise SystemExit(1)

print(
    "celviz_gpgpu_opencl_event_waitlist_profiling_verify: pass "
    f"events={metrics.get('events')} edges={metrics.get('edges')} "
    f"completed={metrics.get('completed_events')} failed={metrics.get('failed_events')} "
    f"validation_rejections={metrics.get('validation_rejections')}"
)
PY
