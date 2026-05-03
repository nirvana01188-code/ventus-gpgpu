#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

verification_dir="artifacts/rank_01_vivante_3d_gpgpu_ip/verification"
output_dir="$verification_dir/verilator_coverage"
rerun_e8=0

usage() {
  cat <<'EOF'
usage: scripts/accept_celviz_gpgpu_ip_full.sh [--rerun-e8] [--output-dir DIR]

Runs the main Celviz GPGPU IP acceptance suite and validates the supplemental
E8 Verilator coverage artifact bundle. By default this script does not rerun
the slow Verilator coverage lane; pass --rerun-e8 to regenerate E8 first.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --rerun-e8)
      rerun_e8=1
      shift
      ;;
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

log() {
  printf '%s\n' "$*"
}

fail() {
  log "celviz_gpgpu_ip_full_acceptance: fail"
  log "reason: $*"
  exit 1
}

[[ -x scripts/accept_celviz_gpgpu_ip.sh || -f scripts/accept_celviz_gpgpu_ip.sh ]] || fail "missing main acceptance script"
[[ -x scripts/verify_celviz_gpgpu_verilator_coverage.sh || -f scripts/verify_celviz_gpgpu_verilator_coverage.sh ]] || fail "missing E8 verification script"
[[ -x scripts/verify_celviz_gpgpu_phase2.sh || -f scripts/verify_celviz_gpgpu_phase2.sh ]] || fail "missing phase-2 verification script"
[[ -x scripts/verify_celviz_gpgpu_phase3.sh || -f scripts/verify_celviz_gpgpu_phase3.sh ]] || fail "missing phase-3 verification script"
[[ -x scripts/verify_celviz_gpgpu_phase4.sh || -f scripts/verify_celviz_gpgpu_phase4.sh ]] || fail "missing phase-4 verification script"
[[ -x scripts/verify_celviz_gpgpu_phase5.sh || -f scripts/verify_celviz_gpgpu_phase5.sh ]] || fail "missing phase-5 verification script"
[[ -x scripts/verify_celviz_gpgpu_phase6.sh || -f scripts/verify_celviz_gpgpu_phase6.sh ]] || fail "missing phase-6 verification script"
[[ -x scripts/verify_celviz_gpgpu_phase7_coalescing.sh || -f scripts/verify_celviz_gpgpu_phase7_coalescing.sh ]] || fail "missing phase-7 coalescing verification script"
[[ -x scripts/verify_celviz_gpgpu_phase7_config_sweep.sh || -f scripts/verify_celviz_gpgpu_phase7_config_sweep.sh ]] || fail "missing phase-7 config sweep verification script"
[[ -x scripts/verify_celviz_gpgpu_phase7_control_flow_manager.sh || -f scripts/verify_celviz_gpgpu_phase7_control_flow_manager.sh ]] || fail "missing phase-7 control-flow manager verification script"
[[ -x scripts/verify_celviz_gpgpu_phase7_memory_streaming.sh || -f scripts/verify_celviz_gpgpu_phase7_memory_streaming.sh ]] || fail "missing phase-7 memory streaming verification script"
[[ -x scripts/verify_celviz_gpgpu_phase7_register_occupancy.sh || -f scripts/verify_celviz_gpgpu_phase7_register_occupancy.sh ]] || fail "missing phase-7 register occupancy verification script"
[[ -x scripts/verify_celviz_gpgpu_phase7_warp_collectives.sh || -f scripts/verify_celviz_gpgpu_phase7_warp_collectives.sh ]] || fail "missing phase-7 warp collectives verification script"
[[ -x scripts/verify_celviz_gpgpu_opencl_conformance_gap_map.sh || -f scripts/verify_celviz_gpgpu_opencl_conformance_gap_map.sh ]] || fail "missing OpenCL conformance gap map verification script"
[[ -x scripts/verify_celviz_gpgpu_phase8_claim_closure.sh || -f scripts/verify_celviz_gpgpu_phase8_claim_closure.sh ]] || fail "missing phase-8 claim closure verification script"
[[ -x scripts/verify_celviz_gpgpu_phase8_work_packages.sh || -f scripts/verify_celviz_gpgpu_phase8_work_packages.sh ]] || fail "missing phase-8 work package verification script"
[[ -x scripts/verify_celviz_gpgpu_opencl_host_api_shim.sh || -f scripts/verify_celviz_gpgpu_opencl_host_api_shim.sh ]] || fail "missing OpenCL host API shim verification script"
[[ -x scripts/verify_celviz_gpgpu_opencl_device_info_table.sh || -f scripts/verify_celviz_gpgpu_opencl_device_info_table.sh ]] || fail "missing OpenCL device-info table verification script"
[[ -x scripts/verify_celviz_gpgpu_opencl_build_error_code_matrix.sh || -f scripts/verify_celviz_gpgpu_opencl_build_error_code_matrix.sh ]] || fail "missing OpenCL build/error-code matrix verification script"
[[ -x scripts/verify_celviz_gpgpu_opencl_event_waitlist_profiling.sh || -f scripts/verify_celviz_gpgpu_opencl_event_waitlist_profiling.sh ]] || fail "missing OpenCL event wait-list/profiling verification script"
[[ -x scripts/verify_celviz_gpgpu_phase9_memory_object_flags.sh || -f scripts/verify_celviz_gpgpu_phase9_memory_object_flags.sh ]] || fail "missing phase-9 memory object flags verification script"
[[ -x scripts/verify_celviz_gpgpu_runtime_queue_semantics.sh || -f scripts/verify_celviz_gpgpu_runtime_queue_semantics.sh ]] || fail "missing runtime queue semantics verification script"
[[ -x scripts/verify_celviz_gpgpu_opencl_rtl_cts_cross_check.sh || -f scripts/verify_celviz_gpgpu_opencl_rtl_cts_cross_check.sh ]] || fail "missing OpenCL RTL/CTS cross-check verification script"
[[ -x scripts/verify_celviz_gpgpu_opencl_c_abi.sh || -f scripts/verify_celviz_gpgpu_opencl_c_abi.sh ]] || fail "missing OpenCL C ABI smoke verification script"
[[ -x scripts/verify_celviz_gpgpu_opencl_userspace_samples.sh || -f scripts/verify_celviz_gpgpu_opencl_userspace_samples.sh ]] || fail "missing OpenCL userspace samples verification script"
[[ -x scripts/verify_celviz_gpgpu_opencl_cts_smoke.sh || -f scripts/verify_celviz_gpgpu_opencl_cts_smoke.sh ]] || fail "missing OpenCL CTS smoke verification script"
[[ -x scripts/verify_celviz_gpgpu_opencl_product_gap_closure.sh || -f scripts/verify_celviz_gpgpu_opencl_product_gap_closure.sh ]] || fail "missing OpenCL product gap closure verification script"
[[ -x scripts/verify_celviz_gpgpu_opencl_kernel_abi_edges.sh || -f scripts/verify_celviz_gpgpu_opencl_kernel_abi_edges.sh ]] || fail "missing OpenCL kernel ABI edge verification script"
[[ -x scripts/verify_celviz_gpgpu_phase9_opencl_conformance_readiness.sh || -f scripts/verify_celviz_gpgpu_phase9_opencl_conformance_readiness.sh ]] || fail "missing phase-9 OpenCL conformance-readiness verification script"
[[ -x scripts/verify_celviz_gpgpu_phase9_memory_conformance.sh || -f scripts/verify_celviz_gpgpu_phase9_memory_conformance.sh ]] || fail "missing phase-9 memory conformance-readiness verification script"
[[ -x scripts/verify_celviz_gpgpu_phase9_driver_os.sh || -f scripts/verify_celviz_gpgpu_phase9_driver_os.sh ]] || fail "missing phase-9 driver/OS conformance-readiness verification script"
[[ -x scripts/verify_celviz_gpgpu_phase9_productization.sh || -f scripts/verify_celviz_gpgpu_phase9_productization.sh ]] || fail "missing phase-9 productization gate verification script"
[[ -x scripts/verify_celviz_eda_methodology.sh || -f scripts/verify_celviz_eda_methodology.sh ]] || fail "missing Celviz EDA methodology verification script"
[[ -x scripts/verify_celviz_gpgpu_coverage_100.sh || -f scripts/verify_celviz_gpgpu_coverage_100.sh ]] || fail "missing 100% verification coverage script"

