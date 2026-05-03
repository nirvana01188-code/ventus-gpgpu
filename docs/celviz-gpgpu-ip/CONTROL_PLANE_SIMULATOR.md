# S2 Control-Plane Simulator

Status: runnable clean-room proxy.

Worker 1 owns the S2 control-plane simulator for the Rank 1 Celviz GPGPU IP
effort. The simulator is standard-library Python and consumes a compact JSON
descriptor stream for GPGPU control-plane behavior:

- `kernel_dispatch`
- `dma_copy`
- `dma_fill`
- `fence_wait`
- `fence_signal`
- `reset`
- expected error cases

The simulator models queue state, status registers, sticky errors, completion
records, completion/error interrupt events, simple AXI/APB transaction counters,
bytes moved, and reset behavior. It is a clean-room proxy and does not claim a
proprietary Vivante command format, driver ABI, firmware ABI, SDK behavior, RTL
equivalence, compiler behavior, OpenCL conformance, or silicon signoff.

## Files

| File | Purpose |
| --- | --- |
| `tools/celviz_gpgpu_ip/control_plane.py` | Simulator CLI and descriptor executor. |
| `artifacts/rank_01_vivante_3d_gpgpu_ip/rtl/control_plane_demo.json` | Default descriptor stream. |
| `artifacts/rank_01_vivante_3d_gpgpu_ip/rtl/control_plane_run.log` | Human-readable run log. |
| `artifacts/rank_01_vivante_3d_gpgpu_ip/rtl/control_plane_metrics.json` | Machine-readable queue, interrupt, counter, and completion evidence. |

## Run

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/celviz_gpgpu_ip/control_plane.py --print-metrics
```

The CLI writes the default demo JSON if it is missing, executes the descriptor
stream, and emits run artifacts under
`artifacts/rank_01_vivante_3d_gpgpu_ip/rtl/`.

To regenerate only the demo descriptor:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/celviz_gpgpu_ip/control_plane.py --write-demo
```

## Descriptor Shape

The demo schema is `celviz.gpgpu.control_plane_demo.v1`. It contains:

- `tier`: one of `gpgpu_nano`, `gpgpu_nano_ultra`,
  `gpgpu_nano_ultra31`
- `queues`: queue ID, base, size, and priority
- `memory_regions`: readable/writable proxy address windows
- `commands`: ordered descriptors with `opcode`, `sequence`, `queue_id`,
  optional `submit_tag`, optional `flags`, and opcode-specific payload fields

Integer fields may be JSON numbers or strings such as `0x80000000`.

## Modeled Behavior

Queue state:

- each command submits one packet to the target queue
- packet retirement advances queue `head`
- submission advances queue `tail`
- per-queue submitted, retired, and error counters are recorded

Interrupts:

- `INT_ON_COMPLETE` raises a completion interrupt on success
- `INT_ON_COMPLETE` raises an error interrupt when the command retires with an
  error
- interrupt events include sequence, queue ID, kind, and message

AXI/APB proxy counters:

- DMA copy reads and writes the requested byte count
- DMA fill writes the requested byte count
- kernel dispatch reads the argument buffer and writes a small per-workgroup
  proxy status footprint
- completion writeback emits a 32-byte AXI write
- command submission emits APB tail/doorbell writes and a status poll read

Reset:

- `reset` clears queue state, sticky status, software fences, prior interrupt
  events, and completion records
- lifetime counters continue to count the reset command itself so the run can
  prove reset behavior occurred

Errors:

- invalid queue IDs produce `ERR_BAD_QUEUE`
- unsupported opcodes produce `ERR_UNSUPPORTED_OPCODE`
- invalid DMA descriptors produce `ERR_BAD_DMA`
- out-of-range or injected memory faults produce `ERR_MMU_FAULT`
- unsatisfied fence waits produce `ERR_FENCE_WAIT`
- scheduler/resource checks can produce `ERR_BAD_DISPATCH` or
  `ERR_SCHEDULER_FAULT`

The default demo includes both successful commands and expected error commands.
Expected errors are considered passing evidence when the observed error matches
the descriptor's `expect_error` field.

## Blueprint Alignment

This simulator supports the S2 control-plane acceptance surface from the active
Rank 1 GPGPU blueprint:

- GPGPU-only command submission
- kernel dispatch queue state
- DMA copy/fill control
- FP16 and FP32 dispatch validation paths
- fence/order modeling
- interrupts and sticky error status
- simple AXI/APB traffic evidence
- reset behavior
- MMU/error-path evidence

Graphics pipeline state such as rasterization, texture sampling, framebuffer,
viewport, scanout, and display control is intentionally out of scope.
