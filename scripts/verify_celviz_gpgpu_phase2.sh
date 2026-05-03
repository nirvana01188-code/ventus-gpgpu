#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

run_focused=0
output="artifacts/rank_01_vivante_3d_gpgpu_ip/verification/phase2_integration_report.json"

usage() {
  cat <<'EOF'
usage: scripts/verify_celviz_gpgpu_phase2.sh [--run-focused] [--output PATH]

Verifies phase-2 Celviz GPGPU evidence: SIMT compute path, OpenCL subset ABI,
memory system, Linux userspace runtime proxy, supplemental RTL verification,
and synthesis/PPA proxy evidence.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-focused)
      run_focused=1
      shift
      ;;
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

args=(--output "$output")
if [[ "$run_focused" -eq 1 ]]; then
  args+=(--run-focused)
fi

python3 tools/celviz_gpgpu_ip/phase2_integration.py "${args[@]}"
