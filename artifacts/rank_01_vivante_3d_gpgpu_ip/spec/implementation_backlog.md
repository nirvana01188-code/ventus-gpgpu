# Implementation Backlog: Ventus Hooks For Celviz GPGPU IP

Date: 2026-05-02

Owner: Worker 6

This backlog converts the local Ventus framework mapping into concrete future
implementation hooks. It does not edit RTL or scripts. It excludes graphics
pipeline work.

## Priority Legend

| Priority | Meaning |
| --- | --- |
| P0 | Needed to turn existing proxy artifacts into RTL/runtime-backed evidence. |
| P1 | Needed for coverage depth and S5 integration quality. |
| P2 | Useful extension after the baseline evidence loop is stable. |
| Blocked | Requires unavailable proprietary collateral or unimplemented RTL capability. |

## P0 Backlog

| ID | Hook | Files | Work item | Expected evidence |
| --- | --- | --- | --- | --- |
| P0-001 | Runtime descriptor runner | `sim-verilator/ventus_rtlsim.h`, `sim-verilator/kernel.hpp`, `sim-verilator/kernel.cpp`, `sim-verilator/sim_main.cpp` | Build a Rank 1 JSON-to-Ventus launch shim that records kernel name, buffers, global/local sizes, precision mode, tier profile, dispatch id, and readback regions. | S4 log with descriptor, metadata fields, memory upload, launch, step loop, readback hash. |
| P0-002 | Command/status/fence ABI | `ventus/src/axi/AXI4Lite2CTA.scala`, `ventus/src/top/GPGPU_top.scala` | Wrap or extend the 20-register CTA bridge with command id, kernel id, queue doorbell, status, fence id, interrupt enable/status, error code, and optional MMU fault fields. | S2 register smoke proving submit, busy, done, fence complete, interrupt pending/clear. |
| P0-003 | CTA scheduler metrics | `ventus/src/cta/cta_scheduler.scala`, `wg_buffer.scala`, `allocator.scala`, `resource_table.scala`, `cu_interface.scala` | Add lightweight counters for accepted WG, blocked WG, allocation denial reason, active WG per CU, WF dispatch, WF done, WG done, and resource dealloc. | S3 scheduler metrics report for vector/matrix/image workloads. |
| P0-004 | Warp scheduler metrics | `ventus/src/pipeline/CTA2warp.scala`, `ventus/src/pipeline/warp_schedule.scala` | Add counters for warp allocation/release, active mask, ready mask, issue-eligible cycles, scoreboard-blocked cycles, exe-blocked cycles, ibuffer-blocked cycles, barrier wait, flush, and end program. | S3 throughput/fairness report and per-workload warp timeline summary. |
| P0-005 | Memory and AXI traffic metrics | `ventus/src/pipeline/LSU.scala`, `ventus/src/L1Cache/DCache/DCache.scala`, `ventus/src/L1Cache/ShareMem/ShareMem.scala`, `ventus/src/L2cache/Scheduler.scala`, `ventus/src/axi/AXI4Adapter.scala` | Add counters for global load/store, shared load/store, coalesced requests, active lane mask utilization, D-cache requests/misses if available, L2 requests, AXI read/write bursts, bytes, and latency bins. | S3 AXI traffic test and S5 bandwidth/latency proxy report. |

## P1 Backlog

| ID | Hook | Files | Work item | Expected evidence |
| --- | --- | --- | --- | --- |
| P1-001 | Workload catalog | `sim-verilator/testcase/vecadd/`, `sim-verilator/testcase/matadd/`, `ventus/txt/adv_gaussian/`, `ventus/txt/adv_nn/`, `ventus/txt/saxpy/`, `ventus/txt/tensor/` | Create a Rank 1 workload manifest mapping test data to vector add, matrix/GEMM proxy, image filter, nearest-neighbor/OpenCV-like proxy, SAXPY/FP32, tensor optional. | Manifest with command lines, expected buffers, and golden comparison source. |
| P1-002 | MMU-enabled profile | `ventus/src/top/parameters.scala`, `ventus/src/mmu/*.scala`, `ventus/src/top/GPGPU_top.scala` | Create an explicit MMU build/profile path, ASID fill setup, TLB miss observation, invalidation, and fault injection. | MMU/fault run log; criteria remains `adapt` until tested. |
| P1-003 | Public tier registry | New artifact/config under Rank 1 package; future code may read it. | Encode CC8000L through CC8800-MP4 public tiers as labels with vec1 units and FP32/FP16 public ops/cycle; map to proxy assumptions separately. | Tier profile report that says measured, model, or assumption for every metric. |
| P1-004 | FP32 golden checks | `ventus/txt/saxpy/`, `sim-verilator/testcase/vecadd/`, `matadd/`, FP32 paths in pipeline | Add tolerance-based golden comparisons for FP32 kernels and label integer-only cases separately. | FP32 run log and comparison JSON. |
| P1-005 | LDS bank conflict test | `ventus/src/L1Cache/ShareMem/BankConflictArbiter.scala`, `ShareMem.scala`, candidate new testcase | Add workload that intentionally stresses same-bank and conflict-free shared memory accesses. | Bank conflict/stall report. |
| P1-006 | Decode capability matrix | `ventus/src/pipeline/DecodeUnit.scala`, `Instructions.scala`, testcase metadata | Produce a supported/unsupported operation matrix for current Rank 1 workload seeds. | Capability matrix with unsupported workload reasons. |