log "celviz_gpgpu_ip_full_acceptance: start"
log "repo_root=$root"
log "e8_output_dir=$output_dir"
log "e8_mode=$([[ "$rerun_e8" -eq 1 ]] && printf 'rerun' || printf 'verify-existing')"

log "gate: main E0-E7 acceptance"
bash scripts/accept_celviz_gpgpu_ip.sh

if [[ "$rerun_e8" -eq 1 ]]; then
  log "gate: regenerate E8 Verilator coverage"
  bash scripts/run_celviz_gpgpu_verilator_coverage.sh --output-dir "$output_dir"
else
  log "gate: verify existing E8 Verilator coverage artifacts"
fi

bash scripts/verify_celviz_gpgpu_verilator_coverage.sh --output-dir "$output_dir"

log "gate: verify phase-2 hardening evidence"
bash scripts/verify_celviz_gpgpu_phase2.sh --run-focused

log "gate: verify phase-3 cross-layer evidence"
bash scripts/verify_celviz_gpgpu_phase3.sh

log "gate: verify phase-4 kernel lowering evidence"
bash scripts/verify_celviz_gpgpu_phase4.sh

log "gate: verify phase-5 executable micro-op evidence"
bash scripts/verify_celviz_gpgpu_phase5.sh

log "gate: verify phase-6 basic GPGPU IP parity evidence"
bash scripts/verify_celviz_gpgpu_phase6.sh

