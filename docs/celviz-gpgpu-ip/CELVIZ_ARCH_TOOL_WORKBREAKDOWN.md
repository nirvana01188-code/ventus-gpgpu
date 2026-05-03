# Celviz Architecture Tool Work Breakdown For Rank 1 GPGPU IP

Date: 2026-05-02

## Purpose

This document applies the Celviz architecture-tool method to the active
Rank 1 Vivante 3D GPGPU IP / Celviz GPGPU IP effort in this repository. The
implementation target is a clean-room compute proxy built on the open-source
Ventus GPGPU framework.

The older Rank 12 Vivante 3D GPU proxy is retained as historical work only. It
is superseded for active planning by this Rank 1 GPGPU package and must not be
used as completion evidence for OpenCL-like kernels, shader-unit scaling,
FP16/FP32 compute, AXI traffic, or throughput scaling.

## Celviz Method Applied

The Celviz architecture loop is translated into a hardware-IP evidence loop:

| Celviz architecture loop item | Rank 1 GPGPU equivalent |
| --- | --- |
| Requirement text | Public Rank 1 Vivante 3D GPGPU IP blueprint plus clean-room scope |
| Benchmark suite | Vector add, memory copy, GEMM/convolution proxy, image filter, FP16/FP32 proxy, scheduler scaling, AXI traffic |
| Runtime workspace | Repo-local artifacts under `artifacts/rank_01_vivante_3d_gpgpu_ip/` |
| Simulator or model patch | Small Ventus/model/runtime/control-plane changes with logged commands |
| Gain summary | Kernel latency proxy, byte traffic, ops count, tier-normalized throughput, occupancy, pass/pending/fail state |
| Blocking benchmark | The lowest-evidence Rank 1 criterion that still lacks a real artifact or command |
| Final validation | Repeatable logs, metrics JSON, criteria-to-evidence rows, and integration notes |

Celviz `tools/architecture` remains a read-only method reference. This
repository does not vendor Celviz and does not patch Celviz as a scratchpad.

## Acceptance Boundary

Allowed active claims:

- Clean-room proxy architecture for Rank 1 GPGPU IP.
- Public tier metadata for shader-unit and FP16/FP32 operations-per-cycle
  labels.
- Deterministic software model evidence for vector add, GEMM/convolution
  proxy, image filter, memory copy, and FP16 metadata.
- OpenCL-like runtime descriptors and demos.
- Ventus-based reuse/adaptation of CTA scheduling, warp scheduling, FP32/vector
  pipeline, LSU/cache/L2/AXI, and simulation surfaces.

Forbidden active claims:

- Silicon signoff, tapeout readiness, STA/CDC/DFT closure, production PPA, or
  safety certification.
- Official OpenCL, OpenCV, Vulkan, GLES, or driver/API conformance.
- Vivante RTL, firmware, compiler, SDK, command-stream, cache, MMU, security, or
  performance equivalence.
- Treating Rank 12 triangle, texture, framebuffer, scanout, or graphics
  artifacts as Rank 1 GPGPU completion evidence.

## Seven-Worker Breakdown

| Worker | Lane | Inputs | Outputs | Exit condition |
| --- | --- | --- | --- | --- |
| Worker 1 | Architecture decomposition | Public Rank 1 blueprint, Ventus source, Celviz method | `docs/celviz-gpgpu-ip/ARCHITECTURE_DECOMPOSITION.md`, `spec/architecture_inventory.md` | Every major Rank 1 criterion maps to reuse/adapt/new/blocked/forbidden. |
| Worker 2 | Compute model | Architecture map, workload list, public tier table | S1 `model/run.log`, `metrics.json`, workload outputs and hashes | Deterministic workload evidence records pass/pending/fail and caveats. |
| Worker 3 | Command/control | Ventus host/CTA/AXI surfaces, runtime needs | Command descriptor, register/status/fence/interrupt evidence | Work can be submitted and observed through a clean-room proxy surface. |
| Worker 4 | Verification | Model, runtime, control-plane components | S3 coverage, test commands, `test_results.log` | Harness can report pass/pending/fail truthfully and repeatably. |
| Worker 5 | Runtime demo | Kernel demo JSON, model outputs, command schema | S4 runtime CLI logs and per-kernel outputs | OpenCL-like fixed demo validates and emits deterministic outputs. |
| Worker 6 | Scaling/performance | Public tier metadata, model metrics, scheduler/control evidence | Shader-unit scaling and throughput proxy reports | Scaling assumptions and bottlenecks are explicit and evidence-backed. |
| Worker 7 | Integration/pivot cleanup | All lane outputs and current artifact state | S5 integration docs and Rank 12 supersession notice | Integration evidence framework is coherent and does not overclaim. |

## Work Packages

### WP0: Pivot Cleanup

Objective: make Rank 1 GPGPU the active target without deleting historical
Rank 12 work.

Tasks:

- Add a supersession notice under `docs/celviz-gpu-ip/`.
- Keep all active references pointed at `docs/celviz-gpgpu-ip/` and
  `artifacts/rank_01_vivante_3d_gpgpu_ip/`.
- Mark graphics-only evidence as historical, not invalid.

Evidence:

- `docs/celviz-gpu-ip/SUPERSEDED_BY_GPGPU.md`
- This work breakdown.
- Worker orchestration file.

### WP1: Compute Workloads

Objective: keep the benchmark suite compute-oriented.

Required workload anchors:

