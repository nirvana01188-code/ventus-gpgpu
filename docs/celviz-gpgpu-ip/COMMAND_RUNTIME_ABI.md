# Celviz GPGPU IP Command Runtime ABI

Status: S2 GPGPU-only control-plane skeleton.

This document defines the clean-room runtime ABI for a Celviz GPGPU IP control
plane inside the Ventus GPGPU repository. It describes command submission,
kernel dispatch, DMA movement, scheduling knobs, status/error reporting, and
memory-model expectations. It does not define a 3D graphics command stream,
display pipeline, raster state, texture state, or proprietary Vivante ABI.

## Design Rules

- The ABI is little-endian, versioned, and deterministic.
- Command packets are 64-byte aligned and begin with a fixed 64-byte header.
- The first S2 target is a proxy shell, simulator hook, or thin RTL wrapper.
- Software writes zero to reserved fields. Hardware returns zero for reserved
  register bits until a later ABI version defines them.
- Kernel dispatch and DMA commands are validated before issue. Unsupported
  shader modes, workgroup shapes, address ranges, or reserved bits report an
  ABI error instead of falling through to undefined behavior.
- All names and fields are GPGPU-only. Graphics pipeline registers are
  intentionally out of scope.

## Runtime Objects

| Object | Purpose |
| --- | --- |
| Command queue | Host-visible ring of runtime packets consumed by the command processor. |
| Dispatch descriptor | Kernel entry, grid, local size, argument buffer, shared memory, and shader mode. |
| DMA descriptor | Linear memory copy/fill command with optional fence and interrupt behavior. |
| Scheduler profile | Workgroup, warp, occupancy, and fairness configuration for S2 evidence. |
| Completion record | Retired sequence, submit tag, status, error code, and optional counter snapshot. |
| MMU fault record | Captured fault address, access type, sequence, queue ID, and shader context. |

## Capability Tiers

| Tier | Numeric ID | Shader units | Required runtime features |
| --- | ---: | ---: | --- |
| `gpgpu_nano` | `0x01` | 1 | Single queue, kernel dispatch, DMA copy/fill, FP32 scalar/vector smoke, basic interrupts. |
| `gpgpu_nano_ultra` | `0x02` | 2 | Two queues, workgroup scheduler knobs, FP16/FP32 mode control, AXI counters, MMU fault capture. |
| `gpgpu_nano_ultra31` | `0x03` | 4 | Four queues, richer occupancy limits, per-shader-unit counters, error injection, watchdog, preemption-safe halt. |

The tier names are Celviz GPGPU IP labels. They are acceptance and evidence
tiers only; they do not claim binary compatibility with any proprietary GPU.

## Opcode Registry

| Opcode | Numeric ID | Minimum tier | Purpose |
| --- | ---: | --- | --- |
| `nop` | `0x0000` | `gpgpu_nano` | Ordered no-op used for queue and interrupt smoke tests. |
| `kernel_dispatch` | `0x0001` | `gpgpu_nano` | Dispatch one compute kernel over a workgroup grid. |
| `dma_copy` | `0x0002` | `gpgpu_nano` | Copy a linear byte range from source to destination. |
| `dma_fill` | `0x0003` | `gpgpu_nano` | Fill a linear byte range with a 32-bit pattern. |
| `barrier` | `0x0004` | `gpgpu_nano` | Wait for prior queue work and publish memory effects. |
| `set_scheduler_config` | `0x0005` | `gpgpu_nano_ultra` | Update workgroup/warp scheduling knobs. |
| `set_shader_mode` | `0x0006` | `gpgpu_nano_ultra` | Select FP16/FP32 execution policy and shader-unit mask. |
| `counter_snapshot` | `0x0007` | `gpgpu_nano_ultra` | Latch command, dispatch, DMA, AXI, stall, and fault counters. |

## Packet Header

All command packets begin with this fixed 64-byte header. Opcode payloads follow
immediately after the header.

| Byte offset | Field | Size | Description |
| ---: | --- | ---: | --- |
| `0x00` | `magic` | 4 | ASCII `CVU1`, encoded as `0x31555643`. |
| `0x04` | `abi_version` | 2 | Initial version is `0x0001`. |
| `0x06` | `header_words` | 2 | Header size in 32-bit words; initial value is `16`. |
| `0x08` | `packet_bytes` | 4 | Total packet length including header and payload. |
| `0x0c` | `opcode` | 2 | One value from the opcode registry. |
| `0x0e` | `tier` | 1 | Requested capability tier numeric ID. |
| `0x0f` | `queue_id` | 1 | Command queue index. |
| `0x10` | `sequence` | 8 | Monotonic software sequence number. |
| `0x18` | `flags` | 4 | Common runtime flags. |
| `0x1c` | `context_id` | 4 | Address-space or runtime context identifier. |
| `0x20` | `completion_addr_lo` | 4 | Completion record address bits `31:0`; zero disables memory completion write. |
| `0x24` | `completion_addr_hi` | 4 | Completion record address bits `63:32`. |
| `0x28` | `payload_words` | 2 | Opcode payload size in 32-bit words. |
| `0x2a` | `priority` | 1 | Queue-local priority, `0` lowest through `7` highest. |
| `0x2b` | `reserved0` | 1 | Must be zero. |
| `0x2c` | `payload_crc32` | 4 | Optional payload CRC32; zero disables CRC check. |
| `0x30` | `submit_tag` | 4 | Driver-shim tag copied to completion/status records. |
| `0x34` | `reserved1` | 12 | Must be zero. |

