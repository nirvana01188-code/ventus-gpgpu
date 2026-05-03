# Celviz GPGPU IP Execution Plan

This is the controlling S0-S5 plan for Rank 1 `Celviz GPGPU IP` in
`ventus-gpgpu`. It adapts the public `Vivante 3D GPGPU IP` blueprint to a
clean-room proxy implementation and evidence package.

## Execution Principles

- Active target is `Celviz GPGPU IP`, not `Celviz 3D GPU IP`.
- Use Ventus as the open-source GPGPU framework and simulation substrate.
- Use Celviz as the architecture, verification, simulation, and evidence layer.
- Keep every claim tied to public facts, local proxy artifacts, or licensed
  evidence if such evidence is later added.
- Treat missing logs, unimplemented tests, and absent vendor collateral as
  `unproven` or `blocked`, not complete.

## S0: Public Scope And Evidence Map

Goal: freeze the Rank 1 identity and clean-room boundaries before implementation
work proceeds.

Required work:

- Name `Celviz GPGPU IP` as the active local target.
- Record the public `Vivante 3D GPGPU IP` anchors: CC8000/CC8X00 family,
  OpenCL 1.1/1.2/3.0, OpenCV, shader-unit tiers, and FP32/FP16 ops-per-cycle
  tiers.
- Define the allowed proxy scope: compute models, command/runtime skeletons,
  register maps, tests, demos, and integration evidence.
- Define non-goals for proprietary RTL, firmware, SDK, compiler, driver,
  conformance, certification, and silicon signoff.
- Seed `criteria_to_evidence.csv` so later workers can attach logs and outputs.

S0 evidence:

- `artifacts/rank_01_vivante_3d_gpgpu_ip/manifest.md`
- `artifacts/rank_01_vivante_3d_gpgpu_ip/criteria_to_evidence.csv`
- `artifacts/rank_01_vivante_3d_gpgpu_ip/spec/public_scope.md`

## S1: Golden Compute Models

Goal: create executable, inspectable golden models for the workloads that define
the GPGPU proxy behavior.

Required workloads:

- Vector add.
- GEMM.
- Convolution.
- Image filter.
- Memory copy.

Required model behavior:

- Support FP32 and FP16 paths where practical in the proxy model.
- Report operation counts, memory bytes moved, estimated cycles, and throughput.
- Expose shader-unit scaling knobs aligned to public tier concepts.
- Include scheduling, tiling, and memory-traffic notes.
- Emit deterministic outputs and hashes or numeric tolerances.

Expected evidence:

- `artifacts/rank_01_vivante_3d_gpgpu_ip/model/README.md`
- `artifacts/rank_01_vivante_3d_gpgpu_ip/model/run.log`
- `artifacts/rank_01_vivante_3d_gpgpu_ip/model/metrics.json`

## S2: Control Plane And RTL Skeleton

Goal: implement a Verilator-friendly control-plane proxy that can be compiled or
smoke-run in the Ventus environment.

Required blocks:

- Command processor.
- DMA.
- Scheduler.
- Register map.
- Memory model.

Required behavior:

- Accept command descriptors for kernel dispatch and memory copy.
- Move data through a DMA-like proxy path with bounds and alignment checks.
- Schedule work across configurable shader-unit tiers.
- Expose a documented register map for control, status, queue pointers,
  interrupts, errors, and performance counters.
- Model memory ordering, completion, and error reporting enough for tests.

Expected evidence:

- `artifacts/rank_01_vivante_3d_gpgpu_ip/rtl/README.md`
- `artifacts/rank_01_vivante_3d_gpgpu_ip/rtl/smoke.log`
- `artifacts/rank_01_vivante_3d_gpgpu_ip/rtl/register_map.md`

## S3: Verification

Goal: prove the proxy behavior with repeatable tests and coverage notes.

Required tests:

- FP16 path tests.
- FP32 path tests.
- Command submission tests.
- Interrupt tests.
- AXI traffic tests.
- Throughput scaling tests by configured tier.

Recommended coverage points:

- Vector add, GEMM, convolution, image filter, and memory-copy commands.
- Valid and invalid descriptors.
- DMA alignment and bounds errors.
- Completion interrupts and error interrupts.
- Reset during idle, active command, and pending interrupt states.
- AXI burst size, backpressure, latency, and ordering assumptions.
- Throughput monotonicity across public-style shader-unit tiers.

Expected evidence:

- `artifacts/rank_01_vivante_3d_gpgpu_ip/verification/README.md`
- `artifacts/rank_01_vivante_3d_gpgpu_ip/verification/test_commands.sh`
- `artifacts/rank_01_vivante_3d_gpgpu_ip/verification/test_results.log`
- `artifacts/rank_01_vivante_3d_gpgpu_ip/verification/coverage.md`

## S4: OpenCL-Like CLI Demo

Goal: provide a user-facing demo path that resembles OpenCL kernel submission
without claiming official OpenCL conformance.

Required demo behavior:

- List available proxy devices and configured tier.
- Load or select a kernel name such as `vadd`, `gemm`, `conv2d`,
  `image_filter`, or `memcpy`.
- Bind input and output buffers.
- Submit a command queue.
- Poll or wait for completion.
- Read back output and compare against a CPU/golden result.
- Print metrics such as bytes moved, estimated cycles, latency, and throughput.

Expected evidence:

- `artifacts/rank_01_vivante_3d_gpgpu_ip/demo/README.md`
- `artifacts/rank_01_vivante_3d_gpgpu_ip/demo/run.log`
- `artifacts/rank_01_vivante_3d_gpgpu_ip/demo/outputs/` when generated.

## S5: Integration Evidence

Goal: collect proxy-level SoC integration evidence that can be reviewed without
licensed vendor data.

Required evidence categories:

- Bandwidth.
- Latency.
- Power estimates.
- Reset behavior.
- Interrupt behavior.

Required integration notes:

- AXI/APB or equivalent memory/control-plane assumptions.
- Clock and reset-domain assumptions.
- Queue, DMA, memory-map, and interrupt routing assumptions.
- Power estimate methodology and limitations.
- Clear labels that evidence is proxy-level and not silicon signoff.

Expected evidence:

- `artifacts/rank_01_vivante_3d_gpgpu_ip/integration/README.md`
- `artifacts/rank_01_vivante_3d_gpgpu_ip/integration/bandwidth_latency_power.md`
- `artifacts/rank_01_vivante_3d_gpgpu_ip/integration/reset_clock_interrupt.md`
- `artifacts/rank_01_vivante_3d_gpgpu_ip/integration/security_safety_notes.md`

## Completion Gate

The package is complete only when every S0-S5 criterion in
`criteria_to_evidence.csv` is `pass`, or explicitly `not_applicable` with a
valid clean-room non-goal reason. The absence of evidence is always `unproven`.
