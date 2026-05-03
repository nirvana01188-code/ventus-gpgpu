# S5 Integration Gate

Date: 2026-05-02

Status: actionable gate, proxy-level only.

This gate defines what must be true before the Rank 1 `Celviz GPGPU IP`
package can move S5 from `started` to `pass`. It follows the public Vivante 3D
GPGPU IP blueprint at the level of compute-oriented integration evidence, while
remaining a clean-room proxy on top of Ventus.

This file is not a silicon signoff plan. It does not claim proprietary
VeriSilicon/Vivante behavior, production PPA, official API conformance, CDC/STA
closure, DFT closure, safety certification, or product security.

## Gate Inputs

| Input | Required role |
| --- | --- |
| `tools/celviz_gpgpu_ip/compute_model.py` | Deterministic workload oracle and byte/op counts. |
| `tools/celviz_gpgpu_ip/runtime_cli.py` | OpenCL-like command queue and readback demonstration. |
| `tools/celviz_gpgpu_ip/control_plane.py` | Runnable command/status/fence/interrupt/reset proxy when present. |
| `tools/celviz_gpgpu_ip/perf_model.py` | Proxy bandwidth, latency, throughput, and power-index model when present. |
| `artifacts/rank_01_vivante_3d_gpgpu_ip/rtl/control_plane_config.json` | Register/control surface definition. |
| `artifacts/rank_01_vivante_3d_gpgpu_ip/verification/test_results.log` | Repeatable acceptance transcript. |

## Required Pass Evidence

S5 may be marked `pass` only when all rows below are present as local,
repeatable evidence.

| Gate | Required evidence | Minimum pass token |
| --- | --- | --- |
| AXI/APB control traffic | APB/AXI-lite register read/write counts for queue setup, interrupt clear, status read, and fault read. | `apb_transactions` or `axi_lite_transactions` |
| AXI data traffic | Data-path read/write byte counts for vector add, GEMM or convolution/image filter, and memory copy. | `axi_data_bytes_read` and `axi_data_bytes_written` |
| Command lifecycle | Submit, start, complete, fence visible, and readback phases for at least two workloads. | `command_submit`, `command_start`, `fence_complete` |
| Completion interrupt | Interrupt status set, masked/unmasked behavior documented, clear observed. | `completion_interrupt` and `interrupt_clear` |
| Recoverable fault interrupt | Invalid descriptor or bounds/fault command produces fault code and recoverable interrupt. | `fault_interrupt` and `fault_code` |
| Reset recovery | Reset while idle and reset after a fault both return the proxy to a known command-capable state. | `queue_idle_after_reset` and `post_reset_smoke_status=pass` |
| Clock/timing proxy | Cycle or timestamp fields exist for queue, start, complete, interrupt, and reset. | `clock_cycles_elapsed` or `timestamp_delta_us` |
| Bandwidth/latency proxy | Same workload report includes bytes, estimated cycles, throughput, and assumptions. | `bandwidth_estimate` and `latency_estimate` |
| Power proxy | Power-index methodology is documented and computed from explicit local counters. | `power_index_proxy` |
| Verification binding | S3 script checks the present S5 artifacts and records pass. | `celviz_gpgpu_ip_verification: pass` |

## Acceptance Scenarios

### Scenario S5-A: Clean Command Completion

1. Reset/deassert the proxy.
2. Submit `vector_add`.
3. Observe command start.
4. Observe fence completion.
5. Observe completion interrupt.
6. Clear interrupt.
7. Read output summary and byte counters.

Required fields:

```text
scenario=S5-A-clean-command-completion
command_submit=present
command_start=present
fence_complete=present
completion_interrupt=present
interrupt_clear=present
axi_data_bytes_read=<integer>
axi_data_bytes_written=<integer>
status=pass
```

### Scenario S5-B: DMA Copy And AXI Accounting

1. Bind source and destination buffers.
2. Submit `memory_copy` or `dma_copy`.
3. Record AXI data byte counters and APB/AXI-lite control counters.
4. Read back output hash.

Required fields:

```text
scenario=S5-B-dma-copy-axi-accounting
command_submit=present
axi_lite_transactions=<integer>
axi_data_bytes_read=<integer>
axi_data_bytes_written=<integer>
readback_hash=<sha256>
status=pass
```

