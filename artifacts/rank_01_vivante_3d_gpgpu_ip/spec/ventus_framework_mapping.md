# Artifact Spec: Ventus Framework Mapping

Date: 2026-05-02

Owner: Worker 6

Scope: concrete local mapping from Ventus framework modules to the active
Rank 1 `Celviz GPGPU IP` blueprint. This file is evidence planning, not a code
change and not a Vivante compatibility claim.

## Mapping Contract

| Field | Value |
| --- | --- |
| Active local target | `Celviz GPGPU IP` |
| Public anchor | `Vivante 3D GPGPU IP` |
| Repository | `/Users/nirvana/Documents/New project 2/ventus-gpgpu` |
| Artifact root | `artifacts/rank_01_vivante_3d_gpgpu_ip/` |
| External method | Celviz architecture decomposition method only |
| Explicit exclusion | 3D graphics blocks and historical graphics-only evidence |

## Module Decision Matrix

| ID | Area | Ventus path/module | Blueprint mapping | Decision | Next evidence |
| --- | --- | --- | --- | --- | --- |
| WF-001 | Top shell | `ventus/src/top/GPGPU_top.scala::GPGPU_top` | Compute integration spine with CTA, SM, L2, memory ports. | `reuse` | S2/S3 Verilator smoke with host launch and readback. |
| WF-002 | Host payload | `ventus/src/top/GPGPU_top.scala::host2CTA_data` | Low-level workgroup launch record. | `adapt` | JSON/OpenCL-like descriptor lowering to host fields. |
| WF-003 | AXI top | `ventus/src/top/GPGPU_top.scala::GPGPU_axi_top` | SoC-facing AXI4-Lite control and AXI4 memory boundary. | `adapt` | Register smoke plus AXI traffic capture. |
| WF-004 | Config | `ventus/src/top/parameters.scala` | SM/warp/thread/cache/register/MMU knobs for clean-room tiers. | `adapt` | Profile table with explicit assumptions. |
| WF-005 | CTA scheduler | `ventus/src/cta/cta_scheduler.scala::cta_scheduler_top` | Workgroup admission, CU dispatch, completion. | `reuse` | Occupancy, dispatch, completion, resource-pressure metrics. |
| WF-006 | WG buffer | `ventus/src/cta/wg_buffer.scala::wg_buffer` | Queue pressure and command admission. | `reuse` | Queue depth/backpressure counters. |
| WF-007 | Alloc/resource | `ventus/src/cta/allocator.scala`, `resource_table.scala` | VGPR/SGPR/LDS/WG slot allocation. | `reuse` | Resource denial and active allocation reports. |
| WF-008 | CU interface | `ventus/src/cta/cu_interface.scala::cu_interface` | WG-to-WF splitting, per-WF bases, WF gather, WG done. | `reuse` | WF dispatch/done and dealloc counters. |
| WF-009 | CTA2warp | `ventus/src/pipeline/CTA2warp.scala::CTA2warp` | Hardware warp slot allocation/release. | `reuse` | Active warp slot metrics. |
| WF-010 | Warp scheduler | `ventus/src/pipeline/warp_schedule.scala::warp_scheduler` | Ready masks, barrier, flush, end program, optional ASID. | `reuse` | Ready/blocked/issued/done/barrier counters. |
| WF-011 | SIMT pipeline | `ventus/src/pipeline/pipe.scala` | Main compute execution substrate. | `reuse` | Instruction mix, retire, stall, FP32/LSU counters. |
| WF-012 | Decode/ISA | `ventus/src/pipeline/DecodeUnit.scala`, `Instructions.scala` | Supported operation matrix and fault taxonomy. | `adapt` | Kernel capability matrix. |
| WF-013 | Reg/scoreboard | `regfile.scala`, `operandCollector.scala`, `scoreboard.scala`, `writeback.scala` | Register pressure, hazards, writeback throughput. | `reuse` | SGPR/VGPR pressure and stall reports. |
| WF-014 | FP32 | `fpu_utils.scala`, `FloatDivSqrt.scala`, FP paths in `pipe.scala` | FP32 compute when tests exercise it. | `reuse` when tested | FP32 vector/SAXPY/matrix logs against golden output. |
| WF-015 | FP16 | No proven inspected RTL path. | FP16 public-tier proxy. | `new` / RTL `blocked` | Golden-model FP16 logs; no RTL pass until implemented. |
| WF-016 | LSU | `ventus/src/pipeline/LSU.scala::LSUexe`, `AddrCalculate` | Global/shared memory traffic source. | `reuse` | Load/store/shared/fence/coalescing counters. |
| WF-017 | LDS | `ventus/src/L1Cache/ShareMem/ShareMem.scala`, `BankConflictArbiter.scala` | OpenCL local memory proxy. | `reuse` | Bank conflict and shared-memory stress logs. |
| WF-018 | D-cache | `ventus/src/L1Cache/DCache/DCache.scala`, `DCacheWSHR.scala`, `L1MSHR.scala` | Global memory traffic and cache behavior. | `reuse` | Hit/miss/MSHR/WSHR/byte counters. |
| WF-019 | I-cache | `ventus/src/L1Cache/ICache/ICache.scala` | Kernel fetch/invalidation. | `reuse` | Invalidate/fetch evidence. |
| WF-020 | L2 | `ventus/src/L2cache/Scheduler.scala` and helpers | L2 contention, service latency, bandwidth. | `reuse` | Request/response/latency/bank pressure reports. |
| WF-021 | MMU | `ventus/src/mmu/L1TLB.scala`, `L2TLB.scala`, `PTW.scala`, `AsidLookup.scala` | ASID, TLB, PTW, fault stress. | `reuse` with `adapt` | MMU-enabled profile and fault tests. |
| WF-022 | AXI memory | `ventus/src/axi/AXI4Adapter.scala` | AXI read/write burst traffic evidence. | `reuse` | Burst/byte/outstanding/latency logs. |
| WF-023 | AXI4-Lite | `ventus/src/axi/AXI4Lite.scala`, `AXI4Lite2CTA.scala` | Control plane and status proxy. | `adapt` | Doorbell/status/fence/interrupt register map. |
| WF-024 | RTLSIM C API | `sim-verilator/ventus_rtlsim.h`, `ventus_rtlsim_impl.cpp` | Host/runtime bridge. | `adapt` | JSON descriptor runner and readback. |
| WF-025 | Mini driver | `sim-verilator/sim_main.cpp`, `cmdarg.cpp`, `kernel.cpp`, `physical_mem.cpp` | Existing metadata/data execution loop. | `reuse` | Rank 1 command manifests and memory dumps. |
| WF-026 | Testcases | `sim-verilator/testcase/vecadd`, `matadd`, `ventus/txt/*` | Workload seeds for vector, matrix, image, memory, SAXPY, tensor. | `reuse` / `adapt` | Named benchmark catalog with golden comparison. |
| WF-027 | Tier registry | No direct Ventus module. | Public CC8000/CC8X00 labels and ops/cycle table. | `new` | Clean-room profile JSON/report. |
| WF-028 | Official API conformance | No local evidence. | OpenCL/OpenCV certification. | `blocked` | Only possible with real licensed suites and logs. |

