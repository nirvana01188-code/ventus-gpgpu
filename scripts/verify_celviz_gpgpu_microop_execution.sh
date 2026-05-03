#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

artifact_root="artifacts/rank_01_vivante_3d_gpgpu_ip"
output_dir="$artifact_root/microop_execution"

usage() {
  cat <<'EOF'
usage: scripts/verify_celviz_gpgpu_microop_execution.sh [--output-dir DIR]

Executes clean-room phase-4 micro-op lowering evidence through the phase-5
interpreter. This is not a production ISA simulator, compiler backend,
SPIR-V/LLVM path, Vivante ISA, or proprietary command-stream compatibility
claim.
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

python3 tools/celviz_gpgpu_ip/microop_interpreter.py \
  --artifact-root "$artifact_root" \
  --output-dir "$output_dir"
