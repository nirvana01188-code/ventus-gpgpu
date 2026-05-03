# OpenCL Userspace Samples

clean-room executable userspace samples using the Celviz OpenCL host API shim, OpenCL C subset compiler, runtime proxy, and microop interpreter evidence. This is not Khronos CTS, not official OpenCL conformance, not a Khronos ICD, not libOpenCL, and not a production driver claim.

## Boundary

These samples are executable readiness evidence only. They are not official OpenCL conformance, not Khronos CTS, not a Khronos ICD, and not libOpenCL.

## Samples

- `vector_add`: status=`pass` writes=`2` reads=`1` commands=`4` microop_hash=`f998298c240cb303e059fb12398fc974eaf700bcfae021c2bdea45b3fac8ae3f`
- `gemm`: status=`pass` writes=`2` reads=`1` commands=`4` microop_hash=`911fceed2dd17b761f3fe702cee560796989ffd71475700af0a6a6e6472913d0`
- `conv2d`: status=`pass` writes=`2` reads=`1` commands=`4` microop_hash=`d5fe2b065e3f25a6a540877c8d003fede5cd93e5d509c6996ef19e823a03269a`
- `image_filter`: status=`pass` writes=`1` reads=`1` commands=`3` microop_hash=`eafdb0707431eda4992fb4663356d0b62f91f78ec9e78f7744e5712ffecf4101`

## Error Paths

- `build_rejects_unsupported_double` path=`host_api_shim.clBuildProgram` pass=`True`
- `kernel_name_error_path` path=`host_api_shim.clCreateKernel` pass=`True`
- `runtime_rejects_out_of_bounds_write_buffer` path=`runtime_proxy.write_buffer` pass=`True`

## Evidence

- JSON: `artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_userspace_samples.json`
