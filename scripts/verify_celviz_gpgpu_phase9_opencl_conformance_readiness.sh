#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

output_dir="artifacts/rank_01_vivante_3d_gpgpu_ip/verification"

usage() {
  cat <<'EOF'
usage: scripts/verify_celviz_gpgpu_phase9_opencl_conformance_readiness.sh [--output-dir DIR]

Generates and verifies Phase-9 OpenCL conformance-readiness artifacts:
CTS-oriented matrix, OpenCL subset positive/negative tests, ICD/runtime host API
contract, and productization gates. This does not claim Khronos CTS pass,
official OpenCL conformance, production ICD/runtime, production DRM driver,
RTL structural coverage 100%, or signoff completion.
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

python3 tools/celviz_gpgpu_ip/phase9_opencl_conformance_readiness.py --output-dir "$output_dir"

python3 - "$output_dir/phase9_opencl_conformance_readiness_report.json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
errors = []

def require(condition, message):
    if not condition:
        errors.append(message)

require(data.get("schema") == "celviz.gpgpu.phase9_opencl_conformance_readiness.v1", "schema mismatch")
require(data.get("status") == "pass", "status is not pass")
scope = data.get("clean_room_scope", "")
for token in (
    "not Khronos CTS",
    "not official OpenCL conformance",
    "not a product ICD",
    "not a production Linux kernel/DRM driver",
    "not RTL structural coverage 100%",
    "not synthesis/STA/power/DFT/physical/silicon signoff",
):
    require(token in scope, f"scope token missing: {token}")

requirements = data.get("requirements", [])
require(len(requirements) >= 12, "expected at least twelve CTS-oriented requirement categories")
allowed_status = {"absent", "proxy", "partial", "ready"}
for item in requirements:
    require(item.get("current_status") in allowed_status, f"bad status for {item.get('category')}")
    require(item.get("local_evidence"), f"missing evidence for {item.get('category')}")
    require(item.get("blocker_to_official_conformance"), f"missing blocker for {item.get('category')}")
    require(item.get("next_executable_test"), f"missing next test for {item.get('category')}")
    require("not official OpenCL conformance" in item.get("claim_boundary", ""), f"overclaim boundary missing for {item.get('category')}")

paths = data.get("artifact_paths", {})
expected_paths = {
    "opencl_subset_conformance_tests",
    "opencl_icd_runtime_contract",
    "phase9_opencl_readiness_gates",
    "opencl_cts_readiness_matrix",
}
require(set(paths) == expected_paths, f"artifact path keys mismatch: {sorted(paths)}")
for name, raw_path in paths.items():
    artifact = Path(raw_path)
    require(artifact.exists() and artifact.stat().st_size > 0, f"missing artifact: {name}")
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    require(payload.get("status") == "pass", f"artifact did not pass: {name}")

subset = json.loads(Path(paths["opencl_subset_conformance_tests"]).read_text(encoding="utf-8"))
require(subset.get("positive_count", 0) >= 9, "positive subset test depth too shallow")
require(subset.get("negative_count", 0) >= 12, "negative subset test depth too shallow")
icd = json.loads(Path(paths["opencl_icd_runtime_contract"]).read_text(encoding="utf-8"))
require(len(icd.get("host_api_contract", [])) >= 16, "host API contract depth too shallow")
gates = json.loads(Path(paths["phase9_opencl_readiness_gates"]).read_text(encoding="utf-8"))
require(len(gates.get("gates", [])) >= 6, "productization gate depth too shallow")

for doc in (
    Path("docs/celviz-gpgpu-ip/PHASE9_OPENCL_CONFORMANCE_READINESS.md"),
    Path("docs/celviz-gpgpu-ip/OPENCL_ICD_RUNTIME_CONTRACT.md"),
    Path("docs/celviz-gpgpu-ip/PHASE9_OPENCL_READINESS_GATES.md"),
):
    require(doc.exists() and doc.stat().st_size > 0, f"missing doc: {doc}")

if errors:
    for error in errors:
        print(f"[FAIL] {error}", file=sys.stderr)
    raise SystemExit(1)

print(f"celviz_gpgpu_phase9_opencl_conformance_readiness_verify: pass requirements={len(requirements)} artifacts={len(paths)}")
PY
