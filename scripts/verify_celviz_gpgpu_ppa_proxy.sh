#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

output="artifacts/rank_01_vivante_3d_gpgpu_ip/ppa/ppa_proxy_report.json"

usage() {
  cat <<'EOF'
usage: scripts/verify_celviz_gpgpu_ppa_proxy.sh [--output PATH]

Generates and validates clean-room synthesis/PPA proxy evidence. This is a
proxy report only: it is not logic synthesis, timing closure, physical power
signoff, or tapeout readiness.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output)
      output="$2"
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

python3 tools/celviz_gpgpu_ip/ppa_proxy.py --output "$output"

python3 - "$output" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
errors = []

def require(condition, message):
    if not condition:
        errors.append(message)

require(data.get("schema") == "celviz.gpgpu.ppa_proxy.v1", "schema mismatch")
require(data.get("status") == "pass", "status is not pass")
scope = data.get("clean_room_scope", "")
for token in ("clean-room", "not a physical synthesis report", "STA/timing closure", "silicon/tapeout readiness"):
    require(token in scope, f"scope token missing: {token}")
summary = data.get("source_summary", {})
require(int(summary.get("file_count", 0)) > 0, "no source files counted")
require(int(summary.get("nonblank_lines", 0)) > 0, "no source lines counted")
require(int(summary.get("marker_hit_count", 0)) > 0, "no Celviz markers counted")
tiers = {item.get("tier") for item in data.get("public_baseline_tiers", [])}
require({"CC8000L", "CC8000"}.issubset(tiers), "public baseline tier rows missing")
metrics = data.get("proxy_metrics", {})
for field in ("area_proxy_units", "frequency_proxy_index", "activity_proxy_index", "power_proxy_index"):
    require(float(metrics.get(field, 0)) > 0, f"proxy metric missing or zero: {field}")
require(data.get("limitations"), "limitations missing")
for check in data.get("checks", []):
    require(check.get("pass") is True, f"check failed: {check.get('name')}")

if errors:
    for error in errors:
        print(f"[FAIL] {error}", file=sys.stderr)
    raise SystemExit(1)

print(
    "celviz_gpgpu_ppa_proxy_verify: pass "
    f"files={summary.get('file_count')} markers={summary.get('marker_hit_count')} "
    f"area_proxy={metrics.get('area_proxy_units')} "
    f"freq_index={metrics.get('frequency_proxy_index')}"
)
PY
