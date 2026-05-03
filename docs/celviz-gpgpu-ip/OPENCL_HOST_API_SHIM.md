# OpenCL Host API Shim

clean-room OpenCL host API shim for Celviz GPGPU IP readiness; executes a local subset lifecycle through the compiler ABI and runtime proxy. Not a Khronos ICD, not libOpenCL, not official OpenCL conformance, not CTS pass evidence, not a production Linux driver, and not Vivante proprietary compatibility.

## Executed Lifecycle

- `clGetPlatformIDs` -> `CL_SUCCESS` handle=`platform_1`
- `clGetDeviceIDs` -> `CL_SUCCESS` handle=`device_2`
- `clGetDeviceInfo` -> `CL_SUCCESS` handle=``
- `clGetDeviceInfo` -> `CL_SUCCESS` handle=``
- `clGetDeviceInfo` -> `CL_SUCCESS` handle=``
- `clGetDeviceInfo` -> `CL_SUCCESS` handle=``
- `clGetDeviceInfo` -> `CL_SUCCESS` handle=``
- `clGetDeviceInfo` -> `CL_SUCCESS` handle=``
- `clGetDeviceInfo` -> `CL_SUCCESS` handle=``
- `clGetDeviceInfo` -> `CL_SUCCESS` handle=``
- `clGetDeviceInfo` -> `CL_SUCCESS` handle=``
- `clGetDeviceInfo` -> `CL_SUCCESS` handle=``
- `clGetDeviceInfo` -> `CL_SUCCESS` handle=``
- `clGetDeviceInfo` -> `CL_SUCCESS` handle=``
- `clGetDeviceInfo` -> `CL_SUCCESS` handle=``
- `clGetDeviceInfo` -> `CL_SUCCESS` handle=``
- `clGetDeviceInfo` -> `CL_SUCCESS` handle=``
- `clGetDeviceInfo` -> `CL_SUCCESS` handle=``
- `clCreateContext` -> `CL_SUCCESS` handle=`context_3`
- `clCreateCommandQueueWithProperties` -> `CL_SUCCESS` handle=`queue_4`
- `clCreateBuffer` -> `CL_SUCCESS` handle=`buffer_5`
- `clCreateBuffer` -> `CL_SUCCESS` handle=`buffer_6`
- `clCreateBuffer` -> `CL_SUCCESS` handle=`buffer_7`
- `clEnqueueWriteBuffer` -> `CL_SUCCESS` handle=`event_8`
- `clEnqueueWriteBuffer` -> `CL_SUCCESS` handle=`event_9`
- `clCreateProgramWithSource` -> `CL_SUCCESS` handle=`program_10`
- `clBuildProgram` -> `CL_SUCCESS` handle=``
- `clCreateKernel` -> `CL_SUCCESS` handle=`kernel_11`
- `clSetKernelArg` -> `CL_SUCCESS` handle=``
- `clSetKernelArg` -> `CL_SUCCESS` handle=``
- `clSetKernelArg` -> `CL_SUCCESS` handle=``
- `clSetKernelArg` -> `CL_SUCCESS` handle=``
- `clEnqueueNDRangeKernel` -> `CL_SUCCESS` handle=`event_12`
- `clEnqueueReadBuffer` -> `CL_SUCCESS` handle=`event_13`
- `clWaitForEvents` -> `CL_SUCCESS` handle=``
- `clFinish` -> `CL_SUCCESS` handle=``
- `clReleaseEvent` -> `CL_SUCCESS` handle=`event_13`
- `clReleaseEvent` -> `CL_SUCCESS` handle=`event_12`
- `clReleaseEvent` -> `CL_SUCCESS` handle=`event_8`
- `clReleaseEvent` -> `CL_SUCCESS` handle=`event_9`
- `clReleaseKernel` -> `CL_SUCCESS` handle=`kernel_11`
- `clReleaseProgram` -> `CL_SUCCESS` handle=`program_10`
- `clReleaseBuffer` -> `CL_SUCCESS` handle=`buffer_5`
- `clReleaseBuffer` -> `CL_SUCCESS` handle=`buffer_6`
- `clReleaseBuffer` -> `CL_SUCCESS` handle=`buffer_7`
- `clReleaseQueue` -> `CL_SUCCESS` handle=`queue_4`
- `clReleaseContext` -> `CL_SUCCESS` handle=`context_3`
- `clReleaseDevice` -> `CL_SUCCESS` handle=`device_2`
- `clReleasePlatform` -> `CL_SUCCESS` handle=`platform_1`

