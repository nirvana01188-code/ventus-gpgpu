#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build_root="${CELVIZ_GPGPU_BUILD_ROOT:-/tmp/ventus-gpgpu-celviz-build}"
mode="auto"
actual_build_kind=""
native_runtime=""
coverage_build=0
if [[ "${VLIB_COVERAGE:-0}" == "1" || "${CELVIZ_GPGPU_COVERAGE_BUILD:-0}" == "1" ]]; then
  coverage_build=1
fi

usage() {
  cat <<'EOF'
usage: scripts/build_celviz_gpgpu_runtime.sh [--auto|--fast-relink|--full] [--coverage] [--build-root DIR]

Builds the Celviz GPGPU native runtime in a no-space temporary workspace.

Modes:
  --auto         Preserve an existing Verilated model and fast relink if possible;
                 otherwise run the full sim-verilator library build.
  --fast-relink Recompile/relink only the runtime C ABI against an existing
                 Verilated model under the build root.
  --full         Run the full sim-verilator library build in the build root.
  --coverage     Force a full Verilator rebuild with VLIB_COVERAGE=1.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --auto)
      mode="auto"
      shift
      ;;
    --fast-relink)
      mode="fast-relink"
      shift
      ;;
    --full)
      mode="full"
      shift
      ;;
    --coverage)
      coverage_build=1
      shift
      ;;
    --build-root)
      build_root="$2"
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

if [[ "$coverage_build" -eq 1 && "$mode" == "fast-relink" ]]; then
  echo "--coverage requires --auto or --full so the Verilated model is rebuilt with coverage counters" >&2
  exit 2
fi
export CELVIZ_GPGPU_COVERAGE_BUILD="$coverage_build"

manifest_dir="$build_root/sim-verilator/build/libVentusRTL"
manifest_path="${CELVIZ_GPGPU_BUILD_MANIFEST:-$manifest_dir/celviz_gpgpu_runtime_build_manifest.json}"
build_log_path="${CELVIZ_GPGPU_BUILD_LOG:-$manifest_dir/celviz_gpgpu_runtime_build_log.jsonl}"

required_symbols=(
  ventus_rtlsim_get_default_config
  ventus_rtlsim_init
  ventus_rtlsim_finish
  ventus_rtlsim_step
  ventus_rtlsim_add_kernel
  ventus_rtlsim_pmemcpy_h2d
  ventus_rtlsim_pmemcpy_d2h
  ventus_rtlsim_get_time
  celviz_gpgpu_device_tier_get_default
  celviz_gpgpu_runtime_proxy_attach
  celviz_gpgpu_runtime_proxy_detach
  celviz_gpgpu_runtime_proxy_submit_copy_h2d
  celviz_gpgpu_runtime_proxy_submit_copy_d2h
  celviz_gpgpu_runtime_proxy_submit_fill
  celviz_gpgpu_runtime_proxy_get_device
  celviz_gpgpu_runtime_proxy_get_queue_count
  celviz_gpgpu_runtime_proxy_get_queue_snapshot
  celviz_gpgpu_runtime_proxy_get_pending_count
  celviz_gpgpu_runtime_proxy_get_metrics
  celviz_gpgpu_runtime_proxy_reset_metrics
  celviz_gpgpu_runtime_proxy_signal_named_fence
  celviz_gpgpu_runtime_proxy_wait_named_fence
)

optional_symbols=(
  celviz_gpgpu_runtime_proxy_get_queue_by_id
  celviz_gpgpu_runtime_proxy_get_queue_pending_count
  celviz_gpgpu_runtime_proxy_reset_queue
  celviz_gpgpu_runtime_proxy_submit_kernel
  celviz_gpgpu_runtime_proxy_inject_next_error
  celviz_gpgpu_runtime_proxy_submit_fault
  celviz_gpgpu_runtime_proxy_step
  celviz_gpgpu_runtime_proxy_get_command_status
  celviz_gpgpu_runtime_proxy_get_last_event
  celviz_gpgpu_runtime_proxy_get_fence_value
  celviz_gpgpu_runtime_proxy_get_named_fence_value
  celviz_gpgpu_runtime_proxy_signal_fence
  celviz_gpgpu_runtime_proxy_wait_fence
)

utc_now() {
  date -u '+%Y-%m-%dT%H:%M:%SZ'
}

