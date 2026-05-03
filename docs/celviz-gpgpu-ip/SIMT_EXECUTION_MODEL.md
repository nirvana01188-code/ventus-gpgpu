# SIMT Execution Model Evidence

Status: implemented for S1 real compute core path phase 1.

The clean-room SIMT execution model lives at:

```text
tools/celviz_gpgpu_ip/simt_execution_model.py
```

It is a deterministic software execution path for the existing proxy workloads,
not a Vivante ISA, RTL, firmware, driver, compiler, timing, or conformance
model.  The purpose is to make the compute path explicit enough for evidence:
wavefront scheduling, per-lane register-file access, ALU operations, LSU
operations, scoreboard hazards, and barriers.

## Workloads

The model executes these simplified instruction/event streams:

- `vector_add`: load A/B vectors, lane-wise add, barrier, store output.
- `gemm_proxy`: load matrix A/B operands, multiply-add accumulation, barrier,
  store C.
- `convolution_proxy`: load image pixels and 3x3 coefficients, multiply-add
  accumulation, barrier, store output.
- `image_filter`: load u8 image taps, integer add accumulation with edge
  truncation, barrier, store intermediate sums, then deterministic output-pack.

## Evidence

Running the default compute model writes:

```text
artifacts/rank_01_vivante_3d_gpgpu_ip/model/outputs/simt_execution.json
```

The focused CLI can be run directly:

```sh
python3 tools/celviz_gpgpu_ip/simt_execution_model.py --check --print-summary
```

The JSON evidence includes:

- `simt_topology.wavefront_size`
- `simt_topology.register_file`
- `simt_topology.alu`
- `simt_topology.lsu`
- `simt_topology.scoreboard`
- `simt_topology.barrier`
- per-workload `trace` events for `warp_schedule`, `register_write`,
  `alu_op`, `lsu_op`, `scoreboard_hazard`, and `barrier`
- aggregate counters for scheduler issues, register reads/writes, ALU ops, LSU
  loads/stores, scoreboard hazards, and barriers

Latest generated focused validation summary:

```text
status=pass
workloads=vector_add,gemm_proxy,convolution_proxy,image_filter
scheduler_issues=390
register_reads=2208
register_writes=2208
alu_ops=1206
lsu_loads=1238
lsu_stores=141
scoreboard_hazard_events=380
scoreboard_hazard_cycles=1710
barrier_events=19
```
