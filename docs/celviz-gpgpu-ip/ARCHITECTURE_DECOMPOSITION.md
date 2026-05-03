# Celviz GPGPU IP Architecture Decomposition

Date: 2026-05-02

Worker scope: Worker 1, Celviz architecture-tool decomposition for the Rank 1
Vivante 3D GPGPU IP clean-room proxy using the Ventus GPGPU repository.

## Boundary Statement

Celviz is used here as an external architecture method only. The target project
remains:

- `/Users/nirvana/Documents/New project 2/ventus-gpgpu`

Celviz source remains read-only reference material:

- `/Users/nirvana/Desktop/codextest/celviz/tools/architecture`

The target IP is the Rank 1 Vivante 3D GPGPU IP execution blueprint, not the
older Rank 12 Vivante 3D GPU IP graphics proxy. This document therefore
prioritizes OpenCL-like compute kernels, shader-unit scaling, FP16/FP32
throughput tiers, scheduling/runtime/model evidence, AXI traffic, and
throughput scaling. It intentionally does not decompose Ventus into a 3D
raster, texture, framebuffer, scanout, or blit pipeline.

Reference public anchors:

- `/Users/nirvana/Desktop/codextest/verisilicon-ip-blueprints/blueprints/03_Vivante3DGPGPUIP.md`
- `/Users/nirvana/Desktop/codextest/verisilicon-ip-blueprints/ip_execution/rank_01_vivante_3d_gpgpu_ip.md`

Active local routing anchors:

- `docs/celviz-gpgpu-ip/RANK01_VIVANTE_3D_GPGPU_IP_BLUEPRINT.md`
- `artifacts/rank_01_vivante_3d_gpgpu_ip/`
- `./scripts/accept_celviz_gpgpu_ip.sh`

The older Rank 12 graphics package may be cited only as historical background
or process reference. It is excluded from active GPGPU acceptance and cannot
close any Rank 1 compute criterion.

## Celviz Method Applied

The Celviz architecture-loop reference decomposes an architecture task into a
requirement, measurable benchmark suite, runtime-only simulator workspace,
real subprocess run, gain evaluation, and next patch directive. For this repo,
the method becomes a documentation and evidence contract:

1. Identify executable Ventus layers that already exist.
2. Bind every layer to concrete files and expected evidence.
3. Map those layers to the Rank 1 GPGPU acceptance criteria.
4. Mark each item as `reuse`, `adapt`, `new`, `blocked`, or `forbidden`.
5. Keep public proxy evidence separate from proprietary Vivante equivalence.
6. Do not claim a benchmark, conformance suite, throughput tier, or FP mode is
   closed without logs and mapped evidence.

Status legend:

| Status | Meaning |
| --- | --- |
| `reuse` | Existing Ventus structure directly supports the Rank 1 proxy evidence. |
| `adapt` | Existing Ventus structure is useful but needs a wrapper, metric, tier mapping, shim, or test binding. |
| `new` | No equivalent Ventus block exists; implement a clean-room proxy model, runtime layer, test, or report. |
| `blocked` | Requires licensed VeriSilicon collateral, confidential API/conformance material, or unavailable signoff evidence. |
| `forbidden` | Must not be claimed, modeled, or named as proprietary Vivante behavior. |

## Rank 1 GPGPU Target

Public facts from the blueprint:

- Vivante CC8000/CC8X00 family supports OpenCL 1.1/1.2/3.0 and OpenCV across
  public tiers.
- Public shader-unit scale is 16 to 2048 vec1-equivalent shader units.
- Public FP32/FP16 operations per cycle range from 32/64 to 4096/8192.
- Acceptance requires vector add, GEMM/convolution proxy, image filter, memory
  copy, shader-unit scaling, FP16/FP32 tests, command submission, interrupts,
  AXI traffic, and throughput scaling by configured tier.

Clean-room interpretation:

- Ventus is the compute and memory substrate for executable proxy evidence.
- A new model/runtime layer will present OpenCL-like kernels and tier profiles.
- Public tiers are labels and scaling targets, not claims of Vivante RTL
  equivalence.
- FP32 maps to existing Ventus 32-bit scalar/vector/FPU machinery. FP16 needs a
  proxy model and, if desired later, RTL adaptation; it is not already proven by
  the current Ventus FPU code.

