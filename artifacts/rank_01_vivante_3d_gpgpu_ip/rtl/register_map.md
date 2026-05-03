# Celviz GPGPU IP Register Map

Status: S2 GPGPU-only proxy-shell blueprint.

This register map defines the clean-room MMIO control plane for Celviz GPGPU
IP. Offsets are relative to the GPGPU IP MMIO base selected by the integration
wrapper. The map covers command processing, DMA, kernel dispatch scheduling,
shader-unit tier scaling, FP16/FP32 mode control, counters, interrupts, status,
errors, and MMU fault capture. It intentionally excludes 3D graphics pipeline
registers.

## Register Conventions

- Registers are 32-bit, little-endian, and naturally aligned.
- Address fields are split into low/high 32-bit words.
- Writes to reserved bits must be zero. Reads from reserved bits return zero.
- Write-one-to-clear fields are marked `W1C`.
- Initial implementation may model registers in a simulator or software shell.
  RTL/Chisel implementation can follow after queue and fault behavior are
  proven.

## Address Blocks

| Offset range | Block | Purpose |
| ---: | --- | --- |
| `0x0000-0x00ff` | Identity and capability | ABI version, tier mask, shader-unit limits, FP mode support. |
| `0x0100-0x01ff` | Command queues | Ring base, size, head/tail, doorbell, queue status, completions. |
| `0x0200-0x02ff` | Kernel dispatch | Kernel entry, grid/local dimensions, argument buffer, resource hints. |
| `0x0300-0x03ff` | DMA engine | Copy/fill source, destination, byte count, stride, control/status. |
| `0x0400-0x04ff` | Scheduler and shader mode | Workgroup/warp policy, shader-unit mask, FP16/FP32 mode. |
| `0x0500-0x05ff` | Interrupt/status/error | Global control, interrupt mask/status, error capture, watchdog. |
| `0x0600-0x06ff` | MMU fault | Translation control, fault address, access type, command context. |
| `0x0700-0x07ff` | AXI and performance counters | Command, dispatch, DMA, AXI byte/beat, stall, and fault counters. |

## Identity And Capability Registers

| Offset | Name | Access | Reset | Description |
| ---: | --- | --- | ---: | --- |
| `0x0000` | `CVU_ID` | RO | `0x31555643` | ASCII `CVU1`. |
| `0x0004` | `CVU_ABI_VERSION` | RO | `0x00010000` | Major/minor ABI version. |
| `0x0008` | `CVU_BUILD_ID` | RO | impl | Build or simulation ID. |
| `0x000c` | `CVU_CAP_TIER_MASK` | RO | impl | Bit 0 `gpgpu_nano`, bit 1 `gpgpu_nano_ultra`, bit 2 `gpgpu_nano_ultra31`. |
| `0x0010` | `CVU_CAP_OPCODE_MASK` | RO | impl | Bit 0 `nop`, bit 1 `kernel_dispatch`, bit 2 `dma_copy`, bit 3 `dma_fill`, bit 4 `barrier`, bit 5 `set_scheduler_config`, bit 6 `set_shader_mode`, bit 7 `counter_snapshot`. |
| `0x0014` | `CVU_CAP_SHADER_LIMITS0` | RO | impl | Bits `7:0` max shader units, `15:8` max queues, `23:16` max workgroups per shader unit, `31:24` max warps per shader unit. |
| `0x0018` | `CVU_CAP_SHADER_LIMITS1` | RO | impl | Bits `15:0` max local work items, bits `31:16` max shared memory KiB per shader unit. |
| `0x001c` | `CVU_CAP_FP_MODE_MASK` | RO | impl | Bit 0 FP32, bit 1 FP16, bit 2 mixed FP16/FP32, bit 3 FP16 rate x2 metadata. |
| `0x0020` | `CVU_CAP_MEMORY_MODEL` | RO | impl | Bit 0 physical addressing, bit 1 IOVA/MMU, bit 2 completion writeback, bit 3 command fences. |
| `0x0024` | `CVU_CAP_AXI_COUNTER_MASK` | RO | impl | Bit 0 read bytes, bit 1 write bytes, bit 2 read beats, bit 3 write beats, bit 4 stalls. |

