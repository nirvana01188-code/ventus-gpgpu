#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

output_dir="artifacts/rank_01_vivante_3d_gpgpu_ip/verification"

usage() {
  cat <<'EOF'
usage: scripts/verify_celviz_gpgpu_phase8_claim_closure.sh [--output-dir DIR]

Generates and verifies Phase-8 closure evidence for known non-complete claim
boundaries. This advances readiness and executable work packages; it does not
claim proprietary Vivante compatibility, official OpenCL conformance,
production Linux DRM driver readiness, RTL structural coverage closure,
synthesis/STA/power/DFT/physical/silicon signoff, or silicon performance.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-dir)
      output_dir="$2"
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

python3 tools/celviz_gpgpu_ip/phase8_claim_closure.py --output-dir "$output_dir"

python3 - "$output_dir/phase8_claim_closure_report.json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
errors = []

def require(condition, message):
    if not condition:
        errors.append(message)

require(data.get("schema") == "celviz.gpgpu.phase8_claim_closure.v1", "schema mismatch")
require(data.get("status") == "pass", "status is not pass")
lanes = data.get("lanes", [])
require(len(lanes) == 6, "expected six closure lanes")
expected = {
    "vivante_proprietary_compatibility",
    "official_opencl_conformance",
    "production_linux_kernel_drm_driver",
    "rtl_structural_coverage_100",
    "signoff_synthesis_sta_power_dft_physical_silicon",
    "phase7_proxy_not_silicon_performance",
}
ids = {lane.get("id") for lane in lanes}
require(ids == expected, f"lane ids mismatch: {sorted(ids)}")
for lane in lanes:
    require(lane.get("claim_status") == "not_completed", f"lane completion overclaim: {lane.get('id')}")
    require(lane.get("status") == "pass", f"lane failed: {lane.get('id')}")
    require(lane.get("blockers"), f"lane blockers missing: {lane.get('id')}")
    require(lane.get("next_executable_steps"), f"lane next steps missing: {lane.get('id')}")
work_packages = data.get("work_packages", [])
require(len(work_packages) >= 6, "work packages missing")
scope = data.get("clean_room_scope", "")
for token in (
    "not proprietary Vivante compatibility",
    "not official OpenCL conformance",
    "not a production Linux DRM driver",
    "not RTL structural coverage closure",
    "not synthesis/STA/power/DFT/physical/silicon signoff",
    "not silicon performance evidence",
):
    require(token in scope, f"scope token missing: {token}")

if errors:
    for error in errors:
        print(f"[FAIL] {error}", file=sys.stderr)
    raise SystemExit(1)

print(f"celviz_gpgpu_phase8_claim_closure_verify: pass lanes={len(lanes)} work_packages={len(work_packages)}")
PY