## Architecture Layers

### G0: Top-Level GPGPU Shell

| Ventus source | Observed structure | Rank 1 GPGPU use | Status |
| --- | --- | --- | --- |
| `ventus/src/top/GPGPU_top.scala` | `GPGPU_top` connects host requests, CTA interface, SM wrappers, cluster/L2 arbitration, L2 cache, optional MMU path, and external memory ports. | Compute IP integration spine for S2 RTL smoke and S5 bandwidth evidence. | `reuse` |
| `ventus/src/top/GPGPU_top.scala` | `GPGPU_axi_top` and `GPGPU_axi_adapter_top` connect AXI4-Lite control and AXI memory master wiring. | SoC-facing proxy boundary for command submission and AXI traffic tests. | `adapt` |
| `ventus/src/top/GPGPU_SimWrapper.scala` | Simulation wrapper exposes host request/response, L2 request/response, cycle and instruction counters, ASID fill when MMU is enabled, and I-cache invalidate. | Verilator evidence surface for scheduler, throughput, AXI/memory, and MMU tests. | `reuse` |
| `ventus/src/top/parameters.scala` | Default config exposes `num_sm = 2`, `num_warp = 8`, `num_thread = 32`, L1/L2/cache/MMU parameters, register-file sizes, and CTA scheduler capacities. | Seed configuration for tier scaling experiments and public shader-unit mapping. | `adapt` |

Rank 1 implication:

- Ventus can represent a small compute-tier proxy and can be scaled in a
  controlled clean-room configuration study.
- Public CC8000/CC8X00 tier labels need a separate profile table that maps
  `shader_units_vec1_equiv` to Ventus knobs such as SM count, lanes/thread
  width, active warps, issue assumptions, and model-level throughput scale.

### G1: Command, Runtime, And OpenCL-Like Dispatch

| Ventus source | Observed structure | Rank 1 GPGPU use | Status |
| --- | --- | --- | --- |
| `ventus/src/top/GPGPU_top.scala` | `host2CTA_data` carries workgroup id, wavefront count, wavefront size, start PC, ASID, 3D kernel dimensions, CSR metadata, VGPR/SGPR/LDS/PDS sizes, and base addresses. | Lower OpenCL-like kernel launch descriptors into Ventus CTA dispatch. | `adapt` |
| `ventus/src/axi/AXI4Lite2CTA.scala` | 20 AXI4-Lite registers feed `host2CTA_data`; response exposes completed workgroup id. | Register skeleton for command submission, queue doorbell, completion/fence, and interrupt smoke. | `adapt` |
| `sim-verilator/ventus_rtlsim.h`, `ventus_rtlsim.cpp`, `ventus_rtlsim_impl.cpp` | C API around `libVentusRTL.so` for upper driver simulation. | Runtime shim target for S4 OpenCL-like CLI/demo. | `adapt` |
| `sim-verilator/kernel.cpp`, `cta_sche_wrapper.cpp`, `physical_mem.cpp`, `sim_main.cpp` | Mini driver loads `.metadata` and `.data`, splits kernels into CTAs, manages physical memory, and dumps memory. | Seed runtime path for vector add, matrix, image-filter, and memory-copy workloads. | `reuse` |

Required adaptation:

- Define clean-room kernel descriptors: `kernel_id`, global size, local size,
  argument buffer, precision mode, tier profile, queue id, fence id, and memory
  regions.
- Lower compatible compute kernels to `host2CTA_data`; keep model-only kernels
  in the golden model when RTL binaries or toolchain support are unavailable.
- Add command/status/fault/interrupt evidence. Existing completion is
  workgroup-oriented, so a proxy fence and interrupt register model is needed.

Forbidden:

- Do not call the proxy command ABI a Vivante command stream.
- Do not claim official OpenCL runtime, ICD, compiler, or driver compliance.

### G2: CTA And Workgroup Scheduler

