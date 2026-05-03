# Architecture Inventory For Rank 1 Vivante 3D GPGPU IP

Date: 2026-05-02

This S0 inventory maps the open-source Ventus GPGPU framework onto the Rank 1
Vivante 3D GPGPU IP public clean-room proxy target. Celviz is used only as an
external architecture decomposition and evidence-loop method. This repository is
not moved into Celviz and does not vendor Celviz source code.

## Inputs Read

| Input | Role |
| --- | --- |
| `ventus/src/top/` | Top wrappers, host command input, CTA/SM/L2 integration, AXI wrappers, simulation wrappers, external memory. |
| `ventus/src/cta/` | Workgroup/CTA scheduling, allocation, resource tracking, and CU dispatch. |
| `ventus/src/pipeline/` | Warp scheduling, SIMT control, decode/issue, ALU/FPU/LSU/tensor hooks, scoreboard, operand collector, regfile, writeback. |
| `ventus/src/L1Cache/` | I-cache, D-cache, shared memory/LDS, atomics, L1-to-L2 arbitration. |
| `ventus/src/L2cache/` | L2 scheduler, MSHR, banks, source/sink paths, cache parameters. |
| `ventus/src/mmu/` | L1 TLB, L2 TLB, ASID lookup, PTW, invalidation/refill basis. |
| `ventus/src/axi/` | AXI4 memory adapter and AXI4-Lite control bridge. |
| `sim-verilator/` and `sim-verilator-nocache/` | Verilator library, mini driver, C API, physical memory, kernel splitting, testcase flow. |
| `sim-verilator/testcase/` and `ventus/txt/` | Seed vector/matrix/memory and advanced workload data. |
| Rank 1 blueprint | Public acceptance frame: OpenCL/OpenCV, shader-unit scaling, FP16/FP32 ops/cycle, scheduler/runtime/model, AXI traffic, throughput scaling. |
| Celviz architecture tool reference | Method only: measurable layers, benchmark/evidence loop, runtime boundary, truthful pass/fail claims. |

## Public Target Summary

| Public anchor | Clean-room proxy interpretation |
| --- | --- |
| OpenCL 1.1/1.2/3.0 and OpenCV listed for public tiers | Provide OpenCL-like kernel descriptors and OpenCV-like image-filter workloads; do not claim official API conformance. |
| 16 to 2048 vec1-equivalent shader units | Provide public tier profiles and clean-room scaling model; do not equate Ventus SM/lane counts to Vivante shader units. |
| 32/64 to 4096/8192 FP32/FP16 ops/cycle | Provide FP32 RTL-backed or model-backed evidence where tested; provide FP16 model evidence unless RTL FP16 is added and verified. |
| Scheduler/runtime/model work | Reuse Ventus CTA and warp schedulers; add runtime descriptors, metrics, and model reports. |
| AXI traffic | Reuse Ventus L2-to-AXI adapter and memory hierarchy for traffic logs and stress tests. |
| Throughput scaling | Use Celviz-style benchmark/gain reports over vector add, memory copy, GEMM/convolution proxy, and image filter. |

## Inventory Matrix

