#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

artifact_root="artifacts/rank_01_vivante_3d_gpgpu_ip"
output="$artifact_root/verification/phase6_memory_trace_integration_report.json"
refresh_inputs=1

usage() {
  cat <<'EOF'
usage: scripts/verify_celviz_gpgpu_phase6_memory.sh [--output FILE] [--no-refresh-inputs]

Builds clean-room Phase 6B micro-op memory trace integration evidence. The
gate reads phase-5 micro-op execution JSON plus the phase-1 memory model
evidence and checks per-kernel load/store traces, global memory semantics, and
coalescing/proxy memory model closure. It is not a production ISA simulator,
Vivante compatibility claim, cache microarchitecture, timing/PPA signoff, or
API conformance claim.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output)
      output="$2"
      shift 2
      ;;
    --no-refresh-inputs)
      refresh_inputs=0
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

if [[ "$refresh_inputs" -eq 1 ]]; then
  python3 tools/celviz_gpgpu_ip/memory_model.py \
    --artifact-root "$artifact_root/memory" \
    --verify

  python3 tools/celviz_gpgpu_ip/microop_interpreter.py \
    --artifact-root "$artifact_root" \
    --output-dir "$artifact_root/microop_execution"
fi

python3 tools/celviz_gpgpu_ip/phase6_memory_trace_integration.py \
  --artifact-root "$artifact_root" \
  --output "$output" \
  --print-summary