## Common Flags

| Bit | Name | Description |
| ---: | --- | --- |
| `0` | `INT_ON_COMPLETE` | Raise completion interrupt when the command retires. |
| `1` | `FENCE_BEFORE` | Wait for prior memory operations before execution. |
| `2` | `FENCE_AFTER` | Publish writes before marking completion. |
| `3` | `ALLOW_PROXY_FALLBACK` | Permit proxy-shell or simulator execution when RTL execution is absent. |
| `4` | `CAPTURE_COUNTERS` | Latch command/DMA/AXI counters into the completion record. |
| `8` | `INJECT_DISPATCH_ERROR` | Request scheduler or shader dispatch error injection. |
| `9` | `INJECT_DMA_ERROR` | Request DMA bounds/alignment error injection. |
| `10` | `INJECT_MMU_FAULT` | Request MMU translation or permission fault injection. |
| `11` | `KERNEL_USES_FP16` | Dispatch payload requires FP16 mode support. |
| `12` | `KERNEL_USES_FP32` | Dispatch payload requires FP32 mode support. |
| `31:13` | `RESERVED` | Must be zero. |

## Opcode Payloads

### `kernel_dispatch`

| Field | Size | Description |
| --- | ---: | --- |
| `kernel_entry_lo`, `kernel_entry_hi` | 8 | Kernel instruction entry address. |
| `arg_buffer_lo`, `arg_buffer_hi` | 8 | Kernel argument buffer address. |
| `arg_bytes` | 4 | Argument buffer size in bytes. |
| `grid_x`, `grid_y`, `grid_z` | 12 | Workgroup grid dimensions. |
| `local_x`, `local_y`, `local_z` | 12 | Work items per workgroup dimension. |
| `shared_bytes` | 4 | Requested shared/local memory per workgroup. |
| `private_bytes_per_thread` | 4 | Runtime estimate used for occupancy checks. |
| `sgpr_count`, `vgpr_count` | 4 | Scalar/vector register allocation hints, two `uint16` values. |
| `required_fp_mode` | 1 | `0` default, `1` FP32, `2` FP16, `3` mixed FP16/FP32. |
| `scheduler_hint` | 1 | `0` default, `1` latency, `2` throughput, `3` fair-share. |
| `reserved` | 2 | Must be zero. |

### `dma_copy`

| Field | Size | Description |
| --- | ---: | --- |
| `src_addr_lo`, `src_addr_hi` | 8 | Source address. |
| `dst_addr_lo`, `dst_addr_hi` | 8 | Destination address. |
| `byte_count` | 8 | Number of bytes to copy. |
| `src_stride` | 4 | Optional source stride; zero means linear. |
| `dst_stride` | 4 | Optional destination stride; zero means linear. |
| `line_bytes` | 4 | Optional line width for strided copies; zero means one linear span. |
| `line_count` | 4 | Optional line count for strided copies; zero means one linear span. |

### `dma_fill`

| Field | Size | Description |
| --- | ---: | --- |
| `dst_addr_lo`, `dst_addr_hi` | 8 | Destination address. |
| `byte_count` | 8 | Number of bytes to fill. |
| `pattern_u32` | 4 | Repeated little-endian 32-bit fill pattern. |
| `reserved` | 4 | Must be zero. |

### `set_scheduler_config`

| Field | Size | Description |
| --- | ---: | --- |
| `max_workgroups_per_shader_unit` | 2 | Occupancy cap per shader unit. |
| `max_warps_per_shader_unit` | 2 | Warp cap per shader unit. |
| `warp_size` | 2 | Initial legal value is `32`; future profiles may add more. |
| `issue_policy` | 1 | `0` round-robin, `1` oldest-ready, `2` priority-age. |
| `preemption_granularity` | 1 | `0` none, `1` workgroup boundary, `2` warp boundary. |
| `fairness_window_cycles` | 4 | Age window for priority-age policy. |
| `watchdog_cycles` | 4 | Dispatch watchdog; zero disables. |
| `reserved` | 4 | Must be zero. |

### `set_shader_mode`

| Field | Size | Description |
| --- | ---: | --- |
| `shader_unit_enable_mask` | 4 | Bitmask of enabled shader units. |
| `fp_mode` | 1 | `0` default, `1` FP32-only, `2` FP16-only, `3` mixed. |
| `denorm_mode` | 1 | `0` preserve, `1` flush-to-zero. |
| `rounding_mode` | 1 | `0` nearest-even; other values reserved. |
| `reserved0` | 1 | Must be zero. |
| `fp16_rate_x2` | 1 | Nonzero advertises two FP16 lanes per FP32 lane in the proxy model. |
| `reserved1` | 3 | Must be zero. |

