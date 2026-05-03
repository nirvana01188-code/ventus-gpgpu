#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

artifact_root="artifacts/rank_01_vivante_3d_gpgpu_ip"
output="artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_product_gap_closure.json"
doc="docs/celviz-gpgpu-ip/OPENCL_PRODUCT_GAP_CLOSURE.md"
verify_only=0

usage() {
  cat <<'EOF'
usage: scripts/verify_celviz_gpgpu_opencl_product_gap_closure.sh [--artifact-root DIR] [--output FILE] [--doc FILE] [--verify-only]

Generates and verifies the OpenCL product gap-closure ledger. The ledger
classifies current evidence into executable subset done, partial, and blocked
items. It must not claim official OpenCL conformance, Khronos CTS pass,
Khronos ICD loader integration, libOpenCL ABI completion, or a production
kernel driver.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --artifact-root)
      artifact_root="$2"
      shift 2
      ;;
    --output)
      output="$2"
      shift 2
      ;;
    --doc)
      doc="$2"
      shift 2
      ;;
    --verify-only)
      verify_only=1
      shift
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

args=(--artifact-root "$artifact_root" --output "$output" --doc "$doc")
if [[ "$verify_only" -eq 1 ]]; then
  args+=(--verify-only)
fi

python3 tools/celviz_gpgpu_ip/opencl_product_gap_closure.py "${args[@]}"

python3 - "$output" "$doc" <<'PY'
import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
doc_path = Path(sys.argv[2])
data = json.loads(report_path.read_text(encoding="utf-8"))
doc = doc_path.read_text(encoding="utf-8")
errors = []

def require(condition, message):
    if not condition:
        errors.append(message)

require(data.get("schema") == "celviz.gpgpu.opencl_product_gap_closure.v1", "schema mismatch")
require(data.get("status") == "pass", "status is not pass")
ledger = data.get("ledger", [])
require(len(ledger) >= 13, "expected at least thirteen ledger items")
by_id = {item.get("id"): item for item in ledger}
required_blocked = {
    "icd_loader",
    "libopencl_abi",
    "kernel_driver",
    "khronos_cts",
    "images",
    "samplers",
    "svm",
    "atomics",
    "out_of_order_queues",
}
for gap_id in required_blocked:
    require(gap_id in by_id, f"missing required blocked item: {gap_id}")
    require(by_id.get(gap_id, {}).get("classification") == "blocked", f"{gap_id} is not blocked")

require(any(item.get("classification") == "done" for item in ledger), "no executable subset done items")
require(any(item.get("classification") == "partial" for item in ledger), "no partial items")
require(by_id.get("event_waitlist_and_profiling_proxy", {}).get("classification") == "partial", "event wait-list proxy not partial")

summary = data.get("summary", {})
for key in (
    "official_opencl_conformance",
    "khronos_cts_pass",
    "product_icd_loader",
    "libopencl_abi",
    "production_kernel_driver",
):
    require(summary.get(key) is False, f"overclaim summary flag is not false: {key}")

scope = data.get("clean_room_scope", "")
for token in (
    "not an official OpenCL conformance claim",
    "not Khronos CTS pass evidence",
    "not a Khronos ICD loader integration",
    "not a libOpenCL ABI implementation",
    "not a production Linux kernel/DRM driver",
):
    require(token in scope, f"scope token missing: {token}")
    require(token in doc, f"doc scope token missing: {token}")

for section in ("Executable Subset Done", "Partial", "Blocked"):
    require(section in doc, f"doc missing section: {section}")
for token in ("ICD loader", "libOpenCL ABI", "Production Linux kernel/DRM driver", "Khronos CTS", "Images", "Samplers", "Shared Virtual Memory", "Atomics", "Out-of-order queues"):
    require(token in doc, f"doc missing gap token: {token}")

for item in ledger:
    require(item.get("evidence"), f"missing evidence list for {item.get('id')}")
    require(item.get("next_executable_step"), f"missing next executable step for {item.get('id')}")
    require("not official OpenCL conformance" in item.get("claim_boundary", ""), f"missing per-item boundary for {item.get('id')}")

if errors:
    for error in errors:
        print(f"[FAIL] {error}", file=sys.stderr)
    raise SystemExit(1)

print(f"celviz_gpgpu_opencl_product_gap_closure_verify: pass items={len(ledger)} done={summary.get('done')} partial={summary.get('partial')} blocked={summary.get('blocked')}")
PY
