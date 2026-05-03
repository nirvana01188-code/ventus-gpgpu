#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

bash scripts/check_celviz_gpgpu_boundary.sh

python3 - "$root" <<'PY'
import json
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
ARTIFACT_ROOT = root / "artifacts/rank_01_vivante_3d_gpgpu_ip"

IMPLEMENTATION_SUFFIXES = {".scala", ".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx", ".py"}
FORBIDDEN_EVIDENCE_ROOTS = (
    "docs/celviz-gpu-ip",
    "artifacts/rank_12_vivante_3d_gpu_ip",
)
ACTIVE_IMPLEMENTATION_ROOTS = (
    "ventus/src",
    "sim-verilator",
    "tools/celviz_gpgpu_ip",
    "tools/celviz_eda_methodology",
)
SCRIPT_SOURCE_ROOTS = (
    "scripts",
)

checks = {
    "top_debug_plumbing": (
        root / "ventus/src/top/GPGPU_top.scala",
        [
            r"class\s+CelvizGPGPUDebug\s*\(",
            r"val\s+celviz_debug\s*=\s*Output\s*\(\s*new\s+CelvizGPGPUDebug",
            r"io\.celviz_debug\.cta_scheduler\s*:=\s*cta\.io\.celviz_debug",
            r"io\.celviz_debug\.warp_scheduler\s*\(\s*i\s*\)\s*:=\s*sm_wrapper\s*\(\s*i\s*\)\.celviz_debug(?:\.warp_scheduler)?",
            r"dontTouch\s*\(\s*io\.celviz_debug\s*\)",
        ],
    ),
    "pipe_warp_debug_plumbing": (
        root / "ventus/src/pipeline/pipe.scala",
        [
            r"val\s+celviz_debug\s*=\s*Output\s*\(\s*new\s+(?:CelvizWarpSchedulerDebug|CelvizPipeDebug)",
            r"io\.celviz_debug(?:\.warp_scheduler)?\s*:=\s*warp_sche\.io\.celviz_debug",
            r"dontTouch\s*\(\s*io\.celviz_debug\s*\)",
        ],
    ),
    "axi_control_plane_csr": (
        root / "ventus/src/axi/AXI4Lite2CTA.scala",
        [
            r"commandDoorbellReg",
            r"completionCountReg",
            r"irqPendingReg",
            r"errorStatusReg",
            r"apbAxilReadCountReg",
            r"apbAxilWriteCountReg",
            r"celvizAxiMmioCounter",
        ],
    ),
    "e2_rtl_control_plane_axi_csr_gate": (
        root / "ventus/src/axi/AXI4Lite2CTA.scala",
        [
            r"commandDoorbellReg",
            r"commandCountReg",
            r"commandIdReg",
            r"fenceIdReg",
            r"completionCountReg",
            r"completionStatusReg",
            r"queueDoorbellReg\s*=\s*commandDoorbellReg",
            r"queueDoorbellCountReg",
            r"irqStatusReg",
            r"irqMaskReg",
            r"irqClearReg",
            r"irqPendingReg",
            r"errorStatusReg",
            r"errorCountReg",
            r"apbAxilReadCountReg",
            r"apbAxilWriteCountReg",
            r"apbReadCountReg\s*=\s*apbAxilReadCountReg",
            r"apbWriteCountReg\s*=\s*apbAxilWriteCountReg",
            r"axilReadCountReg\s*=\s*apbAxilReadCountReg",
            r"axilWriteCountReg\s*=\s*apbAxilWriteCountReg",
            r"celvizQueueDoorbellStatus",
            r"celvizQueueDoorbellCounter",
            r"celvizCommandCounter",
            r"celvizCompletionCounter",
            r"celvizIrqCounter",
            r"celvizErrorCounter",
            r"celvizApbReadCounter",
            r"celvizApbWriteCounter",
            r"celvizAxiReadCounter",
            r"celvizAxiWriteCounter",
            r"dontTouch\s*\(\s*celvizQueueDoorbellStatus\s*\)",
            r"dontTouch\s*\(\s*celvizAxiReadCounter\s*\)",
            r"dontTouch\s*\(\s*celvizAxiWriteCounter\s*\)",
        ],
    ),
    "e2_rtl_control_plane_doorbell_irq_error_flow": (
        root / "ventus/src/axi/AXI4Lite2CTA.scala",
        [
            r"irqCommand",
            r"irqCompletion",
            r"irqError",
            r"irqKnownMask",
            r"errDoorbellBusy",
            r"errRspBackpressure",
            r"errInvalidRegAddr",
            r"errReadOnlyWrite",
            r"doorbellPending",
            r"commandAccepted",
            r"proxyDoorbell",
            r"legacyDoorbell",
            r"regs\s*\(\s*completionCountReg\s*\)\s*:=\s*regs\s*\(\s*completionCountReg\s*\)\s*\+\s*1\.U",
            r"regs\s*\(\s*irqStatusReg\s*\)\s*:=\s*regs\s*\(\s*irqStatusReg\s*\)\s*\|\s*irqCompletion",
            r"regs\s*\(\s*irqStatusReg\s*\)\s*:=\s*regs\s*\(\s*irqStatusReg\s*\)\s*\|\s*irqError",
            r"regs\s*\(\s*errorStatusReg\s*\)\s*:=\s*regs\s*\(\s*errorStatusReg\s*\)\s*\|\s*errDoorbellBusy",
            r"regs\s*\(\s*commandCountReg\s*\)\s*:=\s*regs\s*\(\s*commandCountReg\s*\)\s*\+\s*1\.U",
            r"regs\s*\(\s*commandDoorbellReg\s*\)\s*:=\s*doorbellPending\s*\|\s*proxyDoorbell",
            r"regs\s*\(\s*queueDoorbellCountReg\s*\)\s*:=\s*regs\s*\(\s*queueDoorbellCountReg\s*\)\s*\+\s*1\.U",
            r"regs\s*\(\s*errorCountReg\s*\)\s*:=\s*regs\s*\(\s*errorCountReg\s*\)\s*\+\s*celvizErrorEventCount",
            r"regs\s*\(\s*irqCountReg\s*\)\s*:=\s*regs\s*\(\s*irqCountReg\s*\)\s*\+\s*celvizIrqEventCount",
            r"regs\s*\(\s*irqPendingReg\s*\)\s*:=\s*irqPendingBits",
        ],
    ),
    "e2_rtl_control_plane_apb_axi_counter_flow": (
        root / "ventus/src/axi/AXI4Lite2CTA.scala",
        [
            r"regs\s*\(\s*apbAxilWriteCountReg\s*\)\s*:=\s*regs\s*\(\s*apbAxilWriteCountReg\s*\)\s*\+\s*1\.U",
            r"regs\s*\(\s*apbAxilReadCountReg\s*\)\s*:=\s*regs\s*\(\s*apbAxilReadCountReg\s*\)\s*\+\s*1\.U",
            r"celvizAxiReadFire\s*:=\s*true\.B",
            r"celvizAxiWriteFire\s*:=\s*true\.B",
            r"when\s*\(\s*io\.ctl\.ar\.arvalid\s*&&\s*arready\s*\)",
            r"when\s*\(\s*io\.ctl\.w\.wvalid\s*&&\s*wready\s*\)",
            r"dontTouch\s*\(\s*celvizAxiReadFire\s*\)",
            r"dontTouch\s*\(\s*celvizAxiWriteFire\s*\)",
        ],
    ),
    "cta_scheduler_counters": (
        root / "ventus/src/cta/cta_scheduler.scala",
        [
            r"class\s+io_cta_scheduler_celviz_debug",
            r"host_wg_accepted_count",
            r"cu_wf_dispatch_fire_total_count",
            r"alloc_resource_busy_cycle_count",
            r"io\.host_wg_new\.fire",
            r"io\.host_wg_done\.fire",
        ],
    ),
    "e2_scheduler_handoff_counters": (
        root / "ventus/src/cta/cta_scheduler.scala",
        [
            r"class\s+io_cta_scheduler_celviz_debug",
            r"host_wg_accepted_count",
            r"host_wg_done_count",
            r"cu_wf_dispatch_fire_count",
            r"cu_wf_dispatch_fire_total_count",
            r"cu_wf_done_fire_count",
            r"cu_wf_done_fire_total_count",
            r"alloc_resource_busy_cycle_count",
            r"val\s+host_wg_accepted_fire\s*=\s*io\.host_wg_new\.fire",
            r"val\s+host_wg_done_fire\s*=\s*io\.host_wg_done\.fire",
            r"val\s+cu_wf_dispatch_fire\s*=\s*VecInit\s*\(\s*\(\s*0\s+until\s+NUM_CU\s*\)\.map\s*\(\s*i\s*=>\s*io\.cu_wf_new\s*\(\s*i\s*\)\.fire\s*\)\s*\)",
            r"val\s+cu_wf_done_fire\s*=\s*VecInit\s*\(\s*\(\s*0\s+until\s+NUM_CU\s*\)\.map\s*\(\s*i\s*=>\s*io\.cu_wf_done\s*\(\s*i\s*\)\.fire\s*\)\s*\)",
            r"io\.celviz_debug\.host_wg_accepted_count\s*:=\s*eventCounter\s*\(\s*host_wg_accepted_fire\s*\)",
            r"io\.celviz_debug\.cu_wf_dispatch_fire_total_count\s*:=\s*eventCounterBy\s*\(\s*PopCount\s*\(\s*cu_wf_dispatch_fire\s*\)\s*\)",
            r"io\.celviz_debug\.alloc_resource_busy_cycle_count\s*:=\s*eventCounter\s*\(\s*alloc_resource_busy\s*\)",
        ],
    ),
    "e2_rtl_debug_observability_top": (
        root / "ventus/src/top/GPGPU_top.scala",
        [
            r"class\s+CelvizGPGPUDebug\s*\(\s*numSms\s*:\s*Int\s*\)\s+extends\s+Bundle",
            r"val\s+cta_scheduler\s*=\s*new\s+io_cta_scheduler_celviz_debug\s*\(\s*NUMBER_CU\s*\)",
            r"val\s+control\s*=\s*new\s+CelvizGPGPUControlDebug\s*\(\s*numSms\s*\)",
            r"val\s+warp_scheduler\s*=\s*Vec\s*\(\s*numSms\s*,\s*new\s+CelvizWarpSchedulerDebug\s*\)",
            r"val\s+pipe\s*=\s*Vec\s*\(\s*numSms\s*,\s*new\s+CelvizPipeDebug\s*\)",
            r"val\s+celviz_debug\s*=\s*Output\s*\(\s*new\s+CelvizGPGPUDebug\s*\(\s*NSms\s*\)\s*\)",
            r"io\.celviz_debug\.cta_scheduler\s*:=\s*cta\.io\.celviz_debug",
            r"io\.celviz_debug\.control\.host_req_fire\s*:=\s*io\.host_req\.fire",
            r"io\.celviz_debug\.control\.cta_dispatch_fire_mask\s*:=\s*VecInit\s*\(\s*\(\s*0\s+until\s+NUMBER_CU\s*\)\.map\s*\(\s*i\s*=>\s*cta\.io\.CTA2warp\s*\(\s*i\s*\)\.fire\s*\)\s*\)\.asUInt",
            r"io\.celviz_debug\.warp_scheduler\s*\(\s*i\s*\)\s*:=\s*sm_wrapper\s*\(\s*i\s*\)\.celviz_debug\.warp_scheduler",
            r"io\.celviz_debug\.pipe\s*\(\s*i\s*\)\s*:=\s*sm_wrapper\s*\(\s*i\s*\)\.celviz_debug",
            r"dontTouch\s*\(\s*io\.celviz_debug\s*\)",
        ],
    ),
    "e2_rtl_debug_observability_warp": (
        root / "ventus/src/pipeline/warp_schedule.scala",
        [
            r"class\s+CelvizWarpSchedulerDebug\s+extends\s+Bundle",
            r"val\s+celviz_debug\s*=\s*Output\s*\(\s*new\s+CelvizWarpSchedulerDebug\s*\)",
            r"dontTouch\s*\(\s*io\.celviz_debug\s*\)",
            r"warp_accept_event\s*=\s*io\.warpReq\.fire",
            r"branch_flush_event\s*=\s*io\.branch\.fire\s*&\s*io\.branch\.bits\.jump",
            r"scoreboard_blocked_ready_mask\s*=\s*warp_active\s*&\s*io\.scoreboard_busy",
            r"warp_accepted_count\s*=\s*RegInit\s*\(\s*0\.U\s*\(\s*64\.W\s*\)\s*\)",
            r"branch_flush_count\s*=\s*RegInit\s*\(\s*0\.U\s*\(\s*64\.W\s*\)\s*\)",
            r"scoreboard_blocked_ready_mask_cycles\s*=\s*RegInit\s*\(\s*0\.U\s*\(\s*64\.W\s*\)\s*\)",
            r"io\.celviz_debug\.active_mask\s*:=\s*warp_active",
            r"io\.celviz_debug\.ready_mask\s*:=\s*warp_ready",
            r"io\.celviz_debug\.warp_accepted_count\s*:=\s*warp_accepted_count",
            r"io\.celviz_debug\.scoreboard_blocked_ready_mask_cycles\s*:=\s*scoreboard_blocked_ready_mask_cycles",
        ],
    ),
    "warp_scheduler_counters": (
        root / "ventus/src/pipeline/warp_schedule.scala",
        [
            r"class\s+CelvizWarpSchedulerDebug",
            r"warp_accepted_count",
            r"branch_flush_count",
            r"scoreboard_blocked_ready_mask_cycles",
            r"io\.warpReq\.fire",
            r"io\.warpRsp\.valid",
        ],
    ),
    "memory_issue_scoreboard_counters": (
        root / "ventus/src/pipeline/LSU.scala",
        [
            r"class\s+CelvizAddrCalculateDebug",
            r"class\s+CelvizLsuDebug",
            r"dcache_req_fire_count",
            r"shared_req_fire_count",
            r"lsu_rsp_count",
            r"io\.celviz_debug\.addr\s*:=\s*AddrCalc\.io\.celviz_debug",
        ],
    ),
    "issue_counters": (
        root / "ventus/src/pipeline/issue.scala",
        [
            r"class\s+CelvizIssueDebug",
            r"class\s+CelvizIssueV2Debug",
            r"memory_issue_count",
            r"scheduler_issue_count",
            r"input_stall_cycle_count",
        ],
    ),
    "scoreboard_counters": (
        root / "ventus/src/pipeline/scoreboard.scala",
        [
            r"class\s+CelvizScoreboardDebug",
            r"src_hazard_cycle_count",
            r"writeback_hazard_cycle_count",
            r"mem_issue_count",
            r"io\.celviz_debug\.delay\s*:=",
        ],
    ),
    "sim_runtime_proxy_c_api": (
        root / "sim-verilator/celviz_gpgpu_runtime_proxy.h",
        [
            r"celviz_gpgpu_runtime_proxy_attach",
            r"celviz_gpgpu_runtime_proxy_submit_kernel",
            r"celviz_gpgpu_runtime_proxy_submit_copy_h2d",
            r"celviz_gpgpu_runtime_proxy_submit_fill",
            r"celviz_gpgpu_runtime_proxy_step",
            r"celviz_gpgpu_runtime_proxy_get_metrics",
            r"celviz_gpgpu_runtime_proxy_get_queue_snapshot",
            r"celviz_gpgpu_runtime_proxy_get_pending_count",
            r"celviz_gpgpu_runtime_proxy_signal_named_fence",
            r"celviz_gpgpu_runtime_proxy_wait_named_fence",
            r"celviz_gpgpu_runtime_proxy_wait_fence",
        ],
    ),
    "native_runtime_abi_header": (
        root / "sim-verilator/celviz_gpgpu_runtime_proxy.h",
        [
            r"CELVIZ_GPGPU_DLL_PUBLIC\s+bool\s+celviz_gpgpu_runtime_proxy_get_queue_snapshot\s*\(",
            r"CELVIZ_GPGPU_DLL_PUBLIC\s+uint64_t\s+celviz_gpgpu_runtime_proxy_get_pending_count\s*\(",
            r"CELVIZ_GPGPU_DLL_PUBLIC\s+celviz_gpgpu_error_t\s+celviz_gpgpu_runtime_proxy_submit_fill\s*\(",
            r"CELVIZ_GPGPU_DLL_PUBLIC\s+celviz_gpgpu_error_t\s+celviz_gpgpu_runtime_proxy_signal_named_fence\s*\(",
            r"CELVIZ_GPGPU_DLL_PUBLIC\s+celviz_gpgpu_error_t\s+celviz_gpgpu_runtime_proxy_wait_named_fence\s*\(",
            r"celviz_gpgpu_queue_t\*\s+queues",
            r"uint32_t\s+queue_count",
            r"uint64_t\s+fence_waits",
            r"uint64_t\s+fence_signals",
        ],
    ),
    "e5_runtime_proxy_submission_interrupt_axi_reset_abi": (
        root / "sim-verilator/celviz_gpgpu_runtime_proxy.h",
        [
            r"celviz_gpgpu_kernel_descriptor_t",
            r"celviz_gpgpu_buffer_binding_t",
            r"CELVIZ_GPGPU_OPCODE_KERNEL_DISPATCH",
            r"CELVIZ_GPGPU_OPCODE_DMA_COPY",
            r"CELVIZ_GPGPU_OPCODE_DMA_FILL",
            r"CELVIZ_GPGPU_ERROR_BAD_DMA",
            r"CELVIZ_GPGPU_ERROR_MMU_FAULT",
            r"CELVIZ_GPGPU_EVENT_COMMAND_COMPLETE",
            r"CELVIZ_GPGPU_EVENT_COMMAND_ERROR",
            r"celviz_gpgpu_runtime_proxy_submit_kernel\s*\(",
            r"celviz_gpgpu_runtime_proxy_submit_copy_h2d\s*\(",
            r"celviz_gpgpu_runtime_proxy_submit_copy_d2h\s*\(",
            r"celviz_gpgpu_runtime_proxy_submit_fill\s*\(",
            r"celviz_gpgpu_runtime_proxy_reset_queue\s*\(",
            r"celviz_gpgpu_runtime_proxy_inject_next_error\s*\(",
            r"uint64_t\s+commands_submitted",
            r"uint64_t\s+resets",
            r"uint64_t\s+axi_read_transactions",
            r"uint64_t\s+axi_write_transactions",
            r"uint64_t\s+completion_interrupts",
            r"uint64_t\s+error_interrupts",
        ],
    ),
    "e1_queue_lifecycle_status_polling_abi": (
        root / "sim-verilator/celviz_gpgpu_runtime_proxy.h",
        [
            r"CELVIZ_GPGPU_COMMAND_QUEUED",
            r"CELVIZ_GPGPU_COMMAND_SUBMITTED",
            r"CELVIZ_GPGPU_COMMAND_RUNNING",
            r"CELVIZ_GPGPU_COMMAND_COMPLETE",
            r"CELVIZ_GPGPU_COMMAND_ERROR",
            r"uint64_t\s+head",
            r"uint64_t\s+tail",
            r"uint64_t\s+submitted",
            r"uint64_t\s+retired",
            r"uint64_t\s+errors",
            r"celviz_gpgpu_runtime_proxy_get_queue_count\s*\(",
            r"celviz_gpgpu_runtime_proxy_get_queue_snapshot\s*\(",
            r"celviz_gpgpu_runtime_proxy_get_queue_by_id\s*\(",
            r"celviz_gpgpu_runtime_proxy_get_pending_count\s*\(",
            r"celviz_gpgpu_runtime_proxy_get_queue_pending_count\s*\(",
            r"celviz_gpgpu_runtime_proxy_get_command_status\s*\(",
            r"celviz_gpgpu_runtime_proxy_get_last_event\s*\(",
            r"celviz_gpgpu_command_status_is_terminal\s*\(",
        ],
    ),
    "e1_dma_fill_copy_fence_error_metrics_abi": (
        root / "sim-verilator/celviz_gpgpu_runtime_proxy.h",
        [
            r"CELVIZ_GPGPU_OPCODE_DMA_COPY",
            r"CELVIZ_GPGPU_OPCODE_DMA_FILL",
            r"CELVIZ_GPGPU_ERROR_MMU_FAULT",
            r"CELVIZ_GPGPU_ERROR_FENCE_WAIT",
            r"CELVIZ_GPGPU_EVENT_MMU_FAULT",
            r"CELVIZ_GPGPU_EVENT_WATCHDOG",
            r"celviz_gpgpu_runtime_proxy_submit_copy_h2d\s*\(",
            r"celviz_gpgpu_runtime_proxy_submit_copy_d2h\s*\(",
            r"celviz_gpgpu_runtime_proxy_submit_fill\s*\(",
            r"celviz_gpgpu_runtime_proxy_inject_next_error\s*\(",
            r"celviz_gpgpu_runtime_proxy_submit_fault\s*\(",
            r"celviz_gpgpu_runtime_proxy_get_named_fence_value\s*\(",
            r"celviz_gpgpu_runtime_proxy_signal_named_fence\s*\(",
            r"celviz_gpgpu_runtime_proxy_wait_named_fence\s*\(",
            r"uint64_t\s+commands_submitted",
            r"uint64_t\s+commands_completed",
            r"uint64_t\s+commands_failed",
            r"uint64_t\s+dma_copies",
            r"uint64_t\s+dma_fills",
            r"uint64_t\s+fence_waits",
            r"uint64_t\s+fence_signals",
            r"uint64_t\s+bytes_read",
            r"uint64_t\s+bytes_written",
            r"uint64_t\s+bytes_moved",
            r"uint64_t\s+error_interrupts",
            r"uint64_t\s+mmu_faults",
            r"uint64_t\s+queue_errors",
        ],
    ),
    "sim_runtime_proxy_implementation": (
        root / "sim-verilator/ventus_rtlsim.cpp",
        [
            r"extern\s+\"C\"\s+celviz_gpgpu_error_t\s+celviz_gpgpu_runtime_proxy_attach",
            r"ventus_rtlsim_add_kernel",
            r"ventus_rtlsim_pmemcpy_h2d",
            r"ventus_rtlsim_pmemcpy_d2h",
            r"ventus_rtlsim_step",
            r"named_fences",
            r"celviz_gpgpu_runtime_proxy_submit_fill",
            r"celviz_gpgpu_runtime_proxy_get_queue_snapshot",
            r"commands_completed",
        ],
    ),
    "e1_queue_lifecycle_status_polling_implementation": (
        root / "sim-verilator/ventus_rtlsim.cpp",
        [
            r"static\s+void\s+celviz_submit_to_queue\s*\(",
            r"queue->tail\+\+",
            r"queue->doorbell\+\+",
            r"queue->submitted\+\+",
            r"queue->head\+\+",
            r"queue->retired\+\+",
            r"queue->errors\+\+",
            r"static\s+uint64_t\s+celviz_pending_command_count\s*\(",
            r"static\s+uint64_t\s+celviz_pending_command_count_for_queue\s*\(",
            r"static\s+void\s+celviz_mark_submitted_commands_running\s*\(",
            r"CELVIZ_GPGPU_COMMAND_QUEUED",
            r"CELVIZ_GPGPU_COMMAND_RUNNING",
            r"extern\s+\"C\"\s+bool\s+celviz_gpgpu_runtime_proxy_get_queue_snapshot\s*\(",
            r"extern\s+\"C\"\s+bool\s+celviz_gpgpu_runtime_proxy_get_queue_by_id\s*\(",
            r"extern\s+\"C\"\s+uint64_t\s+celviz_gpgpu_runtime_proxy_get_pending_count\s*\(",
            r"extern\s+\"C\"\s+bool\s+celviz_gpgpu_runtime_proxy_get_command_status\s*\(",
            r"extern\s+\"C\"\s+bool\s+celviz_gpgpu_runtime_proxy_get_last_event\s*\(",
        ],
    ),
    "e1_dma_fill_copy_fence_error_metrics_implementation": (
        root / "sim-verilator/ventus_rtlsim.cpp",
        [
            r"extern\s+\"C\"\s+celviz_gpgpu_error_t\s+celviz_gpgpu_runtime_proxy_submit_copy_h2d\s*\(",
            r"extern\s+\"C\"\s+celviz_gpgpu_error_t\s+celviz_gpgpu_runtime_proxy_submit_copy_d2h\s*\(",
            r"extern\s+\"C\"\s+celviz_gpgpu_error_t\s+celviz_gpgpu_runtime_proxy_submit_fill\s*\(",
            r"CELVIZ_GPGPU_OPCODE_DMA_COPY",
            r"CELVIZ_GPGPU_OPCODE_DMA_FILL",
            r"ventus_rtlsim_pmemcpy_h2d\s*\(",
            r"ventus_rtlsim_pmemcpy_d2h\s*\(",
            r"state->metrics\.dma_copies\+\+",
            r"state->metrics\.dma_fills\+\+",
            r"state->metrics\.bytes_read\s*\+=",
            r"state->metrics\.bytes_written\s*\+=",
            r"state->metrics\.bytes_moved\s*\+=",
            r"static\s+bool\s+celviz_take_injected_error\s*\(",
            r"state->inject_next_error",
            r"CELVIZ_GPGPU_ERROR_MMU_FAULT",
            r"state->metrics\.mmu_faults\+\+",
            r"std::unordered_map\s*<\s*std::string\s*,\s*uint64_t\s*>\s+named_fences",
            r"state->named_fences\s*\[\s*fence_name\s*\]\s*=\s*std::max",
            r"while\s*\(\s*state->named_fences\s*\[\s*fence_name\s*\]\s*<\s*fence_value",
            r"state->metrics\.fence_signals\+\+",
            r"state->metrics\.fence_waits\+\+",
            r"CELVIZ_GPGPU_ERROR_FENCE_WAIT",
        ],
    ),
    "e5_runtime_proxy_submission_interrupt_axi_reset_implementation": (
        root / "sim-verilator/ventus_rtlsim.cpp",
        [
            r"celviz_submit_to_queue\s*\(",
            r"queue->doorbell\+\+",
            r"queue->submitted\+\+",
            r"celviz_finish_command\s*\(",
            r"state->metrics\.commands_completed\+\+",
            r"state->metrics\.commands_failed\+\+",
            r"state->metrics\.completion_interrupts\+\+",
            r"state->metrics\.error_interrupts\+\+",
            r"state->metrics\.bytes_read\s*\+=",
            r"state->metrics\.bytes_written\s*\+=",
            r"state->metrics\.bytes_moved\s*\+=",
            r"state->metrics\.resets\+\+",
            r"celviz_gpgpu_runtime_proxy_reset_queue\s*\(",
            r"celviz_gpgpu_runtime_proxy_submit_fault\s*\(",
            r"celviz_take_injected_error\s*\(",
            r"CELVIZ_GPGPU_ERROR_BAD_DMA",
            r"CELVIZ_GPGPU_ERROR_MMU_FAULT",
        ],
    ),
    "native_runtime_abi_implementation": (
        root / "sim-verilator/ventus_rtlsim.cpp",
        [
            r"std::unordered_map\s*<\s*std::string\s*,\s*uint64_t\s*>\s+named_fences",
            r"extern\s+\"C\"\s+bool\s+celviz_gpgpu_runtime_proxy_get_queue_snapshot\s*\(",
            r"\*out_queue\s*=\s*proxy->queues\s*\[\s*queue_index\s*\]",
            r"extern\s+\"C\"\s+uint64_t\s+celviz_gpgpu_runtime_proxy_get_pending_count\s*\(",
            r"celviz_pending_command_count\s*\(\s*celviz_get_state_const\s*\(\s*proxy\s*\)\s*\)",
            r"extern\s+\"C\"\s+celviz_gpgpu_error_t\s+celviz_gpgpu_runtime_proxy_submit_fill\s*\(",
            r"CELVIZ_GPGPU_OPCODE_DMA_FILL",
            r"ventus_rtlsim_pmemcpy_h2d\s*\(\s*proxy->sim\s*,\s*dst\s*,\s*data\.data\s*\(\s*\)\s*,\s*size\s*\)",
            r"extern\s+\"C\"\s+celviz_gpgpu_error_t\s+celviz_gpgpu_runtime_proxy_signal_named_fence\s*\(",
            r"state->named_fences\s*\[\s*fence_name\s*\]\s*=\s*std::max",
            r"extern\s+\"C\"\s+celviz_gpgpu_error_t\s+celviz_gpgpu_runtime_proxy_wait_named_fence\s*\(",
            r"while\s*\(\s*state->named_fences\s*\[\s*fence_name\s*\]\s*<\s*fence_value",
        ],
    ),
    "tools_runtime_command_layer": (
        root / "tools/celviz_gpgpu_ip/runtime_proxy.py",
        [
            r"celviz\.gpgpu\.runtime_commands\.v1",
            r"CELVIZ_GPGPU_RUNTIME_PROXY_MAGIC",
            r"ventus_rtlsim_add_kernel",
            r"celviz_gpgpu_runtime_proxy_submit_fill",
            r"celviz_gpgpu_runtime_proxy_submit_copy_h2d",
            r"native_proxy_snapshot",
            r"runtime_status\.json",
            r"runtime_metrics\.json",
        ],
    ),
    "e1_control_plane_runtime_contract": (
        root / "tools/celviz_gpgpu_ip/control_plane.py",
        [
            r"ERR_MMU_FAULT",
            r"ERR_FENCE_WAIT",
            r"QueueState",
            r"queue\.submit_packet",
            r"queue\.retire_packet",
            r"queue_head",
            r"queue_tail",
            r"expected_error",
            r"error_expected",
            r"validate_expected_error\s*\(",
            r"def\s+handle_dma_fill\s*\(",
            r"def\s+handle_dma_copy\s*\(",
            r"def\s+handle_fence_signal\s*\(",
            r"def\s+handle_fence_wait\s*\(",
            r"INJECT_MMU_FAULT",
            r"queue_state",
            r"completion_records",
            r"interrupt_events",
        ],
    ),
    "e5_control_plane_strict_command_irq_axi_dma_reset_gate": (
        root / "tools/celviz_gpgpu_ip/control_plane.py",
        [
            r"def\s+execute_command\s*\(",
            r"state\.counters\[\s*[\"']commands_submitted[\"']\s*\]\s*\+=\s*1",
            r"queue\.submit_packet\s*\(",
            r"def\s+retire\s*\(",
            r"state\.emit_interrupt\s*\(",
            r"completion_interrupts",
            r"error_interrupts",
            r"def\s+handle_reset\s*\(",
            r"state\.reset_runtime_state\s*\(",
            r"state\.counters\[\s*[\"']resets[\"']\s*\]\s*\+=\s*1",
            r"def\s+handle_dma_fill\s*\(",
            r"byte_count\s*%\s*4",
            r"ERR_BAD_DMA",
            r"def\s+handle_dma_copy\s*\(",
            r"memory_contains\s*\(",
            r"ERR_MMU_FAULT",
            r"def\s+add_axi_read\s*\(",
            r"def\s+add_axi_write\s*\(",
            r"axi_read_transactions",
            r"axi_write_transactions",
            r"queues\[\{index\}\]\.base\s+must\s+be\s+64-byte\s+aligned",
            r"size_bytes\s+must\s+be\s+a\s+power\s+of\s+two",
            r"validate_expected_error\s*\(",
        ],
    ),
    "native_runtime_python_bridge": (
        root / "tools/celviz_gpgpu_ip/runtime_proxy.py",
        [
            r"REQUIRED_SYMBOLS\s*=\s*\(",
            r"\"celviz_gpgpu_runtime_proxy_submit_fill\"",
            r"\"celviz_gpgpu_runtime_proxy_get_queue_snapshot\"",
            r"\"celviz_gpgpu_runtime_proxy_get_pending_count\"",
            r"\"celviz_gpgpu_runtime_proxy_signal_named_fence\"",
            r"\"celviz_gpgpu_runtime_proxy_wait_named_fence\"",
            r"self\.lib\.celviz_gpgpu_runtime_proxy_submit_fill\.argtypes\s*=",
            r"self\.lib\.celviz_gpgpu_runtime_proxy_get_queue_snapshot\.argtypes\s*=",
            r"self\.lib\.celviz_gpgpu_runtime_proxy_get_pending_count\.restype\s*=\s*ctypes\.c_uint64",
            r"self\.lib\.celviz_gpgpu_runtime_proxy_signal_named_fence\.argtypes\s*=",
            r"self\.lib\.celviz_gpgpu_runtime_proxy_wait_named_fence\.argtypes\s*=",
            r"def\s+c_queue_snapshot\s*\(",
        ],
    ),
    "e1_runtime_python_bridge_consistency": (
        root / "tools/celviz_gpgpu_ip/runtime_proxy.py",
        [
            r"CelvizGpgpuRuntimeMetrics",
            r"commands_submitted",
            r"commands_completed",
            r"commands_failed",
            r"dma_copies",
            r"dma_fills",
            r"fence_waits",
            r"fence_signals",
            r"mmu_faults",
            r"queue_errors",
            r"def\s+expected_error_name\s*\(",
            r"def\s+native_result_passed\s*\(",
            r"def\s+native_abi_symbol_coverage\s*\(",
            r"def\s+native_queue_totals\s*\(",
            r"def\s+native_runtime_acceptance\s*\(",
            r"def\s+annotate_native_expected_errors\s*\(",
            r"\"expected_error_passes\"",
            r"\"required_categories\"",
            r"\"missing_categories\"",
            r"\"failed_categories\"",
            r"runtime_metrics\s*\[\s*\"native_runtime_acceptance\"\s*\]\s*=\s*native_acceptance",
            r"\"native_proxy_snapshot\"\s*:\s*native_proxy_snapshot",
            r"status_payload\s*\[\s*\"native_runtime_acceptance\"\s*\]",
            r"status_payload\s*\[\s*\"native_proxy_snapshot\"\s*\]",
            r"INJECT_MMU_FAULT",
        ],
    ),
    "e5_runtime_cli_descriptor_submission_dma_gate": (
        root / "tools/celviz_gpgpu_ip/runtime_proxy.py",
        [
            r"def\s+normalize_commands\s*\(",
            r"command_opcode\s*\(",
            r"unsupported\s+by\s+runtime\s+proxy",
            r"normalize_memory_regions\s*\(",
            r"device_address",
            r"size_bytes",
            r"RuntimeProxyError",
            r"CelvizGpgpuRuntimeMetrics",
            r"resets",
            r"axi_read_transactions",
            r"axi_write_transactions",
            r"completion_interrupts",
            r"error_interrupts",
            r"maybe_request_native_error_injection\s*\(",
            r"celviz_gpgpu_runtime_proxy_inject_next_error",
            r"native_command_results",
            r"native_proxy_snapshot",
        ],
    ),
    "native_runtime_acceptance": (
        root / "tools/celviz_gpgpu_ip/runtime_proxy.py",
        [
            r"native_command_results\s*:\s*List\s*\[\s*Dict\s*\[\s*str\s*,\s*Any\s*\]\s*\]\s*=\s*\[\]",
            r"native_proxy_snapshot\s*:\s*Dict\s*\[\s*str\s*,\s*Any\s*\]\s*=\s*\{\}",
            r"bridge\.lib\.celviz_gpgpu_runtime_proxy_submit_fill\s*\(",
            r"bridge\.lib\.celviz_gpgpu_runtime_proxy_signal_named_fence\s*\(",
            r"bridge\.lib\.celviz_gpgpu_runtime_proxy_wait_named_fence\s*\(",
            r"bridge\.lib\.celviz_gpgpu_runtime_proxy_get_queue_snapshot\s*\(",
            r"bridge\.lib\.celviz_gpgpu_runtime_proxy_get_pending_count\s*\(",
            r"\"native_command_results\"\s*:\s*native_command_results",
            r"\"native_proxy_snapshot\"\s*:\s*native_proxy_snapshot",
            r"\"runtime_bridge\"\s*:\s*bridge_status",
        ],
    ),
    "e6_integration_evidence_tool": (
        root / "tools/celviz_gpgpu_ip/integration_evidence.py",
        [
            r"celviz\.gpgpu\.e6_integration_evidence\.v1",
            r"bandwidth",
            r"latency",
            r"proxy_power",
            r"reset_clock",
            r"security_safety",
            r"non_goals",
            r"perf_model_metrics\.json",
            r"control_plane_metrics\.json",
            r"negative_boundary_evidence\.json",
            r"security_safety_notes\.md",
            r"reset_clock_interrupt\.md",
            r"silicon signoff",
            r"licensed vendor collateral",
            r"def\s+build_payload\s*\(",
        ],
    ),
    "e8_verilator_coverage_report_tool": (
        root / "tools/celviz_gpgpu_ip/verilator_coverage_report.py",
        [
            r"celviz\.gpgpu\.verilator_coverage_report\.v1",
            r"clean-room Verilator/runtime coverage evidence",
            r"no proprietary Vivante compatibility",
            r"parse_lcov_info",
            r"coverage_dat",
            r"coverage_info",
            r"functional_coverage_percent",
            r"feature_bins",
            r"require_functional_100",
            r"pending_count_zero",
        ],
    ),
    "verification_coverage_100_tool": (
        root / "tools/celviz_gpgpu_ip/verification_coverage_100.py",
        [
            r"celviz\.gpgpu\.verification_coverage_100\.v1",
            r"functional_acceptance_verification_bins",
            r"EXPECTED_E1_OPCODES",
            r"EXPECTED_E4_KERNELS",
            r"EXPECTED_E5_CONTROL_FIELDS",
            r"EXPECTED_E8_BINS",
            r"coverage_percent",
            r"rtl_structural_coverage_observation",
            r"--require-100",
        ],
    ),
    "phase2_integration_tool": (
        root / "tools/celviz_gpgpu_ip/phase2_integration.py",
        [
            r"celviz\.gpgpu\.phase2_integration\.v1",
            r"simt_compute_core_path",
            r"opencl_subset_runtime_abi",
            r"memory_system_phase1",
            r"linux_userspace_runtime_proxy",
            r"rtl_verilator_supplemental_phase1",
            r"ppa_proxy_phase1",
            r"--run-focused",
        ],
    ),
    "phase3_cross_layer_tool": (
        root / "tools/celviz_gpgpu_ip/phase3_cross_layer.py",
        [
            r"celviz\.gpgpu\.phase3_cross_layer\.v1",
            r"kernel_set_opencl_runtime_simt_aligned",
            r"kernel_abi_metadata_to_runtime_command",
            r"simt_memory_semantics_aligned",
            r"runtime_os_submission_semantics_aligned",
            r"verification_targets_cover_cross_layer_paths",
            r"ppa_proxy_links_to_cross_layer_scope",
        ],
    ),
    "kernel_lowering_tool": (
        root / "tools/celviz_gpgpu_ip/kernel_lowering.py",
        [
            r"celviz\.gpgpu\.kernel_lowering\.v1",
            r"uop_global_load",
            r"uop_global_store",
            r"uop_alu_mad",
            r"uop_write_completion",
            r"real compiler backend",
        ],
    ),
    "phase4_lowering_integration_tool": (
        root / "tools/celviz_gpgpu_ip/phase4_lowering_integration.py",
        [
            r"celviz\.gpgpu\.phase4_lowering_integration\.v1",
            r"lowering_matches_runtime_dispatch_set",
            r"lowering_matches_simt_workloads",
            r"lowering_covers_memory_ops",
            r"phase3_dependency_pass",
        ],
    ),
    "microop_interpreter_tool": (
        root / "tools/celviz_gpgpu_ip/microop_interpreter.py",
        [
            r"celviz\.gpgpu\.microop_interpreter\.v1",
            r"not a production ISA simulator",
            r"uop_global_load",
            r"uop_global_store",
            r"oracle_hash_match",
            r"memory_trace_non_empty",
        ],
    ),
    "phase5_microop_integration_tool": (
        root / "tools/celviz_gpgpu_ip/phase5_microop_integration.py",
        [
            r"celviz\.gpgpu\.phase5_microop_integration\.v1",
            r"microop_execution_report_pass",
            r"executed_kernel_set_matches_lowering_and_runtime",
            r"oracle_workloads_match_simt_workloads",
            r"microop_memory_trace_links_memory_model",
        ],
    ),
    "compiler_ir_tool": (
        root / "tools/celviz_gpgpu_ip/compiler_ir.py",
        [
            r"celviz\.gpgpu\.compiler_ir\.v1",
            r"virtual_registers",
            r"predicate_registers",
            r"cfg_edges",
            r"def_use",
            r"not SPIR-V",
        ],
    ),
    "phase6_memory_trace_integration_tool": (
        root / "tools/celviz_gpgpu_ip/phase6_memory_trace_integration.py",
        [
            r"celviz\.gpgpu\.phase6_memory_trace_integration\.v1",
            r"input_reports_pass_and_clean_room_scoped",
            r"memory_model_load_store_copy_fill_event_schema_closes",
            r"aggregate_microop_memory_counts_match_report",
            r"proprietary Vivante compatibility claim",
        ],
    ),
    "driver_submission_model_tool": (
        root / "tools/celviz_gpgpu_ip/driver_submission_model.py",
        [
            r"celviz\.gpgpu\.driver_submission_model\.v1",
            r"queue_lifecycle_no_pending",
            r"completion_and_error_paths_present",
            r"kernel_dispatch_set_modeled",
            r"not a Linux",
        ],
    ),
    "synthesis_readiness_tool": (
        root / "tools/celviz_gpgpu_ip/synthesis_readiness.py",
        [
            r"celviz\.gpgpu\.synthesis_readiness\.v1",
            r"tool_unavailable",
            r"debug_observability_hooks_present",
            r"ppa_proxy_present",
            r"not logic synthesis",
        ],
    ),
    "yosys_synthesis_probe_tool": (
        root / "tools/celviz_gpgpu_ip/yosys_synthesis_probe.py",
        [
            r"celviz\.gpgpu\.yosys_synthesis_probe\.v1",
            r"coverage_prefix_sanitizer_executed",
            r"raw_probe_executed",
            r"sanitized_probe_executed",
            r"synthesis_probe_blocked_by_generated_verilog",
            r"not target-library",
        ],
    ),
    "phase7_coalescing_score_tool": (
        root / "tools/celviz_gpgpu_ip/phase7_coalescing_score.py",
        [
            r"celviz\.gpgpu\.phase7_coalescing_score\.v1",
            r"transactions_reduce_for_all_kernels",
            r"aggregate_reduction_positive",
            r"coalescing_efficiency",
            r"not a proprietary cache",
        ],
    ),
    "phase7_config_sweep_tool": (
        root / "tools/celviz_gpgpu_ip/phase7_config_sweep.py",
        [
            r"celviz\.gpgpu\.phase7_config_sweep\.v1",
            r"best_config_by_kernel_present",
            r"area_normalized_perf_proxy_positive",
            r"issue_width",
            r"register_file_banks",
            r"not RTL synthesis",
        ],
    ),
    "phase7_control_flow_manager_tool": (
        root / "tools/celviz_gpgpu_ip/phase7_control_flow_manager.py",
        [
            r"celviz\.gpgpu\.phase7_control_flow_manager\.v1",
            r"dynamic_uop_reduction_positive_for_loop_kernels",
            r"active_mask_evidence_present",
            r"reconvergence_evidence_present",
            r"uop_cf_join",
            r"not a proprietary branch-stack implementation",
        ],
    ),
    "phase7_memory_streaming_tool": (
        root / "tools/celviz_gpgpu_ip/phase7_memory_streaming.py",
        [
            r"celviz\.gpgpu\.phase7_memory_streaming\.v1",
            r"stream_windows_present",
            r"outstanding_slots_present",
            r"projected_scoreboard_wait_reduction_positive",
            r"uop_stream_wait",
            r"not a proprietary LSU/cache/bus implementation",
        ],
    ),
    "phase7_register_occupancy_tool": (
        root / "tools/celviz_gpgpu_ip/phase7_register_occupancy.py",
        [
            r"celviz\.gpgpu\.phase7_register_occupancy\.v1",
            r"peak_vregs_peak_sregs_present",
            r"occupancy_limit_reason_present",
            r"bank_conflict_proxy_present",
            r"SGPR_BUDGET",
            r"not a physical register-file implementation",
        ],
    ),
    "phase7_warp_collectives_tool": (
        root / "tools/celviz_gpgpu_ip/phase7_warp_collectives.py",
        [
            r"celviz\.gpgpu\.phase7_warp_collectives\.v1",
            r"software_sequence_vs_hardware_projection",
            r"collective_vocabulary_projected",
            r"uop_warp_shuffle",
            r"uop_warp_ballot",
            r"not CUDA or OpenCL subgroup conformance",
        ],
    ),
    "opencl_conformance_gap_map_tool": (
        root / "tools/celviz_gpgpu_ip/opencl_conformance_gap_map.py",
        [
            r"celviz\.gpgpu\.opencl_conformance_gap_map\.v1",
            r"OpenCL-like subset evidence only",
            r"not an official OpenCL conformance",
            r"Khronos CTS",
            r"official OpenCL ICD/runtime stack",
        ],
    ),
    "phase8_claim_closure_tool": (
        root / "tools/celviz_gpgpu_ip/phase8_claim_closure.py",
        [
            r"celviz\.gpgpu\.phase8_claim_closure\.v1",
            r"vivante_proprietary_compatibility",
            r"official_opencl_conformance",
            r"production_linux_kernel_drm_driver",
            r"rtl_structural_coverage_100",
            r"signoff_synthesis_sta_power_dft_physical_silicon",
            r"phase7_proxy_not_silicon_performance",
        ],
    ),
    "phase8_work_package_artifacts_tool": (
        root / "tools/celviz_gpgpu_ip/phase8_work_package_artifacts.py",
        [
            r"celviz\.gpgpu\.phase8_work_package_artifacts\.v1",
            r"opencl_negative_tests",
            r"drm_uapi_contract",
            r"structural_coverage_uplift_plan",
            r"signoff_requirements",
            r"phase7_overclaim_scan",
            r"vivante_clean_room_boundary_checklist",
        ],
    ),
    "eda_methodology_manifest_tool": (
        root / "tools/celviz_eda_methodology/verify_methodology_manifest.py",
        [
            r"celviz\.eda_methodology\.verification\.v1",
            r"all_required_sections_present",
            r"functional_structural_boundary_written",
            r"microop_execution_method_written",
            r"no_overclaim_wording_written",
        ],
    ),
    "ppa_proxy_tool": (
        root / "tools/celviz_gpgpu_ip/ppa_proxy.py",
        [
            r"celviz\.gpgpu\.ppa_proxy\.v1",
            r"CC8000L",
            r"CC8000",
            r"area_proxy_units",
            r"frequency_proxy_index",
            r"not a physical synthesis report",
        ],
    ),
}