| Ventus source | Observed structure | Rank 1 GPGPU use | Status |
| --- | --- | --- | --- |
| `ventus/src/cta/cta_scheduler.scala` | `cta_scheduler_top` composes WG buffer, allocator, resource table, and CU interface. | Workgroup admission, resource allocation, and completion basis. | `reuse` |
| `ventus/src/cta/wg_buffer.scala` | Buffers host workgroups and exposes allocation/dispatch metadata. | Evidence for queued kernel launches and multi-workgroup pressure. | `reuse` |
| `ventus/src/cta/allocator.scala`, `resource_table.scala`, `cu_interface.scala` | Allocate VGPR/SGPR/LDS/PDS resources and dispatch wavefronts to CUs. | Scheduler/runtime/model mapping for occupancy and scaling. | `reuse` |
| `docs/cta_scheduler/*.md` | Existing CTA scheduler design notes and diagrams. | Human-readable architecture evidence for scheduler decomposition. | `reuse` |

Rank 1 implication:

- CTA scheduling is one of the strongest reuse areas for OpenCL-like kernels.
- Public shader-unit scaling must include scheduler occupancy and resource
  pressure metrics, not only arithmetic throughput labels.
- Runtime/model evidence should track admitted workgroups, active wavefronts,
  completed workgroups, stall/resource-denial reasons, and per-tier occupancy.

### G3: Warp Scheduler And SIMT Pipeline

| Ventus source | Observed structure | Rank 1 GPGPU use | Status |
| --- | --- | --- | --- |
| `ventus/src/pipeline/pipe.scala` | Per-SM pipeline instantiates warp scheduler, decode, operand collector, issue, ALU, vector ALU, FPU, LSU, SFU, multiplier, tensor core, SIMT branch stack, CSR, scoreboard, instruction buffer, writeback, and counters. | Main shader/compute execution substrate. | `reuse` |
| `ventus/src/pipeline/warp_schedule.scala`, `CTA2warp.scala` | Warp creation, PC scheduling, ready masks, branch/flush handling, CTA handoff. | Warp scheduling evidence for throughput and fairness. | `reuse` |
| `ventus/src/pipeline/ibuffer.scala`, `issue.scala`, `DecodeUnit.scala`, `Instructions.scala` | Instruction buffering, issue arbitration, decode, and instruction taxonomy. | ISA-capability map and unsupported-op/error taxonomy. | `adapt` |
| `ventus/src/pipeline/branch_join.scala`, `SIMT_STACK.scala`, `PCcontrol.scala` | SIMT control flow and reconvergence mechanisms. | Branch/divergence stress for OpenCL-like kernels. | `reuse` |

Rank 1 implication:

- This layer supports vector add, matrix add, memory copy, branch/divergence,
  and potentially GEMM/convolution proxy kernels when binaries are available.
- The public Vivante `vec1-equivalent shader unit` metric should be represented
  as a proxy profile, not directly equated to Ventus threads, lanes, or SMs.
- Suggested proxy formula for evidence reports:
  `proxy_vec1_units = active_sms * active_lanes_per_sm * issue_slots_per_cycle *
  precision_width_factor`, where every term must be listed as a clean-room
  modeling assumption.

### G4: Register File, Hazards, And Operand Collection

| Ventus source | Observed structure | Rank 1 GPGPU use | Status |
| --- | --- | --- | --- |
| `ventus/src/pipeline/regfile.scala` | Vector/scalar register storage accessed through the operand collector. | Register pressure and occupancy evidence. | `reuse` |
| `ventus/src/pipeline/operandCollector.scala` | Banked operand collection and scalar/vector operand routing. | Bank conflict and throughput stall evidence. | `reuse` |
| `ventus/src/pipeline/scoreboard.scala` | Per-warp hazards, fence tracking, writeback tracking, and delay/busy signals. | Scheduler stall, dependency, and memory-fence evidence. | `reuse` |
| `ventus/src/pipeline/writeback.scala` | Scalar/vector writeback into the register file. | Completion/throughput accounting. | `reuse` |

Rank 1 implication:

- Register pressure is a first-class limiter for shader-unit scaling and must
  appear in S1/S3/S5 metrics.
- OpenCL-like kernels should report VGPR/SGPR/LDS requirements and observed
  occupancy, especially for GEMM/convolution and image-filter workloads.

### G5: FP32, FP16, Integer, And Tensor Datapaths

