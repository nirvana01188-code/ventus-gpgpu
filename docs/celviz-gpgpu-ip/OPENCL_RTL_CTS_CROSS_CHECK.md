# OpenCL RTL/CTS Readiness Cross-Check

Generated: `2026-05-03T05:51:17+00:00`

Status: `pass`

OpenCL host API shim to RTL/coverage cross-check for Celviz GPGPU IP readiness. This maps local clean-room dispatch/event/buffer paths to existing RTL debug counters and Verilator functional coverage bins. It is not Khronos CTS, not official OpenCL conformance, not a product ICD, not RTL structural coverage 100%, and not silicon signoff.

## Summary

- CTS ready: `false`
- RTL structural coverage closed: `false`
- Purpose: map local OpenCL host shim dispatch/event/buffer paths to existing RTL counters and Verilator functional bins.

## Path Mappings

| Path | Pass | Host APIs | Runtime opcodes | RTL counters | Coverage bins |
| --- | --- | --- | --- | --- | --- |
| `host_dispatch_to_kernel_dispatch` | `true` | clCreateProgramWithSource:Y, clBuildProgram:Y, clCreateKernel:Y, clSetKernelArg:Y, clEnqueueNDRangeKernel:Y, clFinish:Y | kernel_dispatch:Y | commands_submitted:Y, commands_completed:Y, kernel_dispatches:Y, apb_writes:Y, apb_reads:Y | queues:Y, native_command_categories:Y, pending_count_zero:Y |
| `host_events_to_interrupt_fence_paths` | `true` | clEnqueueNDRangeKernel:Y, clEnqueueReadBuffer:Y, clWaitForEvents:Y, clFinish:Y | kernel_dispatch:Y | completion_interrupts:Y, interrupt_clears:Y, fence_waits:Y, fence_signals:Y | completion_interrupt:Y, fence_wait:Y, fence_signal:Y, pending_count_zero:Y |
| `host_buffers_to_dma_and_axi_paths` | `true` | clCreateBuffer:Y, clEnqueueWriteBuffer:Y, clEnqueueReadBuffer:Y, clReleaseBuffer:Y | kernel_dispatch:Y | bytes_read:Y, bytes_written:Y, axi_read_transactions:Y, axi_write_transactions:Y, dma_copies:Y, dma_fills:Y | dma_fill:Y, dma_copy:Y, dma_copy_h2d:Y, dma_copy_d2h:Y, native_command_categories:Y |
| `host_negative_api_to_fault_bins` | `true` | clGetDeviceInfo:Y, clCreateCommandQueueWithProperties:Y, clCreateKernel:Y, clSetKernelArg:Y, clCreateBuffer:Y | kernel_dispatch:Y | commands_failed:Y, error_interrupts:Y, mmu_faults:Y, scheduler_faults:Y | error_interrupt:Y, mmu_fault:Y, scheduler_fault:Y |

## Checks

- `host_api_trace_present`: `pass`
- `runtime_commands_have_opencl_kernels`: `pass`
- `runtime_proxy_metrics_pass`: `pass`
- `control_plane_metrics_pass`: `pass`
- `verilator_functional_bins_pass`: `pass`
- `opencl_readiness_scope_present`: `pass`
- `supplemental_structural_targets_recorded`: `pass`
- `dispatch_mapping_pass`: `pass`
- `event_mapping_pass`: `pass`
- `buffer_mapping_pass`: `pass`
- `negative_mapping_pass`: `pass`
- `no_cts_or_structural_overclaim`: `pass`

## Structural Metrics

These metrics are observations only. They are not a structural coverage closure or waiver signoff.

```json
{
  "branch": {
    "found": 2134626,
    "hit": 614495,
    "percent": 28.787,
    "status": "available"
  },
  "line": {
    "found": 97500,
    "hit": 77108,
    "percent": 79.085,
    "status": "available"
  },
  "status": "reported_separately_not_a_closure_claim",
  "toggle": {
    "found": null,
    "hit": null,
    "percent": null,
    "reason": "toggle counts were not present in coverage info",
    "status": "unavailable"
  }
}
```

## Claim Boundaries

```json
{
  "khronos_cts_pass": false,
  "official_opencl_conformance": false,
  "product_icd": false,
  "rtl_structural_coverage_100": false,
  "silicon_signoff": false
}
```

## Completion Rule

This cross-check is complete when the JSON status is `pass` and all mappings show host API coverage, runtime opcode evidence, RTL/debug counter evidence, and Verilator functional-bin evidence. It still does not mean Khronos CTS readiness, official OpenCL conformance, product ICD readiness, RTL structural 100%, or silicon signoff.