script_checks = {
    "e3_native_runtime_build_script_manifest_log_source": (
        root / "scripts/build_celviz_gpgpu_runtime.sh",
        [
            r"build_root=\"\$\{CELVIZ_GPGPU_BUILD_ROOT:-/tmp/ventus-gpgpu-celviz-build\}\"",
            r"usage:\s+scripts/build_celviz_gpgpu_runtime\.sh\s+\[--auto\|--fast-relink\|--full\]",
            r"sync_workspace\s*\(\)",
            r"rsync\s+-a\s+--delete",
            r"have_verilated_core\s*\(\)",
            r"fast_relink\s*\(\)",
            r"full_build\s*\(\)",
            r"find\s+\"\$build_root/sim-verilator/build/libVentusRTL\"\s+-path\s+'\*/libVentusRTL\.so'",
            r"native runtime build did not produce libVentusRTL\.so",
            r"printf\s+'CELVIZ_GPGPU_RUNTIME_LIB=%s\\n'",
        ],
    ),
    "e3_acceptance_native_build_manifest_log_gate": (
        root / "scripts/accept_celviz_gpgpu_ip.sh",
        [
            r"e3_native_runtime_build_manifest_log",
            r"native_runtime_build\.log",
            r"e3_native_runtime_build_manifest\.json",
            r"CELVIZ_GPGPU_RUNTIME_LIB=",
            r"exported_symbols",
            r"missing_exported_symbols",
            r"subprocess\.run\s*\(\s*\[\"nm\"",
            r"libVentusRTL\.so",
        ],
    ),
    "e3_acceptance_native_require_runtime_snapshot_gate": (
        root / "scripts/accept_celviz_gpgpu_ip.sh",
        [
            r"e3_native_runtime_output_check",
            r"runtime_metrics\.json",
            r"runtime_status\.json",
            r"native_proxy_snapshot",
            r"native_runtime_acceptance",
            r"abi_symbol_coverage",
            r"optional_present_symbols",
            r"queue_totals",
            r"pending_count",
            r"native_command_results",
            r"pending count is not zero",
        ],
    ),
    "e4_acceptance_demo_model_output_gate": (
        root / "scripts/accept_celviz_gpgpu_ip.sh",
        [
            r"e4_demo_model_output_check",
            r"e4_kernel_demo_fixture",
            r"e4_kernel_demo\.json",
            r"kernel_demo_outputs",
            r"buffer_binds\.json",
            r"queue_trace\.json",
            r"device_tiers\.json",
            r"convolution_proxy",
            r"fp16_proxy",
            r"readback_sha256",
            r"golden",
        ],
    ),
    "e5_acceptance_strict_control_runtime_gate": (
        root / "scripts/accept_celviz_gpgpu_ip.sh",
        [
            r"e5_demo=\"\$artifact_root/rtl/e5_verification_demo\.json\"",
            r"e5_verification_coverage",
            r"e5_verification_output_check",
            r"command_submission",
            r"interrupt_clears",
            r"invalid_descriptors",
            r"dma_bounds_errors",
            r"dma_alignment_errors",
            r"throughput_tier_link",
            r"ERR_BAD_DMA",
            r"ERR_UNSUPPORTED_OPCODE",
        ],
    ),
    "e5_verification_strict_evidence_gate": (
        root / "scripts/verify_celviz_gpgpu_ip.sh",
        [
            r"e5_command_submission_strict",
            r"e5_interrupt_reset_axi_strict",
            r"e5_illegal_descriptor_negative_paths",
            r"e5_dma_bounds_alignment",
            r"e5_tier_throughput_monotonicity",
            r"e5_verification_demo\.json",
            r"ERR_SCHEDULER_FAULT",
            r"ERR_BAD_DMA",
            r"dma_bounds_errors",
            r"dma_alignment_errors",
            r"throughput_monotonicity_cues",
        ],
    ),
    "e6_verification_integration_evidence_gate": (
        root / "scripts/verify_celviz_gpgpu_ip.sh",
        [
            r"e6_integration_evidence_gate",
            r"bandwidth_latency_power\.md",
            r"reset_clock_interrupt\.md",
            r"security_safety_notes\.md",
            r"perf_model_metrics\.json",
            r"bandwidth_latency_power_proxy",
            r"reset_clock_assumptions",
            r"security_safety_notes",
            r"explicit_non_goals",
            r"no_silicon_signoff_claim",
        ],
    ),
    "e6_acceptance_integration_evidence_gate": (
        root / "scripts/accept_celviz_gpgpu_ip.sh",
        [
            r"tools/celviz_gpgpu_ip/integration_evidence\.py",
            r"e6_integration_evidence",
            r"e6_integration_output_check",
            r"e6_integration_evidence\.json",
            r"bandwidth_latency_power\.md",
            r"reset_clock_interrupt\.md",
            r"security_safety_notes\.md",
            r"perf_model_metrics\.json",
            r"bandwidth/latency/power proxy",
            r"reset/clock/interrupt assumptions",
            r"security/safety functional proxy boundary",
            r"explicit non-goals and no silicon signoff",
        ],
    ),
    "e8_coverage_run_script": (
        root / "scripts/run_celviz_gpgpu_verilator_coverage.sh",
        [
            r"VLIB_COVERAGE=1",
            r"CELVIZ_GPGPU_COVERAGE_FILE",
            r"verilator_coverage\s+--write-info",
            r"verilator_coverage\s+--annotate",
            r"verilator_coverage_report\.py",
            r"--require-functional-100",
            r"functional_bins_gate=100%",
            r"rtl_line_toggle_coverage_claim=not_claimed",
        ],
    ),
    "e8_coverage_verify_script": (
        root / "scripts/verify_celviz_gpgpu_verilator_coverage.sh",
        [
            r"verilator_coverage_report\.json",
            r"report/dut\.v",
            r"functional_coverage_percent",
            r"feature_bins",
            r"require_functional_100",
            r"functional_bins_gate=100%",
            r"rtl_line_toggle_coverage_claim=not_claimed",
            r"clean-room no-overclaim boundary token",
        ],
    ),
    "e8_full_acceptance_wrapper": (
        root / "scripts/accept_celviz_gpgpu_ip_full.sh",
        [
            r"scripts/accept_celviz_gpgpu_ip\.sh",
            r"scripts/run_celviz_gpgpu_verilator_coverage\.sh",
            r"scripts/verify_celviz_gpgpu_verilator_coverage\.sh",
            r"scripts/verify_celviz_gpgpu_phase2\.sh",
            r"scripts/verify_celviz_gpgpu_phase3\.sh",
            r"scripts/verify_celviz_gpgpu_phase4\.sh",
            r"scripts/verify_celviz_gpgpu_phase5\.sh",
            r"scripts/verify_celviz_gpgpu_phase6\.sh",
            r"scripts/verify_celviz_gpgpu_phase7_coalescing\.sh",
            r"scripts/verify_celviz_gpgpu_coverage_100\.sh",
            r"--rerun-e8",
            r"e8_mode=",
            r"celviz_gpgpu_ip_full_acceptance: pass",
        ],
    ),
    "verification_coverage_100_script": (
        root / "scripts/verify_celviz_gpgpu_coverage_100.sh",
        [
            r"verification_coverage_100\.json",
            r"verification_coverage_100\.py",
            r"--require-100",
            r"RTL structural Verilator line/toggle/source metrics are kept",
        ],
    ),
    "phase2_verification_script": (
        root / "scripts/verify_celviz_gpgpu_phase2.sh",
        [
            r"phase2_integration_report\.json",
            r"phase2_integration\.py",
            r"--run-focused",
            r"SIMT compute path",
            r"OpenCL subset ABI",
            r"memory system",
            r"Linux userspace runtime proxy",
        ],
    ),
    "phase3_verification_script": (
        root / "scripts/verify_celviz_gpgpu_phase3.sh",
        [
            r"phase3_cross_layer_report\.json",
            r"phase3_cross_layer\.py",
            r"OpenCL-like kernel ABI",
            r"runtime command",
            r"SIMT execution",
            r"memory semantics",
        ],
    ),
    "kernel_lowering_script": (
        root / "scripts/verify_celviz_gpgpu_kernel_lowering.sh",
        [
            r"kernel_lowering\.py",
            r"output_dir=\"artifacts/rank_01_vivante_3d_gpgpu_ip/lowering\"",
            r"not a production compiler backend",
        ],
    ),
    "phase4_verification_script": (
        root / "scripts/verify_celviz_gpgpu_phase4.sh",
        [
            r"verify_celviz_gpgpu_kernel_lowering\.sh",
            r"phase4_lowering_integration\.py",
        ],
    ),
    "microop_execution_script": (
        root / "scripts/verify_celviz_gpgpu_microop_execution.sh",
        [
            r"microop_interpreter\.py",
            r"output_dir=\"\$artifact_root/microop_execution\"",
            r"not a production ISA simulator",
        ],
    ),
    "phase5_verification_script": (
        root / "scripts/verify_celviz_gpgpu_phase5.sh",
        [
            r"verify_celviz_gpgpu_phase4\.sh",
            r"verify_celviz_gpgpu_microop_execution\.sh",
            r"phase5_microop_integration\.py",
        ],
    ),
    "compiler_ir_script": (
        root / "scripts/verify_celviz_gpgpu_compiler_ir.sh",
        [
            r"compiler_ir\.py",
        ],
    ),
    "phase6_memory_script": (
        root / "scripts/verify_celviz_gpgpu_phase6_memory.sh",
        [
            r"phase6_memory_trace_integration\.py",
        ],
    ),
    "driver_submission_script": (
        root / "scripts/verify_celviz_gpgpu_driver_submission.sh",
        [
            r"driver_submission_model\.py",
        ],
    ),
    "synthesis_readiness_script": (
        root / "scripts/verify_celviz_gpgpu_synthesis_readiness.sh",
        [
            r"synthesis_readiness\.py",
        ],
    ),
    "yosys_synthesis_probe_script": (
        root / "scripts/verify_celviz_gpgpu_yosys_synthesis_probe.sh",
        [
            r"yosys_synthesis_probe\.py",
            r"--timeout-s",
            r"not target-library",
        ],
    ),
    "phase7_coalescing_script": (
        root / "scripts/verify_celviz_gpgpu_phase7_coalescing.sh",
        [
            r"phase7_coalescing_score\.py",
        ],
    ),
    "phase7_config_sweep_script": (
        root / "scripts/verify_celviz_gpgpu_phase7_config_sweep.sh",
        [
            r"phase7_config_sweep\.py",
        ],
    ),
    "phase7_control_flow_manager_script": (
        root / "scripts/verify_celviz_gpgpu_phase7_control_flow_manager.sh",
        [
            r"phase7_control_flow_manager\.py",
        ],
    ),
    "phase7_memory_streaming_script": (
        root / "scripts/verify_celviz_gpgpu_phase7_memory_streaming.sh",
        [
            r"phase7_memory_streaming\.py",
        ],
    ),
    "phase7_register_occupancy_script": (
        root / "scripts/verify_celviz_gpgpu_phase7_register_occupancy.sh",
        [
            r"phase7_register_occupancy\.py",
        ],
    ),
    "phase7_warp_collectives_script": (
        root / "scripts/verify_celviz_gpgpu_phase7_warp_collectives.sh",
        [
            r"phase7_warp_collectives\.py",
        ],
    ),
    "opencl_conformance_gap_map_script": (
        root / "scripts/verify_celviz_gpgpu_opencl_conformance_gap_map.sh",
        [
            r"opencl_conformance_gap_map\.py",
            r"not an official OpenCL conformance claim",
            r"gap map",
        ],
    ),
    "phase8_claim_closure_script": (
        root / "scripts/verify_celviz_gpgpu_phase8_claim_closure.sh",
        [
            r"phase8_claim_closure\.py",
            r"not proprietary Vivante compatibility",
            r"not official OpenCL conformance",
            r"not a production Linux DRM driver",
            r"not RTL structural coverage closure",
            r"not synthesis/STA/power/DFT/physical/silicon signoff",
            r"not silicon performance",
        ],
    ),
    "phase8_work_packages_script": (
        root / "scripts/verify_celviz_gpgpu_phase8_work_packages.sh",
        [
            r"phase8_work_package_artifacts\.py",
            r"OpenCL subset negative",
            r"DRM-like UAPI contract",
            r"RTL structural coverage uplift plan",
            r"Phase7 overclaim scan",
            r"does not claim completion",
        ],
    ),
    "opencl_host_api_shim_script": (
        root / "scripts/verify_celviz_gpgpu_opencl_host_api_shim.sh",
        [
            r"opencl_host_api_shim\.py",
            r"clGetPlatformIDs",
            r"clEnqueueNDRangeKernel",
            r"Negative Error-Code Tests",
            r"not official OpenCL conformance",
        ],
    ),
    "phase9_opencl_conformance_readiness_script": (
        root / "scripts/verify_celviz_gpgpu_phase9_opencl_conformance_readiness.sh",
        [
            r"phase9_opencl_conformance_readiness\.py",
            r"CTS-oriented matrix",
            r"OpenCL subset positive/negative tests",
            r"ICD/runtime host API",
            r"not claim Khronos CTS pass",
            r"not official OpenCL conformance",
        ],
    ),
    "phase9_memory_conformance_script": (
        root / "scripts/verify_celviz_gpgpu_phase9_memory_conformance.sh",
        [
            r"phase9_memory_conformance_gate\.py",
            r"phase9_memory_conformance_readiness_gate\.json",
            r"Phase 9 Memory Conformance Gates",
            r"Official conformance claim",
            r"global",
            r"atomics",
        ],
    ),
    "phase9_driver_os_script": (
        root / "scripts/verify_celviz_gpgpu_phase9_driver_os.sh",
        [
            r"phase9_driver_os_conformance\.py",
            r"Phase-9 driver/OS",
            r"DRM-like submission",
            r"OpenCL-like queue semantics",
        ],
    ),
    "phase9_productization_script": (
        root / "scripts/verify_celviz_gpgpu_phase9_productization.sh",
        [
            r"phase9_productization_gates\.py",
            r"PYTHONDONTWRITEBYTECODE=1",
        ],
    ),
    "eda_methodology_script": (
        root / "scripts/verify_celviz_eda_methodology.sh",
        [
            r"verify_methodology_manifest\.py",
        ],
    ),
    "phase6_verification_script": (
        root / "scripts/verify_celviz_gpgpu_phase6.sh",
        [
            r"verify_celviz_gpgpu_compiler_ir\.sh",
            r"verify_celviz_gpgpu_phase6_memory\.sh",
            r"verify_celviz_gpgpu_driver_submission\.sh",
            r"verify_celviz_gpgpu_synthesis_readiness\.sh",
            r"verify_celviz_gpgpu_yosys_synthesis_probe\.sh",
            r"verify_celviz_eda_methodology\.sh",
            r"celviz_gpgpu_phase6: pass",
        ],
    ),
    "ppa_proxy_script": (
        root / "scripts/verify_celviz_gpgpu_ppa_proxy.sh",
        [
            r"ppa_proxy_report\.json",
            r"ppa_proxy\.py",
            r"not logic synthesis",
            r"timing closure",
        ],
    ),
    "e8_acceptance_pycompile_gate": (
        root / "scripts/accept_celviz_gpgpu_ip.sh",
        [
            r"python_py_compile",
            r"tools/celviz_gpgpu_ip/verilator_coverage_report\.py",
            r"tools/celviz_gpgpu_ip/verification_coverage_100\.py",
            r"tools/celviz_gpgpu_ip/phase2_integration\.py",
            r"tools/celviz_gpgpu_ip/phase3_cross_layer\.py",
            r"tools/celviz_gpgpu_ip/phase4_lowering_integration\.py",
            r"tools/celviz_gpgpu_ip/phase5_microop_integration\.py",
            r"tools/celviz_gpgpu_ip/kernel_lowering\.py",
            r"tools/celviz_gpgpu_ip/microop_interpreter\.py",
            r"tools/celviz_gpgpu_ip/ppa_proxy\.py",
            r"tools/celviz_gpgpu_ip/simt_execution_model\.py",
            r"tools/celviz_gpgpu_ip/opencl_subset\.py",
            r"tools/celviz_gpgpu_ip/memory_model\.py",
            r"tools/celviz_gpgpu_ip/linux_runtime_proxy\.py",
            r"tools/celviz_gpgpu_ip/verify_linux_runtime_proxy\.py",
            r"scripts/tools/artifacts/celviz_gpgpu_verilator_supplemental_phase1\.py",
        ],
    ),
}

