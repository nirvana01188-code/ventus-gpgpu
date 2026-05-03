# Rank 1 Execution Blueprint: Vivante 3D GPGPU IP

Generated: 2026-05-01

Repository target: `Celviz GPGPU IP` inside `ventus-gpgpu`.

This is the local Rank 1 execution and acceptance blueprint for the public
`Vivante 3D GPGPU IP` anchor. It adapts the upstream blueprint into a
clean-room Ventus/Celviz work package and makes `Celviz GPGPU IP` the active
target.

## Identity

| Field | Value |
| --- | --- |
| Rank | 1 |
| IP | Vivante 3D GPGPU IP |
| Local target | Celviz GPGPU IP |
| Track | T0 AI Compute |
| Stage path | S0-S5 |
| Source blueprint | `blueprints/03_Vivante3DGPGPUIP.md` |
| Source blueprint exists | yes |
| Artifact root | `artifacts/rank_01_vivante_3d_gpgpu_ip/` |
| Standard validation command | `make verify-t0` or `./verification/run_t0.sh` |

## Why This IP Is Codex-Suitable

This is the highest-value digital compute target in the current public IP
ranking. The public anchor exposes enough surface for clean-room proxy work:
OpenCL/OpenCV positioning, shader-unit scaling tiers, FP16/FP32 throughput
tiers, command/runtime behavior, scheduling, memory traffic, and integration
evidence.

## Official Public Spec Anchors

- CC8000/CC8X00 family.
- OpenCL 1.1/1.2/3.0 support is listed in the public table.
- OpenCV support is listed in the public table.
- Public shader-unit tiers range from 16 to 2048 vec1-equivalent shader units.
- Public FP32/FP16 operations-per-cycle tiers range from 32/64 to 4096/8192.

## Clean-Room Proxy Scope

Codex and Celviz may implement public-information-derived proxy models,
control-plane skeletons, tests, demos, register maps, command queues, and
integration evidence for this IP.

The work must stay within public anchors and local acceptance criteria. It may
model the shape of a scalable GPGPU integration target, but it must not claim
to reproduce proprietary Vivante microarchitecture, compiler behavior, RTL,
firmware, SDK, driver, verification suites, or silicon data.

## Non-Goals

- Do not claim equivalence to proprietary VeriSilicon RTL, firmware, SDK,
  compiler, hard macro, or production IP.
- Do not claim official OpenCL, OpenCV, AXI, safety, security, or conformance
  certification unless real licensed suites and evidence are present.
- Do not claim silicon PPA, STA, DFT, CDC/RDC signoff, ISO 26262 signoff, or
  tapeout readiness from proxy artifacts.
- Mark any requirement that needs licensed vendor collateral as `blocked` in
  `criteria_to_evidence.csv`.

## Execution Flow

| Stage | Execution work | Required evidence | AI1 gate |
| --- | --- | --- | --- |
| S0 | Freeze public facts, API/framework anchors, clean-room proxy scope, interfaces, workloads, active target, and non-goals. | `artifacts/rank_01_vivante_3d_gpgpu_ip/manifest.md`, `artifacts/rank_01_vivante_3d_gpgpu_ip/criteria_to_evidence.csv`, `artifacts/rank_01_vivante_3d_gpgpu_ip/spec/public_scope.md` | AI1 marks `pass` only when mapped evidence exists and commands/logs prove the work. |
| S1 | Build executable golden models for vector add, GEMM, convolution, image filter, memory copy, scheduling, tiling, and memory traffic. | `artifacts/rank_01_vivante_3d_gpgpu_ip/model/README.md`, `artifacts/rank_01_vivante_3d_gpgpu_ip/model/run.log`, `artifacts/rank_01_vivante_3d_gpgpu_ip/model/metrics.json` | AI1 marks `pass` only when mapped evidence exists and commands/logs prove the work. |
| S2 | Implement Verilator-friendly command processor, DMA, scheduler, register map, and memory-model skeletons. | `artifacts/rank_01_vivante_3d_gpgpu_ip/rtl/README.md`, `artifacts/rank_01_vivante_3d_gpgpu_ip/rtl/smoke.log`, `artifacts/rank_01_vivante_3d_gpgpu_ip/rtl/register_map.md` | AI1 marks `pass` only when mapped evidence exists and commands/logs prove the work. |
| S3 | Add unit/cocotb tests for FP16, FP32, command submission, interrupts, AXI traffic, and throughput scaling by configured tier. | `artifacts/rank_01_vivante_3d_gpgpu_ip/verification/README.md`, `artifacts/rank_01_vivante_3d_gpgpu_ip/verification/test_commands.sh`, `artifacts/rank_01_vivante_3d_gpgpu_ip/verification/test_results.log`, `artifacts/rank_01_vivante_3d_gpgpu_ip/verification/coverage.md` | AI1 marks `pass` only when mapped evidence exists and commands/logs prove the work. |
| S4 | Add an OpenCL-like CLI demo for kernel submission, argument binding, dispatch, result readback, and output inspection. | `artifacts/rank_01_vivante_3d_gpgpu_ip/demo/README.md`, `artifacts/rank_01_vivante_3d_gpgpu_ip/demo/run.log`, `artifacts/rank_01_vivante_3d_gpgpu_ip/demo/outputs/` when applicable | AI1 marks `pass` only when mapped evidence exists and commands/logs prove the work. |
| S5 | Record proxy-level SoC integration evidence: bandwidth, latency, power estimates, reset behavior, interrupt behavior, AXI/APB maps, and clock-domain assumptions. | `artifacts/rank_01_vivante_3d_gpgpu_ip/integration/README.md`, `artifacts/rank_01_vivante_3d_gpgpu_ip/integration/bandwidth_latency_power.md`, `artifacts/rank_01_vivante_3d_gpgpu_ip/integration/reset_clock_interrupt.md`, `artifacts/rank_01_vivante_3d_gpgpu_ip/integration/security_safety_notes.md` | AI1 marks `pass` only when mapped evidence exists and commands/logs prove the work. |