## P2 Backlog

| ID | Hook | Files | Work item | Expected evidence |
| --- | --- | --- | --- | --- |
| P2-001 | Tensor/GEMM exploration | `ventus/txt/tensor/`, tensor path in `ventus/src/pipeline/pipe.scala` | Explore tensor metadata/data as an optional GEMM accelerator proxy after baseline GEMM/matrix evidence works. | Optional GEMM/tensor report with no proprietary equivalence claims. |
| P2-002 | Atomic smoke | `ventus/src/L1Cache/AtomicUnit/AtomicUnit.scala`, LSU path | Add one atomic counter or reduction smoke for memory consistency proxy. | Atomic smoke log and expected-result check. |
| P2-003 | Cache/no-cache comparison | `sim-verilator/`, `sim-verilator-nocache/` | Run identical workload manifests in cache and no-cache variants to estimate cache sensitivity. | Cache sensitivity report. |
| P2-004 | Waveform bundle | `sim-verilator` `--waveform` flow | Define a minimal waveform capture preset for command submit, CTA dispatch, warp schedule, LSU, L2, AXI. | Debug waveform recipe and sample run metadata. |

## Blocked Backlog

| ID | Item | Reason |
| --- | --- | --- |
| B-001 | Proprietary Vivante command stream compatibility | Requires vendor command stream documentation/RTL/firmware. |
| B-002 | Official OpenCL/OpenCV conformance | Requires licensed conformance suites and official runtime/compiler stack. |
| B-003 | RTL-backed FP16 pass | No proven FP16 execution path was found during local inspection. |
| B-004 | Real CC8000/CC8X00 PPA or shader-unit equivalence | Public tables are not enough to infer proprietary microarchitecture. |
| B-005 | Graphics pipeline implementation | Out of scope for active Rank 1 GPGPU compute target. |

## Top 5 Next Code Hooks

1. `ventus/src/axi/AXI4Lite2CTA.scala`: implement or wrap command/status/fence/interrupt registers around the existing CTA launch bridge.
2. `sim-verilator/ventus_rtlsim.h` and `sim-verilator/kernel.hpp`: implement a Rank 1 host/runtime shim that consumes JSON kernel descriptors and drives metadata/data launches.
3. `ventus/src/cta/cta_scheduler.scala` and `ventus/src/cta/cu_interface.scala`: expose scheduler occupancy/resource/WF dispatch/WG completion counters.
4. `ventus/src/pipeline/warp_schedule.scala` and `ventus/src/pipeline/CTA2warp.scala`: expose warp ready/blocked/issued/done and barrier/flush counters.
5. `ventus/src/pipeline/LSU.scala`, `ventus/src/L1Cache/DCache/DCache.scala`, `ventus/src/L1Cache/ShareMem/ShareMem.scala`, `ventus/src/L2cache/Scheduler.scala`, `ventus/src/axi/AXI4Adapter.scala`: expose memory hierarchy and AXI traffic counters.

## Suggested Worker Split After This Backlog

| Worker | Slice |
| --- | --- |
| Runtime worker | P0-001 and workload manifest P1-001. |
| Control-plane worker | P0-002 and fence/interrupt smoke. |
| Scheduler worker | P0-003 and P0-004. |
| Memory worker | P0-005, P1-005, P2-003. |
| Verification worker | Convert the above hooks into S3 commands, logs, and coverage notes. |

## Completion Guard

Mark an item complete only when the implementing worker leaves code, commands,
logs, and artifact paths under `artifacts/rank_01_vivante_3d_gpgpu_ip/`.
Absent evidence is `unproven`. Vendor equivalence, conformance, and silicon
claims stay `blocked`.

