#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

python3 tools/celviz_gpgpu_ip/phase7_coalescing_score.py "$@"