- `vector_add`
- `gemm_proxy`
- `convolution_proxy` or image-filter proxy
- `memory_copy`
- FP32 path with operation counts
- FP16 proxy metadata until RTL support exists
- Shader-unit scaling table and throughput proxy

Current evidence handles:

- `artifacts/rank_01_vivante_3d_gpgpu_ip/model/run.log`
- `artifacts/rank_01_vivante_3d_gpgpu_ip/model/metrics.json`
- `artifacts/rank_01_vivante_3d_gpgpu_ip/model/outputs/`

### WP2: Runtime And Command Submission

Objective: bridge OpenCL-like kernel descriptors to a clean-room command and
status surface.

Required elements:

- Kernel descriptor with global/local sizes, precision mode, arguments, memory
  regions, queue id, fence id, and tier.
- Command submission token.
- Completion/fence token.
- Recoverable fault and unsupported-feature status.
- AXI4-Lite control transaction accounting.

Current evidence handles:

- `artifacts/rank_01_vivante_3d_gpgpu_ip/demo/kernel_demo.json`
- `artifacts/rank_01_vivante_3d_gpgpu_ip/demo/run.log`
- `artifacts/rank_01_vivante_3d_gpgpu_ip/demo/outputs/summary.json`

Open dependency:

- Verification harness and runtime component naming must agree on the accepted
  runtime entry point.
- Control-plane evidence remains pending until Worker 3 lands its artifacts.

### WP3: AXI Bandwidth, Latency, And Power Proxy

Objective: create S5 evidence around data movement without claiming production
PPA.

Required metrics:

- AXI4-Lite control read/write counts.
- AXI data read/write byte counts.
- Burst or transaction count where available.
- Kernel latency proxy in cycles or model steps.
- Effective bytes per cycle when a cycle count exists.
- Energy or power as a proxy estimate only, with assumptions listed.

Current status:

- S1 model records byte counts and FP32 operation counts.
- RTL-backed AXI counters and real cycle logs are pending.
- Power is an estimate framework only, not measured silicon power.

Evidence file:

- `artifacts/rank_01_vivante_3d_gpgpu_ip/integration/bandwidth_latency_power.md`

### WP4: Shader-Unit Scaling

Objective: keep public CC8000/CC8X00 tier metadata distinct from local measured
Ventus performance.

Required fields:

- Public tier name.
- Public vec1-equivalent shader units.
- Public FP32 and FP16 operations-per-cycle labels.
- Clean-room proxy assumptions.
- Workload stability result.
- Throughput proxy result.
- Bottleneck note.

Current evidence handles:

- `artifacts/rank_01_vivante_3d_gpgpu_ip/model/outputs/shader_unit_scaling.json`
- `artifacts/rank_01_vivante_3d_gpgpu_ip/model/metrics.json`

### WP5: Clock, Reset, And Interrupt

Objective: document the SoC integration contract and the proof still needed.

Required elements:

- Reset behavior: idle state, command cancellation or drain, status clear.
- Clock behavior: single proxy clock domain unless evidence shows otherwise.
- Interrupt behavior: completion, fault, mask/status/clear.
- Evidence commands and logs.

Current status:

- Architectural surfaces exist in Ventus host/CTA/sim wrapper form.
- Completion/fault interrupt proxy evidence is pending control-plane work.

Evidence file:

- `artifacts/rank_01_vivante_3d_gpgpu_ip/integration/reset_clock_interrupt.md`

### WP6: Security And Safety Non-Goals

Objective: make risk boundaries explicit without pretending certification work
has been done.

Required notes:

- No safety certification.
- No secure boot, DRM, protected content, side-channel, or isolation claim.
- MMU/ASID/TLB are proxy architecture hooks, not product security evidence.
- Fault injection is verification evidence, not safety signoff.

Evidence file:

- `artifacts/rank_01_vivante_3d_gpgpu_ip/integration/security_safety_notes.md`

## Evidence Closure Rules

| State | Meaning |
| --- | --- |
| `pass` | Artifact exists, command is documented, log/metrics contains expected tokens, and caveats do not invalidate the claim. |
| `started` | Artifact or plan exists, but quantitative logs or dependent lanes are incomplete. |
| `pending` | Expected future evidence is not present yet, or another lane must land first. |
| `blocked` | Licensed/proprietary collateral or unavailable capability is required. |
| `forbidden` | Claim is outside the clean-room Rank 1 target and must not be made. |

Worker 7 should prefer `started` or `pending` over optimistic pass language for
AXI bandwidth, real kernel latency, power, interrupt behavior, and RTL FP16
until the concrete logs exist.

## Current Integration Snapshot

| Evidence area | Current state | Reason |
| --- | --- | --- |
| S1 compute model | `pass` | `model/run.log` records `status=pass` and deterministic workload metrics. |
| S4 runtime demo | `pass` for demo artifact | `demo/run.log` records `status=pass` and per-kernel hashes. |
| S3 verification harness | `pending` overall | Harness exists, but runtime/control-plane component candidates still need alignment/completion. |
| AXI traffic | `started` | Architecture basis exists; RTL/control counters are pending. |
| Kernel latency proxy | `started` | Operation and byte counts exist; cycle-accurate logs are pending. |
| Shader-unit scaling | `started` | Public tier table exists; measured local scaling runs are pending. |
| Clock/reset/interrupt | `started` | Contract documented; control-plane evidence is pending. |
| Security/safety | `started` | Non-goals documented; no certification or product-security evidence claimed. |