errors = []
for name, (path, patterns) in checks.items():
    if not path.exists():
        errors.append(f"{name}: missing {path.relative_to(root)}")
        continue
    rel_path = path.relative_to(root)
    rel_string = rel_path.as_posix()
    if any(rel_string == prefix or rel_string.startswith(prefix + "/") for prefix in FORBIDDEN_EVIDENCE_ROOTS):
        errors.append(f"{name}: forbidden_rank12_evidence_path {rel_path}")
        continue
    if not any(rel_string == prefix or rel_string.startswith(prefix + "/") for prefix in ACTIVE_IMPLEMENTATION_ROOTS):
        errors.append(f"{name}: outside_active_gpgpu_implementation_root {rel_path}")
        continue
    if path.suffix not in IMPLEMENTATION_SUFFIXES or "docs" in rel_path.parts or "verification" in rel_path.parts:
        errors.append(f"{name}: non-implementation evidence path {rel_path}")
        continue
    text = path.read_text(encoding="utf-8", errors="replace")
    missing = [pat for pat in patterns if re.search(pat, text, re.MULTILINE) is None]
    if missing:
        errors.append(f"{name}: missing patterns {missing} in {path.relative_to(root)}")

for name, (path, patterns) in script_checks.items():
    if not path.exists():
        errors.append(f"{name}: missing {path.relative_to(root)}")
        continue
    rel_path = path.relative_to(root)
    rel_string = rel_path.as_posix()
    if any(rel_string == prefix or rel_string.startswith(prefix + "/") for prefix in FORBIDDEN_EVIDENCE_ROOTS):
        errors.append(f"{name}: forbidden_rank12_evidence_path {rel_path}")
        continue
    if not any(rel_string == prefix or rel_string.startswith(prefix + "/") for prefix in SCRIPT_SOURCE_ROOTS):
        errors.append(f"{name}: outside_script_source_root {rel_path}")
        continue
    if path.suffix not in {".sh"}:
        errors.append(f"{name}: non-shell-script source path {rel_path}")
        continue
    text = path.read_text(encoding="utf-8", errors="replace")
    missing = [pat for pat in patterns if re.search(pat, text, re.MULTILINE) is None]
    if missing:
        errors.append(f"{name}: missing patterns {missing} in {path.relative_to(root)}")

