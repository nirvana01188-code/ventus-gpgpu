#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$root"

log_file="artifacts/rank_01_vivante_3d_gpgpu_ip/verification/test_results.log"
mkdir -p "$(dirname "$log_file")"

{
  echo "celviz_gpgpu_ip_verification: command_matrix"
  echo "  - vector_add"
  echo "  - gemm_convolution_image_filter"
  echo "  - memory_copy"
  echo "  - shader_unit_scaling"
  echo "  - fp16_fp32_paths"
  echo "  - command_submission"
  echo "  - interrupts"
  echo "  - axi_traffic"
  echo "  - throughput_scaling_by_tier"
  echo "  - fp16_proxy_outputs"
  echo "  - runtime_queue_phases"
  echo "  - interrupt_error_reset_tokens"
  echo "  - axi_apb_transaction_counters"
  echo "  - throughput_monotonicity_cues"
  echo "  - source_hook_axi4lite2cta_register_counters"
  echo "  - source_hook_axi4lite2cta_csr_plumbing"
  echo "  - source_hook_cta_scheduler_debug_counters"
  echo "  - source_hook_warp_scheduler_debug_counters"
  echo "  - source_hook_sim_verilator_runtime_proxy_api"
  echo "  - source_hook_tools_runtime_cli_hooks"
  echo "  - source_level_hook_strictness"
  echo "  - source_hook_implementation_files_only"
  echo "  - celviz_gpgpu_source_check"
  echo "  - native_runtime_abi_header"
  echo "  - native_runtime_abi_implementation"
  echo "  - native_runtime_python_bridge"
  echo "  - native_queue_snapshot"
  echo "  - native_pending_count"
  echo "  - native_named_fence"
  echo "  - native_submit_fill"
  echo "  - native_proxy_snapshot"
  echo "  - native_runtime_acceptance"
  echo "  - e1_runtime_command_stream_fixture"
  echo "  - e1_dma_fill_copy_h2d_d2h"
  echo "  - e1_queue_lifecycle_observability"
  echo "  - e1_named_fence_wait_signal"
  echo "  - e1_status_polling_expectations"
  echo "  - e1_expected_error_injection"
  echo "  - e3_native_runtime_build_or_relink"
  echo "  - e3_require_runtime_bind"
  echo "  - e3_native_queue_metric_snapshots"
  echo "  - e4_demo_model_evidence"
  echo "  - e4_kernel_demo_fixture"
  echo "  - e4_vector_add_golden_compare"
  echo "  - e4_gemm_convolution_image_filter"
  echo "  - e4_memory_copy_golden_compare"
  echo "  - e4_fp16_fp32_paths"
  echo "  - e4_tier_scaling"
  echo "  - e4_buffer_bindings"
  echo "  - e4_dispatch_readback_golden_compare"
  echo "  - e5_verification_coverage"
  echo "  - e5_command_submission"
  echo "  - e5_interrupts"
  echo "  - e5_axi_traffic"
  echo "  - e5_reset_behavior"
  echo "  - e5_invalid_descriptors"
  echo "  - e5_dma_bounds_alignment"
  echo "  - e5_tier_throughput_scaling"
  echo "  - optional_present_file_strictness"
  echo
  python3 - <<'PY'
import json
from pathlib import Path

root = Path("artifacts/rank_01_vivante_3d_gpgpu_ip")

def load_json(path):
    return json.loads(path.read_text())

def parse_int(value):
    if isinstance(value, int):
        return value
    return int(str(value), 0)

def in_region(regions, addr, size):
    for region in regions:
        base = parse_int(region["base"])
        end = base + int(region["size"])
        if base <= addr and addr + size <= end:
            return True
    return False

demo = load_json(root / "rtl/control_plane_demo.json")
metrics = load_json(root / "rtl/control_plane_metrics.json")
tiers = load_json(root / "demo/outputs/device_tiers.json")
model_scaling = load_json(root / "model/outputs/shader_unit_scaling.json")

counters = metrics["counters"]
commands = demo["commands"]
regions = demo["memory_regions"]
queue_state = metrics["queue_state"]
tokens = metrics["evidence_tokens"]

errors = []
if metrics.get("status") != "pass":
    errors.append("control_plane_metrics status is not pass")
if counters["commands_submitted"] != len(commands) or counters["commands_completed"] != len(commands):
    errors.append("command submission/completion count does not match command stream")
if any(int(q["submitted"]) != int(q["retired"]) for q in queue_state.values()):
    errors.append("queue submitted/retired counts are not closed")
if counters["completion_interrupts"] <= 0 or counters["error_interrupts"] <= 0:
    errors.append("completion and error interrupt counters must both be non-zero")
if not {"completion", "error"}.issubset({event["kind"] for event in metrics["interrupt_events"]}):
    errors.append("interrupt events must include completion and error kinds")
if not tokens.get("axi_traffic") or counters["axi_read_transactions"] <= 0 or counters["axi_write_transactions"] <= 0:
    errors.append("AXI traffic token and read/write transactions are required")
if not tokens.get("reset_behavior") or counters["resets"] != 1:
    errors.append("reset behavior token and exactly one reset command are required")

negative = [cmd for cmd in commands if cmd.get("expect_error")]
expected_errors = {cmd["expect_error"] for cmd in negative}
if expected_errors != {"ERR_SCHEDULER_FAULT", "ERR_MMU_FAULT", "ERR_FENCE_WAIT"}:
    errors.append("invalid descriptor/error coverage must include scheduler, MMU, and fence errors")

dma_ops = {"dma_fill", "dma_copy", "host_to_device", "device_to_host"}
valid_dma = [cmd for cmd in commands if cmd["opcode"] in dma_ops and not cmd.get("expect_error")]
for cmd in valid_dma:
    size = int(cmd["byte_count"])
    if size <= 0 or size % 16 != 0:
        errors.append(f"DMA command sequence {cmd['sequence']} has invalid size/alignment")
    for key in ("src_addr", "dst_addr"):
        if key in cmd:
            addr = parse_int(cmd[key])
            if addr % 16 != 0 or not in_region(regions, addr, size):
                errors.append(f"DMA command sequence {cmd['sequence']} has out-of-range or unaligned {key}")
mmu_bad = [cmd for cmd in negative if cmd.get("expect_error") == "ERR_MMU_FAULT"]
if not mmu_bad or all(in_region(regions, parse_int(cmd.get("src_addr", "0")), int(cmd.get("byte_count", 0))) for cmd in mmu_bad):
    errors.append("DMA bounds negative path must include an out-of-range MMU descriptor")

runtime_tiers = tiers["tier_scaling"]
if len(runtime_tiers) < 4:
    errors.append("runtime tier scaling must include at least four configured tiers")
for field in ("shader_units_vec1", "fp16_ops_per_cycle", "fp32_ops_per_cycle"):
    values = [int(row[field]) for row in runtime_tiers]
    if values != sorted(values):
        errors.append(f"runtime tier field {field} is not monotonic")
model_rows = sorted(model_scaling["tiers"], key=lambda row: int(row["shader_units_vec1"]))
for field in ("fp16_ops_per_cycle", "fp32_ops_per_cycle"):
    values = [int(row[field]) for row in model_rows]
    if any(values[i] > values[i + 1] for i in range(len(values) - 1)):
        errors.append(f"model tier field {field} is not non-decreasing after shader-unit sort")

if errors:
    print("e5_verification_coverage: fail")
    for error in errors:
        print(f"  - {error}")
    raise SystemExit(1)

print("e5_verification_coverage: pass")
print(f"  - e5_command_submission=pass submitted={counters['commands_submitted']} completed={counters['commands_completed']} queues={len(queue_state)}")
print(f"  - e5_interrupts=pass completion_interrupts={counters['completion_interrupts']} error_interrupts={counters['error_interrupts']}")
print(f"  - e5_axi_traffic=pass read_tx={counters['axi_read_transactions']} write_tx={counters['axi_write_transactions']} bytes_read={counters['bytes_read']} bytes_written={counters['bytes_written']}")
print(f"  - e5_reset_behavior=pass resets={counters['resets']}")
print(f"  - e5_invalid_descriptors=pass expected_errors={','.join(sorted(expected_errors))}")
print(f"  - e5_dma_bounds_alignment=pass valid_dma_commands={len(valid_dma)} negative_mmu_descriptors={len(mmu_bad)}")
print(f"  - e5_tier_throughput_scaling=pass runtime_tiers={len(runtime_tiers)} model_tiers={len(model_rows)}")
PY
  echo
  bash scripts/check_celviz_gpgpu_sources.sh
  echo
  ./scripts/verify_celviz_gpgpu_ip.sh
} 2>&1 | tee "$log_file"