### `counter_snapshot`

| Field | Size | Description |
| --- | ---: | --- |
| `counter_select_mask` | 4 | Bits select command, dispatch, DMA, AXI, stall, and fault counters. |
| `snapshot_addr_lo`, `snapshot_addr_hi` | 8 | Optional memory address for snapshot writeback. |
| `reserved` | 4 | Must be zero. |

## Queue ABI

Each command queue is a host-visible ring:

| Field | Description |
| --- | --- |
| `base` | 64-byte aligned physical or IOVA base address. |
| `size_bytes` | Power-of-two queue size, minimum `4096`. |
| `head` | Hardware-consumed byte offset. |
| `tail` | Software-produced byte offset. |
| `doorbell` | Software write that notifies the command processor of new packets. |
| `priority` | Queue priority used only after packet validation. |

Initial S2 supports queue `0` in all tiers. `gpgpu_nano_ultra` may expose two
queues, and `gpgpu_nano_ultra31` may expose four queues. Hardware validates
packet alignment, length, version, tier, opcode, queue ID, priority, reserved
bits, and payload-specific constraints before issuing a command.

## Scheduler Model

The scheduler model is intentionally small but explicit:

- Workgroups are allocated to enabled shader units according to queue priority,
  issue policy, resource availability, and fairness window.
- Warps are formed with `warp_size = 32` in the S2 skeleton.
- A workgroup is eligible when its local size, register use, shared memory, and
  FP mode fit the selected tier.
- `gpgpu_nano` is single shader-unit, single-queue, round-robin only.
- `gpgpu_nano_ultra` adds two shader units, FP16/FP32 mode control, and
  scheduler register programming.
- `gpgpu_nano_ultra31` adds four shader units, per-unit enable masks, richer
  counters, and halt-at-boundary behavior for integration tests.

## Memory Model

- Command queue, payload, completion, DMA, argument, and snapshot addresses are
  physical addresses or IOVAs in the configured context.
- `FENCE_BEFORE` ensures prior writes visible to the device are observed before
  command issue.
- `FENCE_AFTER` ensures device writes are visible before completion retirement.
- DMA copy and fill commands are ordered within a queue. Cross-queue ordering
  requires a software fence or an implementation-specific timeline semaphore in
  a later ABI.
- Kernel memory consistency follows the Ventus compute memory model for global,
  shared, and private memory. This ABI only defines command-level ordering and
  fault capture.
- MMU faults are sticky until cleared and capture the first faulting address for
  a command sequence.

## Completion And Errors

Each retired command updates `last_sequence`, `last_tag`, `last_status`, and
`last_error` registers. If `completion_addr` is nonzero, the command processor
also writes a 32-byte completion record containing sequence, submit tag, status,
error code, queue ID, and optional counter snapshot token.

| Error code | Name | Meaning |
| ---: | --- | --- |
| `0x0000` | `OK` | Command completed. |
| `0x0001` | `ERR_BAD_MAGIC` | Packet magic is not `CVU1`. |
| `0x0002` | `ERR_BAD_VERSION` | ABI version is unsupported. |
| `0x0003` | `ERR_BAD_LENGTH` | Packet/header/payload length is invalid. |
| `0x0004` | `ERR_UNSUPPORTED_TIER` | Requested tier is not implemented by this build. |
| `0x0005` | `ERR_UNSUPPORTED_OPCODE` | Opcode is unknown or unsupported for the tier. |
| `0x0006` | `ERR_BAD_QUEUE` | Queue ID, head/tail, size, or alignment is invalid. |
| `0x0007` | `ERR_BAD_DISPATCH` | Grid, local size, resource usage, or FP mode is invalid. |
| `0x0008` | `ERR_BAD_DMA` | DMA range, stride, size, or alignment is invalid. |
| `0x0009` | `ERR_MMU_FAULT` | MMU translation, permission, or injected fault occurred. |
| `0x000a` | `ERR_SCHEDULER_FAULT` | Scheduler resource allocation or injected dispatch error. |
| `0x000b` | `ERR_TIMEOUT` | Watchdog expired. |
| `0x000c` | `ERR_COUNTER_FAULT` | Counter snapshot address or selector is invalid. |

## Required S2 Evidence

- Queue programming: base, size, head, tail, doorbell, and retirement.
- Kernel dispatch queue: at least one FP32 dispatch and one FP16-capability
  validation path.
- DMA: linear copy/fill validation, byte counters, and error path.
- Scheduler: workgroup/warp config, shader-unit tier scaling, and halt/busy
  status.
- Memory model: fence bits, completion writeback, AXI traffic counters, and MMU
  fault capture.
- Interrupt/status/error: completion interrupt, queue error, scheduler fault,
  DMA error, MMU fault, watchdog, clear path, and sticky status behavior.