def load_json(name, relative_path):
    path = ARTIFACT_ROOT / relative_path
    if not path.exists():
        errors.append(f"{name}: missing {path.relative_to(root)}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"{name}: invalid JSON in {path.relative_to(root)}: {exc}")
        return {}


def load_optional_json(name, relative_path):
    path = ARTIFACT_ROOT / relative_path
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"{name}: invalid JSON in {path.relative_to(root)}: {exc}")
        return {}


def load_text(name, relative_path):
    path = ARTIFACT_ROOT / relative_path
    if not path.exists():
        errors.append(f"{name}: missing {path.relative_to(root)}")
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        errors.append(f"{name}: empty {path.relative_to(root)}")
    return text


def require_e6(condition, message):
    if not condition:
        errors.append(f"e6_integration_evidence: {message}")


def forbidden_silicon_claims(text):
    forbidden = []
    pattern = re.compile(
        r"\b(?:silicon\s+(?:signoff|ppa)|tapeout\s+readiness|tapeout\s+ready|"
        r"foundry-ready|cdc/sta|sta/cdc|dft\s+closure|timing\s+signoff)\b"
        r".{0,96}\b(?:pass|passed|complete|closed|proven|ready|certified|claimed?)\b",
        re.IGNORECASE | re.DOTALL,
    )
    negation = re.compile(
        r"\b(?:not|no|without|unproven|forbidden|outside|does\s+not|do\s+not|"
        r"must\s+not|remain\s+unproven|does\s+not\s+satisfy)\b",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        window = text[max(0, match.start() - 140): match.end() + 40]
        if not negation.search(window):
            forbidden.append(" ".join(match.group(0).split()))
    return forbidden


def validate_e6_integration_evidence():
    integration_dir = ARTIFACT_ROOT / "integration"
    readme = load_text("e6_integration_readme", Path("integration/README.md"))
    bandwidth = load_text("e6_bandwidth_latency_power_doc", Path("integration/bandwidth_latency_power.md"))
    reset_clock = load_text("e6_reset_clock_interrupt_doc", Path("integration/reset_clock_interrupt.md"))
    security = load_text("e6_security_safety_notes_doc", Path("integration/security_safety_notes.md"))
    perf_log = load_text("e6_perf_model_run_log", Path("integration/perf_model_run.log"))
    gate_path = root / "docs/celviz-gpgpu-ip/S5_INTEGRATION_GATE.md"
    if gate_path.exists():
        gate_text = gate_path.read_text(encoding="utf-8", errors="replace")
    else:
        errors.append(f"e6_integration_gate_doc: missing {gate_path.relative_to(root)}")
        gate_text = ""
    perf_metrics = load_json("e6_perf_model_metrics", Path("integration/perf_model_metrics.json"))

    combined = "\n".join([readme, bandwidth, reset_clock, security, gate_text, perf_log])
    combined_lower = combined.lower()

    require_e6((integration_dir / "README.md").exists(), "integration README is missing")
    require_e6("bandwidth" in bandwidth.lower() and "latency" in bandwidth.lower() and "power" in bandwidth.lower(), "bandwidth/latency/power doc lacks required proxy topics")
    for token in (
        "bandwidth_bytes_per_cycle",
        "latency_proxy_cycles",
        "aggregate_power_index_proxy",
        "tier_validation_check name=power_proxy_monotonic pass=true",
    ):
        require_e6(token.lower() in (bandwidth + "\n" + perf_log).lower(), f"missing proxy token {token}")

    require_e6("reset_asserted" in reset_clock and "queue_idle_after_reset" in reset_clock, "reset assumptions are not explicit")
    require_e6("clock_model=single_proxy_clock" in reset_clock, "single proxy clock assumption is missing")
    require_e6("clock_cycles_elapsed" in reset_clock or "timestamp_delta_us" in reset_clock, "clock timing evidence units are not listed")

    require_e6("non-goals" in security.lower() or "does not claim" in security.lower(), "security/safety non-goals are not explicit")
    for token in ("security", "safety", "certification", "functional proxy", "not as security certification"):
        require_e6(token in security.lower(), f"security/safety note missing {token}")

    for token in (
        "not allowed",
        "does not claim",
        "not measured rtl",
        "not silicon ppa",
        "not api conformance",
        "not a silicon signoff plan",
    ):
        require_e6(token in combined_lower, f"explicit non-goal/caveat missing {token}")

    forbidden = forbidden_silicon_claims(combined)
    require_e6(not forbidden, f"possible silicon signoff claim: {forbidden[:3]}")

    require_e6(perf_metrics.get("schema") == "celviz.gpgpu.proxy_perf_model.v1", "perf model schema mismatch")
    require_e6(perf_metrics.get("status") == "pass", "perf model status is not pass")
    assumptions = perf_metrics.get("assumptions", {})
    claim_boundary = str(assumptions.get("claim_boundary", "")).lower()
    clock_model = str(assumptions.get("clock_model", "")).lower()
    require_e6("proxy model only" in claim_boundary and "not silicon ppa" in claim_boundary, "perf claim boundary is incomplete")
    require_e6("no frequency" in clock_model and "timing closure" in clock_model, "perf clock assumption is incomplete")
    require_e6(bool(assumptions.get("activity_weights")), "power proxy activity weights are missing")

    tier_validation = perf_metrics.get("tier_validation", {})
    checks = {str(item.get("name")): item for item in tier_validation.get("checks", []) if isinstance(item, dict)}
    for name in (
        "minimum_three_tiers_selected",
        "axi_byte_pressure_fields_present",
        "axi_byte_pressure_monotonic",
        "latency_proxy_monotonic",
        "power_proxy_monotonic",
    ):
        require_e6(checks.get(name, {}).get("pass") is True, f"tier validation check missing/pass=false: {name}")
    selected_tiers = tier_validation.get("selected_tiers", [])
    require_e6(isinstance(selected_tiers, list) and len(selected_tiers) >= 3, "selected tier count is below 3")
    require_e6(len(perf_metrics.get("estimates", [])) > 0, "perf estimates are missing")


def require_e4(condition, message):
    if not condition:
        errors.append(f"e4_demo_model_evidence: {message}")


def nonempty_sha(value):
    return isinstance(value, str) and len(value) >= 32


def int_field(mapping, field, default=0):
    try:
        value = mapping.get(field, default)
        if isinstance(value, str):
            return int(value, 0)
        return int(value)
    except Exception:
        return default


def result_digest(output):
    return output.get("result_sha256") or output.get("hashes", {}).get("result_sha256")


kernel_demo = load_json("e4_kernel_demo_fixture", Path("demo/kernel_demo.json"))
summary = load_json("e4_demo_summary", Path("demo/outputs/summary.json"))
kernel_metrics = load_json("e4_demo_kernel_metrics", Path("demo/outputs/kernel_metrics.json"))
buffer_binds = load_json("e4_demo_buffer_binds", Path("demo/outputs/buffer_binds.json"))
device_tiers = load_json("e4_demo_device_tiers", Path("demo/outputs/device_tiers.json"))
queue_trace = load_json("e4_demo_queue_trace", Path("demo/outputs/queue_trace.json"))
demo_outputs = {
    "vector_add": load_json("e4_demo_vector_add", Path("demo/outputs/vector_add.json")),
    "gemm_proxy": load_json("e4_demo_gemm", Path("demo/outputs/gemm_proxy.json")),
    "image_filter": load_json("e4_demo_image_filter", Path("demo/outputs/image_filter.json")),
    "memory_copy": load_json("e4_demo_memory_copy", Path("demo/outputs/memory_copy.json")),
}
optional_convolution_demo = load_optional_json("e4_demo_convolution", Path("demo/outputs/convolution_proxy.json"))
if optional_convolution_demo is not None:
    demo_outputs["convolution_proxy"] = optional_convolution_demo
model_metrics = load_json("e4_model_metrics", Path("model/metrics.json"))
model_outputs = {
    "vector_add": load_json("e4_model_vector_add", Path("model/outputs/vector_add.json")),
    "gemm_proxy": load_json("e4_model_gemm", Path("model/outputs/gemm_proxy.json")),
    "convolution_proxy": load_json("e4_model_convolution", Path("model/outputs/convolution_proxy.json")),
    "memory_copy": load_json("e4_model_memory_copy", Path("model/outputs/memory_copy.json")),
    "shader_unit_scaling": load_json("e4_model_shader_unit_scaling", Path("model/outputs/shader_unit_scaling.json")),
}
control_demo = load_json("e5_control_plane_demo", Path("rtl/control_plane_demo.json"))
control_metrics = load_json("e5_control_plane_metrics", Path("rtl/control_plane_metrics.json"))
validate_e6_integration_evidence()


def require_e5(condition, message):
    if not condition:
        errors.append(f"e5_strict_gate_evidence: {message}")


def e5_contains_region(regions, address, byte_count, *, write):
    if byte_count < 0:
        return False
    for region in regions:
        base = int_field(region, "base", 0)
        size = int_field(region, "size", int_field(region, "size_bytes", 0))
        readable = bool(region.get("readable", True))
        writable = bool(region.get("writable", True))
        if write and not writable:
            continue
        if not write and not readable:
            continue
        if base <= address and address + byte_count <= base + size:
            return True
    return False


e5_commands = control_demo.get("commands", [])
e5_queues = {int_field(queue, "queue_id", -1): queue for queue in control_demo.get("queues", [])}
e5_regions = control_demo.get("memory_regions", [])
require_e5(control_demo.get("schema") == "celviz.gpgpu.control_plane_demo.v1", "control_plane_demo schema mismatch")
require_e5(isinstance(e5_commands, list) and len(e5_commands) >= 16, "control_plane_demo command stream is too small")
e5_opcodes = {str(command.get("opcode")) for command in e5_commands}
for opcode in (
    "reset",
    "dma_fill",
    "dma_copy",
    "host_to_device",
    "device_to_host",
    "kernel_dispatch",
    "fence_signal",
    "fence_wait",
    "counter_snapshot",
    "set_scheduler_config",
    "set_shader_mode",
):
    require_e5(opcode in e5_opcodes, f"control_plane_demo missing opcode {opcode}")
e5_sequences = [int_field(command, "sequence", -1) for command in e5_commands]
require_e5(e5_sequences == sorted(set(e5_sequences)), "command sequences are not unique and increasing")
require_e5(e5_commands and e5_commands[0].get("opcode") == "reset", "command stream does not begin with reset")
for queue_id, queue in e5_queues.items():
    base = int_field(queue, "base", 0)
    size = int_field(queue, "size_bytes", 0)
    require_e5(queue_id >= 0, "queue_id missing")
    require_e5(base % 64 == 0, f"queue {queue_id} base is not 64-byte aligned")
    require_e5(size >= 4096 and size & (size - 1) == 0, f"queue {queue_id} ring size is not power-of-two >= 4096")
for command in e5_commands:
    opcode = str(command.get("opcode"))
    queue_id = int_field(command, "queue_id", -1)
    require_e5(queue_id in e5_queues, f"command {command.get('sequence')} references unknown queue {queue_id}")
    if opcode in {"dma_fill", "dma_copy", "host_to_device", "device_to_host"}:
        byte_count = int_field(command, "byte_count", 0)
        require_e5(byte_count > 0, f"{opcode} command {command.get('sequence')} byte_count is not positive")
        require_e5(byte_count % 4 == 0, f"{opcode} command {command.get('sequence')} byte_count is not 4-byte aligned")
        if "src_addr" in command:
            src = int_field(command, "src_addr", 0)
            require_e5(src % 4 == 0, f"{opcode} command {command.get('sequence')} src_addr is not 4-byte aligned")
            if command.get("expect_error") is None:
                require_e5(e5_contains_region(e5_regions, src, byte_count, write=False), f"{opcode} source is outside readable memory")
        if "dst_addr" in command:
            dst = int_field(command, "dst_addr", 0)
            require_e5(dst % 4 == 0, f"{opcode} command {command.get('sequence')} dst_addr is not 4-byte aligned")
            if command.get("expect_error") is None:
                require_e5(e5_contains_region(e5_regions, dst, byte_count, write=True), f"{opcode} destination is outside writable memory")
e5_expected_errors = {
    str(command.get("expect_error"))
    for command in e5_commands
    if command.get("expect_error") is not None
}
require_e5({"ERR_MMU_FAULT", "ERR_FENCE_WAIT", "ERR_SCHEDULER_FAULT"}.issubset(e5_expected_errors), "missing expected illegal/negative-path errors")
require_e5(
    any("INJECT_DISPATCH_ERROR" in set(command.get("flags", [])) for command in e5_commands),
    "missing illegal descriptor/scheduler fault injection",
)

e5_counters = control_metrics.get("counters", {})
e5_records = control_metrics.get("completion_records", [])
e5_interrupts = control_metrics.get("interrupt_events", [])
require_e5(control_metrics.get("status") == "pass", "control_plane_metrics status is not pass")
require_e5(int_field(e5_counters, "commands_submitted", -1) == len(e5_commands), "commands_submitted does not equal fixture command count")
require_e5(int_field(e5_counters, "commands_completed", -1) == len(e5_commands), "commands_completed does not equal fixture command count")
require_e5(int_field(e5_counters, "commands_failed", -1) >= len(e5_expected_errors), "commands_failed does not cover expected negative paths")
require_e5(int_field(e5_counters, "resets", 0) >= 1, "reset counter missing")
require_e5(int_field(e5_counters, "completion_interrupts", 0) > 0, "completion interrupts missing")
require_e5(int_field(e5_counters, "error_interrupts", 0) >= len(e5_expected_errors), "error interrupts do not cover expected errors")
require_e5(int_field(e5_counters, "bytes_read", 0) > 0 and int_field(e5_counters, "bytes_written", 0) > 0, "AXI byte traffic missing")
require_e5(int_field(e5_counters, "axi_read_transactions", 0) > 0, "AXI read transactions missing")
require_e5(int_field(e5_counters, "axi_write_transactions", 0) > 0, "AXI write transactions missing")
require_e5(isinstance(e5_records, list) and len(e5_records) == len(e5_commands), "completion_records do not cover all commands")
require_e5({str(event.get("kind")) for event in e5_interrupts}.issuperset({"completion", "error"}), "completion/error interrupt events missing")
for queue_id, queue in control_metrics.get("queue_state", {}).items():
    require_e5(int_field(queue, "submitted", -1) == int_field(queue, "retired", -2), f"queue {queue_id} not fully retired")
for expected_error in e5_expected_errors:
    require_e5(
        any(record.get("error") == expected_error and record.get("error_expected") is True for record in e5_records),
        f"completion_records missing expected error {expected_error}",
    )

core_demo_kernels = {"vector_add", "gemm_proxy", "image_filter", "memory_copy"}
optional_demo_kernels = {"convolution_proxy"}
allowed_demo_kernels = core_demo_kernels | optional_demo_kernels
kernel_entries = {str(item.get("name")): item for item in kernel_demo.get("kernels", [])}
kernel_names = set(kernel_entries)
summary_kernel_names = set(summary.get("kernels", {}))
require_e4(core_demo_kernels.issubset(kernel_names), f"kernel_demo missing core kernels: {sorted(core_demo_kernels - kernel_names)}")
require_e4(kernel_names.issubset(allowed_demo_kernels), f"kernel_demo has unexpected kernels: {sorted(kernel_names - allowed_demo_kernels)}")
require_e4(summary.get("status") == "pass", "demo summary status is not pass")
require_e4(summary.get("completion_status") == "complete", "demo summary completion_status is not complete")
require_e4(int_field(summary, "kernel_count", -1) == len(summary_kernel_names), "demo summary kernel_count mismatch")
require_e4(core_demo_kernels.issubset(summary_kernel_names), "demo summary missing core kernel hashes")
require_e4(summary_kernel_names.issubset(allowed_demo_kernels), f"demo summary has unexpected kernels: {sorted(summary_kernel_names - allowed_demo_kernels)}")
require_e4(summary_kernel_names.issubset(kernel_names), "demo summary includes kernels absent from kernel_demo")
for kernel_name, digest in summary.get("kernels", {}).items():
    require_e4(nonempty_sha(digest), f"summary kernel {kernel_name} missing result hash")

declared_buffers = {str(buffer.get("id")): buffer for buffer in kernel_demo.get("buffers", [])}
require_e4(len(declared_buffers) >= 10, "kernel_demo does not declare expected buffers")
for kernel_name, entry in kernel_entries.items():
    args = entry.get("args", [])
    require_e4(entry.get("queue_id"), f"{kernel_name} missing queue_id dispatch target")
    require_e4(entry.get("global_size") and entry.get("local_size"), f"{kernel_name} missing dispatch sizes")
    global_bindings = [arg for arg in args if arg.get("address_space") == "global"]
    require_e4(global_bindings, f"{kernel_name} has no global buffer bindings")
    access_modes = {str(arg.get("access")) for arg in global_bindings}
    require_e4("read" in access_modes and "write" in access_modes, f"{kernel_name} does not bind read and write buffers")
    for arg in global_bindings:
        buffer_id = str(arg.get("buffer_id"))
        require_e4(buffer_id in declared_buffers, f"{kernel_name} references unknown buffer {buffer_id}")

binding_map = buffer_binds.get("kernel_bindings", {})
require_e4(summary_kernel_names.issubset(set(binding_map)), "buffer_binds missing summary kernels")
for kernel_name in summary_kernel_names:
    binds = binding_map.get(kernel_name, [])
    global_binds = [bind for bind in binds if bind.get("address_space") == "global"]
    require_e4(global_binds, f"{kernel_name} missing global binds in buffer_binds.json")
    require_e4(
        {"read", "write"}.issubset({str(bind.get("access")) for bind in global_binds}),
        f"{kernel_name} buffer_binds do not cover read/write",
    )
    for bind in global_binds:
        require_e4(bind.get("buffer_id") in declared_buffers, f"{kernel_name} bind uses unknown buffer")
        require_e4(int_field(bind, "buffer_size_bytes", 0) > 0, f"{kernel_name} bind has no buffer size")

events = queue_trace.get("events", [])
require_e4(queue_trace.get("status") in {"pass", "complete"}, "queue_trace status is not pass/complete")
require_e4(int_field(queue_trace, "event_count", -1) == len(events), "queue_trace event_count mismatch")
for kernel_name in summary_kernel_names:
    kernel_events = [event for event in events if event.get("kernel") == kernel_name]
    phases = {str(event.get("phase")) for event in kernel_events}
    require_e4({"submit", "wait", "readback"}.issubset(phases), f"{kernel_name} missing submit/wait/readback phases")
    for phase in ("submit", "wait", "readback"):
        phase_events = [event for event in kernel_events if event.get("phase") == phase]
        require_e4(len(phase_events) == 1, f"{kernel_name} has {len(phase_events)} {phase} events")
        for event in phase_events:
            require_e4(event.get("status") == "complete", f"{kernel_name} {phase} event not complete")
            require_e4(event.get("completion_status") == "success", f"{kernel_name} {phase} event not success")
    submit = next((event for event in kernel_events if event.get("phase") == "submit"), {})
    readback = next((event for event in kernel_events if event.get("phase") == "readback"), {})
    require_e4(submit.get("buffer_binds"), f"{kernel_name} submit event missing buffer binds")
    require_e4(nonempty_sha(readback.get("readback_sha256")), f"{kernel_name} readback missing sha")
    require_e4(readback.get("readback_sha256") == summary.get("kernels", {}).get(kernel_name), f"{kernel_name} readback hash does not match summary golden hash")

for kernel_name, output in demo_outputs.items():
    if kernel_name not in summary_kernel_names:
        continue
    require_e4(output.get("pass") is True, f"{kernel_name} demo output pass flag is not true")
    require_e4(nonempty_sha(result_digest(output)), f"{kernel_name} demo output missing result hash")
    require_e4(result_digest(output) == summary.get("kernels", {}).get(kernel_name), f"{kernel_name} demo result hash does not match summary golden hash")
require_e4(demo_outputs["vector_add"].get("result") == demo_outputs["vector_add"].get("expected"), "vector_add result does not match expected golden")
require_e4(demo_outputs["memory_copy"].get("source_sha256") == demo_outputs["memory_copy"].get("result_sha256"), "memory_copy source/result hash mismatch")
require_e4(demo_outputs["gemm_proxy"].get("shape", {}).get("m") and demo_outputs["gemm_proxy"].get("shape", {}).get("n"), "gemm shape missing")
require_e4(demo_outputs["image_filter"].get("filter") and demo_outputs["image_filter"].get("width") and demo_outputs["image_filter"].get("height"), "image_filter metadata missing")
if "convolution_proxy" in demo_outputs and "convolution_proxy" in summary_kernel_names:
    convolution_demo = demo_outputs["convolution_proxy"]
    require_e4(convolution_demo.get("golden_comparison", {}).get("status") == "pass", "convolution demo golden comparison did not pass")
    require_e4(convolution_demo.get("input_shape") and convolution_demo.get("output_shape"), "convolution demo shape metadata missing")

metrics_by_kernel = kernel_metrics.get("kernels", {})
require_e4(summary_kernel_names.issubset(set(metrics_by_kernel)), "kernel_metrics missing summary kernels")
for kernel_name, metric in metrics_by_kernel.items():
    require_e4(metric.get("model_data_available") is True, f"{kernel_name} metrics missing model_data_available")
    require_e4(metric.get("queue_id"), f"{kernel_name} metrics missing queue_id")
    require_e4(int_field(metric, "work_items", 0) > 0, f"{kernel_name} metrics missing work_items")
    require_e4(int_field(metric, "bytes_read", 0) >= 0, f"{kernel_name} metrics missing bytes_read")
    require_e4(int_field(metric, "bytes_written", 0) >= 0, f"{kernel_name} metrics missing bytes_written")

devices = sorted(device_tiers.get("devices", []), key=lambda device: int_field(device, "shader_units_vec1", 0))
require_e4(int_field(device_tiers, "device_count", -1) == len(devices), "device_tiers count mismatch")
require_e4(len(devices) >= 4, "device_tiers does not cover at least four tiers")
last_shader_units = last_fp16 = last_fp32 = -1
for device in devices:
    shader_units = int_field(device, "shader_units_vec1", 0)
    fp16_ops = int_field(device, "fp16_ops_per_cycle", 0)
    fp32_ops = int_field(device, "fp32_ops_per_cycle", 0)
    require_e4(shader_units > last_shader_units, "device_tiers shader_units are not strictly increasing")
    require_e4(fp16_ops >= last_fp16, "device_tiers FP16 ops are not monotonic")
    require_e4(fp32_ops >= last_fp32, "device_tiers FP32 ops are not monotonic")
    require_e4(device.get("runtime_tier") and device.get("device_id"), "device_tiers entry missing id/tier")
    last_shader_units, last_fp16, last_fp32 = shader_units, fp16_ops, fp32_ops

require_e4(model_metrics.get("status") == "pass", "model metrics status is not pass")
require_e4(model_metrics.get("pass_by_workload", {}).get("vector_add") is True, "model vector_add did not pass")
require_e4(model_metrics.get("pass_by_workload", {}).get("gemm_proxy") is True, "model gemm did not pass")
require_e4(model_metrics.get("pass_by_workload", {}).get("convolution_proxy") is True, "model convolution did not pass")
require_e4(model_metrics.get("pass_by_workload", {}).get("memory_copy") is True, "model memory_copy did not pass")
require_e4(bool(model_metrics.get("precision", {}).get("fp16_path")), "model FP16 precision path missing")
require_e4(bool(model_metrics.get("precision", {}).get("fp32_path")), "model FP32 precision path missing")
require_e4(int_field(model_metrics.get("totals", {}), "fp16_proxy_ops", 0) > 0, "model FP16 op total is zero")
require_e4(int_field(model_metrics.get("totals", {}), "fp32_ops", 0) > 0, "model FP32 op total is zero")

for workload in ("vector_add", "gemm_proxy"):
    output = model_outputs[workload]
    require_e4(output.get("precision_path") == "FP32", f"model {workload} FP32 precision path missing")
    require_e4(int_field(output, "fp32_ops", 0) > 0, f"model {workload} fp32_ops missing")
    fp16 = output.get("fp16_proxy", {})
    require_e4(fp16.get("status") == "executed_proxy", f"model {workload} FP16 proxy did not execute")
    require_e4(fp16.get("method"), f"model {workload} FP16 proxy method missing")
    require_e4(nonempty_sha(fp16.get("result_sha256")), f"model {workload} FP16 result hash missing")
    require_e4(fp16.get("error_vs_fp32", {}).get("max_abs") is not None, f"model {workload} FP16 tolerance metadata missing")
    require_e4(nonempty_sha(output.get("result_sha256")), f"model {workload} FP32 result hash missing")

convolution = model_outputs["convolution_proxy"]
require_e4(convolution.get("alias") == "image_filter", "model convolution alias does not map to image_filter")
require_e4(convolution.get("precision_path") == "FP32", "model convolution FP32 precision path missing")
require_e4(int_field(convolution, "fp32_ops", 0) > 0, "model convolution fp32_ops missing")
require_e4(convolution.get("fp16_proxy", {}).get("status") in {"metadata_only", "executed_proxy"}, "model convolution FP16 metadata marker missing")
require_e4(convolution.get("fp16_proxy", {}).get("method") or convolution.get("fp16_proxy", {}).get("sample_head"), "model convolution FP16 method/sample missing")
require_e4(nonempty_sha(convolution.get("result_sha256")), "model convolution result hash missing")
memory_copy = model_outputs["memory_copy"]
require_e4(memory_copy.get("pass") is True, "model memory_copy pass flag is not true")
require_e4(memory_copy.get("source_sha256") == memory_copy.get("destination_sha256"), "model memory_copy source/destination hash mismatch")
require_e4(int_field(memory_copy, "bytes_copied", 0) > 0, "model memory_copy byte count missing")

model_tiers = sorted(model_outputs["shader_unit_scaling"].get("tiers", []), key=lambda tier: int_field(tier, "shader_units_vec1", 0))
require_e4(len(model_tiers) >= len(devices), "model shader_unit_scaling tiers do not cover demo tiers")
last_shader_units = last_fp16 = last_fp32 = -1
for tier in model_tiers:
    shader_units = int_field(tier, "shader_units_vec1", 0)
    fp16_ops = int_field(tier, "fp16_ops_per_cycle", 0)
    fp32_ops = int_field(tier, "fp32_ops_per_cycle", 0)
    require_e4(shader_units >= last_shader_units, "model shader scaling shader_units are not sorted")
    require_e4(fp16_ops >= last_fp16, "model shader scaling FP16 ops are not monotonic")
    require_e4(fp32_ops >= last_fp32, "model shader scaling FP32 ops are not monotonic")
    last_shader_units, last_fp16, last_fp32 = shader_units, fp16_ops, fp32_ops

if errors:
    print("celviz_gpgpu_source_check: fail")
    for error in errors:
        print(f"  - {error}")
    raise SystemExit(1)

print("celviz_gpgpu_source_check: pass")
for name in checks:
    print(f"  - {name}")
for name in script_checks:
    print(f"  - {name}")
print("  - e4_demo_model_evidence")
print("  - e4_kernel_demo_fixture")
print("  - e4_vector_add_golden_compare")
print("  - e4_gemm_convolution_image_filter")
print("  - e4_memory_copy_golden_compare")
print("  - e4_fp16_fp32_paths")
print("  - e4_tier_scaling")
print("  - e4_buffer_bindings")
print("  - e4_dispatch_readback_golden_compare")
print("  - source_hook_implementation_files_only")
print("  - source_hook_rank12_boundary_enforced")
PY