## Hooks By Blueprint Stage

### S1 Model And Workload Hooks

| Workload | Current Ventus seed | Next hook | Status |
| --- | --- | --- | --- |
| Vector add | `sim-verilator/testcase/vecadd/`, `ventus/txt/adv_vecadd*` | Promote one metadata/data case to standard smoke; compare readback to golden model. | `reuse` |
| GEMM/convolution proxy | `sim-verilator/testcase/matadd/`, `ventus/txt/adv_matadd/`, `ventus/txt/tensor/` | Start with matrix-add memory/compute smoke, then add tiled GEMM proxy descriptor. | `adapt` |
| Image filter | `ventus/txt/adv_gaussian/`, `adv_gaussian_1x16/` | Wrap as buffer-based image filter; compare dump to golden output. | `adapt` |
| Memory copy | `sim-verilator` physical memory h2d/d2h and dump path | Add copy/fill descriptor and readback hash. | `new` around reused API |
| FP32 | `saxpy`, mat/vec seeds, FP paths | Add FP32 golden tolerance checks. | `adapt` |
| FP16 | No RTL proof | Keep model-only until RTL path exists. | `new` / RTL `blocked` |

### S2 Command And RTL Skeleton Hooks

| Need | Hook | First code touch for future worker |
| --- | --- | --- |
| Command queue | `AXI4Lite2CTA` register bridge | Add queue-depth or single-entry command wrapper with command id and status. |
| Kernel dispatch | `host2CTA_data` and `CTAinterface` | Descriptor lowering and field validation. |
| DMA copy/fill | `ventus_rtlsim_pmemcpy_h2d/d2h` and AXI memory path | Runtime-side copy/fill first; RTL-side DMA proxy later. |
| Fence/interrupt | `CTA2host_data` completion from `cta_scheduler_top` | Add fence id and interrupt status proxy around WG done. |
| Fault/error | MMU and decode/unsupported-op taxonomy | Add error code fields and tests; do not claim vendor fault codes. |

