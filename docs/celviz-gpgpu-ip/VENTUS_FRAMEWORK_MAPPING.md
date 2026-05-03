# Ventus Framework Mapping For Celviz GPGPU IP

Date: 2026-05-02

Worker: Worker 6

Target: active Rank 1 `Celviz GPGPU IP`, anchored to the public
`Vivante 3D GPGPU IP` blueprint.

Boundary: this is a GPGPU compute mapping only. Celviz is used as an external
architecture decomposition method. This repository remains the implementation
workspace. Do not treat rasterization, texture sampling, triangle setup,
framebuffer, scanout, display, or blit work as Rank 1 completion evidence.

The older Rank 12 graphics package is preserved as history/reference only and
is excluded from active GPGPU acceptance.

Active acceptance routing:

- Local blueprint: `docs/celviz-gpgpu-ip/RANK01_VIVANTE_3D_GPGPU_IP_BLUEPRINT.md`
- Artifact root: `artifacts/rank_01_vivante_3d_gpgpu_ip/`
- Acceptance entrypoint: `./scripts/accept_celviz_gpgpu_ip.sh`

## Inputs Inspected

| Input | Purpose |
| --- | --- |
| `docs/celviz-gpgpu-ip/RANK01_VIVANTE_3D_GPGPU_IP_BLUEPRINT.md` | Active public clean-room target, S0-S5 gates, and acceptance criteria. |
| `docs/celviz-gpgpu-ip/ARCHITECTURE_DECOMPOSITION.md` | Existing Celviz-style architecture inventory and non-goals. |
| `./scripts/accept_celviz_gpgpu_ip.sh` | Authoritative one-key active acceptance entrypoint for Rank 1 GPGPU evidence. |
| `artifacts/rank_01_vivante_3d_gpgpu_ip/spec/public_scope.md` | Public facts and blocked claims. |
| `artifacts/rank_01_vivante_3d_gpgpu_ip/spec/architecture_inventory.md` | Existing layer inventory that this worker refines into implementation hooks. |
| `ventus/src/top/` | Top shell, host dispatch payload, GPGPU top, AXI wrapper, config knobs. |
| `ventus/src/cta/` | Workgroup buffer, allocator, resource table, CU interface, CTA scheduler. |
| `ventus/src/pipeline/` | Warp scheduler, CTA-to-warp bridge, SIMT pipeline, LSU, scoreboard, regfile, execution units. |
| `ventus/src/L1Cache/` | D-cache, I-cache, shared memory/LDS, atomic unit, L1-to-L2 arbitration. |
| `ventus/src/L2cache/` | L2 scheduler, MSHR, banked store, source/sink channels. |
| `ventus/src/mmu/` | L1 TLB, L2 TLB, PTW, ASID lookup, invalidation/refill basis. |
| `ventus/src/axi/` | AXI4 memory adapter and AXI4-Lite CTA bridge. |
| `sim-verilator/`, `sim-verilator-nocache/` | C API, mini driver, kernel metadata loader, physical memory, testcase execution flow. |
| `sim-verilator/testcase/`, `ventus/txt/` | Existing vector, matrix, Gaussian, nearest-neighbor, SAXPY, tensor, barrier, and memory testcase seeds. |

## Mapping Status Legend

| Status | Meaning |
| --- | --- |
| `reuse` | Existing Ventus module can serve the Rank 1 compute proxy with evidence collection. |
| `adapt` | Existing module is useful but needs a wrapper, metric tap, config, command schema, or testcase binding. |
| `new` | No local Ventus equivalent exists; implement a clean-room proxy layer or report. |
| `blocked` | Requires vendor/proprietary collateral, licensed conformance suites, or silicon evidence. |

## Rank 1 Blueprint Needs

