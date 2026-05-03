#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

bash scripts/verify_celviz_gpgpu_phase4.sh
bash scripts/verify_celviz_gpgpu_microop_execution.sh
python3 tools/celviz_gpgpu_ip/phase5_microop_integration.py
