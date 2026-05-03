#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$root"

python3 scripts/tools/artifacts/celviz_gpgpu_verilator_supplemental_phase1.py "$@"