| Blueprint need | Clean-room Ventus interpretation |
| --- | --- |
| OpenCL-like compute | Kernel descriptors and runtime CLI that lower to Ventus metadata/data or C API launch records. |
| OpenCV-like workload | Buffer-based image/filter kernels; no texture unit, raster pipe, or framebuffer implication. |
| Shader-unit scaling | Public CC8000/CC8X00 tier profiles mapped to explicit Ventus/proxy assumptions. |
| FP32/FP16 paths | FP32 can be RTL-backed when testcases exercise the path; FP16 remains model/proxy until RTL support exists. |
| Command submission | AXI4-Lite or runtime shim writes kernel launch descriptors, doorbells, status, fences, errors, and interrupts. |
| Scheduler evidence | CTA and warp scheduler metrics for active workgroups, active warps, stalls, resource pressure, and completion. |
| Memory/AXI traffic | LSU, D-cache, shared memory, L2, MMU, and AXI adapter traffic reports. |
| S5 integration | Proxy-level bandwidth, latency, reset, clock, interrupt, and safety/security notes, not silicon signoff. |

## Acceptance Boundary

Only Rank 1 compute evidence mapped to the local GPGPU blueprint and accepted
through `./scripts/accept_celviz_gpgpu_ip.sh` is active GPGPU acceptance
evidence. Superseded Rank 12 graphics evidence may inform formatting or
process, but it cannot satisfy vector add, GEMM/convolution proxy, image
filter, memory copy, FP16/FP32, scheduler, AXI, command, interrupt, or
throughput criteria.

## Framework Mapping

### 1. Top Shell And Configuration

| Ventus path | Current role | Rank 1 use | Status | Implementation hook |
| --- | --- | --- | --- | --- |
| `ventus/src/top/parameters.scala` | Defines `num_sm = 2`, `num_warp = 8`, `num_thread = 32`, cache sizes, register slots, shared memory, L2, and `MMU_ENABLED = false`. | Seed clean-room tier profiles and scheduler/memory scale experiments. | `adapt` | Add a future GPGPU tier profile layer that records profile name, SM/thread/warp assumptions, FP32/FP16 model scaling, and whether MMU is enabled. |
| `ventus/src/top/GPGPU_top.scala` | `host2CTA_data`, `CTAinterface`, `GPGPU_top`, `GPGPU_axi_top`, and AXI adapter top. | Main compute IP integration spine for S2/S3/S5. | `reuse` / `adapt` | Lower OpenCL-like descriptors to `host2CTA_data`; add status/fence/interrupt proxy around completion. |
| `ventus/src/top/GPGPU_SimWrapper.scala` | Simulation wrapper around host request/response, L2 request/response, counters, ASID fill, and I-cache invalidation. | Verilator-facing evidence surface. | `reuse` | Hook runtime/test harness to collect cycle, instruction, host response, and memory traffic observations. |
| `ventus/src/top/FakeCache.scala`, `Mem_SimWrapper.scala`, `ExternalMemModel.scala`, `MemBox.scala` | Simulation and memory helper blocks. | Memory-model and no-cache/sensitivity evidence. | `adapt` | Use as controlled comparison points for memory-copy, image-filter, and AXI traffic tests. |

### 2. Host Runtime And Command Path

| Ventus path | Current role | Rank 1 use | Status | Implementation hook |
| --- | --- | --- | --- | --- |
| `ventus/src/axi/AXI4Lite2CTA.scala` | 20 MMIO registers write a single CTA launch payload and read workgroup completion. | Register skeleton for command submission and status. | `adapt` | Extend or wrap with queue doorbell, command id, kernel id, precision mode, tier profile id, DMA copy/fill op, fence id, interrupt enable/status, error code, and MMU fault fields. |
| `sim-verilator/ventus_rtlsim.h` | C API for default config, sim init/step/finish, kernel add, memory copy, parameter query, and I-cache invalidate. | S4 OpenCL-like runtime bridge. | `adapt` | Build a `celviz_gpgpu` host shim that converts JSON descriptors to `ventus_kernel_metadata_t`, memory uploads, kernel submission, stepping, readback, and metrics. |
| `sim-verilator/kernel.hpp`, `kernel.cpp` | Loads metadata/data, exposes kernel name, grid size, workgroup/warp/thread counts, LDS/PDS/SGPR/VGPR usage, start PC, and buffers. | Kernel descriptor source of truth for existing testcases. | `reuse` | Add descriptor export/import tooling that records resource usage and maps kernels to blueprint workloads. |
| `sim-verilator/cmdarg.cpp`, `sim_main.cpp` | Mini-driver command parser and runtime loop. | Repeatable S3/S4 command pattern. | `adapt` | Generate `ventus_cmdargs.txt` for Rank 1 workloads and capture dump/readback hashes. |