## Command Queue Registers

The S2 shell exposes queue 0 at `0x0100-0x013f`. Implementations with multiple
queues may repeat the block every `0x40` bytes.

| Offset | Name | Access | Reset | Description |
| ---: | --- | --- | ---: | --- |
| `0x0100` | `CVU_Q0_BASE_LO` | RW | `0` | Command ring base address bits `31:0`. |
| `0x0104` | `CVU_Q0_BASE_HI` | RW | `0` | Command ring base address bits `63:32`. |
| `0x0108` | `CVU_Q0_SIZE_BYTES` | RW | `0` | Power-of-two ring size in bytes, minimum `4096`. |
| `0x010c` | `CVU_Q0_HEAD` | RW/RO | `0` | Hardware-consumed byte offset. Software writes only during reset/init. |
| `0x0110` | `CVU_Q0_TAIL` | RW | `0` | Software-produced byte offset. |
| `0x0114` | `CVU_Q0_DOORBELL` | WO | `0` | Write nonzero to notify new work. |
| `0x0118` | `CVU_Q0_CONTROL` | RW | `0` | Bit 0 enable, bit 1 reset queue, bit 2 halt after current command, bit 3 proxy fallback enable. |
| `0x011c` | `CVU_Q0_STATUS` | RO | `0` | Bit 0 enabled, bit 1 busy, bit 2 empty, bit 3 full, bit 4 stalled, bit 5 faulted. |
| `0x0120` | `CVU_Q0_PRIORITY` | RW | `0` | Queue priority `0-7`; higher values win after fairness aging. |
| `0x0124` | `CVU_Q0_LAST_SEQUENCE_LO` | RO | `0` | Last retired command sequence bits `31:0`. |
| `0x0128` | `CVU_Q0_LAST_SEQUENCE_HI` | RO | `0` | Last retired command sequence bits `63:32`. |
| `0x012c` | `CVU_Q0_LAST_TAG` | RO | `0` | Last retired command `submit_tag`. |
| `0x0130` | `CVU_Q0_LAST_STATUS` | RO | `0` | Last retired completion status/error code. |
| `0x0134` | `CVU_Q0_COMPLETION_ADDR_LO` | RW | `0` | Default completion record address bits `31:0`. |
| `0x0138` | `CVU_Q0_COMPLETION_ADDR_HI` | RW | `0` | Default completion record address bits `63:32`. |

## Kernel Dispatch Registers

These direct-control registers mirror the `kernel_dispatch` packet payload and
support smoke tests without constructing a full ring packet.

| Offset | Name | Access | Reset | Description |
| ---: | --- | --- | ---: | --- |
| `0x0200` | `CVU_DISPATCH_KERNEL_ENTRY_LO` | RW | `0` | Kernel instruction entry address bits `31:0`. |
| `0x0204` | `CVU_DISPATCH_KERNEL_ENTRY_HI` | RW | `0` | Kernel instruction entry address bits `63:32`. |
| `0x0208` | `CVU_DISPATCH_ARG_BASE_LO` | RW | `0` | Argument buffer address bits `31:0`. |
| `0x020c` | `CVU_DISPATCH_ARG_BASE_HI` | RW | `0` | Argument buffer address bits `63:32`. |
| `0x0210` | `CVU_DISPATCH_ARG_BYTES` | RW | `0` | Argument buffer size in bytes. |
| `0x0214` | `CVU_DISPATCH_GRID_X` | RW | `1` | Workgroup grid dimension X. |
| `0x0218` | `CVU_DISPATCH_GRID_Y` | RW | `1` | Workgroup grid dimension Y. |
| `0x021c` | `CVU_DISPATCH_GRID_Z` | RW | `1` | Workgroup grid dimension Z. |
| `0x0220` | `CVU_DISPATCH_LOCAL_X` | RW | `32` | Work items per workgroup dimension X. |
| `0x0224` | `CVU_DISPATCH_LOCAL_Y` | RW | `1` | Work items per workgroup dimension Y. |
| `0x0228` | `CVU_DISPATCH_LOCAL_Z` | RW | `1` | Work items per workgroup dimension Z. |
| `0x022c` | `CVU_DISPATCH_SHARED_BYTES` | RW | `0` | Shared/local memory bytes per workgroup. |
| `0x0230` | `CVU_DISPATCH_PRIVATE_BYTES` | RW | `0` | Private bytes per work item for occupancy checks. |
| `0x0234` | `CVU_DISPATCH_REG_HINTS` | RW | `0` | Bits `15:0` SGPR count, `31:16` VGPR count. |
| `0x0238` | `CVU_DISPATCH_MODE` | RW | `1` | Bits `1:0` FP mode, bits `7:4` scheduler hint, bits `31:8` reserved. |
| `0x023c` | `CVU_DISPATCH_START` | WO | `0` | Write `1` to launch the direct-control dispatch. |
| `0x0240` | `CVU_DISPATCH_STATUS` | RO | `0` | Bit 0 busy, bit 1 done, bit 2 resource blocked, bit 3 faulted. |