| ID | Layer | Ventus basis | Rank 1 mapping | Decision | Evidence handle |
| --- | --- | --- | --- | --- | --- |
| R1-A0.1 | Top shell | `GPGPU_top` connects host, CTA, SMs, clusters, L2, optional MMU, and external memory. | Compute IP integration spine. | `reuse` | S2 smoke, S5 integration. |
| R1-A0.2 | AXI top | `GPGPU_axi_top`, `GPGPU_axi_adapter_top`. | AXI4-Lite control plus AXI4 memory master proxy. | `adapt` | Register map, AXI traffic logs. |
| R1-A0.3 | Simulation top | `GPGPU_SimWrapper` exposes host/L2 interfaces and counters. | Verilator evidence surface. | `reuse` | S2/S3 run logs. |
| R1-A0.4 | Config knobs | `parameters.scala`: `num_sm`, `num_warp`, `num_thread`, cache and register sizes. | Public tier scaling profile basis. | `adapt` | Tier profile metrics. |
| R1-A1.1 | Kernel launch | `host2CTA_data` fields for WG id, WF count/size, PC, ASID, 3D grid, CSR, VGPR/SGPR/LDS/PDS. | Lower OpenCL-like kernel descriptors. | `adapt` | Runtime command tests. |
| R1-A1.2 | Control bridge | `AXI4Lite2CTA` register bridge to CTA dispatch. | Command queue, doorbell, status, fence, interrupt proxy skeleton. | `adapt` | S2 register/control smoke. |
| R1-A1.3 | Runtime C API | `ventus_rtlsim.h/cpp`, `ventus_rtlsim_impl.cpp`. | Driver shim and CLI demo target. | `adapt` | S4 demo logs. |
| R1-A1.4 | Mini driver | `sim_main.cpp`, `kernel.cpp`, `physical_mem.cpp`, `cta_sche_wrapper.cpp`. | Workload materialization and result inspection. | `reuse` | S3/S4 testcase outputs. |
| R1-A2.1 | CTA scheduler | `cta_scheduler_top`, WG buffer, allocator, resource table, CU interface. | Workgroup scheduling, occupancy, resource pressure. | `reuse` | Scheduler metrics. |
| R1-A2.2 | Warp scheduler | `warp_schedule.scala`, `CTA2warp.scala`. | Warp dispatch, ready masks, branch/flush behavior. | `reuse` | Warp scheduling traces/counters. |
| R1-A2.3 | SIMT pipeline | `pipe.scala` with decode, issue, ALU, FPU, LSU, SFU, MUL, tensor hook, CSR, branch, scoreboard, writeback. | OpenCL-like compute execution substrate. | `reuse` | Vector/matrix/image/kernel logs. |
| R1-A2.4 | Decode/ISA taxonomy | `DecodeUnit.scala`, `Instructions.scala`. | Supported/unsupported op map and error classes. | `adapt` | Shader/runtime fault tests. |
| R1-A3.1 | Register file | `regfile.scala`. | VGPR/SGPR pressure, occupancy, and scale limits. | `reuse` | Occupancy metrics. |
| R1-A3.2 | Operand collector | `operandCollector.scala`. | Bank pressure and issue stall evidence. | `reuse` | Stall metrics. |
| R1-A3.3 | Scoreboard | `scoreboard.scala`. | Dependency, fence, and writeback hazard tracking. | `reuse` | Scheduler stall reports. |
| R1-A3.4 | Writeback | `writeback.scala`. | Completion accounting. | `reuse` | Throughput counters. |
| R1-A4.1 | FP32 | `fpu_utils.scala`, `FloatDivSqrt.scala`, `FPUexe` path in `pipe.scala`. | FP32 kernels and metrics. | `reuse` when tested | FP32 vector/GEMM logs. |
| R1-A4.2 | Integer/vector | `ALU.scala`, `Multiplier.scala`, `IntDivMod.scala`, vector ALU/MUL in `pipe.scala`. | Indexing, integer kernels, memory-copy helpers. | `reuse` | Integer/kernel logs. |
| R1-A4.3 | FP16 | No proven FP16 RTL path in inspected FPU files. | Model-level FP16 proxy and optional future RTL extension. | `new` / RTL proof `blocked` | S1 model metrics, S3 FP16 tests. |
| R1-A4.4 | Tensor/GEMM hook | `vTCexe` instantiated in `pipe.scala`, tensor test data under `ventus/txt/tensor`. | GEMM/convolution proxy exploration. | `adapt` | GEMM/convolution reports. |
| R1-A5.1 | LSU | `LSU.scala`. | Global/shared memory traffic, memory copy, image filter, AXI source. | `reuse` | LSU/memory counters. |
| R1-A5.2 | L1 I-cache | `ICache.scala`. | Instruction-fetch and invalidation evidence. | `reuse` | I-cache test logs. |
| R1-A5.3 | L1 D-cache | `DCache.scala`, `DCacheWSHR.scala`, `L1MSHR.scala`. | Global memory traffic, cache miss, bandwidth/latency evidence. | `reuse` | Memory stress logs. |
| R1-A5.4 | Shared memory/LDS | `ShareMem.scala`, `BankConflictArbiter.scala`. | OpenCL local memory and bank-conflict evidence. | `reuse` | LDS/bank tests. |
| R1-A5.5 | Atomics | `AtomicUnit.scala`. | Atomic kernel smoke and memory consistency proxy. | `adapt` | Atomic test logs. |
| R1-A5.6 | L2 cache | `L2cache/Scheduler.scala`, MSHR, BankedStore, Source/Sink modules. | L2 contention, bandwidth, traffic shaping. | `reuse` | S5 bandwidth/latency. |
| R1-A5.7 | MMU | `L1TLB.scala`, `L2TLB.scala`, `PTW.scala`, `AsidLookup.scala`. | ASID/context setup, TLB stress, fault injection. | `reuse` with config `adapt` | MMU/fault logs. |
| R1-A5.8 | AXI memory | `AXI4Adapter.scala`. | AXI read/write burst traffic evidence. | `reuse` | AXI traffic report. |
| R1-A5.9 | AXI4-Lite | `AXI4Lite.scala`, `AXI4Lite2CTA.scala`. | Control-plane model, status, interrupt/fence proxy. | `adapt` | Register smoke. |
| R1-A6.1 | Testcases | `sim-verilator/testcase/vecadd`, `matadd`, `ventus/txt/adv_*`, `saxpy`, `tensor`. | Benchmark seed catalog. | `reuse` / `adapt` | S3/S4 commands and logs. |
| R1-A6.2 | No-cache sim | `sim-verilator-nocache/`. | Control lane for cache sensitivity and traffic comparisons. | `adapt` | Cache/no-cache comparison. |
| R1-N1 | Public tier registry | No direct Ventus block. | CC8000/CC8X00 clean-room profiles. | `new` | S0/S1 metrics. |
| R1-N2 | OpenCL-like runtime schema | No direct Ventus block. | Kernel descriptors, queues, args, precision mode, fences. | `new` | S2/S4 demos. |
| R1-N3 | Golden compute model | Partial seed in test data only. | Vector add, memory copy, GEMM/convolution, image filter, FP16/FP32. | `new` | S1 run log, metrics JSON. |
| R1-N4 | Throughput scaling model | Existing counters only. | Tier-normalized throughput and occupancy reports. | `new` | S1/S5 reports. |
| R1-N5 | Interrupt/fence proxy | Workgroup completion only. | Driver-visible fence/interrupt status. | `new` / `adapt` | S2/S3 tests. |