append_event() {
  local event="$1"
  local status="${2:-info}"
  mkdir -p "$(dirname "$build_log_path")"
  CELVIZ_GPGPU_COVERAGE_BUILD="$coverage_build" \
  python3 - "$build_log_path" "$event" "$status" "$(utc_now)" "$root" "$build_root" "$mode" "$actual_build_kind" "${native_runtime:-}" <<'PY'
import json
import os
import sys

path, event, status, timestamp, repo_root, build_root, mode, actual_build, runtime_lib = sys.argv[1:10]
payload = {
    "schema": "celviz.gpgpu.runtime_build_log.v1",
    "timestamp_utc": timestamp,
    "event": event,
    "status": status,
    "repo_root": repo_root,
    "build_root": build_root,
    "requested_mode": mode,
    "actual_build": actual_build or None,
    "coverage_build": os.environ.get("CELVIZ_GPGPU_COVERAGE_BUILD") == "1",
    "fast_relink_used": actual_build == "fast-relink",
    "full_build_used": actual_build in {"full", "full-coverage"},
    "native_runtime_lib": runtime_lib or None,
}
with open(path, "a", encoding="utf-8") as handle:
    handle.write(json.dumps(payload, sort_keys=True) + "\n")
PY
}

write_manifest() {
  local status="$1"
  local runtime_lib="${2:-}"
  local error_message="${3:-}"
  local required_joined
  local optional_joined
  required_joined="$(printf '%s\n' "${required_symbols[@]}")"
  optional_joined="$(printf '%s\n' "${optional_symbols[@]}")"

  mkdir -p "$(dirname "$manifest_path")"
  CELVIZ_REQUIRED_SYMBOLS="$required_joined" \
  CELVIZ_OPTIONAL_SYMBOLS="$optional_joined" \
  CELVIZ_GPGPU_COVERAGE_BUILD="$coverage_build" \
  python3 - "$manifest_path" "$build_log_path" "$(utc_now)" "$root" "$build_root" "$mode" "$actual_build_kind" "$runtime_lib" "$status" "$error_message" <<'PY'
import json
import os
import subprocess
import sys
from pathlib import Path

(
    manifest_path,
    build_log_path,
    timestamp,
    repo_root,
    build_root,
    requested_mode,
    actual_build,
    runtime_lib,
    status,
    error_message,
) = sys.argv[1:11]

required = [symbol for symbol in os.environ.get("CELVIZ_REQUIRED_SYMBOLS", "").splitlines() if symbol]
optional = [symbol for symbol in os.environ.get("CELVIZ_OPTIONAL_SYMBOLS", "").splitlines() if symbol]


def normalize_symbol(symbol: str) -> str:
    symbol = symbol.rsplit("@", 1)[0]
    if symbol.startswith("_"):
        symbol = symbol[1:]
    return symbol


def nm_symbols(path: str) -> list[str]:
    if not path:
        return []
    commands = [
        ["nm", "-D", "--defined-only", "-g", path],
        ["nm", "-gU", path],
        ["nm", "-g", path],
    ]
    output = ""
    for command in commands:
        try:
            output = subprocess.check_output(command, stderr=subprocess.DEVNULL, text=True)
            break
        except (OSError, subprocess.CalledProcessError):
            output = ""
    symbols = set()
    for line in output.splitlines():
        fields = line.split()
        if not fields:
            continue
        if len(fields) >= 3 and fields[-2] == "U":
            continue
        if len(fields) >= 2 and fields[-1] == "U":
            continue
        symbols.add(normalize_symbol(fields[-1]))
    return sorted(symbols)


exports = nm_symbols(runtime_lib)
export_set = set(exports)
present = [symbol for symbol in required if symbol in export_set]
missing = [symbol for symbol in required if symbol not in export_set]
optional_present = [symbol for symbol in optional if symbol in export_set]
optional_missing = [symbol for symbol in optional if symbol not in export_set]

payload = {
    "schema": "celviz.gpgpu.runtime_build_manifest.v1",
    "timestamp_utc": timestamp,
    "status": status,
    "repo_root": repo_root,
    "build_root": build_root,
    "requested_mode": requested_mode,
    "actual_build": actual_build or None,
    "coverage_build": os.environ.get("CELVIZ_GPGPU_COVERAGE_BUILD") == "1",
    "fast_relink_used": actual_build == "fast-relink",
    "full_build_used": actual_build in {"full", "full-coverage"},
    "path_with_spaces_workaround": {
        "enabled": True,
        "synced_repo_to_build_root": True,
    },
    "native_runtime_lib": runtime_lib or None,
    "native_runtime_exists": bool(runtime_lib and Path(runtime_lib).is_file()),
    "manifest_path": manifest_path,
    "build_log_path": build_log_path,
    "symbol_check": {
        "tool": "nm",
        "required_count": len(required),
        "present_count": len(present),
        "missing_count": len(missing),
        "complete": not missing,
        "present_symbols": present,
        "missing_symbols": missing,
        "optional_count": len(optional),
        "optional_present_count": len(optional_present),
        "optional_missing_count": len(optional_missing),
        "optional_present_symbols": optional_present,
        "optional_missing_symbols": optional_missing,
    },
}
if error_message:
    payload["error"] = error_message

Path(manifest_path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

on_error() {
  local status=$?
  local line="$1"
  local command="$2"
  set +e
  local message="line ${line}: ${command} (exit=${status})"
  append_event "error" "fail"
  write_manifest "fail" "${native_runtime:-}" "$message"
  printf 'CELVIZ_GPGPU_RUNTIME_BUILD_MANIFEST=%s\n' "$manifest_path" >&2
  printf 'CELVIZ_GPGPU_RUNTIME_BUILD_LOG=%s\n' "$build_log_path" >&2
  exit "$status"
}
trap 'on_error "$LINENO" "$BASH_COMMAND"' ERR

configure_java() {
  if command -v java >/dev/null 2>&1 && java -version >/dev/null 2>&1; then
    return 0
  fi

  local candidate
  for candidate in \
    /opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home \
    /opt/homebrew/opt/openjdk/libexec/openjdk.jdk/Contents/Home \
    /usr/local/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home \
    /usr/local/opt/openjdk/libexec/openjdk.jdk/Contents/Home; do
    if [[ -x "$candidate/bin/java" ]]; then
      export JAVA_HOME="$candidate"
      export PATH="$JAVA_HOME/bin:$PATH"
      return 0
    fi
  done
}

sync_workspace() {
  mkdir -p "$build_root"
  rsync -a --delete \
    --exclude '.git' \
    --exclude 'out' \
    --exclude 'logs' \
    --exclude 'sim-verilator/build' \
    --exclude 'sim-verilator/logs' \
    "$root"/ "$build_root"/
}

verilator_include_dir() {
  local include_dir
  include_dir="$(pkg-config --variable=includedir verilator 2>/dev/null || true)"
  if [[ -n "$include_dir" && -d "$include_dir" ]]; then
    printf '%s\n' "$include_dir"
    return 0
  fi

  if command -v verilator >/dev/null 2>&1; then
    include_dir="$(
      verilator -V 2>/dev/null \
        | sed -n 's/.*VERILATOR_ROOT[[:space:]]*=[[:space:]]*//p' \
        | head -n 1
    )"
    if [[ -n "$include_dir" && -d "$include_dir/include" ]]; then
      printf '%s\n' "$include_dir/include"
      return 0
    fi
  fi

  for include_dir in \
    /opt/homebrew/Cellar/verilator/*/share/verilator/include \
    /usr/local/Cellar/verilator/*/share/verilator/include \
    /usr/share/verilator/include; do
    if [[ -d "$include_dir" ]]; then
      printf '%s\n' "$include_dir"
      return 0
    fi
  done

  echo "unable to locate Verilator include directory" >&2
  return 1
}

have_verilated_core() {
  local obj_dir="$build_root/sim-verilator/build/libVentusRTL/debug"
  [[ -f "$obj_dir/libVdut.a" && -f "$obj_dir/libverilated.a" && -f "$obj_dir/Vdut.h" ]]
}

fast_relink() {
  local sim_dir="$build_root/sim-verilator"
  local obj_dir="$sim_dir/build/libVentusRTL/debug"
  local verilator_include
  local spdlog_fmt_cflags
  local spdlog_fmt_libs

  if ! have_verilated_core; then
    echo "fast relink requires existing libVdut.a, libverilated.a, and Vdut.h under $obj_dir" >&2
    return 1
  fi

  verilator_include="$(verilator_include_dir)"
  spdlog_fmt_cflags="$(pkg-config --cflags spdlog fmt 2>/dev/null || echo -I/opt/homebrew/include -I/usr/local/include)"
  spdlog_fmt_libs="$(pkg-config --libs spdlog fmt 2>/dev/null || echo -L/opt/homebrew/lib -L/usr/local/lib -lspdlog -lfmt)"

  c++ \
    -I"$obj_dir" \
    -I"$sim_dir" \
    -I"$verilator_include" \
    -I"$verilator_include/vltstd" \
    -DVERILATOR=1 \
    -DVM_COVERAGE=0 \
    -DVM_SC=0 \
    -DVM_TIMING=0 \
    -DVM_TRACE=1 \
    -DVM_TRACE_FST=1 \
    -DVM_TRACE_VCD=0 \
    -DVM_TRACE_SAIF=0 \
    -g -O0 -fPIC -std=c++20 \
    -DSPDLOG_ACTIVE_LEVEL=SPDLOG_LEVEL_TRACE \
    $spdlog_fmt_cflags \
    -c -o "$obj_dir/ventus_rtlsim.o" \
    "$sim_dir/ventus_rtlsim.cpp"

  c++ \
    -g -O0 -fPIC -std=c++20 \
    -DSPDLOG_ACTIVE_LEVEL=SPDLOG_LEVEL_TRACE \
    $spdlog_fmt_cflags \
    -lc \
    $spdlog_fmt_libs \
    -pthread \
    -shared -o "$obj_dir/libVentusRTL.so" \
    "$obj_dir/ventus_rtlsim.o" \
    "$obj_dir/libVdut.a" \
    "$obj_dir/libverilated.a" \
    $spdlog_fmt_libs \
    -pthread -lpthread -lz

  ln -sf "$obj_dir/libVentusRTL.so" "$sim_dir/build/libVentusRTL/libVentusRTL.so"
}

full_build() {
  configure_java || true
  if [[ "$coverage_build" -eq 1 ]]; then
    make -C "$build_root/sim-verilator" clean-verilated
    make -C "$build_root/sim-verilator" lib VLIB_NPROC_CPU=1 VLIB_NPROC_DUT=1 VLIB_COVERAGE=1
  else
    make -C "$build_root/sim-verilator" lib VLIB_NPROC_CPU=1 VLIB_NPROC_DUT=1
  fi
}

mkdir -p "$(dirname "$build_log_path")"
: >"$build_log_path"
append_event "start" "running"
sync_workspace
append_event "sync_workspace" "pass"

case "$mode" in
  auto)
    if [[ "$coverage_build" -eq 1 ]]; then
      actual_build_kind="full-coverage"
      append_event "build_start" "running"
      full_build
    elif have_verilated_core; then
      actual_build_kind="fast-relink"
      append_event "build_start" "running"
      fast_relink
    else
      actual_build_kind="full"
      append_event "build_start" "running"
      full_build
    fi
    ;;
  fast-relink)
    actual_build_kind="fast-relink"
    append_event "build_start" "running"
    fast_relink
    ;;
  full)
    if [[ "$coverage_build" -eq 1 ]]; then
      actual_build_kind="full-coverage"
    else
      actual_build_kind="full"
    fi
    append_event "build_start" "running"
    full_build
    ;;
  *)
    echo "invalid mode: $mode" >&2
    exit 2
    ;;
esac
append_event "build_complete" "pass"

native_runtime="$(find "$build_root/sim-verilator/build/libVentusRTL" -path '*/libVentusRTL.so' -type f -print 2>/dev/null | sort | head -n 1)"
if [[ -z "$native_runtime" ]]; then
  echo "native runtime build did not produce libVentusRTL.so" >&2
  exit 1
fi

write_manifest "pass" "$native_runtime"
append_event "manifest_written" "pass"

printf 'CELVIZ_GPGPU_RUNTIME_LIB=%s\n' "$native_runtime"
printf 'CELVIZ_GPGPU_RUNTIME_BUILD_MANIFEST=%s\n' "$manifest_path"
printf 'CELVIZ_GPGPU_RUNTIME_BUILD_LOG=%s\n' "$build_log_path"
printf 'CELVIZ_GPGPU_RUNTIME_BUILD_MODE=%s\n' "$actual_build_kind"
