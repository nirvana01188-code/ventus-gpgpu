#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

PYTHONDONTWRITEBYTECODE=1 python3 tools/celviz_gpgpu_ip/phase9_productization_gates.py
