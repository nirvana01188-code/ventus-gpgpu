#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

output="artifacts/rank_01_vivante_3d_gpgpu_ip/verification/phase3_cross_layer_report.json"

usage() {
  cat <<'EOF'
usage: scripts/verify_celviz_gpgpu_phase3.sh [--output PATH]

Verifies cross-layer phase-3 evidence: OpenCL-like kernel ABI, runtime command
ABI, SIMT execution, memory semantics, Linux userspace submission, supplemental
verification, and PPA proxy evidence line up as one clean-room stack.
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

python3 tools/celviz_gpgpu_ip/phase3_cross_layer.py --output "$output"