## DMA Engine Registers

| Offset | Name | Access | Reset | Description |
| ---: | --- | --- | ---: | --- |
| `0x0300` | `CVU_DMA_SRC_LO` | RW | `0` | Source address bits `31:0`; ignored by fill. |
| `0x0304` | `CVU_DMA_SRC_HI` | RW | `0` | Source address bits `63:32`; ignored by fill. |
| `0x0308` | `CVU_DMA_DST_LO` | RW | `0` | Destination address bits `31:0`. |
| `0x030c` | `CVU_DMA_DST_HI` | RW | `0` | Destination address bits `63:32`. |
| `0x0310` | `CVU_DMA_BYTE_COUNT_LO` | RW | `0` | Byte count bits `31:0`. |
| `0x0314` | `CVU_DMA_BYTE_COUNT_HI` | RW | `0` | Byte count bits `63:32`. |
| `0x0318` | `CVU_DMA_SRC_STRIDE` | RW | `0` | Optional source stride; zero means linear. |
| `0x031c` | `CVU_DMA_DST_STRIDE` | RW | `0` | Optional destination stride; zero means linear. |
| `0x0320` | `CVU_DMA_LINE_BYTES` | RW | `0` | Optional strided-copy line width; zero means linear. |
| `0x0324` | `CVU_DMA_LINE_COUNT` | RW | `0` | Optional strided-copy line count; zero means linear. |
| `0x0328` | `CVU_DMA_FILL_PATTERN` | RW | `0` | Little-endian 32-bit fill pattern. |
| `0x032c` | `CVU_DMA_CONTROL` | RW | `0` | Bit 0 start copy, bit 1 start fill, bit 2 fence before, bit 3 fence after, bit 4 interrupt on done. |
| `0x0330` | `CVU_DMA_STATUS` | RO/W1C | `0` | Bit 0 busy, bit 1 done, bit 2 range error, bit 3 alignment error, bit 4 MMU fault. |

## Scheduler And Shader Mode Registers

| Offset | Name | Access | Reset | Description |
| ---: | --- | --- | ---: | --- |
| `0x0400` | `CVU_SCHED_CONTROL` | RW | `0` | Bit 0 enable, bit 1 reset scheduler, bit 2 halt at workgroup boundary, bit 3 halt at warp boundary. |
| `0x0404` | `CVU_SCHED_STATUS` | RO | `0` | Bit 0 enabled, bit 1 idle, bit 2 dispatch active, bit 3 resource blocked, bit 4 halted, bit 5 faulted. |
| `0x0408` | `CVU_SCHED_LIMITS` | RW | `0x00082001` | Bits `7:0` max workgroups/SU, `15:8` max warps/SU, `31:16` max local work items. |
| `0x040c` | `CVU_SCHED_POLICY` | RW | `0` | Bits `1:0` issue policy, bits `5:4` preemption granularity, bits `31:8` reserved. |
| `0x0410` | `CVU_SCHED_FAIRNESS_WINDOW` | RW | `0` | Priority aging window in cycles; zero uses implementation default. |
| `0x0414` | `CVU_SHADER_UNIT_ENABLE` | RW | `1` | Enabled shader-unit bitmask. |
| `0x0418` | `CVU_SHADER_UNIT_STATUS` | RO | `1` | Active/implemented shader-unit bitmask after tier and reset gating. |
| `0x041c` | `CVU_SHADER_TIER_SELECT` | RW | `1` | `1` one SU, `2` two SUs, `3` four SUs for the S2 skeleton. |
| `0x0420` | `CVU_FP_MODE` | RW | `1` | `1` FP32-only, `2` FP16-only, `3` mixed FP16/FP32. |
| `0x0424` | `CVU_FP_CONTROL` | RW | `0` | Bit 0 flush FP16 denorms, bit 1 flush FP32 denorms, bit 2 FP16 rate x2 metadata. |
| `0x0428` | `CVU_WATCHDOG_LIMIT` | RW | `0` | Dispatch watchdog in implementation-defined cycles; zero disables. |

