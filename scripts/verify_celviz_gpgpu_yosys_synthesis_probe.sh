#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

timeout_s=60

usage() {
  cat <<'EOF'
usage: scripts/verify_celviz_gpgpu_yosys_synthesis_probe.sh [--timeout-s N]

Runs a bounded Yosys probe against the generated Verilator coverage Verilog.
This records real tool behavior and blockers, but is not target-library
synthesis, STA, power, DFT, physical implementation, or silicon signoff.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --timeout-s)
      timeout_s="$2"
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

python3 tools/celviz_gpgpu_ip/yosys_synthesis_probe.py --timeout-s "$timeout_s"