## IP-Specific Acceptance Criteria

- S1 golden compute model runs vector add, GEMM, convolution, image filter, and
  memory-copy workloads.
- S1/S2 scheduler model shows shader-unit scaling across configured public
  tiers without claiming proprietary scheduling equivalence.
- S2 includes a command processor, DMA path, scheduler, register map, and
  memory model that can be smoke-tested.
- S3 verifies FP16 and FP32 paths, command submission, interrupt behavior, AXI
  traffic, and throughput scaling by configured tier.
- S4 provides an OpenCL-like CLI demo with repeatable command lines and
  inspectable output files or logs.
- S5 records bandwidth, latency, power, reset, and interrupt evidence at proxy
  level and labels any non-proxy silicon claims as blocked.

## AI1 Review Checklist

- [ ] `artifacts/rank_01_vivante_3d_gpgpu_ip/manifest.md` exists and names
      rank 1, `Vivante 3D GPGPU IP`, track `T0 AI Compute`, local target
      `Celviz GPGPU IP`, and source blueprint `blueprints/03_Vivante3DGPGPUIP.md`.
- [ ] `artifacts/rank_01_vivante_3d_gpgpu_ip/criteria_to_evidence.csv` maps
      every criterion in this file to observed artifacts.
- [ ] S0 evidence freezes public facts, clean-room proxy scope, interfaces,
      workloads, active target, and non-goals.
- [ ] S1 evidence includes executable model logs and metrics, or is marked
      `blocked` with a valid reason.
- [ ] S2 evidence includes a loadable, compilable, or smoke-run control-plane
      skeleton, or is marked `blocked` with a valid reason.
- [ ] S3 evidence includes repeatable tests, results, and coverage notes.
- [ ] S4 evidence includes an executable OpenCL-like CLI path and inspectable
      outputs.
- [ ] S5 evidence is explicitly proxy-level and does not claim real silicon
      signoff.
- [ ] No out-of-scope claim appears in docs, logs, manifests, demos, or
      generated reports.

## Authoritative Execution Checklist

This is the single cron-controlled execution surface for the active Celviz
GPGPU IP work. Automation must generate daily todos from this section only and
must not treat Rank 12 graphics documents, generated todo snapshots, or
verification prose as requirement sources.

Completion policy: items may be changed from `[ ]` to `[x]` only after real
implementation and `./scripts/accept_celviz_gpgpu_ip.sh` both pass in the same
tick. Documentation-only updates, mocked runtime behavior, placeholder RTL, or
claims of proprietary Vivante compatibility do not close an item.

<!-- CELVIZ_EXECUTION_CHECKLIST_START -->
- [x] E0. Keep the GPGPU target boundary clean: suppress or quarantine Rank 12
      graphics-only artifacts from active GPGPU acceptance while preserving them
      as historical reference.
- [x] E1. Promote Celviz GPGPU runtime ABI from smoke proxy toward a usable
      command engine: queue lifecycle, DMA fill/copy, named fences, status
      polling, error injection, metrics, and native/Python acceptance must stay
      synchronized.
- [x] E2. Deepen RTL control-plane integration in Ventus: AXI-Lite CSR decode,
      command doorbell, queue pointers, IRQ/error counters, APB/AXI counters,
      scheduler handoff, and debug observability must compile through Chisel.
- [x] E3. Add Verilator-facing execution evidence: build or relink
      `libVentusRTL.so`, bind the native runtime, run command streams with
      `--require-runtime`, and record queue/metric snapshots.
- [x] E4. Strengthen compute and runtime demos: vector add, GEMM, convolution,
      image filter, memory copy, FP16/FP32, tier scaling, buffer binding,
      dispatch, readback, and golden comparison must run from CLI entrypoints.
- [x] E5. Expand verification coverage for command submission, interrupts, AXI
      traffic, reset behavior, invalid descriptors, DMA bounds/alignment, and
      throughput scaling by configured tier.
- [x] E6. Maintain integration evidence for bandwidth, latency, proxy power,
      reset/clock assumptions, security/safety notes, and explicit non-goals
      for licensed vendor collateral or silicon signoff.
- [x] E7. Keep one-key acceptance authoritative: acceptance matrix, source hook
      checker, Python compile, Chisel compile, native runtime build, native
      runtime execution, artifact verification, and `git diff --check` must all
      remain green.
<!-- CELVIZ_EXECUTION_CHECKLIST_END -->

## Completion Rule

This IP may be marked complete only when AI1 reports `pass` for every required
stage in `S0-S5` or marks a stage `not_applicable` with a valid non-goal
reason. Missing evidence is `unproven`, not complete.