## Interrupt, Status, And Error Registers

| Offset | Name | Access | Reset | Description |
| ---: | --- | --- | ---: | --- |
| `0x0500` | `CVU_GLOBAL_CONTROL` | RW | `0` | Bit 0 enable, bit 1 soft reset, bit 2 halt after current command, bit 3 proxy fallback enable. |
| `0x0504` | `CVU_GLOBAL_STATUS` | RO | `0` | Bit 0 enabled, bit 1 idle, bit 2 busy, bit 3 faulted, bit 4 watchdog expired, bit 5 interrupt pending. |
| `0x0508` | `CVU_INT_STATUS` | W1C | `0` | Bit 0 command complete, bit 1 queue error, bit 2 dispatch done, bit 3 DMA done, bit 4 MMU fault, bit 5 scheduler fault, bit 6 watchdog, bit 7 counter snapshot ready. |
| `0x050c` | `CVU_INT_ENABLE` | RW | `0` | Interrupt enable mask using `CVU_INT_STATUS` bits. |
| `0x0510` | `CVU_ERROR_CODE` | RO | `0` | Current ABI/runtime error code. |
| `0x0514` | `CVU_ERROR_INFO0` | RO | `0` | Error-specific value, usually offending opcode, queue ID, or scheduler state. |
| `0x0518` | `CVU_ERROR_INFO1` | RO | `0` | Error-specific value, usually packet offset or address low word. |
| `0x051c` | `CVU_ERROR_INFO2` | RO | `0` | Error-specific value, usually address high word or resource limit. |
| `0x0520` | `CVU_ERROR_CLEAR` | WO | `0` | Write `1` to clear sticky error state. |
| `0x0524` | `CVU_LAST_OPCODE` | RO | `0` | Last decoded opcode. |
| `0x0528` | `CVU_LAST_QUEUE_ID` | RO | `0` | Last decoded queue ID. |

## MMU Fault Registers

| Offset | Name | Access | Reset | Description |
| ---: | --- | --- | ---: | --- |
| `0x0600` | `CVU_MMU_CONTROL` | RW | `0` | Bit 0 enable translation, bit 1 enable fault capture, bit 2 inject next fault, bit 3 use IOVA context ID. |
| `0x0604` | `CVU_MMU_STATUS` | RO/W1C | `0` | Bit 0 fault valid, bit 1 read fault, bit 2 write fault, bit 3 execute fault, bit 4 permission fault, bit 5 translation fault. |
| `0x0608` | `CVU_MMU_CONTEXT_ID` | RW | `0` | Active address-space/context ID. |
| `0x060c` | `CVU_MMU_FAULT_ADDR_LO` | RO | `0` | Captured fault address bits `31:0`. |
| `0x0610` | `CVU_MMU_FAULT_ADDR_HI` | RO | `0` | Captured fault address bits `63:32`. |
| `0x0614` | `CVU_MMU_FAULT_SEQUENCE_LO` | RO | `0` | Faulting command sequence bits `31:0`. |
| `0x0618` | `CVU_MMU_FAULT_SEQUENCE_HI` | RO | `0` | Faulting command sequence bits `63:32`. |
| `0x061c` | `CVU_MMU_FAULT_OPCODE` | RO | `0` | Opcode active when the fault occurred. |
| `0x0620` | `CVU_MMU_FAULT_QUEUE_ID` | RO | `0` | Queue ID active when the fault occurred. |
| `0x0624` | `CVU_MMU_FAULT_SHADER_UNIT` | RO | `0` | Shader unit or DMA engine ID active when the fault occurred. |

