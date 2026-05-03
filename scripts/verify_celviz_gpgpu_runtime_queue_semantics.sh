#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

PYTHONDONTWRITEBYTECODE=1 python3 tools/celviz_gpgpu_ip/runtime_queue_semantics_gate.py