| Ventus source | Observed structure | Rank 1 GPGPU use | Status |
| --- | --- | --- | --- |
| `ventus/src/pipeline/ALU.scala` | 32-bit scalar integer ALU operations. | Address arithmetic, indexing, integer kernels, control code. | `reuse` |
| `ventus/src/pipeline/fpu_utils.scala`, `FloatDivSqrt.scala` | `Float32` and 32-bit FPU helper/execution structures. | FP32 path for vector add, GEMM/convolution proxy, and image filters. | `reuse` |
| `ventus/src/pipeline/Multiplier.scala`, `mul_utils.scala`, `IntDivMod.scala` | Multiply/divide units and helpers. | Integer and mixed arithmetic kernels. | `reuse` |
| `ventus/src/pipeline/pipe.scala` | Instantiates `vTCexe` tensor core path. | Possible future tensor/GEMM exploration hook. | `adapt` |
| Current Ventus FPU tree | No explicit proven FP16 execution path was found in the inspected FPU basis. | FP16 public-tier evidence must start as model-level and test-level proxy. | `new` |

FP precision decision:

- FP32: `reuse` for RTL-backed compute evidence when testcases exercise the FPU
  path and logs are captured.
- FP16: `new` clean-room golden model and conversion/packing tests are required.
  RTL FP16 is `blocked` until a real Ventus FP16 path is implemented and tested
  or licensed/vendor collateral is supplied.
- FP32/FP16 operations-per-cycle public tables are `adapt` into tier profiles;
  they are not measured Vivante throughput.

### G6: LSU, L1, Shared Memory, L2, MMU, And AXI

| Ventus source | Observed structure | Rank 1 GPGPU use | Status |
| --- | --- | --- | --- |
| `ventus/src/pipeline/LSU.scala` | Global/shared memory operations, D-cache requests, CSR interactions, fences. | Memory-copy, image-filter, GEMM load/store, and AXI traffic source. | `reuse` |
| `ventus/src/L1Cache/ICache/ICache.scala` | Instruction cache with invalidate and optional TLB path. | Instruction-fetch and control-path evidence. | `reuse` |
| `ventus/src/L1Cache/DCache/DCache.scala`, `DCacheWSHR.scala`, `L1MSHR.scala` | Data cache, MSHR/WSHR, tag access, memory request arbitration, optional TLB path. | Global memory traffic, cache miss, bandwidth, and latency evidence. | `reuse` |
| `ventus/src/L1Cache/ShareMem/ShareMem.scala`, `BankConflictArbiter.scala` | Shared memory with bank conflict arbitration. | OpenCL local-memory/LDS proxy and bank-conflict tests. | `reuse` |
| `ventus/src/L1Cache/AtomicUnit/AtomicUnit.scala` | Atomic operation support in L1 path. | Atomic kernel proxy and memory consistency smoke. | `adapt` |
| `ventus/src/L2cache/Scheduler.scala` and supporting files | L2 scheduler, banks, directory/test store, MSHRs, source/sink channels. | L2 contention, bandwidth/latency, throughput scaling evidence. | `reuse` |
| `ventus/src/mmu/L1TLB.scala`, `L2TLB.scala`, `PTW.scala`, `AsidLookup.scala` | L1/L2 TLB, ASID lookup, PTW and invalidate/refill paths. | MMU stress, fault injection, ASID/context setup. | `reuse` with `adapt` fault taxonomy |
| `ventus/src/axi/AXI4Adapter.scala` | Converts L2 TileLink-like requests to AXI4 read/write bursts. | Required AXI traffic evidence. | `reuse` |
| `ventus/src/axi/AXI4Lite.scala`, `AXI4Lite2CTA.scala` | AXI4-Lite MMIO and dispatch bridge. | Control-plane, command submission, status, and interrupt proxy. | `adapt` |

Rank 1 implication:

- This layer directly supports AXI traffic, memory-copy, bandwidth stress, and
  throughput scaling evidence.
- Image filter and convolution workloads can be modeled as buffer kernels; no
  texture/raster claims are needed.
- MMU must be enabled/configured explicitly in evidence. Current default
  `MMU_ENABLED` is false, so MMU tests are `adapt`/configuration work, not an
  always-on proven default.

### G7: Verilator, Testcases, And Evidence Loop

