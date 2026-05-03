# Celviz GPGPU IP Parity Status

Status: active engineering evidence, not product signoff.

This document tracks how far the Ventus-based Celviz GPGPU IP proxy has moved
toward a basic GPGPU IP comparison point. It is intentionally clean-room and
does not claim proprietary Vivante compatibility, official OpenCL conformance,
production Linux driver readiness, timing closure, physical PPA signoff, safety
certification, or silicon readiness.

## Current Closed Gates

The current acceptance stack closes these machine-checked gates:

- E0-E7 acceptance: source hooks, RTL debug/control-plane hooks, runtime ABI,
  native runtime binding, demo workloads, negative contracts, and integration
  evidence.
- E8 supplemental Verilator functional coverage: 100% functional bins, with
  RTL structural line/branch/toggle metrics kept separate.
- Phase 2 hardening: SIMT compute path, OpenCL-like subset ABI, memory model,
  Linux userspace runtime proxy, supplemental Verilator fixtures, and PPA proxy.
- Phase 3 cross-layer evidence: OpenCL-like kernels align across runtime, SIMT,
  memory, OS runtime proxy, supplemental verification, and PPA proxy.
- Phase 4 kernel lowering: four OpenCL-like kernels lower into clean-room
  micro-op evidence.
- Phase 5 executable micro-ops: lowered micro-ops execute through a deterministic
  interpreter, generate memory traces, and match compute-oracle result hashes.

Latest observed functional/acceptance coverage:

```text
coverage=100.000%
hit=203
total=203
missed_bins=[]
```

Latest observed Phase 5 execution:

```text
kernels=4
uops_executed=63
memory_events=1379
```

## Basic GPGPU IP Comparison Axes

| Axis | Current Celviz State | Evidence | Boundary |
| --- | --- | --- | --- |
| Compute core | SIMT/SIMD proxy with wavefront, register, ALU, LSU, scoreboard, and barrier counters | `simt_execution.json`, Phase 2/3 reports | Not a completed production shader core |
| Programming model | OpenCL-like subset for vector add, GEMM, conv2d, image filter | `opencl_subset_evidence.json`, ABI JSON, runtime commands | Not OpenCL 3.0 or official conformance |
| Compiler path | Kernel ABI lowering to micro-op vocabulary | Phase 4 lowering reports | Not LLVM/SPIR-V or vendor ISA |
| Executable IR | Micro-op interpreter executes lowered kernels and checks oracle hashes | Phase 5 reports | Not a production ISA simulator |
| Memory system | Global/local/constant semantics, DMA, cache/coalescing proxy, micro-op traces | Memory model + Phase 5 memory events | Not a proprietary cache/LSU implementation |
| Runtime/driver | Userspace runtime and Linux/DRM-like proxy submission evidence | E3, Phase 2/3 runtime evidence | Not a kernel driver or DRM compatibility claim |
| Verification | Functional/acceptance bins at 100%, supplemental Verilator structural observations | `verification_coverage_100.json`, E8 reports | RTL structural coverage is not 100% |
| PPA | Area/frequency proxy and public tier linkage | PPA proxy report | Not synthesis, STA, power, or signoff |

## Phase 6 Closure Target

Phase 6 exists to move from executable evidence toward a stronger "basic GPGPU
IP proxy" comparison layer:

- Compiler IR: virtual registers, predicate registers, basic blocks, CFG edges,
  def-use, and branch/predicate evidence.
- Memory trace integration: per-kernel micro-op load/store traces linked to
  memory model semantics and coalescing proxy evidence.
- Driver submission model: queue, fence, event, error, and pending-count
  lifecycle evidence against runtime commands and Linux userspace proxy reports.
- Synthesis readiness: tool availability, source scope, unsupported constructs,
  and proxy PPA boundary evidence.
- Celviz methodology: reusable EDA flow documentation and machine-checkable
  methodology manifest so future IP work can reuse the same blueprint-to-gate
  process.

## Not-Yet-Closed Product Gaps

The following items must remain open until backed by stronger evidence:

- Production compiler backend or SPIR-V/LLVM ingestion.
- Full OpenCL runtime and official conformance.
- Real Linux kernel driver, IOMMU integration, or DRM/KMS compatibility.
- Structural RTL coverage closure, CDC, lint waiver closure, formal proofs, and
  constrained-random regression scale-out.
- Logic synthesis through a real target library, STA, area, power, and timing
  closure.
- Security, safety, reliability, DFT, scan, or silicon signoff.
- Proprietary Vivante ISA, firmware, driver, SDK, or command-stream
  compatibility.

## Acceptance Rule

Any future "basic parity" claim must pass the full acceptance wrapper and must
keep the claim boundary visible in generated evidence:

```sh
bash scripts/check_celviz_gpgpu_sources.sh
bash scripts/accept_celviz_gpgpu_ip_full.sh
git diff --check
```

The allowed claim is:

> Ventus-based Celviz clean-room GPGPU IP proxy with executable OpenCL-like
> subset evidence and machine-checked functional/acceptance gates.

The disallowed claim is:

> Vivante-compatible GPGPU IP, official OpenCL GPU, production driver stack, or
> silicon-ready GPU IP.
