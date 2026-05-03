#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

output_dir="artifacts/rank_01_vivante_3d_gpgpu_ip/lowering"

usage() {
  cat <<'EOF'
usage: scripts/verify_celviz_gpgpu_kernel_lowering.sh [--output-dir DIR]

Generates clean-room micro-op lowering evidence from the OpenCL-like subset ABI.
This is not a production compiler backend, ISA, SPIR-V/LLVM path, or Vivante
command-stream compatibility claim.
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

python3 tools/celviz_gpgpu_ip/kernel_lowering.py --output-dir "$output_dir"
