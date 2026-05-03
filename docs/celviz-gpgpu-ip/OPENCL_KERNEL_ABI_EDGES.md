# OpenCL Kernel ABI Negative/Edge Runner

OpenCL kernel ABI negative/edge evidence for the local clean-room Celviz GPGPU IP subset only; not Khronos CTS, not official OpenCL conformance, not libOpenCL/ICD behavior, and not proprietary Vivante compiler/runtime/driver/firmware/command-stream compatibility

## Summary

- Status: `pass`
- Cases: `14`
- JSON: `artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_kernel_abi_edges.json`
- Existing capabilities: `opencl_subset.compile_kernel`, `opencl_build_error_code_matrix.OpenCLSubsetMatrixShim`

## Categories

- `arg size/index/type`: `pass` `4/4` statuses=CL_INVALID_ARG_INDEX, CL_INVALID_ARG_SIZE, CL_INVALID_MEM_OBJECT, CL_SUCCESS
- `buffer access mismatch`: `pass` `2/2` statuses=CL_BUILD_PROGRAM_FAILURE, CL_INVALID_ARG_VALUE
- `global/local size`: `pass` `4/4` statuses=CL_BUILD_PROGRAM_FAILURE, CL_INVALID_WORK_GROUP_SIZE, CL_SUCCESS
- `unsupported address spaces/builtins/double`: `pass` `4/4` statuses=CL_BUILD_PROGRAM_FAILURE

## Cases

- `abi_arg_layout_vector_scalar_edges` `arg size/index/type` expected `CL_SUCCESS` observed `CL_SUCCESS` status=`pass`
- `set_arg_reject_bad_index` `arg size/index/type` expected `CL_INVALID_ARG_INDEX` observed `CL_INVALID_ARG_INDEX` status=`pass`
- `set_arg_reject_bad_size` `arg size/index/type` expected `CL_INVALID_ARG_SIZE` observed `CL_INVALID_ARG_SIZE` status=`pass`
- `set_arg_reject_pointer_type_mismatch` `arg size/index/type` expected `CL_INVALID_MEM_OBJECT` observed `CL_INVALID_MEM_OBJECT` status=`pass`
- `compile_reject_missing_pointer_buffer_metadata` `buffer access mismatch` expected `CL_BUILD_PROGRAM_FAILURE` observed `CL_BUILD_PROGRAM_FAILURE` status=`pass`
- `set_arg_reject_buffer_access_mismatch` `buffer access mismatch` expected `CL_INVALID_ARG_VALUE` observed `CL_INVALID_ARG_VALUE` status=`pass`
- `compile_accept_3d_global_local_edge` `global/local size` expected `CL_SUCCESS` observed `CL_SUCCESS` status=`pass`
- `compile_reject_zero_global_size` `global/local size` expected `CL_BUILD_PROGRAM_FAILURE` observed `CL_BUILD_PROGRAM_FAILURE` status=`pass`
- `compile_reject_non_divisible_local_size` `global/local size` expected `CL_BUILD_PROGRAM_FAILURE` observed `CL_BUILD_PROGRAM_FAILURE` status=`pass`
- `enqueue_reject_local_workgroup_too_large` `global/local size` expected `CL_INVALID_WORK_GROUP_SIZE` observed `CL_INVALID_WORK_GROUP_SIZE` status=`pass`
- `build_reject_generic_address_space` `unsupported address spaces/builtins/double` expected `CL_BUILD_PROGRAM_FAILURE` observed `CL_BUILD_PROGRAM_FAILURE` status=`pass`
- `build_reject_image_address_object` `unsupported address spaces/builtins/double` expected `CL_BUILD_PROGRAM_FAILURE` observed `CL_BUILD_PROGRAM_FAILURE` status=`pass`
- `build_reject_unsupported_builtin` `unsupported address spaces/builtins/double` expected `CL_BUILD_PROGRAM_FAILURE` observed `CL_BUILD_PROGRAM_FAILURE` status=`pass`
- `build_reject_double_precision` `unsupported address spaces/builtins/double` expected `CL_BUILD_PROGRAM_FAILURE` observed `CL_BUILD_PROGRAM_FAILURE` status=`pass`

## Coverage Boundary

This is an executable negative/edge runner for the local kernel ABI path. It covers argument size/index/type handling, global/local launch geometry, unsupported address spaces, unsupported builtins, unsupported double precision, and buffer access mismatch behavior by invoking the existing subset compiler and error-code matrix shim.

It is not Khronos CTS, not official OpenCL conformance, not a product ICD/libOpenCL implementation, and not proprietary Vivante compatibility evidence.
