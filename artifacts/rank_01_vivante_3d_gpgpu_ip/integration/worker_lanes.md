# Integration Worker Lanes

Date: 2026-05-02

Status: proxy pass for current clean-room evidence package.

Overall E6 state: pass_proxy.

This file is the integration-facing view of the seven-worker plan. It records
handoffs, dependencies, and current evidence states for the active Rank 1
Vivante 3D GPGPU IP / Celviz GPGPU IP target. E6 is a clean-room integration
evidence state only; it does not claim licensed vendor collateral, proprietary
Vivante compatibility, official API conformance, RTL timing closure, production
PPA, or silicon signoff.

## Active And Historical Roots

| Root | Status | Use |
| --- | --- | --- |
| `docs/celviz-gpgpu-ip/` | active | Rank 1 GPGPU docs and architecture method. |
| `artifacts/rank_01_vivante_3d_gpgpu_ip/` | active | Rank 1 GPGPU evidence. |
| `docs/celviz-gpu-ip/` | superseded historical | Rank 12 graphics proxy docs; read for history/style only. |
| `artifacts/rank_12_vivante_3d_gpu_ip/` | superseded historical | Rank 12 graphics proxy artifacts; not active evidence. |

## Lane Summary

| Worker | Lane | Current evidence | Integration state |
| --- | --- | --- | --- |
| Worker 1 | Architecture | `docs/celviz-gpgpu-ip/ARCHITECTURE_DECOMPOSITION.md`, `spec/architecture_inventory.md` | Started/pass for S0 planning. |
| Worker 2 | Golden model | `model/run.log`, `model/metrics.json`, `model/outputs/` | Pass for deterministic S1 model evidence. |
| Worker 3 | Command/control | `control_plane.py`, `control_plane_run.log`, `control_plane_metrics.json` | Pass for runnable clean-room proxy control plane. |
| Worker 4 | Verification | `verification/README.md`, `coverage.md`, `test_commands.sh`, `test_results.log` | Pass for combined proxy evidence and strict optional-present checks. |
| Worker 5 | Runtime demo | `demo/kernel_demo.json`, `demo/run.log`, `demo/outputs/summary.json` | Pass for S4 demo artifact. |
| Worker 6 | Tier/scaling | Public shader-unit table plus `perf_model_metrics.json` tier estimates | Pass for proxy scaling evidence. |
| Worker 7 | Integration | This directory plus S5 scenario gate, E6 evidence index, acceptance matrix, and supersession notice | `pass_proxy` for E6 integration evidence. |

## E6 Acceptance Surface

| E6 item | Machine-verifiable evidence | Pass condition |
| --- | --- | --- |
| Integration README | `artifacts/rank_01_vivante_3d_gpgpu_ip/integration/README.md` | Contains `Overall E6 state: pass_proxy`, explicit evidence paths, and the no-overclaim boundary for licensed vendor collateral and silicon signoff. |
| Worker lanes | `artifacts/rank_01_vivante_3d_gpgpu_ip/integration/worker_lanes.md` | Contains active Rank 1 roots, lane ownership, `pass_proxy` E6 state, and future-work exclusions. |
| Acceptance matrix | `artifacts/rank_01_vivante_3d_gpgpu_ip/verification/acceptance_matrix.json` | Parses with `python3 -m json.tool` and includes `e6_integration_evidence.status == "pass_proxy"` with evidence paths and pass conditions. |
| Verification handoff | `artifacts/rank_01_vivante_3d_gpgpu_ip/verification/test_results.log` | Log records command submission, interrupts, AXI traffic, reset behavior, invalid descriptors, DMA bounds/alignment, and tier throughput proxy evidence for E6 consumption. |
| E6 docs gate | `artifacts/rank_01_vivante_3d_gpgpu_ip/verification/acceptance_matrix.json` | The `e6_integration_docs_gate` command exits 0 against the checked-in README, worker lanes, and matrix. Broader script/source gates remain separate lanes. |

## Current Evidence Tokens

| Token | Current source | State | Notes |
| --- | --- | --- | --- |
| `vector_add` | S1 model, S4 demo | pass | Deterministic output and hashes exist. |
| `gemm_convolution_image_filter` | S1 model, S4 demo | pass | Harness token passes in combined verification. |
| `memory_copy` | S1 model, S4 demo | pass | Byte-copy integrity exists. |
| `shader_unit_scaling` | S1 model metrics, perf model | pass_proxy | Public metadata and proxy tier estimates exist; measured RTL scaling remains out of scope. |
| `fp16_fp32_paths` | S1 model metrics | pass_proxy | FP32 model passes; FP16 proxy arithmetic executes for vector_add and gemm_proxy. |
| `command_submission` | Runtime queue and control-plane simulator | pass_proxy | Runtime and control-plane logs record command submission phases. |
| `interrupts` | Control-plane metrics | pass_proxy | Completion and expected error interrupt events are recorded. |
| `axi_traffic` | Control-plane metrics, perf model | pass_proxy | AXI transactions, beats, and bytes exist as deterministic proxy counters. |
| `throughput_scaling_by_tier` | Perf model | pass_proxy | Nine public-style tiers are evaluated with proxy throughput estimates. |

