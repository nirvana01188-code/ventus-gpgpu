# OpenCL Build Log And Error Code Matrix

clean-room OpenCL-style build log/error-code matrix for Celviz GPGPU IP subset evidence only; not Khronos CTS, not official OpenCL conformance, not libOpenCL/ICD, and not proprietary Vivante compiler/SDK/firmware/driver/command-stream compatibility

## Summary

- Status: `pass`
- Cases: `22`
- JSON: `artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_build_error_code_matrix.json`

## Categories

- `NDRange geometry`: `pass` `6/6` codes=CL_INVALID_GLOBAL_WORK_SIZE, CL_INVALID_VALUE, CL_INVALID_WORK_DIMENSION, CL_INVALID_WORK_GROUP_SIZE, CL_SUCCESS
- `buffer errors`: `pass` `3/3` codes=CL_INVALID_VALUE, CL_SUCCESS
- `clBuildProgram`: `pass` `5/5` codes=CL_BUILD_PROGRAM_FAILURE, CL_INVALID_BUILD_OPTIONS, CL_INVALID_PROGRAM, CL_SUCCESS
- `clCreateKernel`: `pass` `3/3` codes=CL_INVALID_KERNEL_NAME, CL_INVALID_PROGRAM_EXECUTABLE, CL_SUCCESS
- `clSetKernelArg`: `pass` `5/5` codes=CL_INVALID_ARG_INDEX, CL_INVALID_ARG_SIZE, CL_INVALID_ARG_VALUE, CL_INVALID_MEM_OBJECT, CL_SUCCESS

## Matrix

- `build_success_vector_add` `clBuildProgram` expected `CL_SUCCESS` observed `CL_SUCCESS` status=`pass`
- `build_reject_unsupported_double` `clBuildProgram` expected `CL_BUILD_PROGRAM_FAILURE` observed `CL_BUILD_PROGRAM_FAILURE` status=`pass`
- `build_reject_multi_kernel_source` `clBuildProgram` expected `CL_BUILD_PROGRAM_FAILURE` observed `CL_BUILD_PROGRAM_FAILURE` status=`pass`
- `build_reject_options` `clBuildProgram` expected `CL_INVALID_BUILD_OPTIONS` observed `CL_INVALID_BUILD_OPTIONS` status=`pass`
- `build_invalid_program_handle` `clBuildProgram` expected `CL_INVALID_PROGRAM` observed `CL_INVALID_PROGRAM` status=`pass`
- `create_kernel_success` `clCreateKernel` expected `CL_SUCCESS` observed `CL_SUCCESS` status=`pass`
- `create_kernel_missing_symbol` `clCreateKernel` expected `CL_INVALID_KERNEL_NAME` observed `CL_INVALID_KERNEL_NAME` status=`pass`
- `create_kernel_unbuilt_program` `clCreateKernel` expected `CL_INVALID_PROGRAM_EXECUTABLE` observed `CL_INVALID_PROGRAM_EXECUTABLE` status=`pass`
- `set_arg_success_all_vector_add_args` `clSetKernelArg` expected `CL_SUCCESS` observed `CL_SUCCESS` status=`pass`
- `set_arg_bad_index` `clSetKernelArg` expected `CL_INVALID_ARG_INDEX` observed `CL_INVALID_ARG_INDEX` status=`pass`
- `set_arg_bad_size` `clSetKernelArg` expected `CL_INVALID_ARG_SIZE` observed `CL_INVALID_ARG_SIZE` status=`pass`
- `set_arg_invalid_mem_object` `clSetKernelArg` expected `CL_INVALID_MEM_OBJECT` observed `CL_INVALID_MEM_OBJECT` status=`pass`
- `set_arg_wrong_buffer_access` `clSetKernelArg` expected `CL_INVALID_ARG_VALUE` observed `CL_INVALID_ARG_VALUE` status=`pass`
- `ndrange_success` `clEnqueueNDRangeKernel` expected `CL_SUCCESS` observed `CL_SUCCESS` status=`pass`
- `ndrange_bad_work_dim` `clEnqueueNDRangeKernel` expected `CL_INVALID_WORK_DIMENSION` observed `CL_INVALID_WORK_DIMENSION` status=`pass`
- `ndrange_zero_global_size` `clEnqueueNDRangeKernel` expected `CL_INVALID_GLOBAL_WORK_SIZE` observed `CL_INVALID_GLOBAL_WORK_SIZE` status=`pass`
- `ndrange_non_divisible_local` `clEnqueueNDRangeKernel` expected `CL_INVALID_WORK_GROUP_SIZE` observed `CL_INVALID_WORK_GROUP_SIZE` status=`pass`
- `ndrange_local_wg_too_large` `clEnqueueNDRangeKernel` expected `CL_INVALID_WORK_GROUP_SIZE` observed `CL_INVALID_WORK_GROUP_SIZE` status=`pass`
- `ndrange_nonzero_global_offset` `clEnqueueNDRangeKernel` expected `CL_INVALID_VALUE` observed `CL_INVALID_VALUE` status=`pass`
- `buffer_success_read_write` `clCreateBuffer` expected `CL_SUCCESS` observed `CL_SUCCESS` status=`pass`
- `buffer_zero_size` `clCreateBuffer` expected `CL_INVALID_VALUE` observed `CL_INVALID_VALUE` status=`pass`
- `buffer_bad_flags` `clCreateBuffer` expected `CL_INVALID_VALUE` observed `CL_INVALID_VALUE` status=`pass`

Boundary: this matrix is executable subset evidence. It is not Khronos CTS, not official OpenCL conformance, and not proprietary Vivante compatibility.
