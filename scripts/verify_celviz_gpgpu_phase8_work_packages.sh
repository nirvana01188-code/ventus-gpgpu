#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

output_dir="artifacts/rank_01_vivante_3d_gpgpu_ip/verification/phase8_work_package_artifacts"

usage() {
  cat <<'EOF'
usage: scripts/verify_celviz_gpgpu_phase8_work_packages.sh [--output-dir DIR]

Generates concrete Phase-8 work-package artifacts: OpenCL subset negative
tests, DRM-like UAPI contract, RTL structural coverage uplift plan, signoff
input requirements, Phase7 overclaim scan, and Vivante clean-room boundary
checklist. This does not claim completion of the external/signoff items.
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

python3 tools/celviz_gpgpu_ip/phase8_work_package_artifacts.py --output-dir "$output_dir"

python3 - "$output_dir/phase8_work_package_artifacts_report.json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
errors = []

def require(condition, message):
    if not condition:
        errors.append(message)

require(data.get("schema") == "celviz.gpgpu.phase8_work_package_artifacts.v1", "schema mismatch")
require(data.get("status") == "pass", "status is not pass")
paths = data.get("artifact_paths", {})
expected = {
    "opencl_negative_tests",
    "drm_uapi_contract",
    "structural_coverage_uplift_plan",
    "signoff_requirements",
    "phase7_overclaim_scan",
    "vivante_clean_room_boundary_checklist",
}
require(set(paths) == expected, f"artifact path keys mismatch: {sorted(paths)}")
for name, raw_path in paths.items():
    artifact = Path(raw_path)
    require(artifact.exists() and artifact.stat().st_size > 0, f"missing artifact: {name}")
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    require(payload.get("status") == "pass", f"artifact did not pass: {name}")
    require(payload.get("claim_boundary"), f"artifact claim boundary missing: {name}")
scope = data.get("clean_room_scope", "")
for token in (
    "not proprietary Vivante compatibility",
    "not official OpenCL conformance",
    "not production Linux kernel/DRM driver readiness",
    "not RTL structural coverage closure",
    "not synthesis/STA/power/DFT/physical/silicon signoff",
    "not silicon performance evidence",
):
    require(token in scope, f"scope token missing: {token}")

if errors:
    for error in errors:
        print(f"[FAIL] {error}", file=sys.stderr)
    raise SystemExit(1)

print(f"celviz_gpgpu_phase8_work_package_artifacts_verify: pass artifacts={len(paths)}")
PY
