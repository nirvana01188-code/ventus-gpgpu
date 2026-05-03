# Reset, Clock, Fence, And Interrupt Integration Notes

Date: 2026-05-02

Status: `pass_proxy` for current clean-room evidence package.

This file defines the Rank 1 GPGPU proxy contract for reset, clock, completion,
fault, fence, and interrupt evidence. E5 now provides runnable clean-room
control-plane and verification evidence for the reset, interrupt, fault, DMA
negative-path, and post-reset-smoke cases described below.

## Boundary

Allowed:

- Clean-room proxy reset/clock/interrupt behavior.
- Ventus simulation and control-plane evidence when commands and logs exist.
- Completion and recoverable-fault behavior as observable tokens.

Not allowed:

- Proprietary Vivante interrupt controller, firmware, driver, or command-stream
  compatibility claims.
- Silicon reset-domain, clock-domain-crossing, DFT, scan, or timing signoff.
- API conformance claims.

## Integration Surfaces

| Surface | Ventus/proxy basis | Current disposition |
| --- | --- | --- |
| Host dispatch | `host2CTA_data` and CTA scheduler input. | Adapt for OpenCL-like descriptors. |
| AXI4-Lite control | `AXI4Lite2CTA` register bridge pattern. | Adapt for queue/status/fence/interrupt model. |
| Completion | Workgroup completion response and runtime output status. | `pass_proxy`; fence signal/wait and completion interrupt evidence are present. |
| Fault | Unsupported op, MMU fault, invalid descriptor, timeout, and recoverable compute error classes. | `pass_proxy`; E5 records scheduler, MMU/DMA bounds, fence-wait, invalid descriptor, and DMA alignment/bounds fault evidence. |
| Interrupt | Completion and fault interrupt status/mask/clear. | `pass_proxy`; E5 records completion/error interrupts plus clear events. |
| Reset | Proxy command/status reset behavior. | `pass_proxy`; E5 records boot reset, post-fault reset recovery, and pending/active flush cases. |
| Clock | Single proxy clock assumption plus cycle-domain performance model. | `pass_proxy` for proxy assumptions only; CDC/STA/signoff not claimed. |

## Reset Contract

Expected proxy reset behavior:

1. New command submission is blocked while reset is asserted.
2. Queue, fence, status, interrupt pending bits, and recoverable fault state are
   returned to idle values.
3. In-flight model/runtime work is either cancelled before launch or allowed to
   drain before reset is reported complete. The selected behavior must be
   stated by the control-plane lane.
4. After reset deassertion, a known-good `vector_add` or `memory_copy` command
   can be submitted and observed.

Required evidence fields:

| Field | Meaning |
| --- | --- |
| `reset_asserted` | Reset request was issued. |
| `queue_idle_after_reset` | Queue reports empty or idle. |
| `interrupt_status_after_reset` | Pending interrupt state is clear. |
| `fault_status_after_reset` | Recoverable fault state is clear or explicitly sticky. |
| `post_reset_smoke_status` | Known-good command succeeds after reset. |

Current E5 disposition:

| Evidence item | Source | Observed value | Status |
| --- | --- | --- | --- |
| Boot reset recovery | `rtl/control_plane_run.log`, sequence 1 | `status=complete error=OK`; reset cleared queues, sticky status, fences, and live interrupt state while preserving audit records. | `pass_proxy` |
| Reset recovery token | `rtl/control_plane_metrics.json.runtime_control_evidence.reset_recovery` | `reset_asserted=true`, `queue_idle_after_reset=true`, `interrupt_status_after_reset=clear`, `fault_status_after_reset=clear`, `post_reset_smoke_status=pass`, `reset_recoveries=1`. | `pass_proxy` |
| Post-fault reset and smoke | `rtl/e5_verification_demo.json`, sequences 10-11 | `e5-post-fault-reset` followed by `e5-post-reset-smoke-fill`. | `pass_proxy` |
| Pending/active reset flush | `rtl/e5_outputs/negative_boundary_check.log` and `negative_boundary_evidence.json` | `reset_pending_active=2`, `reset_clears_sticky_error_and_pending_state=true`, cases `pending_dma_flush` and `active_dispatch_flush`. | `pass_proxy` |

