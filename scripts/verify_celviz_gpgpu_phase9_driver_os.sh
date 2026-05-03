#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

# Phase-9 driver/OS conformance-readiness gate for DRM-like submission,
# queue/fence/event lifecycle, fault paths, and OpenCL-like queue semantics.
# This is not a production Linux DRM driver or official OpenCL conformance.
PYTHONDONTWRITEBYTECODE=1 python3 tools/celviz_gpgpu_ip/phase9_driver_os_conformance.py
