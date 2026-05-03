#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

artifact_root="artifacts/rank_01_vivante_3d_gpgpu_ip"
rtl_dir="$artifact_root/rtl"
verification_dir="$artifact_root/verification"
output_dir="$verification_dir/verilator_coverage"
build_root="${CELVIZ_GPGPU_COVERAGE_BUILD_ROOT:-/tmp/ventus-gpgpu-celviz-coverage-build}"
run_root="${CELVIZ_GPGPU_COVERAGE_RUN_ROOT:-/tmp/ventus-gpgpu-celviz-coverage-run}"
runtime_outputs="$run_root/runtime_outputs"
runtime_status="$runtime_outputs/runtime_status.json"
runtime_metrics="$runtime_outputs/runtime_metrics.json"
runtime_run_log="$run_root/runtime_cli.log"
command_stream="$rtl_dir/control_plane_demo.json"
report_tool="tools/celviz_gpgpu_ip/verilator_coverage_report.py"

usage() {
  cat <<'EOF'
usage: scripts/run_celviz_gpgpu_verilator_coverage.sh [--output-dir DIR]

Runs the supplemental Celviz GPGPU Verilator coverage lane. The 100% gate is
for declared clean-room functional bins; RTL line/source/toggle percentages are
reported separately and are not claimed as silicon signoff.
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

run_log="$output_dir/run.log"
coverage_dat="$output_dir/coverage.dat"
coverage_info="$output_dir/coverage.info"
coverage_report="$output_dir/verilator_coverage_report.json"
coverage_annotate_dir="$output_dir/report"

log() {
  printf '%s\n' "$*"
}

fail() {
  log "celviz_gpgpu_verilator_coverage: fail"
  log "reason: $*"
  exit 1
}

require_file_nonempty() {
  local path="$1"
  local label="$2"
  [[ -s "$path" ]] || fail "$label is missing or empty: $path"
}

require_tool() {
  local tool="$1"
  command -v "$tool" >/dev/null 2>&1 || fail "required tool not found in PATH: $tool"
}

extract_var() {
  local name="$1"
  local file="$2"
  awk -F= -v key="$name" '$1 == key { value=$2 } END { if (value != "") print value }' "$file"
}

mkdir -p "$verification_dir" "$output_dir" "$run_root"
: >"$run_log"
exec > >(tee -a "$run_log") 2>&1

log "celviz_gpgpu_verilator_coverage: start"
log "repo_root=$root"
log "build_root=$build_root"
log "run_root=$run_root"
log "run_log=$run_log"
log "coverage_scope=functional_bins_gate_not_rtl_line_or_toggle_100_percent_claim"

case "$root" in
  *" "*) log "repo_root_contains_spaces=true; building in /tmp build root" ;;
  *) log "repo_root_contains_spaces=false; still building in /tmp build root for consistency" ;;
esac

