# Rank 1 GPGPU Integration Evidence

Date: 2026-05-02

This directory is the E6 integration evidence framework for the active Rank 1
Vivante 3D GPGPU IP / Celviz GPGPU IP clean-room proxy.

It connects the architecture, model, runtime, verification, scaling, and
control-plane lanes into a single audit surface. It does not claim silicon
signoff, tapeout readiness, official API conformance, proprietary Vivante
compatibility, production PPA, safety/security certification, licensed vendor
collateral availability, or silicon signoff readiness.

## Files

| File | Purpose |
| --- | --- |
| `README.md` | E6 integration scope and evidence index. |
| `worker_lanes.md` | Seven-worker dependency map, E6 handoffs, and current pass state. |
| `bandwidth_latency_power.md` | AXI bandwidth, kernel latency proxy, shader-unit scaling, and power-estimate framework. |
| `reset_clock_interrupt.md` | Reset, clock, fence, and interrupt integration contract. |
| `security_safety_notes.md` | Explicit security and safety non-goals. |
| `perf_model_run.log` | Proxy performance model transcript. |
| `perf_model_metrics.json` | Proxy bandwidth, latency, tier-scaling, and power-index metrics. |
| `docs/celviz-gpgpu-ip/S5_INTEGRATION_GATE.md` | Actionable scenario gate reused by E6 for proxy evidence. |

## Evidence Inputs

| Input | Current role |
| --- | --- |
| `docs/celviz-gpgpu-ip/ARCHITECTURE_DECOMPOSITION.md` | S0 architecture boundary and Ventus mapping. |
| `docs/celviz-gpgpu-ip/WORKER_ORCHESTRATION.md` | Seven-worker coordination and dependencies. |
| `docs/celviz-gpgpu-ip/CELVIZ_ARCH_TOOL_WORKBREAKDOWN.md` | Celviz architecture-tool evidence loop for Rank 1. |
| `artifacts/rank_01_vivante_3d_gpgpu_ip/spec/architecture_inventory.md` | Reuse/adapt/new/blocked/forbidden architecture inventory. |
| `artifacts/rank_01_vivante_3d_gpgpu_ip/model/run.log` | S1 compute model run log. |
| `artifacts/rank_01_vivante_3d_gpgpu_ip/model/metrics.json` | Workload metrics, byte counts, FP32 ops, FP16 proxy notes, public tier table. |
| `artifacts/rank_01_vivante_3d_gpgpu_ip/demo/run.log` | S4 OpenCL-like runtime demo evidence. |
| `artifacts/rank_01_vivante_3d_gpgpu_ip/demo/outputs/summary.json` | Runtime demo summary and per-kernel status. |
| `artifacts/rank_01_vivante_3d_gpgpu_ip/rtl/control_plane_run.log` | Runnable control-plane transcript with reset, DMA, fences, dispatch, faults, and interrupts. |
| `artifacts/rank_01_vivante_3d_gpgpu_ip/rtl/control_plane_metrics.json` | APB/AXI counters, completion records, interrupt events, queue state, and fault evidence. |
| `artifacts/rank_01_vivante_3d_gpgpu_ip/integration/perf_model_metrics.json` | Proxy cycles, bandwidth, throughput, and power-index estimates by public-style tier. |
| `artifacts/rank_01_vivante_3d_gpgpu_ip/verification/test_results.log` | S3 harness status and required token list. |

## Current E6 Status

Overall E6 state: `pass_proxy`.

E6-D is accepted at clean-room proxy level when the machine-verifiable
integration docs and matrix evidence below are present, parseable, and internally
consistent. This is not a licensed vendor collateral review, proprietary Vivante
compatibility claim, official API conformance result, RTL timing signoff, or
silicon signoff.

| Area | State | Evidence |
| --- | --- | --- |
| AXI bandwidth and traffic | `pass_proxy` | `control_plane_metrics.json` records APB reads/writes plus AXI read/write transactions, beats, and byte counts; `perf_model_metrics.json` records bandwidth pressure estimates. |
| Kernel latency proxy | `pass_proxy` | Runtime queue phases and perf-model proxy cycles exist; no RTL timing or silicon latency is claimed. |
| Shader-unit scaling | `pass_proxy` | Public tier metadata and proxy throughput estimates exist across 9 CC8000/CC8X00-style tiers. |
| Clock/reset/interrupt | `pass_proxy` | Control-plane run records reset, completion interrupts, error interrupts, fences, and expected recoverable faults; clock evidence is proxy cycle-estimate only. |
| Security/safety | `pass_proxy` | Functional robustness notes and recoverable fault evidence exist; no certified safety/security claim is made. |

## E6 Machine-Verifiable Evidence

| Check | Evidence path | Pass condition |
| --- | --- | --- |
| Acceptance matrix parses | `artifacts/rank_01_vivante_3d_gpgpu_ip/verification/acceptance_matrix.json` | `python3 -m json.tool artifacts/rank_01_vivante_3d_gpgpu_ip/verification/acceptance_matrix.json` exits 0 and includes `e6_integration_evidence.status == "pass_proxy"`. |
| Worker-lane state is explicit | `artifacts/rank_01_vivante_3d_gpgpu_ip/integration/worker_lanes.md` | The file contains `Overall E6 state: pass_proxy`, active Rank 1 roots, and no completed claim for licensed vendor collateral or silicon signoff. |
| Integration README state is explicit | `artifacts/rank_01_vivante_3d_gpgpu_ip/integration/README.md` | The file contains this E6 status section, the evidence paths, and the no-overclaim boundary. |
| Verification evidence remains consumable | `artifacts/rank_01_vivante_3d_gpgpu_ip/verification/test_results.log` | The log records the E5 proxy coverage lines consumed by E6: command submission, interrupts, AXI traffic, reset behavior, invalid descriptors, DMA bounds/alignment, and tier throughput scaling. |
| E6 docs gate is executable | `artifacts/rank_01_vivante_3d_gpgpu_ip/verification/acceptance_matrix.json` | The `e6_integration_docs_gate` command exits 0 against the checked-in docs and matrix. Broader script/source gates remain separate lanes. |

## S5 Promotion Gate

The S5 scenario gate remains the named scenario checklist that E6 consumes.
It has proxy-level evidence for these scenarios:

| Scenario | Required outcome |
| --- | --- |
| S5-A clean command completion | Submit/start/fence/interrupt/clear/readback sequence with AXI byte counters. |
| S5-B DMA copy and AXI accounting | DMA or memory-copy command with control/data transaction counters and output hash. |
| S5-C recoverable fault | Invalid descriptor or bounds fault with fault interrupt, code, clear/recovery, and post-fault smoke pass. |
| S5-D reset recovery | Idle reset and post-fault reset with queue idle, interrupt/fault status, and post-reset smoke pass. |
| S5-E tier scaling proxy | Same workload across at least three public-style tiers with proxy throughput monotonicity. |

The detailed gate is maintained in
`docs/celviz-gpgpu-ip/S5_INTEGRATION_GATE.md`. The current package satisfies the
gate at clean-room proxy level through local logs/JSON metrics and the S3/E5
harness transcript. It still does not satisfy RTL trace, licensed vendor
collateral review, silicon PPA, CDC/STA, DFT, certification, official API
conformance, or silicon signoff gates.

## Active Target Reminder

The active target is Rank 1 GPGPU. Historical Rank 12 3D GPU artifacts remain
under `docs/celviz-gpu-ip/` and `artifacts/rank_12_vivante_3d_gpu_ip/`, but
they are superseded for active evidence. They should not be deleted, and they
should not be counted as Rank 1 GPGPU pass evidence.
