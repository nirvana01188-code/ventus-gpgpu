#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

output_dir="artifacts/rank_01_vivante_3d_gpgpu_ip/verification"

usage() {
  cat <<'EOF'
usage: scripts/verify_celviz_gpgpu_opencl_conformance_gap_map.sh [--output-dir DIR] [--verify-only]

Generates and verifies the OpenCL conformance gap map diagram. The diagram is
not an official OpenCL conformance claim; it maps current OpenCL-like subset
evidence to remaining conformance gaps.
EOF
}

verify_arg=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-dir)
      output_dir="$2"
      shift 2
      ;;
    --verify-only)
      verify_arg="--verify-only"
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

if [[ -n "$verify_arg" ]]; then
  python3 tools/celviz_gpgpu_ip/opencl_conformance_gap_map.py \
    --output-dir "$output_dir" \
    "$verify_arg"
else
  python3 tools/celviz_gpgpu_ip/opencl_conformance_gap_map.py \
    --output-dir "$output_dir"
fi
