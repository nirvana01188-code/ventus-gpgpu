# RISC-V GPU Performance Research For Celviz GPGPU IP

Status: research-to-implementation backlog.

This note maps public RISC-V GPU/GPGPU ideas to the current Ventus-based
Celviz clean-room GPGPU IP proxy. It is not a proprietary Vivante analysis and
does not claim compatibility with any vendor ISA, driver, firmware, or SDK.

## Sources Reviewed

- Vortex GitHub: full-stack open-source RISC-V GPGPU with configurable cores,
  warps, threads, ALU/FPU/LSU/SFU units, issue width, local memory, and L1/L2/L3
  caches.
  <https://github.com/vortexgpgpu/vortex>
- Vortex OpenCL paper: RISC-V SIMT architecture with minimal ISA extension and
  OpenCL runtime integration.
  <https://arxiv.org/abs/2002.12151>
- Vortex MICRO paper: FPGA implementation, OpenCL/OpenGL stack, and scalability
  up to 32 FPGA cores in the published configuration.
  <https://arxiv.org/abs/2110.10857>
- Ventus poster: RVV-based GPGPU, 64 sGPRs, 256 vGPRs, workgroup metadata,
  memory-space access, task allocation, CTA scheduler, banked register files,
  Tensor Core direction, LLVM/PoCL/driver/ISS stack.
  <https://riscv-europe.org/summit/2023/media/proceedings/posters/2023-06-07-Kexiang-YANG-poster.pdf>
- Decoupled control-flow/data-access RISC-V GPGPU paper: hardware control-flow
  manager and decoupled memory streaming lanes, reporting large reductions in
  dynamic instruction count for regular memory-intensive kernels.
  <https://arxiv.org/abs/2512.00032>
- Vortex warp-level features paper: hardware vs software implementation of
  subgroup/warp-level collectives.
  <https://arxiv.org/abs/2505.03102>
- Memory coalescing and irregular access work: reorder/coalescing techniques
  for irregular GPGPU memory access.
  <https://arxiv.org/abs/2007.07131>

## Current Celviz Baseline

The current local stack already has:

- OpenCL-like subset: `vector_add`, `gemm`, `conv2d`, `image_filter`.
- Runtime command ABI and native runtime proxy.
- SIMT execution evidence with wavefront/register/ALU/LSU/scoreboard/barrier
  counters.
- Memory model with global/local/constant/DMA/cache/coalescing proxy semantics.
- Kernel lowering to clean-room micro-ops.
- Executable micro-op interpreter with per-kernel memory traces.
- Compiler IR evidence with virtual registers, predicate registers, basic
  blocks, CFG edges, and def-use.
- Driver submission proxy with queue/fence/event lifecycle evidence.
- Synthesis readiness and bounded Yosys probe evidence.

Latest functional/acceptance gate:

```text
coverage=100.000%
hit=260
total=260
```

## Performance Ideas Worth Importing

### P0: Decoupled Control-Flow Manager

Why:

- Branch/predicate management overhead is a known RISC-V SIMT bottleneck.
- Recent RISC-V GPGPU work points to hardware control-flow management as a
  high-leverage path for regular loops and predicated kernels.

Use here:

- Extend `compiler_ir.py` and `microop_interpreter.py` with explicit
  `uop_cf_push`, `uop_cf_mask`, `uop_cf_join`, `uop_predicated_branch`.
- Add counters for dynamic control uops, active-mask transitions, branch
  reconvergence points, and skipped inactive lanes.
- Add a `phase7_control_flow_manager.py` evidence tool that compares baseline
  micro-op dynamic instruction count with a compressed control-flow manager
  projection.

Expected local benefit:

- Reduces dynamic uop count for `gemm` and `conv2d` loops.
- Provides a direct path from current predicate/CFG evidence to performance
  modeling.

Acceptance target:

```text
phase7_control_flow_manager: pass
dynamic_uop_reduction > 0 for gemm and conv2d
active_mask/reconvergence evidence present
```

### P0: Decoupled Memory Streaming Lanes

Why:

- GEMM, convolution, and filters are memory-orchestration heavy.
- Decoupling address generation/load streams from ALU work can hide latency and
  reduce scheduler stalls.

Use here:

- Add `uop_stream_open`, `uop_stream_load`, `uop_stream_wait`,
  `uop_stream_close` to the clean-room uop vocabulary.
- In `phase6_memory_trace_integration.py`, derive stream windows from per-kernel
  memory traces.
- Add a streaming projection report: outstanding stream slots, load distance,
  ALU overlap, and potential scoreboard stall reduction.

Expected local benefit:

- Better evidence for LSU/scoreboard optimization.
- Directly useful for `gemm`, `conv2d`, and `image_filter` memory traces.

Acceptance target:

```text
phase7_memory_streaming: pass
stream_windows > 0
projected_scoreboard_wait_reduction > 0
```

### P0: Real Coalescing Score And Segment Utilization

Why:

- Current model records coalescing proxy semantics, but not a strong per-kernel
  bandwidth efficiency score.
- Vortex and general GPGPU literature treat memory hierarchy/coalescing as a
  major performance lever.

Use here:

- Convert micro-op memory events into 32/64/128-byte memory transactions.
- Report naive transactions vs coalesced transactions per kernel and per
  argument.