[[ "$build_root" == /tmp/* ]] || fail "build root must be under /tmp to avoid space-sensitive Verilator make paths: $build_root"
[[ "$run_root" == /tmp/* ]] || fail "run root must be under /tmp: $run_root"

require_tool bash
require_tool python3
require_tool rsync
require_tool verilator
require_tool verilator_coverage

require_file_nonempty "scripts/build_celviz_gpgpu_runtime.sh" "native runtime build script"
require_file_nonempty "tools/celviz_gpgpu_ip/runtime_cli.py" "runtime CLI"
require_file_nonempty "$command_stream" "complex Celviz GPGPU command stream fixture"
require_file_nonempty "$report_tool" "Verilator coverage report tool"

rm -rf "$run_root" "$coverage_annotate_dir"
mkdir -p "$runtime_outputs"
rm -f "$coverage_dat" "$coverage_info" "$coverage_report"

build_capture="$run_root/build_runtime_coverage.env"
: >"$build_capture"

log "build: full native runtime with Verilator coverage enabled"
existing_runtime="$build_root/sim-verilator/build/libVentusRTL/debug/libVentusRTL.so"
existing_manifest="$build_root/sim-verilator/build/libVentusRTL/celviz_gpgpu_runtime_build_manifest.json"
if [[ "${CELVIZ_GPGPU_FORCE_COVERAGE_REBUILD:-0}" != "1" && -s "$existing_runtime" && -s "$existing_manifest" ]] && \
  python3 - "$existing_manifest" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
raise SystemExit(0 if data.get("coverage_build") is True and data.get("status") == "pass" else 1)
PY
then
  log "build: reusing existing coverage-enabled native runtime"
  {
    printf 'CELVIZ_GPGPU_RUNTIME_LIB=%s\n' "$existing_runtime"
    printf 'CELVIZ_GPGPU_RUNTIME_BUILD_MANIFEST=%s\n' "$existing_manifest"
    printf 'CELVIZ_GPGPU_RUNTIME_BUILD_LOG=%s\n' "$build_root/sim-verilator/build/libVentusRTL/celviz_gpgpu_runtime_build_log.jsonl"
    printf 'CELVIZ_GPGPU_RUNTIME_BUILD_MODE=%s\n' "full-coverage-reused"
  } | tee "$build_capture"
else
  (
    export VLIB_COVERAGE=1
    export CELVIZ_GPGPU_BUILD_ROOT="$build_root"
    bash scripts/build_celviz_gpgpu_runtime.sh --full --build-root "$build_root"
  ) | tee "$build_capture"
fi

native_runtime="$(extract_var CELVIZ_GPGPU_RUNTIME_LIB "$build_capture")"
[[ -n "$native_runtime" ]] || fail "native runtime build did not print CELVIZ_GPGPU_RUNTIME_LIB"
require_file_nonempty "$native_runtime" "coverage-enabled native runtime"

verilated_debug_dir="$build_root/sim-verilator/build/libVentusRTL/debug"
require_file_nonempty "$verilated_debug_dir/Vdut.h" "Verilator generated header"
require_file_nonempty "$verilated_debug_dir/libVdut.a" "Verilator generated DUT archive"
require_file_nonempty "$verilated_debug_dir/libverilated.a" "Verilator support archive"
require_file_nonempty "$build_root/sim-verilator/build/libVentusRTL/libVentusRTL.so" "Verilator runtime symlink target"

log "runtime: running complex Celviz GPGPU command stream through runtime_cli --require-runtime"
(
  export CELVIZ_GPGPU_RUNTIME_LIB="$native_runtime"
  export CELVIZ_GPGPU_COVERAGE_FILE="$root/$coverage_dat"
  python3 tools/celviz_gpgpu_ip/runtime_cli.py \
    --commands "$command_stream" \
    --runtime-lib "$native_runtime" \
    --require-runtime \
    --output-dir "$runtime_outputs" \
    --run-log "$runtime_run_log" \
    --print-status \
    --print-artifacts
)

require_file_nonempty "$runtime_run_log" "runtime CLI command log"
require_file_nonempty "$runtime_status" "runtime status artifact"
require_file_nonempty "$runtime_metrics" "runtime metrics artifact"
require_file_nonempty "$coverage_dat" "Verilator coverage.dat"

log "coverage: converting coverage.dat to LCOV info"
verilator_coverage --write-info "$coverage_info" "$coverage_dat"
require_file_nonempty "$coverage_info" "Verilator coverage.info"

log "coverage: annotating structural coverage report"
mkdir -p "$coverage_annotate_dir"
(
  cd "$build_root/sim-verilator"
  verilator_coverage --annotate "$root/$coverage_annotate_dir" --annotate-all "$root/$coverage_dat"
)
if [[ ! -e "$coverage_annotate_dir/index.html" ]]; then
  {
    printf '<!doctype html>\n'
    printf '<html><head><meta charset="utf-8"><title>Celviz GPGPU Verilator Coverage</title></head><body>\n'
    printf '<h1>Celviz GPGPU Verilator Coverage</h1>\n'
    printf '<p>Verilator structural coverage annotation generated. See adjacent annotated files for details.</p>\n'
    printf '<p>Functional bins gate is tracked in verilator_coverage_report.json and is separate from RTL line/source/toggle coverage.</p>\n'
    printf '</body></html>\n'
  } >"$coverage_annotate_dir/index.html"
fi
require_file_nonempty "$coverage_annotate_dir/index.html" "Verilator coverage report index"

log "coverage: generating JSON report"
python3 "$report_tool" \
  --coverage-dat "$coverage_dat" \
  --coverage-info "$coverage_info" \
  --runtime-metrics "$runtime_metrics" \
  --output "$coverage_report" \
  --require-functional-100
require_file_nonempty "$coverage_report" "Verilator coverage JSON report"

python3 - "$coverage_report" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
status = data.get("status", "unknown")
percent = data.get("functional_coverage_percent")
if status not in {"pass", "ok", True}:
    raise SystemExit(f"coverage report did not pass gate: status={status!r}")
if percent is not None and float(percent) < 100.0:
    raise SystemExit(f"functional bins gate below 100%: {percent}")
PY

log "celviz_gpgpu_verilator_coverage: pass"
log "functional_bins_gate=100%"
log "rtl_line_toggle_coverage_claim=not_claimed"
log "coverage_dat=$coverage_dat"
log "coverage_info=$coverage_info"
log "coverage_report=$coverage_report"
log "run_log=$run_log"