## Required Rank 1 Architecture Layers

### OpenCL-Like Runtime And Command Plane

Required:

- Kernel descriptor schema with global/local work sizes, arguments, memory
  regions, precision mode, queue id, fence id, and tier profile.
- Command submission path through MMIO or runtime shim.
- Completion, fence, interrupt, status, and fault records.

Ventus mapping:

- Adapt `host2CTA_data` as the low-level compute launch payload.
- Adapt `AXI4Lite2CTA` from a 20-register CTA bridge into a richer proxy command
  control plane.
- Adapt `sim-verilator` C API and mini driver for S4 demos.

Decision:

- `adapt` Ventus dispatch/runtime.
- `new` OpenCL-like clean-room command schema and evidence metrics.
- `forbidden` official OpenCL ICD/compiler/runtime claims.

### Scheduler And Shader-Unit Scaling

Required:

- Scheduler model for public shader-unit tiers.
- Runtime metrics showing active workgroups, active warps, occupancy, stalls,
  resource pressure, and throughput scaling.

Ventus mapping:

- Reuse CTA scheduler, allocator, resource table, CU interface, warp scheduler,
  and pipeline counters.
- Adapt `parameters.scala` knobs into small/medium/large proxy profiles.
- Add a public tier registry for CC8000L through CC8800-MP4 labels.

Decision:

- `reuse` scheduler structures.
- `adapt` Ventus parameters to clean-room scale studies.
- `new` tier registry and scaling reports.

### FP16 And FP32 Compute

Required:

- FP16/FP32 test coverage and operations-per-cycle tier reporting.

Ventus mapping:

- Reuse inspected FP32 basis (`Float32`, FPU utilities, FPU execution path)
  only when tests exercise it and logs exist.
- Start FP16 as a golden-model precision mode with conversion, rounding, and
  error-tolerance tests.
- Do not count FP16 RTL evidence until implemented and verified.

Decision:

- FP32: `reuse` plus evidence.
- FP16: `new` model/test proxy; RTL proof `blocked`.
- Public FP ops/cycle: `adapt` to tier profiles, not measured Vivante data.

### Workloads

Required:

- Vector add.
- GEMM/convolution proxy.
- Image filter.
- Memory copy.
- Scheduler and throughput scaling.
- AXI traffic stress.

Ventus mapping:

- Reuse `sim-verilator/testcase/vecadd`.
- Reuse/adapt `matadd`, `saxpy`, `adv_gaussian`, `adv_nn`, `tensor`, and memory
  dump flows as workload seeds.
- Add golden model outputs and metrics for workloads not yet RTL-backed.

Decision:

- `reuse` existing vector/matrix seeds.
- `adapt` advanced test data into named benchmark cases.
- `new` golden model and metrics schema for missing kernels.

### Memory, MMU, And AXI Traffic

Required:

- AXI traffic tests.
- Bandwidth and latency reports.
- MMU stress/fault evidence.

Ventus mapping:

- Reuse LSU, D-cache, shared memory, L2 cache, and AXI4 adapter.
- Reuse L1/L2 TLB, PTW, and ASID lookup, but enable/configure MMU explicitly.
- Adapt logs/counters into traffic summaries.

Decision:

- `reuse` memory hierarchy and AXI adapter.
- `adapt` MMU configuration and traffic accounting.
- `new` AXI report format and pass/fail thresholds.

### Simulation And Verification

Required:

- Repeatable commands and logs for S1-S5 evidence.
- No fake benchmark closure.

Ventus mapping:

- Reuse `make -j run`, `make RELEASE=1 -j run`, `-f ventus_args.txt`,
  `--dump-mem`, and waveform options from `sim-verilator`.
- Add rank_01-specific scripts and evidence paths in future worker scopes.

Decision:

- `reuse` Verilator flow.
- `adapt` scripts/reporting to Rank 1 path names.
- `new` criteria-to-evidence mapping and metrics JSON.

## Reuse, Adapt, New, Blocked, Forbidden

### Reuse

- Top-level GPGPU integration spine.
- CTA/workgroup scheduling and resource allocation.
- Warp scheduler, SIMT pipeline, register file, scoreboard, operand collector,
  writeback, LSU, FP32/vector datapath.
- I-cache, D-cache, shared memory, L2 cache, AXI4 memory adapter.
- L1/L2 TLB, PTW, ASID lookup as proxy MMU basis.
- Verilator library, mini driver, and seed vector/matrix testcases.

### Adapt

- `host2CTA_data` and AXI4-Lite registers for OpenCL-like command descriptors.
- Ventus configuration knobs to public tier labels and shader-unit scaling
  assumptions.
- Existing workload data to Rank 1 benchmark names.
- Existing counters/logs to Celviz-style metrics.
- MMU tests because the current default has `MMU_ENABLED = false`.
- Existing scripts and helper names that still reference older clean-room work,
  when they are adapted to the active Rank 1 GPGPU target.

### New

- Rank 1 GPGPU capability/tier registry.
- OpenCL-like kernel descriptor and runtime/CLI schema.
- Golden FP16 path and precision comparison tests.
- Golden GEMM/convolution, image filter, memory-copy, and throughput scaling
  models where RTL testcases are not present.
- Interrupt/fence/status/fault proxy model.
- AXI traffic, occupancy, bandwidth, latency, and throughput metrics schema.

### Blocked

- Licensed VeriSilicon/Vivante RTL, firmware, SDK, compiler, driver, command
  streams, proprietary manuals, release notes, errata, or conformance suites.
- Official OpenCL/OpenCV certification or compliance claims.
- Real CC8000/CC8X00 PPA, timing, cache/MMU/security behavior, or silicon
  signoff.
- RTL-backed FP16 acceptance until a tested implementation is present.

### Forbidden Equivalent Claims

- Do not claim Ventus is a Vivante CC8000/CC8X00 implementation.
- Do not claim command-stream, ISA, compiler, firmware, SDK, or driver
  compatibility.
- Do not equate Ventus `num_sm`, `num_thread`, `num_warp`, or lanes exactly to
  Vivante vec1 shader units.
- Do not reuse graphics/raster/framebuffer/texture evidence from historical
  graphics-only packages as Rank 1 GPGPU completion evidence.
- Do not claim official conformance, production PPA, or tapeout readiness.

## Initial Work Slices

| Slice | Output | Architecture basis |
| --- | --- | --- |
| S0-A | Freeze this inventory and decomposition. | Celviz method plus Ventus source read. |
| S0-B | Define Rank 1 public tier registry and clean-room non-goals. | Public Vivante GPGPU blueprint. |
| S1-A | Golden compute model for vector add, memory copy, GEMM/convolution proxy, image filter, FP32, FP16. | New clean-room model. |
| S1-B | Scheduler/tier throughput model with occupancy and memory pressure. | CTA scheduler, warp scheduler, regfile, L1/L2, AXI assumptions. |
| S2-A | Register/control shell and command descriptor smoke. | `AXI4Lite2CTA`, `host2CTA_data`, `GPGPU_SimWrapper`. |
| S2-B | Verilator compute smoke through seed testcases. | `sim-verilator/testcase/vecadd`, `matadd`. |
| S3-A | FP16/FP32, command, interrupt/fence, AXI traffic, MMU/fault, throughput scaling tests. | Ventus tests plus new proxy tests. |
| S4-A | OpenCL-like CLI/runtime demo with inspectable outputs and logs. | `sim-verilator` C API and mini-driver pattern. |
| S5-A | Proxy SoC integration report for AXI, clocks/resets, interrupts, latency, bandwidth, and energy estimates. | Ventus counters/logs plus Celviz evidence-loop method. |

## Acceptance Notes

- Missing evidence is `unproven`, not complete.
- A stage may be complete only when its artifact path under
  `artifacts/rank_01_vivante_3d_gpgpu_ip/` contains mapped evidence and logs.
- Public tier names may be used for organization, but every metric must state
  whether it is measured RTL simulation, golden-model output, or a proxy
  estimate.
- The architecture direction is GPGPU compute. 3D graphics features are outside
  this worker's Rank 1 mapping unless a later blueprint explicitly re-adds them.
- Historical Rank 12 graphics-only material is reference context only and is not
  an active acceptance source for this Rank 1 GPGPU package.