## Clock Contract

Current assumption:

```text
clock_model=single_proxy_clock
clock_proxy_basis=cycle-domain performance model
```

This assumption is sufficient for model/runtime integration notes and E6
integration evidence. It is not CDC closure, STA, implementation timing
evidence, multi-clock-domain validation, or signoff evidence.

Auditable clock/proxy evidence:

| Field | Current evidence | Status |
| --- | --- |
| `clock_name` | `single_proxy_clock` assumption in this document. | `pass_proxy` for assumption disclosure. |
| `clock_cycles_elapsed` | `integration/perf_model_metrics.json` records `total_kernel_cycles_proxy` and `latency_proxy_cycles` by public-style tier. | `pass_proxy` for proxy cycle estimates. |
| `clock_gate_state` | Not implemented or claimed. | `not_applicable_proxy` |
| `reset_sync_cycles` | Not observed as RTL cycles; reset recovery is state-based in E5 logs. | `future_rtl` |
| `claim_boundary` | `perf_model_metrics.json.assumptions.clock_model` states no frequency, voltage, capacitance, or timing closure is assumed. | `pass_proxy` |

## Fence And Completion Contract

Expected behavior:

- Each command descriptor carries or is assigned a fence id.
- Completion makes the fence observable through status polling.
- Completion can raise a completion interrupt if unmasked.
- Polling and interrupt modes should both be testable.

Required tokens:

```text
command_submission
fence_complete
completion_interrupt
interrupt_clear
```

The S3/S5 harness now records `command_submission`, `interrupts`, and E5
interrupt/reset/AXI strict evidence. Fence evidence is present through
`fence_signal`, `fence_wait`, and `fence_signals=2` in
`rtl/control_plane_metrics.json`.

## Interrupt Contract

Minimum interrupt classes:

| Interrupt class | Trigger | Expected recovery |
| --- | --- | --- |
| Completion | Kernel or workgroup command completes. | Clear interrupt, read fence/status, submit next command. |
| Recoverable fault | Invalid descriptor, unsupported feature, MMU/fault proxy, or timeout. | Capture fault code, clear or reset affected queue, submit known-good command. |

Required register/status concepts:

- Interrupt status.
- Interrupt mask or enable.
- Interrupt clear.
- Fault code.
- Faulting queue or command id.
- Fence id.

Current E5 interrupt evidence:

| Evidence item | Source | Observed value | Status |
| --- | --- | --- | --- |
| Completion interrupts | `rtl/control_plane_metrics.json.counters` | `completion_interrupts=13`. | `pass_proxy` |
| Fault/error interrupts | `rtl/control_plane_metrics.json.counters` | `error_interrupts=3`; expected fault sequences include scheduler, MMU/DMA bounds, and fence-wait timeout. | `pass_proxy` |
| Interrupt clear | `rtl/control_plane_metrics.json.counters` and `interrupt_events` | `interrupt_clears=16`; each completion/error event has an acknowledged `clear` event in the emitted event list. | `pass_proxy` |
| Verification gate | `verification/test_results.log` | `e5_interrupts=pass completion_interrupts=13 error_interrupts=3`; optional `e5_interrupt_reset_axi_strict=present`. | `pass_proxy` |

## Current Evidence Snapshot

| Evidence | State | Notes |
| --- | --- | --- |
| S1 model command-like workload completion | `pass` | `model/run.log` records all deterministic workloads as pass. |
| S4 runtime demo completion | `pass` for demo | `demo/run.log` records `demo_status=pass` and output hashes. |
| S3 `command_submission` token | `pass_proxy` | Harness runs the runtime CLI and control-plane simulator. |
| S3 `interrupts` token | `pass_proxy` | Control-plane metrics record completion and expected error interrupt events. |
| E5 reset behavior | `pass_proxy` | `test_results.log` records `e5_reset_behavior=pass resets=1`; negative-boundary evidence adds two reset pending/active flush cases. |
| E5 interrupt clear | `pass_proxy` | `control_plane_metrics.json` records 16 interrupt clears for completion/error events. |
| E5 invalid descriptor evidence | `pass_proxy` | Negative-boundary evidence records 5 invalid descriptor scenarios and required error-record fields. |
| E5 DMA bounds/alignment evidence | `pass_proxy` | Negative-boundary evidence records 5 bounds/alignment scenarios; control-plane E5 gate records valid DMA alignment and one expected MMU bounds fault. |
| Clock/cycle evidence | `pass_proxy` | Perf-model cycle estimates and clock assumptions exist; RTL cycle traces remain future work. |