### 3. CTA And Workgroup Scheduler

| Ventus path | Current role | Rank 1 use | Status | Implementation hook |
| --- | --- | --- | --- | --- |
| `ventus/src/cta/cta_scheduler.scala` | Composes WG buffer, allocator, resource table, and CU interface. | Workgroup admission and completion. | `reuse` | Add metrics taps for host accepted, allocator rejected/stalled, CU selected, workgroup done, resource dealloc, and per-CU occupancy. |
| `ventus/src/cta/wg_buffer.scala` | Buffers host workgroups and passes allocation/dispatch data. | Command queue pressure evidence. | `reuse` | Count queue depth, backpressure cycles, enqueue/dequeue, and oldest command age. |
| `ventus/src/cta/allocator.scala`, `resource_table.scala` | Allocate CU slots, VGPR, SGPR, LDS resources. | Occupancy and resource-pressure evidence for tier scaling. | `reuse` | Report denial reasons by WG slot, VGPR, SGPR, LDS, and CU availability. |
| `ventus/src/cta/cu_interface.scala` | Splits WG into WF, computes per-WF resource bases, gathers WF completion, deallocates resources, reports host WG done. | OpenCL-like workgroup-to-wavefront lowering. | `reuse` | Emit WF dispatch/done counters by CU, WG id, WF tag, and resource base ranges. |
| `docs/cta_scheduler/*.md` | Existing design notes and diagrams. | Human architecture evidence. | `reuse` | Cross-link only; do not move into Celviz. |

### 4. Warp Scheduler And SIMT Pipeline

| Ventus path | Current role | Rank 1 use | Status | Implementation hook |
| --- | --- | --- | --- | --- |
| `ventus/src/pipeline/CTA2warp.scala` | Allocates hardware warp slots, stores WG/WF tags, accepts CTA requests and warp responses. | CTA-to-warp evidence and active warp accounting. | `reuse` | Count warp slot allocation, release, active mask, and failed allocation/backpressure. |
| `ventus/src/pipeline/warp_schedule.scala` | Maintains active warps, PC control, ready masks, branch/flush, barrier/end program tracking, and optional ASID output. | Scheduler fairness, divergence, and throughput evidence. | `reuse` | Add counters for warp ready, issued, blocked by scoreboard, blocked by exe, blocked by ibuffer, barrier wait, flush, and endprg. |
| `ventus/src/pipeline/pipe.scala` | Instantiates decode, issue, ALU/FPU/vector/tensor/LSU/SFU/MUL, CSR, SIMT stack, scoreboard, regfile, writeback. | Main compute datapath. | `reuse` | Add GPGPU metrics bundle or Verilator trace selection for instruction mix, FP32, integer, vector, tensor hook, LSU, stalls, and retire. |
| `ventus/src/pipeline/DecodeUnit.scala`, `Instructions.scala` | Instruction classification and decode. | Supported-op and fault taxonomy. | `adapt` | Produce a supported instruction matrix for Rank 1 kernels and classify unsupported OpenCL-like workloads. |
| `ventus/src/pipeline/SIMT_STACK.scala`, `branch_join.scala`, `PCcontrol.scala` | SIMT reconvergence and branch handling. | Divergence tests for image/filter kernels. | `reuse` | Add branch/divergence stress workload and counters for reconvergence events. |

### 5. Register, Scoreboard, And Compute Paths

