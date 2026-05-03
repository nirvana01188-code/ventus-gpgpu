#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

verification_dir="artifacts/rank_01_vivante_3d_gpgpu_ip/verification"
output_dir="$verification_dir/verilator_coverage"

usage() {
  cat <<'EOF'
usage: scripts/verify_celviz_gpgpu_verilator_coverage.sh [--output-dir DIR]

Validates an existing supplemental Celviz GPGPU Verilator coverage artifact
bundle. This checker is intentionally read-only: it does not rebuild the RTL
model and does not rerun Verilator. The 100% gate is for declared clean-room
functional bins; RTL structural line/source/toggle percentages remain reported
separately and are not treated as silicon signoff.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-dir)
      output_dir="$2"
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

coverage_dat="$output_dir/coverage.dat"
coverage_info="$output_dir/coverage.info"
coverage_report="$output_dir/verilator_coverage_report.json"
coverage_index="$output_dir/report/index.html"
coverage_annotated_dut="$output_dir/report/dut.v"
run_log="$output_dir/run.log"

fail() {
  printf 'celviz_gpgpu_verilator_coverage_verify: fail\n' >&2
  printf 'reason: %s\n' "$*" >&2
  exit 1
}

require_file_nonempty() {
  local path="$1"
  local label="$2"
  [[ -s "$path" ]] || fail "$label is missing or empty: $path"
}

require_log_token() {
  local token="$1"
  grep -F -q "$token" "$run_log" || fail "run.log missing token: $token"
}

require_file_nonempty "$coverage_dat" "Verilator coverage.dat"
require_file_nonempty "$coverage_info" "Verilator coverage.info"
require_file_nonempty "$coverage_report" "Verilator coverage JSON report"
require_file_nonempty "$coverage_index" "Verilator coverage HTML index"
require_file_nonempty "$coverage_annotated_dut" "Verilator annotated dut.v report"
require_file_nonempty "$run_log" "Verilator coverage run log"

require_log_token "celviz_gpgpu_verilator_coverage: pass"
require_log_token "functional_bins_gate=100%"
require_log_token "rtl_line_toggle_coverage_claim=not_claimed"
require_log_token "coverage_scope=functional_bins_gate_not_rtl_line_or_toggle_100_percent_claim"
require_log_token "Coverage Summary:"

python3 - "$coverage_report" "$coverage_dat" "$coverage_info" "$coverage_index" "$coverage_annotated_dut" "$run_log" <<'PY'
import json
import sys
from pathlib import Path

report_path, dat_path, info_path, index_path, annotated_dut_path, log_path = map(Path, sys.argv[1:])
data = json.loads(report_path.read_text())

errors = []

def require(condition, message):
    if not condition:
        errors.append(message)

require(data.get("schema") == "celviz.gpgpu.verilator_coverage_report.v1", "unexpected coverage report schema")
require(data.get("status") == "pass", "coverage report status is not pass")
require(float(data.get("functional_coverage_percent", -1.0)) == 100.0, "functional coverage is not 100%")

scope = data.get("clean_room_scope", "")
require(isinstance(scope, str) and "clean-room" in scope, "clean-room scope missing from report")
for token in (
    "no proprietary Vivante compatibility",
    "API conformance claim",
    "silicon signoff",
    "STA/timing closure",
):
    require(token in scope, f"clean-room no-overclaim boundary token missing: {token}")

feature_bins = data.get("feature_bins")
require(isinstance(feature_bins, list) and feature_bins, "feature_bins must be a non-empty list")
missed = [item.get("name", "<unnamed>") for item in feature_bins or [] if item.get("hit") is not True]
require(not missed, "missed functional bins: " + ", ".join(missed))
require(len(feature_bins or []) >= 15, "functional bin count is unexpectedly low")

requirements = data.get("requirements", {})
require(requirements.get("require_functional_100") is True, "require_functional_100 is not true")
require(requirements.get("failures") == [], "requirement failures are present")
require(data.get("artifact_failures") == [], "artifact failures are present")

runtime_metrics = data.get("runtime_metrics", {})
require(runtime_metrics.get("exists") is True, "runtime metrics artifact is not recorded as existing")
require(runtime_metrics.get("non_empty") is True, "runtime metrics artifact is not recorded as non-empty")
require(runtime_metrics.get("load_status") == "loaded", "runtime metrics artifact was not loaded")
require(int(runtime_metrics.get("size_bytes", 0)) > 0, "runtime metrics recorded size is zero")

artifacts = data.get("verilator_artifacts", {})
for label, expected in (("coverage_dat", dat_path), ("coverage_info", info_path)):
    item = artifacts.get(label, {})
    require(item.get("exists") is True, f"{label} is not recorded as existing")
    require(item.get("non_empty") is True, f"{label} is not recorded as non-empty")
    require(int(item.get("size_bytes", 0)) == expected.stat().st_size, f"{label} size does not match file on disk")

lcov = data.get("lcov_info", {})
require(lcov.get("status") == "available", "LCOV info is not available")
line = lcov.get("line", {})
require(line.get("status") == "available", "line coverage metric is not available")
require(int(line.get("found", 0)) > 0, "line coverage found count is zero")
require(int(line.get("hit", 0)) > 0, "line coverage hit count is zero")
branch = lcov.get("branch", {})
require(branch.get("status") == "available", "branch coverage metric is not available")
require(int(branch.get("found", 0)) > 0, "branch coverage found count is zero")
toggle = lcov.get("toggle", {})
require(toggle.get("status") in {"available", "unavailable"}, "toggle coverage status is malformed")
if toggle.get("status") == "unavailable":
    require("reason" in toggle, "toggle coverage unavailable without a reason")

for path, label in (
    (report_path, "coverage report"),
    (dat_path, "coverage.dat"),
    (info_path, "coverage.info"),
    (index_path, "report/index.html"),
    (annotated_dut_path, "report/dut.v"),
    (log_path, "run.log"),
):
    require(path.exists() and path.stat().st_size > 0, f"{label} missing or empty")

if errors:
    for error in errors:
        print(f"[FAIL] {error}", file=sys.stderr)
    raise SystemExit(1)

print(
    "celviz_gpgpu_verilator_coverage_verify: pass "
    f"functional={data['functional_coverage_percent']:.3f}% "
    f"bins={len(feature_bins)} "
    f"line={line.get('percent')}% "
    f"branch={branch.get('percent')}% "
    f"toggle_status={toggle.get('status')}"
)
PY

printf 'celviz_gpgpu_verilator_coverage_verify: pass\n'