## Residual Evidence Not Claimed By Proxy Pass

The current package is `pass_proxy`; the following remain outside that pass:

| Gate | Residual gap |
| --- | --- |
| Reset | RTL reset-domain implementation, reset synchronization timing, DFT/scan reset checks, and silicon reset signoff. |
| Clock | Multi-clock-domain analysis, CDC closure, STA, frequency/voltage assumptions, and measured timing. |
| Completion | Product driver ABI, proprietary fence semantics, or official API conformance. |
| Interrupt | Vivante-compatible interrupt controller, firmware behavior, interrupt security, or silicon interrupt latency. |
| Verification | Silicon, FPGA, or cycle-accurate RTL trace evidence beyond the current clean-room proxy logs. |

## Required S5 Scenarios

| Scenario | Reset/clock/interrupt focus | Pass evidence |
| --- | --- | --- |
| S5-A clean command completion | Completion interrupt path after a known-good command. | `fence_signal`, `fence_wait`, `completion_interrupt`, `interrupt_clear`, status `pass_proxy`. |
| S5-C recoverable fault | Fault interrupt path and recovery to known-good work. | `fault_interrupt`, `fault_code`, `interrupt_clear`, expected error status, `post_fault_smoke_status=pass_proxy`. |
| S5-D reset recovery | Idle reset, post-fault reset, pending flush, and active dispatch flush. | `queue_idle_after_reset`, `interrupt_status_after_reset`, `fault_status_after_reset`, `post_reset_smoke_status=pass_proxy`. |

Clock evidence is cycle-proxy based at this stage through
`integration/perf_model_metrics.json`; no real clock period, frequency, CDC,
or STA claim is made.

## Minimum Control-Plane Log Shape

Control-plane runs should continue to emit a machine-readable JSON or
line-oriented log with these fields:

```text
command_submit
command_start
fence_complete
completion_interrupt
interrupt_clear
fault_interrupt
fault_code
reset_asserted
queue_idle_after_reset
post_reset_smoke_status
clock_cycles_elapsed
axi_lite_transactions
axi_data_bytes_read
axi_data_bytes_written
```

These are local proxy tokens. They are not evidence of a Vivante-compatible
interrupt controller, clocking architecture, CDC closure, or silicon
reset-domain implementation.

## E6-B Audit Checklist

| E6-B item | Evidence | Result |
| --- | --- | --- |
| Reset recovery | `control_plane_metrics.json.runtime_control_evidence.reset_recovery`, `control_plane_run.log`, E5 post-fault reset fixture. | `pass_proxy` |
| Interrupt clear | `control_plane_metrics.json.counters.interrupt_clears=16` and paired `clear` interrupt events. | `pass_proxy` |
| Invalid descriptor | `negative_boundary_check.log` records `invalid_descriptors=5` with bad magic/version/length/opcode/queue coverage. | `pass_proxy` |
| DMA bounds/alignment | `negative_boundary_check.log` records `dma_bounds_alignment=5` with range and alignment coverage. | `pass_proxy` |
| Post-reset smoke | E5 reset recovery token records `post_reset_smoke_status=pass`; E5 fixture sequences 10-11 show reset then smoke fill. | `pass_proxy` |
| Clock proxy assumptions | This file and `perf_model_metrics.json.assumptions.clock_model` disclose proxy-only cycle assumptions. | `pass_proxy` |
| Non-goal guardrail | Boundary sections forbid proprietary Vivante compatibility, API conformance, CDC/STA/DFT/timing, and silicon signoff claims. | `pass_proxy` |