- Add irregular-access stress patterns later.

Expected local benefit:

- Produces a clear performance metric without pretending to be silicon.
- Helps prioritize layout transformations and kernel ABI lowering changes.

Acceptance target:

```text
phase7_coalescing_score: pass
coalescing_efficiency per kernel
transaction_reduction per kernel
```

### P1: Configurable Issue Width And Execution Unit Mix

Why:

- Vortex exposes configurable ALU/FPU/LSU/SFU blocks and issue width.
- Ventus is configurable in SMs/warps/threads/lanes; our proxy should expose the
  same performance knob family.

Use here:

- Add a parameter sweep model: issue width, ALU lanes, LSU lanes, FPU lanes,
  warp count, register file bank count.
- Feed sweep from current compiler IR and micro-op dynamic counts.
- Produce area/frequency/power proxy deltas alongside throughput projections.

Expected local benefit:

- Gives product-level performance tuning knobs before RTL refactor.
- Links to current PPA proxy and synthesis readiness.

Acceptance target:

```text
phase7_config_sweep: pass
best_config_by_kernel
area_normalized_perf_proxy
```

### P1: Register File Banking And Occupancy Model

Why:

- Ventus public material highlights 64 sGPRs, 256 vGPRs, and banked register
  files.
- Register pressure controls occupancy; bank conflicts control issue rate.

Use here:

- Extend compiler IR with live-range and peak register pressure.
- Model sGPR/vGPR allocation per kernel and bank conflict projection.
- Report occupancy estimate from register use, local memory use, and wavefront
  count.

Expected local benefit:

- Provides a bridge from compiler IR to actual hardware sizing.
- Helps decide whether to optimize register file first or LSU first.

Acceptance target:

```text
phase7_register_occupancy: pass
peak_vregs/peak_sregs
occupancy_limit_reason
bank_conflict_proxy
```

### P1: Hardware Warp/Subgroup Collectives

Why:

- Warp-level primitives such as ballot, vote, shuffle, and subgroup sync matter
  for reductions, scans, GEMM tiling, and image kernels.
- RISC-V GPGPU work explores hardware vs software implementation tradeoffs.

Use here:

- Add clean-room uops for `uop_warp_shuffle`, `uop_warp_ballot`,
  `uop_warp_reduce`.
- Start with software-emulated micro-op sequences, then add hardware-projected
  compressed versions.

Expected local benefit:

- Opens path to reductions and tiled GEMM kernels.
- Gives concrete ABI hooks without claiming CUDA/OpenCL subgroup conformance.

Acceptance target:

```text
phase7_warp_collectives: pass
software_sequence_vs_hardware_projection
```

### P2: Tensor/Dot-Product Unit Projection

Why:

- Ventus public material mentions Tensor Core custom tensor operations.
- Vortex tutorials reference mixed-precision dot-product/tensor extensions.

Use here:

- Keep clean-room and proxy-only.
- Add `uop_dot4`, `uop_mma_tile`, `uop_accumulate_tile` for GEMM evidence.
- Compare scalar/ALU micro-op count against tensor-projected count.

Expected local benefit:

- Large GEMM/conv proxy improvement path.
- Should wait until control-flow and memory streaming evidence is stable.

Acceptance target:

```text
phase8_tensor_projection: pass
gemm_uop_reduction
conv2d_tile_projection
```

## Recommended Next Implementation Order

1. `phase7_coalescing_score.py`
   - Lowest risk.
   - Uses existing micro-op memory traces.
   - Immediate performance metric.

2. `phase7_control_flow_manager.py`
   - Uses current compiler IR CFG/predicate evidence.
   - Directly addresses branch/predicate overhead.

3. `phase7_memory_streaming.py`
   - Uses memory traces plus scoreboard evidence.
   - Creates a strong LSU performance story.

4. `phase7_config_sweep.py`
   - Turns performance evidence into architecture knobs.
   - Connects to PPA proxy and synthesis readiness.

5. `phase7_register_occupancy.py`
   - Extends compiler IR to real occupancy constraints.
   - Useful before RTL register-file/bank refactors.

6. `phase8_tensor_projection.py`
   - High upside for GEMM/conv but should not be first.

## What Not To Import Blindly

- Do not copy Vortex ISA extensions directly. Use them as clean-room design
  inspiration only.
- Do not claim OpenCL 1.2/3.0 conformance just because Vortex has an OpenCL
  stack.
- Do not claim Tensor Core performance without a real datapath, compiler
  lowering, and workload validation.
- Do not optimize for graphics first; current target is GPGPU compute IP.

## Immediate Celviz Backlog

```text
P0 phase7_coalescing_score
P0 phase7_control_flow_manager
P0 phase7_memory_streaming
P1 phase7_config_sweep
P1 phase7_register_occupancy
P1 phase7_warp_collectives
P2 phase8_tensor_projection
```

Each phase must:

- emit JSON evidence with schema/status/checks/summary;
- preserve clean-room boundary text;
- add source-check patterns;
- enter `accept_celviz_gpgpu_ip_full.sh`;
- enter `verification_coverage_100.py`;
- avoid changing the E7 `PASS=24` baseline unless deliberately migrating the
  main acceptance counter.