## Cross-Lane Dependencies

| Dependency | Why it matters | Current action |
| --- | --- | --- |
| W3 to W4 | Verification needs control-plane evidence for `command_submission` and `interrupts`. | Closed at proxy level; S3 runs `control_plane.py`. |
| W5 to W4 | Harness candidate names must recognize the runtime CLI or accepted runtime artifact. | Closed; runtime CLI is a checked component. |
| W6 to W7 | Integration should cite scaling metrics without inventing measured performance. | Closed at proxy level through `perf_model_metrics.json`. |
| W2 to W7 | Bandwidth/latency/power proxy needs model ops and byte counts. | Closed at proxy level through model metrics and perf model. |
| W3 to W7 | Reset/clock/interrupt and AXI traffic need control-plane logs. | Closed at proxy level through control-plane run and metrics. |

## Integration Evidence Checklist

| Area | Required evidence | Current status |
| --- | --- | --- |
| AXI bandwidth | AXI4-Lite/APB and AXI data transaction counters from control proxy plus perf estimates. | pass_proxy |
| Kernel latency proxy | Queue phases plus proxy cycle estimates. | pass_proxy |
| Software latency proxy | FP32 op counts and byte counts from model metrics. | pass |
| Shader-unit scaling | Public tier metadata plus same-workload proxy estimates. | pass_proxy |
| Clock/reset | Reset run plus proxy cycle estimates. | pass_proxy |
| Interrupt | Completion and recoverable-fault interrupt events. | pass_proxy |
| Security/safety | Non-goals and functional robustness boundaries. | pass_proxy |

## Current Second-Pass Worker Assignments

| Worker | Active ownership | Expected next evidence |
| --- | --- | --- |
| Worker 1 | Runnable control-plane simulator. | `control_plane.py`, command/fence/interrupt/reset metrics. |
| Worker 2 | FP16/FP32 compute model strengthening. | FP16 proxy outputs and hashes with clear caveats. |
| Worker 3 | OpenCL-like runtime queue phases. | Device listing, queue submit/wait/readback metrics. |
| Worker 4 | Verification hardening. | Optional-present checks for FP16, control plane, queue phases, AXI/APB counters. |
| Worker 5 | Proxy performance and bandwidth model. | Tier-scaled throughput, bandwidth pressure, power-index evidence. |
| Worker 6 | Ventus framework mapping. | Exact reuse/adapt/new hooks for CTA, warp scheduler, LSU/cache/MMU/AXI/sim/runtime. |
| Worker 7 | E6 integration gate. | Scenario gate, risk register, pass promotion rules, machine-verifiable evidence paths, and no-overclaim boundary. |

## E6 Pass Proxy Notes

E6 is `pass_proxy` because the package has parseable local evidence for the
architecture, compute model, runtime demo, control plane, verification harness,
and proxy performance/scaling lanes, and because the acceptance matrix records
commands that can be run by automation. E6 does not upgrade the evidence to
licensed vendor collateral review, proprietary command-stream compatibility,
official OpenCL conformance, real Verilator timing closure, production PPA,
CDC/STA/DFT closure, or silicon signoff.

## S5 Pass Blockers

The previous S5 proxy blockers are closed as follows:

| Blocker | Closing evidence |
| --- | --- |
| No runnable control-plane reset/fault transcript. | Closed by `rtl/control_plane_run.log`. |
| No AXI/APB transaction counters tied to commands. | Closed by `rtl/control_plane_metrics.json`. |
| No clock/timestamp proxy fields for command lifecycle. | Closed for proxy evidence by runtime phases and perf-model cycle estimates; RTL cycle traces remain future work. |
| No tier-scaling run across multiple public-style tiers. | Closed by `integration/perf_model_metrics.json`. |
| S3 does not consume S5 evidence yet. | Closed by `verification/test_results.log`, including `axi=yes apb=yes`. |

Remaining future-work gates are not blockers for the current clean-room proxy
package: RTL wave traces, real Verilator timing, silicon PPA, CDC/STA/DFT, and
official API conformance remain unclaimed.

## Pivot Cleanup Notes

The Rank 12 package remains in the tree. It should not be deleted or rewritten
by Rank 1 workers. Its graphics evidence can help future readers understand the
project history, but active acceptance must point to Rank 1 GPGPU files only.

Rank 1 integration should always use these active roots:

```text
docs/celviz-gpgpu-ip/
artifacts/rank_01_vivante_3d_gpgpu_ip/
```

## No-Overclaim Rules

Do not use these phrases as completed claims for the active package:

- silicon signoff
- tapeout ready
- production PPA
- OpenCL conformance
- OpenCV conformance
- Vivante-compatible command stream
- Vivante-equivalent RTL
- certified safety mechanism
- product security boundary

Use `proxy`, `model`, `clean-room`, `public metadata`, `started`, `pending`, or
`blocked` when those words better match the evidence.
