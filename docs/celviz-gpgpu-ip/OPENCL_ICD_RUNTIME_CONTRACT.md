# OpenCL ICD Runtime Contract

clean-room OpenCL host API contract for Celviz proxy/runtime alignment; not a Khronos ICD loader integration, not an official OpenCL conformance claim, not a production Linux driver, and not a stable public ABI

## Host API Surface

### clGetPlatformIDs
- Status: proxy
- Proxy mapping: single Celviz clean-room platform descriptor
- Evidence: docs/celviz-gpgpu-ip/OPENCL_SUBSET_ABI.md
- Blocker: No Khronos ICD vendor library or platform enumeration ABI is implemented.
- Next executable test: Add a mock ICD loader fixture that enumerates exactly one Celviz platform.

### clGetDeviceIDs
- Status: proxy
- Proxy mapping: device_tiers.json models tiered GPU-like devices
- Evidence: artifacts/rank_01_vivante_3d_gpgpu_ip/demo/outputs/device_tiers.json
- Blocker: Device type/profile/extensions/limits are not spec-complete.
- Next executable test: Validate CL_DEVICE_TYPE_GPU, work-item limits, memory sizes, and feature queries.

### clGetDeviceInfo
- Status: partial
- Proxy mapping: proxy metrics expose tiers, ops/cycle proxies, and memory metadata
- Evidence: artifacts/rank_01_vivante_3d_gpgpu_ip/demo/outputs/kernel_metrics.json
- Blocker: OpenCL 3.0 device-info table and optional feature query semantics are incomplete.
- Next executable test: Create a device-info golden table and negative tests for unsupported queries.

### clCreateContext
- Status: proxy
- Proxy mapping: linux_runtime_proxy context/device lifecycle
- Evidence: artifacts/rank_01_vivante_3d_gpgpu_ip/os_runtime/linux_runtime_evidence.json
- Blocker: No real ICD context handles, callback semantics, or multi-device context validation.
- Next executable test: Add handle lifetime tests for create/release/error callback cases.

### clCreateCommandQueueWithProperties
- Status: partial
- Proxy mapping: driver_submission_model queue lifecycle and ordered completion
- Evidence: artifacts/rank_01_vivante_3d_gpgpu_ip/driver_submission/queue_lifecycle.json
- Blocker: Out-of-order queues, profiling properties, and full error behavior are absent.
- Next executable test: Map in-order queue semantics to fence/event traces and reject unsupported properties.

### clCreateBuffer
- Status: partial
- Proxy mapping: runtime_proxy memory_regions and buffer_binds
- Evidence: artifacts/rank_01_vivante_3d_gpgpu_ip/demo/outputs/buffer_binds.json
- Blocker: OpenCL flags, host pointer import, sub-buffers, and map/unmap semantics are incomplete.
- Next executable test: Add flag matrix tests for read/write/copy-host-ptr unsupported cases.

### clEnqueueWriteBuffer
- Status: proxy
- Proxy mapping: host_to_device/dma_copy command category
- Evidence: artifacts/rank_01_vivante_3d_gpgpu_ip/rtl/control_plane_demo.json
- Blocker: Blocking/non-blocking, offset bounds, event wait lists, and map coherency are not complete.
- Next executable test: Add offset/bounds/event-wait directed tests through runtime_proxy.

### clEnqueueReadBuffer
- Status: proxy
- Proxy mapping: device_to_host/dma_copy readback and golden hashes
- Evidence: artifacts/rank_01_vivante_3d_gpgpu_ip/demo/outputs/queue_trace.json
- Blocker: Blocking/non-blocking and event wait-list behavior needs CTS-shaped validation.
- Next executable test: Add event-order and negative bounds tests for readback commands.

### clCreateProgramWithSource
- Status: partial
- Proxy mapping: opencl_subset.py parses one-kernel OpenCL C subset sources
- Evidence: tools/celviz_gpgpu_ip/opencl_subset.py
- Blocker: Multi-kernel programs, include options, diagnostics, and full OpenCL C grammar are absent.
- Next executable test: Add source program object tests for one-kernel accepted and multi-kernel rejected cases.

### clBuildProgram
- Status: partial
- Proxy mapping: opencl_subset.py compile_kernel emits ABI JSON
- Evidence: artifacts/rank_01_vivante_3d_gpgpu_ip/demo/opencl_subset/opencl_subset_evidence.json
- Blocker: Build options, binaries, SPIR-V ingestion, logs, and specialization are absent.
- Next executable test: Add build-log and unsupported-option negative tests.

### clCreateKernel
- Status: partial
- Proxy mapping: kernel ABI names and metadata map to runtime dispatch
- Evidence: artifacts/rank_01_vivante_3d_gpgpu_ip/demo/opencl_subset/abi/vector_add.kernel_abi.json
- Blocker: Program-owned kernel handle lifecycle and symbol lookup errors are incomplete.
- Next executable test: Add kernel name lookup tests for valid and missing symbols.

### clSetKernelArg
- Status: partial
- Proxy mapping: ABI scalar_args and buffer metadata bind kernel arguments
- Evidence: docs/celviz-gpgpu-ip/OPENCL_SUBSET_ABI.md
- Blocker: Argument type checking, local memory arg sizing, and retained object lifetime are incomplete.
- Next executable test: Add scalar/vector/pointer/local argument layout tests.

### clEnqueueNDRangeKernel
- Status: partial
- Proxy mapping: runtime kernel_dispatch command models NDRange and local geometry
- Evidence: artifacts/rank_01_vivante_3d_gpgpu_ip/demo/opencl_subset/runtime_commands.json
- Blocker: Work dimension validation, offsets, event wait lists, and unsupported local sizes need full coverage.
- Next executable test: Add NDRange geometry matrix tests and map failures to OpenCL-style error codes.

### clFinish
- Status: proxy
- Proxy mapping: runtime pending_count reaches zero
- Evidence: artifacts/rank_01_vivante_3d_gpgpu_ip/demo/opencl_subset/runtime_proxy/runtime_metrics.json
- Blocker: Per-queue blocking semantics and error propagation are modeled but not API-stable.
- Next executable test: Add queue drain tests with success and injected fault cases.

### clWaitForEvents
- Status: proxy
- Proxy mapping: driver fence/event lifecycle
- Evidence: artifacts/rank_01_vivante_3d_gpgpu_ip/driver_submission/fence_event_lifecycle.json
- Blocker: Event wait-list validation, status transitions, callbacks, and profiling are incomplete.
- Next executable test: Add event dependency graph tests including failure propagation.

### clRelease*
- Status: partial
- Proxy mapping: proxy lifecycle reports close queues and releases handles conceptually
- Evidence: artifacts/rank_01_vivante_3d_gpgpu_ip/os_runtime/linux_runtime_evidence.json
- Blocker: Reference counting, use-after-release errors, and cross-object ownership are absent.
- Next executable test: Add retained/released handle lifecycle tests across context, queue, buffer, program, kernel, and event.