| Ventus source | Observed structure | Rank 1 GPGPU use | Status |
| --- | --- | --- | --- |
| `sim-verilator/README.md` | Builds `libVentusRTL.so` and mini driver; supports `-f ventus_args.txt`, `--waveform`, and `--dump-mem`. | Standard S2/S3 RTL smoke and result-inspection path. | `reuse` |
| `sim-verilator/testcase/vecadd`, `sim-verilator/testcase/matadd` | Existing metadata/data/log style cases for vector and matrix addition. | Seed vector add and matrix/GEMM-like tests. | `reuse` |
| `ventus/txt/adv_*`, `ventus/txt/saxpy`, `ventus/txt/tensor` | Additional workload data including BFS, Gaussian, nearest neighbor, saxpy, tensor examples. | Candidate kernel catalog for OpenCL-like runtime demos. | `adapt` |
| `scripts/accept_celviz_gpgpu_ip.sh` | One-key active acceptance entrypoint for the Rank 1 GPGPU package. | Authoritative acceptance transcript source when paired with Rank 1 mapped evidence. | `reuse` |
| `scripts/verify_celviz_gpu_ip*.sh` | Existing verification scripts from older GPU-IP work. | Pattern only; Rank 1 scripts must target `celviz-gpgpu-ip` and rank_01 paths. | `adapt` |
| `tools/celviz_gpu_ip/*.py` | Existing model/driver/report helpers from older GPU-IP work. | Pattern only; rename/scope carefully if future workers create GPGPU-specific helpers. | `adapt` |

Rank 1 implication:

- Celviz-style evidence must include real run logs, metrics JSON, command
  records, and a criteria-to-evidence map.
- Testcases should be grouped by benchmark intent: vector add, memory copy,
  GEMM/convolution proxy, image filter, FP32, FP16 model, scheduler scaling,
  AXI traffic, MMU/fault, interrupt/fence.

## Public Tier Mapping Strategy

| Public tier concept | Ventus/proxy basis | Decision |
| --- | --- | --- |
| 16-2048 vec1-equivalent shader units | Model-level tier profiles plus Ventus knobs (`num_sm`, `num_thread`, `num_warp`, issue and lane assumptions). | `adapt` |
| FP32 ops/cycle | Existing FP32 FPU/vector execution plus model-level throughput accounting. | `reuse` for FP32 path, `adapt` for public-tier scale. |
| FP16 ops/cycle | No proven RTL FP16 path in inspected code. | `new` model/test proxy; RTL proof `blocked`. |
| OpenCL-like kernels | Existing `.metadata`/`.data`, mini driver, CTA dispatch, and Ventus toolchain expectations. | `adapt` |
| OpenCV/image filter | Buffer-based compute kernels, not graphics/texture units. | `new` golden model plus `adapt` Ventus compute. |
| Scheduler/runtime/model | CTA scheduler, warp scheduler, sim-verilator driver, new metrics. | `reuse` plus `adapt`. |
| AXI traffic | `AXI4Adapter`, L2 cache requests, memory dumps/logs. | `reuse`. |
| Throughput scaling | Celviz benchmark loop and tier profile metrics. | `new` evidence reports plus `adapt` Ventus configs. |

## Reuse / Adapt / New / Blocked / Forbidden

### Reuse

- `GPGPU_top`, `GPGPU_SimWrapper`, and the SM/L2 integration spine.
- CTA scheduler, workgroup buffer, allocator, resource table, and CU interface.
- Warp scheduler, SIMT branch/reconvergence, decode/issue, scoreboard,
  operand collector, regfile, writeback, LSU, and FP32/vector pipeline.
- I-cache, D-cache, shared memory, L2 cache, L1/L2 TLB/PTW/ASID blocks.
- AXI4 memory adapter and AXI4-Lite type definitions.
- Verilator library/mini-driver flow and seed vecadd/matadd testcases.

### Adapt

- Public GPGPU tier profiles to Ventus clean-room scale knobs.
- AXI4-Lite register bridge into a richer command queue/status/fence/interrupt
  model.
- `.metadata`/`.data` testcase flow into OpenCL-like kernel descriptors and
  benchmark manifests.
- Existing counters/logs into Celviz-style metrics for throughput, occupancy,
  latency, bandwidth, memory traffic, and scheduler stalls.
