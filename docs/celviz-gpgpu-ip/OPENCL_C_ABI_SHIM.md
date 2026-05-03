# OpenCL-like C ABI Shim

This directory contains a minimal clean-room userspace C ABI shim for Celviz GPGPU IP smoke testing:

- `runtime/opencl/celviz_opencl.h`
- `runtime/opencl/celviz_opencl.c`
- `runtime/opencl/vector_add_smoke.c`
- `scripts/verify_celviz_gpgpu_opencl_c_abi.sh`

It is intentionally narrow. It is not a Khronos ICD, not `libOpenCL`, not Khronos CTS evidence, not official OpenCL conformance, not a production Linux driver, and not Vivante proprietary compatibility.

## Exported Subset

The shim exports the OpenCL-like calls needed for a single in-process vector-add smoke:

- `clGetPlatformIDs`
- `clGetDeviceIDs`
- `clCreateContext`
- `clCreateCommandQueueWithProperties`
- `clCreateBuffer`
- `clCreateProgramWithSource`
- `clBuildProgram`
- `clGetProgramBuildInfo`
- `clCreateKernel`
- `clSetKernelArg`
- `clEnqueueWriteBuffer`
- `clEnqueueNDRangeKernel`
- `clEnqueueReadBuffer`
- `clFinish`
- `clReleaseMemObject`
- `clReleaseKernel`
- `clReleaseProgram`
- `clReleaseCommandQueue`
- `clReleaseContext`
- `clReleaseEvent`

The implementation keeps opaque handles, validates common invalid values, rejects unsupported queue properties, rejects unsupported OpenCL C tokens in the smoke build path, and executes the `vector_add` kernel on CPU-owned backing storage. That CPU execution is deliberate: the purpose is to prove a stable C ABI lifecycle for userspace integration scaffolding, not to claim hardware execution or conformance.

## Smoke Flow

`runtime/opencl/vector_add_smoke.c` performs the following lifecycle:

1. Discover one clean-room platform and one GPU-like device.
2. Create a context and in-order command queue.
3. Allocate three buffers.
4. Write two float vectors.
5. Build one source string containing `__kernel void vector_add`.
6. Create the kernel, set three buffer args plus element count, enqueue one 1D NDRange, read the output, and check every element.
7. Release every object created by the smoke.

The verifier compiles with `-std=c99 -Wall -Wextra -Werror -pedantic`, links a temporary native smoke binary, runs it, checks exported symbols with `nm`, and writes:

- `artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_c_abi_smoke.json`

Run it with:

```sh
scripts/verify_celviz_gpgpu_opencl_c_abi.sh
```

Expected terminal result:

```text
celviz_gpgpu_opencl_c_abi_verify: pass symbols=19 smoke=vector_add elements=256
```

## Boundary

This shim is a clean-room executable readiness artifact for the Celviz GPGPU IP userspace ABI boundary. It deliberately does not provide Khronos ICD loader integration, OpenCL headers, full OpenCL C parsing, OpenCL device info coverage, binary program ingestion, event profiling, images, samplers, SVM, atomics, pipes, command queue out-of-order execution, or CTS-significant behavior.