### Scenario S5-C: Recoverable Fault

1. Submit an invalid descriptor or out-of-range buffer.
2. Observe fault status and fault interrupt.
3. Clear fault/interrupt or reset the queue.
4. Submit a known-good `memory_copy` smoke command.

Required fields:

```text
scenario=S5-C-recoverable-fault
fault_interrupt=present
fault_code=<nonzero_or_named_code>
faulting_command_id=<id>
interrupt_clear=present
post_fault_smoke_status=pass
status=pass
```

### Scenario S5-D: Reset Recovery

1. Exercise reset while idle.
2. Exercise reset after a recoverable fault.
3. Confirm queue idle, interrupt state, and fault state.
4. Submit a post-reset smoke command.

Required fields:

```text
scenario=S5-D-reset-recovery
reset_asserted=present
queue_idle_after_reset=true
interrupt_status_after_reset=clear
fault_status_after_reset=clear_or_defined_sticky
post_reset_smoke_status=pass
status=pass
```

### Scenario S5-E: Tier Scaling Proxy

1. Run the same workload against at least three public-style tiers.
2. Record shader units, FP32 ops/cycle metadata, estimated cycles, and
   throughput proxy.
3. Check monotonic non-regression of the proxy estimate.

Required fields:

```text
scenario=S5-E-tier-scaling-proxy
shader_unit_tiers=present
throughput_scaling_by_tier=present
monotonic_proxy_scaling=true
claim_scope=proxy_model_only
status=pass
```

## SoC Integration Assumptions

| Surface | Proxy assumption | Evidence needed |
| --- | --- | --- |
| Control bus | AXI4-Lite/APB-like register access is enough for queue setup, status, interrupt, and fault handling. | Register transaction counts and ordered status reads. |
| Data bus | AXI-like data path carries buffer reads/writes for kernels and DMA copies. | Byte counters, burst assumptions, and bounds checks. |
| Interrupt line | One completion/fault interrupt line is acceptable for proxy evidence. | Mask/status/clear sequence and fault class. |
| Reset | One functional reset is enough for proxy evidence. | Idle/fault reset scenarios and post-reset smoke pass. |
| Clock | One proxy clock or timestamp domain is enough until RTL exposes more domains. | Cycle/timestamp deltas with explicit units. |
| Memory map | Control registers and buffers may use a synthetic local map. | Base, size, access type, and protection caveats. |

## Memory Map Expectations

| Region | Proxy purpose | Required attributes |
| --- | --- | --- |
| Control registers | Queue pointers, command doorbell, status, interrupt, fault, counters. | Base, size, register offsets, access width. |
| Descriptor ring | Kernel and DMA descriptors. | Base, entry size, bounds, producer/consumer indexes. |
| Buffer memory | Inputs, outputs, scratch. | Base, size, read/write permissions, bounds checks. |
| Counter window | Optional readback of cycle, byte, and transaction counters. | Counter names and reset behavior. |

## Risk Register

| Risk | Current state | Mitigation |
| --- | --- | --- |
| FP16 evidence can be mistaken for RTL FP16. | Medium. | Label as proxy/model unless a tested RTL path lands. |
| Runtime CLI can be mistaken for OpenCL conformance. | Medium. | Keep `OpenCL-like` and `non-conformant` language in docs/logs. |
| Public CC8000/CC8X00 tier labels can be mistaken for measured local silicon. | Medium. | Separate public metadata from local proxy estimates. |
| S5 could be marked pass with only docs. | High. | Require runnable logs, counters, and verification transcript. |
| Rank 12 graphics artifacts could pollute Rank 1 evidence. | Medium. | Keep superseded notice and active-root checks. |
| Control-plane proxy could imply Vivante command compatibility. | High. | Use `CVU1`/local descriptor language only. |

## Promotion Rule

`criteria_to_evidence.csv` may move `T0-R01-S5-001` from `started` to `pass`
only after:

1. S5-A through S5-E have logs or JSON metrics under
   `artifacts/rank_01_vivante_3d_gpgpu_ip/`.
2. The verification harness consumes those logs or checks equivalent tokens.
3. The integration README links the concrete evidence files.
4. The evidence still avoids proprietary compatibility, conformance, and
   silicon signoff claims.