## Negative Error-Code Tests

- `unsupported_device_info_query`: `CL_INVALID_VALUE` expected `CL_INVALID_VALUE`
- `reject_out_of_order_queue_property`: `CL_INVALID_QUEUE_PROPERTIES` expected `CL_INVALID_QUEUE_PROPERTIES`
- `reject_missing_kernel_name`: `CL_INVALID_KERNEL_NAME` expected `CL_INVALID_KERNEL_NAME`
- `reject_bad_kernel_arg_index`: `CL_INVALID_ARG_INDEX` expected `CL_INVALID_ARG_INDEX`
- `reject_zero_size_buffer`: `CL_INVALID_VALUE` expected `CL_INVALID_VALUE`

## Device Info Matrix

- `CL_DEVICE_TYPE` readiness=`proxy` value=`CL_DEVICE_TYPE_GPU`
- `CL_DEVICE_VENDOR` readiness=`proxy` value=`Celviz clean-room`
- `CL_DEVICE_NAME` readiness=`proxy` value=`Celviz GPGPU IP proxy`
- `CL_DEVICE_VERSION` readiness=`partial` value=`OpenCL 1.2 Celviz-readiness subset`
- `CL_DEVICE_OPENCL_C_VERSION` readiness=`partial` value=`OpenCL C subset`
- `CL_DEVICE_PROFILE` readiness=`proxy` value=`EMBEDDED_PROFILE_PROXY`
- `CL_DEVICE_EXTENSIONS` readiness=`ready` value=``
- `CL_DEVICE_MAX_WORK_ITEM_DIMENSIONS` readiness=`proxy` value=`3`
- `CL_DEVICE_MAX_WORK_GROUP_SIZE` readiness=`proxy` value=`256`
- `CL_DEVICE_MAX_WORK_ITEM_SIZES` readiness=`proxy` value=`[256, 256, 64]`
- `CL_DEVICE_ADDRESS_BITS` readiness=`proxy` value=`40`
- `CL_DEVICE_GLOBAL_MEM_SIZE` readiness=`proxy` value=`268435456`
- `CL_DEVICE_LOCAL_MEM_SIZE` readiness=`proxy` value=`32768`
- `CL_DEVICE_IMAGE_SUPPORT` readiness=`ready` value=`False`
- `CL_DEVICE_SVM_CAPABILITIES` readiness=`ready` value=`0`
- `CL_DEVICE_ATOMIC_MEMORY_CAPABILITIES` readiness=`ready` value=`0`

## Build Log / Error Matrix

- `build_rejects_double`: `CL_BUILD_PROGRAM_FAILURE` pass=`True`
- `kernel_name_error_code`: `CL_INVALID_KERNEL_NAME` pass=`True`
- `negative_arg_index_error_code`: `CL_INVALID_ARG_INDEX` pass=`True`

## Event Profiling Matrix

- `event_8` command=`write_buffer` wait_for=`[]` queued=100 submit=107 start=114 end=121
- `event_9` command=`write_buffer` wait_for=`[]` queued=128 submit=135 start=142 end=149
- `event_12` command=`ndrange_kernel` wait_for=`[]` queued=156 submit=163 start=170 end=177
- `event_13` command=`read_buffer` wait_for=`['event_12']` queued=184 submit=191 start=198 end=205

## Runtime Evidence

- Runtime status: `pass`
- Commands completed: `1`
- Commands failed: `0`
- Pending count: `0`

Boundary: this is an executable readiness shim, not a Khronos ICD or official CTS result.
