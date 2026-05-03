#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

bash scripts/verify_celviz_gpgpu_kernel_lowering.sh
python3 tools/celviz_gpgpu_ip/phase4_lowering_integration.py