log "gate: verify phase-7 coalescing performance evidence"
bash scripts/verify_celviz_gpgpu_phase7_coalescing.sh

log "gate: verify phase-7 control-flow manager performance evidence"
bash scripts/verify_celviz_gpgpu_phase7_control_flow_manager.sh

log "gate: verify phase-7 memory streaming performance evidence"
bash scripts/verify_celviz_gpgpu_phase7_memory_streaming.sh

log "gate: verify phase-7 config sweep performance evidence"
bash scripts/verify_celviz_gpgpu_phase7_config_sweep.sh

log "gate: verify phase-7 register occupancy performance evidence"
bash scripts/verify_celviz_gpgpu_phase7_register_occupancy.sh

log "gate: verify phase-7 warp collectives performance evidence"
bash scripts/verify_celviz_gpgpu_phase7_warp_collectives.sh

log "gate: verify OpenCL conformance gap map"
bash scripts/verify_celviz_gpgpu_opencl_conformance_gap_map.sh

log "gate: verify phase-8 claim closure evidence"
bash scripts/verify_celviz_gpgpu_phase8_claim_closure.sh

log "gate: verify phase-8 work package artifacts"
bash scripts/verify_celviz_gpgpu_phase8_work_packages.sh

log "gate: verify executable OpenCL host API shim"
bash scripts/verify_celviz_gpgpu_opencl_host_api_shim.sh

log "gate: verify OpenCL device-info table"
bash scripts/verify_celviz_gpgpu_opencl_device_info_table.sh

log "gate: verify OpenCL build/error-code matrix"
bash scripts/verify_celviz_gpgpu_opencl_build_error_code_matrix.sh

log "gate: verify OpenCL event wait-list/profiling semantics"
bash scripts/verify_celviz_gpgpu_opencl_event_waitlist_profiling.sh

log "gate: verify phase-9 memory object flags/map/sub-buffer semantics"
bash scripts/verify_celviz_gpgpu_phase9_memory_object_flags.sh

log "gate: verify runtime queue semantics"
bash scripts/verify_celviz_gpgpu_runtime_queue_semantics.sh

log "gate: verify OpenCL host-to-RTL CTS-readiness cross-check"
bash scripts/verify_celviz_gpgpu_opencl_rtl_cts_cross_check.sh

log "gate: verify OpenCL C ABI vector-add smoke"
bash scripts/verify_celviz_gpgpu_opencl_c_abi.sh

log "gate: verify executable OpenCL userspace samples"
bash scripts/verify_celviz_gpgpu_opencl_userspace_samples.sh

log "gate: verify OpenCL CTS-oriented smoke manifest"
bash scripts/verify_celviz_gpgpu_opencl_cts_smoke.sh

log "gate: verify OpenCL product gap closure ledger"
bash scripts/verify_celviz_gpgpu_opencl_product_gap_closure.sh

log "gate: verify OpenCL kernel ABI edge cases"
bash scripts/verify_celviz_gpgpu_opencl_kernel_abi_edges.sh

log "gate: verify phase-9 OpenCL conformance-readiness artifacts"
bash scripts/verify_celviz_gpgpu_phase9_opencl_conformance_readiness.sh

log "gate: verify phase-9 memory conformance-readiness artifacts"
bash scripts/verify_celviz_gpgpu_phase9_memory_conformance.sh

log "gate: verify phase-9 driver/OS conformance-readiness artifacts"
bash scripts/verify_celviz_gpgpu_phase9_driver_os.sh

log "gate: verify phase-9 productization/signoff blocker ledger"
bash scripts/verify_celviz_gpgpu_phase9_productization.sh

log "gate: verify reusable Celviz EDA methodology package"
bash scripts/verify_celviz_eda_methodology.sh

log "gate: verify 100% functional/acceptance coverage"
bash scripts/verify_celviz_gpgpu_coverage_100.sh

log "celviz_gpgpu_ip_full_acceptance: pass"