### S3 Verification Hooks

| Need | Hook | Evidence |
| --- | --- | --- |
| Command submission | AXI4-Lite writes or runtime JSON runner | Register/readback log and status transition. |
| Interrupts/fences | CTA completion path | Fence id observed complete; interrupt pending/clear. |
| AXI traffic | L2-to-AXI adapter | Read/write burst and byte counters. |
| MMU/fault | `MMU_ENABLED` profile plus TLB/PTW | ASID fill, TLB miss, fault injection logs. |
| Throughput scaling | `parameters.scala` profiles plus counters/model | Per-tier profile report with assumptions. |

### S4 Runtime Hooks

| Need | Hook |
| --- | --- |
| Kernel descriptors | `ventus_kernel_metadata_t`, metadata/data files, JSON descriptor. |
| Argument binding | Buffer base/size arrays in metadata and physical memory copies. |
| Dispatch | `ventus_rtlsim_add_kernel` or `ventus_rtlsim_add_kernel__delay_data_loading`. |
| Readback | `ventus_rtlsim_pmemcpy_d2h` and `--dump-mem`. |
| Output inspection | Golden comparison, hashes, metrics JSON, and run log. |

### S5 Integration Hooks

| Need | Hook | Boundary |
| --- | --- | --- |
| Bandwidth/latency | D-cache/L2/AXI counters and simulation cycles. | Proxy-level only. |
| Power | Activity proxies from instruction/memory counters. | Estimate only; no silicon PPA. |
| Reset/clock | Existing top and Verilator reset/step flow. | Functional evidence only. |
| Interrupt | Fence/interrupt proxy once implemented. | Local ABI only. |
| Safety/security | MMU/fault notes and blocked claims. | No certification claims. |

## Boundary Evidence

Historical graphics-only material may be read for context, but it is not active
acceptance evidence for this Rank 1 GPGPU package. Rank 1 completion must be
supported by the artifact paths in this package or by source implementation
paths used by the Rank 1 clean-room proxy.

## Do-Not-Use As Rank 1 Evidence

- Historical graphics-only documentation except as superseded context.
- Historical graphics-only artifact packages as completion evidence.
- Any triangle, texture, raster, framebuffer, scanout, display, or blit artifact.
- Any statement equating Ventus SMs, lanes, or warps exactly to Vivante shader
  units.
- Any statement that the local runtime is an official OpenCL ICD/compiler/SDK.