| Ventus path | Current role | Rank 1 use | Status | Implementation hook |
| --- | --- | --- | --- | --- |
| `ventus/src/pipeline/regfile.scala` | Vector/scalar register storage. | VGPR/SGPR pressure and occupancy evidence. | `reuse` | Tie register usage from metadata to actual occupancy/resource-table metrics. |
| `ventus/src/pipeline/operandCollector.scala` | Operand collection and banked access. | Bank conflict and issue-stall evidence. | `reuse` | Count collector stalls and register-bank conflict pressure. |
| `ventus/src/pipeline/scoreboard.scala` | Hazard, fence, busy, and writeback tracking. | Dependency/fence stall evidence. | `reuse` | Report per-warp scoreboard busy cycles and fence completion. |
| `ventus/src/pipeline/writeback.scala` | Scalar/vector writeback. | Completion and throughput accounting. | `reuse` | Count x/v writebacks and correlate with instruction mix. |
| `ventus/src/pipeline/fpu_utils.scala`, `FloatDivSqrt.scala` | FP32 helper/execution path basis. | FP32 compute evidence when exercised. | `reuse` when tested | Add FP32 vector/GEMM/image workloads and compare against golden output. |
| Current inspected RTL | No proven FP16 execution path found. | FP16 public tier evidence starts in golden model only. | `new` / `blocked` | New FP16 proxy model and tests; RTL FP16 remains blocked until implemented and verified. |

### 6. LDS, LSU, Cache, MMU, And AXI

| Ventus path | Current role | Rank 1 use | Status | Implementation hook |
| --- | --- | --- | --- | --- |
| `ventus/src/pipeline/LSU.scala` | Address calculation, global/shared split, D-cache requests, shared-memory requests, MSHR coalescing, fence end, shift boards. | Memory-copy, image-filter, GEMM/convolution memory traffic source. | `reuse` | Add counters for global load/store, shared load/store, coalesced requests, mask utilization, fence end, and stalled requests. |
| `ventus/src/L1Cache/ShareMem/ShareMem.scala`, `BankConflictArbiter.scala` | Shared memory/LDS with bank conflict arbitration. | OpenCL local-memory proxy. | `reuse` | Create bank-conflict workload and record conflict/replay/stall metrics. |
| `ventus/src/L1Cache/DCache/DCache.scala`, `DCacheWSHR.scala`, `L1MSHR.scala` | D-cache, miss handling, write handling, optional TLB path. | Global memory bandwidth/latency evidence. | `reuse` | Add hit/miss, WSHR/MSHR occupancy, bytes read/write, and stall metrics. |
| `ventus/src/L1Cache/ICache/ICache.scala` | Instruction cache and invalidate path. | Kernel launch/code reload evidence. | `reuse` | Record I-cache invalidate and fetch misses for runtime-submitted kernels. |
| `ventus/src/L1Cache/AtomicUnit/AtomicUnit.scala` | Atomic operation path. | Optional atomic workload proxy. | `adapt` | Add one atomic smoke only after command/runtime basics pass. |
| `ventus/src/L2cache/Scheduler.scala`, `SourceA.scala`, `SinkA.scala`, `SourceD.scala`, `SinkD.scala`, `MSHR.scala`, `BankedStore.scala` | L2 request scheduling, MSHR, banked storage, source/sink channels. | L2 contention, cache service, and S5 bandwidth/latency reports. | `reuse` | Count L2 requests, hits/misses if observable, MSHR pressure, bank occupancy, and response latency. |
| `ventus/src/mmu/L1TLB.scala`, `L2TLB.scala`, `PTW.scala`, `AsidLookup.scala` | TLBs, page table walk, ASID lookup, invalidation/refill. | MMU stress and fault taxonomy. | `reuse` with config `adapt` | Enable an MMU profile and add ASID fill, TLB miss, PTW, invalidation, and fault-injection tests. |
| `ventus/src/axi/AXI4Adapter.scala` | L2-to-AXI read/write burst adapter. | Required AXI traffic evidence. | `reuse` | Instrument burst count, bytes, read/write split, outstanding transactions, and latency bins. |

### 7. Simulator, Testcases, And Evidence

