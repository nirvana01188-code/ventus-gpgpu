#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

artifact_root="artifacts/rank_01_vivante_3d_gpgpu_ip"
output="$artifact_root/verification/verification_coverage_100.json"

usage() {
  cat <<'EOF'
usage: scripts/verify_celviz_gpgpu_coverage_100.sh [--output PATH]

Generates and verifies the Celviz GPGPU 100% functional/acceptance verification
coverage report. RTL structural Verilator line/toggle/source metrics are kept
as separate observations and are not converted into a 100% claim.
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

python3 tools/celviz_gpgpu_ip/verification_coverage_100.py \
  --artifact-root "$artifact_root" \
  --output "$output" \
  --require-100