- MMU tests, because the default config has `MMU_ENABLED = false`.
- Tensor/GEMM hooks, because tensor-core evidence needs explicit tests and
  metrics before it can count.

### New

- Rank 1 `celviz-gpgpu-ip` model/runtime vocabulary and artifact map.
- Public tier profile table for CC8000L, CC8000, CC8200, CC8400, CC8400-MP2,
  CC8400-MP4, CC8800, CC8800-MP2, and CC8800-MP4.
- Golden models for FP16, GEMM/convolution proxy, image filter, memory copy,
  and throughput scaling when RTL-backed kernels are unavailable.
- OpenCL-like command descriptor, runtime CLI, metrics schema, interrupt/fence
  proxy, AXI traffic report, and scheduler scaling report.
- Criteria-to-evidence rows for S0-S5 under `rank_01_vivante_3d_gpgpu_ip`.

### Blocked

- Licensed Vivante RTL, firmware, SDK, compiler, driver, command streams,
  hardware manuals, release notes, errata, conformance suites, or PPA data.
- Official OpenCL/OpenCV compliance evidence without real suites and logs.
- Real CC8000/CC8X00 performance, power, area, cache/MMU/security behavior, or
  silicon signoff evidence.
- RTL FP16 proof until a tested Ventus FP16 path or licensed collateral exists.

### Forbidden

- Do not claim Ventus is Vivante-compatible RTL.
- Do not claim the proxy runtime is an official OpenCL ICD, compiler, or SDK.
- Do not call Ventus threads/lanes/SMs exact Vivante shader units.
- Do not call D-cache/L2 a Vivante texture cache, render backend, or graphics
  cache.
- Do not reuse Rank 12 graphics/framebuffer/triangle acceptance as Rank 1
  GPGPU completion evidence.
- Do not treat old `verify_celviz_gpu_ip` scripts, Rank 12 artifacts, or
  graphics-only reports as an alternate path around
  `./scripts/accept_celviz_gpgpu_ip.sh`.
- Do not claim conformance, certification, tapeout readiness, STA/CDC/DFT, or
  production PPA.

## Evidence Plan By Stage

| Stage | Rank 1 evidence | Architecture mapping |
| --- | --- | --- |
| S0 | Public facts, clean-room scope, architecture inventory, tier profile strategy, reuse/adapt/new/blocked/forbidden matrix. | This document plus `artifacts/rank_01_vivante_3d_gpgpu_ip/spec/architecture_inventory.md`. |
| S1 | Executable golden models for vector add, memory copy, GEMM/convolution proxy, image filter, FP16/FP32 metrics, scheduler/tier estimates, and memory traffic estimates. | New model layer; Ventus testcase catalog as seed. |
| S2 | Verilator-friendly command processor/register shell/scheduler/memory-model smoke logs. | `AXI4Lite2CTA`, `host2CTA_data`, `GPGPU_SimWrapper`, sim-verilator API. |
| S3 | Tests for FP16/FP32, command submission, interrupts/fences, AXI traffic, MMU/fault, scheduler scaling, and throughput scaling. | Ventus tests plus new proxy tests and metrics. |
| S4 | OpenCL-like runtime or CLI demo running kernels and recording outputs. | `sim-verilator` mini-driver/C API plus new command descriptors. |
| S5 | Proxy SoC integration evidence: AXI/APB-style maps, reset/clock/interrupt notes, bandwidth/latency/energy estimates, and safety/security non-goals. | Ventus AXI/cache/counter evidence plus Celviz method. |

## Open Questions For Follow-On Workers

| Question | Current answer |
| --- | --- |
| Should Rank 1 include triangle, texture, or framebuffer tests? | No. Those belong to the old 3D GPU proxy, not this GPGPU-focused target. |
| Can current Ventus run OpenCL-like kernels? | Yes as a proxy through `.metadata`/`.data`, the Ventus toolchain flow, and CTA dispatch; not as official OpenCL compliance. |
| Can current Ventus prove FP16? | No. FP16 starts as a model/test proxy unless RTL support is added and verified. |
| Can public CC8000/CC8X00 tiers be named? | Yes as public tier labels and clean-room profiles; not as performance equivalence. |
| Can Celviz be copied into this repo? | No. Celviz remains an external read-only architecture method. |