## AXI And Performance Counter Registers

| Offset | Name | Access | Reset | Description |
| ---: | --- | --- | ---: | --- |
| `0x0700` | `CVU_PERF_CONTROL` | RW | `0` | Bit 0 enable counters, bit 1 clear counters, bit 2 freeze counters, bit 3 snapshot counters. |
| `0x0704` | `CVU_PERF_COMMANDS` | RO | `0` | Retired command count. |
| `0x0708` | `CVU_PERF_DISPATCHES` | RO | `0` | Retired kernel dispatch count. |
| `0x070c` | `CVU_PERF_DMA_OPS` | RO | `0` | Retired DMA copy/fill count. |
| `0x0710` | `CVU_PERF_AXI_READ_BYTES_LO` | RO | `0` | AXI read bytes bits `31:0`. |
| `0x0714` | `CVU_PERF_AXI_READ_BYTES_HI` | RO | `0` | AXI read bytes bits `63:32`. |
| `0x0718` | `CVU_PERF_AXI_WRITE_BYTES_LO` | RO | `0` | AXI write bytes bits `31:0`. |
| `0x071c` | `CVU_PERF_AXI_WRITE_BYTES_HI` | RO | `0` | AXI write bytes bits `63:32`. |
| `0x0720` | `CVU_PERF_AXI_READ_BEATS` | RO | `0` | AXI read beat count. |
| `0x0724` | `CVU_PERF_AXI_WRITE_BEATS` | RO | `0` | AXI write beat count. |
| `0x0728` | `CVU_PERF_STALL_CYCLES_LO` | RO | `0` | Scheduler/DMA stall cycles bits `31:0`. |
| `0x072c` | `CVU_PERF_STALL_CYCLES_HI` | RO | `0` | Scheduler/DMA stall cycles bits `63:32`. |
| `0x0730` | `CVU_PERF_MMU_FAULTS` | RO | `0` | Captured MMU fault count. |
| `0x0734` | `CVU_PERF_ERROR_COUNT` | RO | `0` | Runtime error count. |

## Error Code Values

| Value | Name | Description |
| ---: | --- | --- |
| `0x0000` | `OK` | No error. |
| `0x0001` | `ERR_BAD_MAGIC` | Command packet magic is invalid. |
| `0x0002` | `ERR_BAD_VERSION` | ABI version is unsupported. |
| `0x0003` | `ERR_BAD_LENGTH` | Packet or payload length is invalid. |
| `0x0004` | `ERR_UNSUPPORTED_TIER` | Requested tier is not implemented. |
| `0x0005` | `ERR_UNSUPPORTED_OPCODE` | Opcode is unknown or unsupported for the tier. |
| `0x0006` | `ERR_BAD_QUEUE` | Queue ID, size, alignment, head, or tail is invalid. |
| `0x0007` | `ERR_BAD_DISPATCH` | Grid, local shape, resource hints, or FP mode is invalid. |
| `0x0008` | `ERR_BAD_DMA` | DMA range, stride, size, or alignment is invalid. |
| `0x0009` | `ERR_MMU_FAULT` | MMU translation, permission, or injected fault. |
| `0x000a` | `ERR_SCHEDULER_FAULT` | Scheduler allocation, halt, or injected dispatch fault. |
| `0x000b` | `ERR_TIMEOUT` | Watchdog expired. |
| `0x000c` | `ERR_COUNTER_FAULT` | Counter snapshot address or selector is invalid. |

## Ventus Integration Notes

The register file is the boundary between the Celviz GPGPU command/runtime
control plane and the Ventus compute framework. The first S2 implementation
should expose this map through a proxy shell that can be loaded, simulated, or
driven by a userspace shim. Once command queue behavior, scheduler mode
programming, DMA, interrupts, MMU-fault reporting, and AXI counters are proven,
the team can decide whether to add Chisel modules under Ventus top-level,
memory, or compute dispatch paths.