| Ventus path | Current role | Rank 1 use | Status | Implementation hook |
| --- | --- | --- | --- | --- |
| `sim-verilator/README.md` | Documents `libVentusRTL.so`, mini driver, `-f`, `--waveform`, and `--dump-mem`. | Execution recipe for repeatable evidence. | `reuse` | Create Rank 1 command manifests that always log command, input, output, and hash. |
| `sim-verilator/testcase/vecadd/` | Existing vector-add metadata/data/log cases. | Vector add S1/S3 seed. | `reuse` | Promote one case to Rank 1 smoke and compare memory dump against golden output. |
| `sim-verilator/testcase/matadd/` | Existing matrix-add metadata/data cases. | GEMM/convolution proxy stepping stone. | `adapt` | Use as matrix memory/compute smoke before full GEMM proxy. |
| `ventus/txt/adv_gaussian/`, `adv_gaussian_1x16/` | Gaussian workload data/log/dump. | Image-filter proxy. | `adapt` | Wrap as image-filter workload with readback and golden comparison. |
| `ventus/txt/adv_nn/` | Nearest-neighbor data/log/dump. | OpenCV-like compute proxy candidate. | `adapt` | Use for memory and branch/divergence stress after baseline tests. |
| `ventus/txt/saxpy/`, `saxpy2/` | SAXPY source/data/vmem. | FP32 compute candidate. | `adapt` | Add FP32 golden comparison and runtime descriptor. |
| `ventus/txt/tensor/` | Tensor metadata/data. | GEMM/tensor hook exploration. | `adapt` | Keep optional until vector/memory/image baselines are stable. |
| `sim-verilator-nocache/` | No-cache simulator variant. | Cache sensitivity/control lane. | `adapt` | Compare cache/no-cache traffic only after identical workload manifests exist. |

## Blocked And Out-Of-Scope Items

| Item | Status | Reason |
| --- | --- | --- |
| Proprietary Vivante command stream, firmware, SDK, compiler, driver, or RTL equivalence | `blocked` | Requires vendor collateral and must not be inferred from public tables. |
| Official OpenCL/OpenCV conformance | `blocked` | Requires licensed conformance tests and real logs. |
| Silicon PPA, STA, CDC/RDC, DFT, safety/security signoff, tapeout readiness | `blocked` | Current artifacts are proxy-level only. |
| RTL-backed FP16 acceptance | `blocked` | No proven FP16 execution path was found in inspected Ventus RTL. |
| Raster/texture/framebuffer/display/3D graphics mapping | `blocked` for Rank 1 | User explicitly pivoted to GPGPU compute; these belong to superseded Rank 12 work. |
| Rank 12 graphics acceptance as Rank 1 completion | `blocked` for Rank 1 | Historical graphics artifacts are preserved but excluded from active GPGPU acceptance. |

## Immediate Worker-Ready Hooks

1. `ventus/src/axi/AXI4Lite2CTA.scala`: wrap or extend the 20-register CTA bridge into a Rank 1 command/status/fence/interrupt proxy.
2. `sim-verilator/ventus_rtlsim.h` plus `sim-verilator/kernel.hpp`: build the host/runtime shim that turns JSON kernel descriptors into metadata/data launches and readback.
3. `ventus/src/cta/cta_scheduler.scala` plus `ventus/src/cta/cu_interface.scala`: add occupancy/resource/completion metrics for scheduler scaling evidence.
4. `ventus/src/pipeline/warp_schedule.scala` plus `ventus/src/pipeline/CTA2warp.scala`: add warp ready/blocked/issued/done counters for throughput and fairness.
5. `ventus/src/pipeline/LSU.scala`, `ventus/src/L1Cache/ShareMem/ShareMem.scala`, `ventus/src/L1Cache/DCache/DCache.scala`, `ventus/src/L2cache/Scheduler.scala`, and `ventus/src/axi/AXI4Adapter.scala`: add memory hierarchy and AXI traffic metrics for memory-copy/image-filter/GEMM workloads.
