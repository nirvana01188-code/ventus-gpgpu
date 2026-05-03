# Phase 9 OpenCL Device Info Table Gate

Status: clean-room `CL_DEVICE_*` device-info readiness table. This is
close to the CTS device-info direction, but it is not Khronos CTS output,
not official OpenCL conformance, and not a product OpenCL driver claim.

## Claim Boundary

OpenCL CL_DEVICE_* device-info readiness table for a clean-room Celviz GPGPU proxy. Values are explicit support taxonomy entries and local proxy evidence, not Khronos CTS results, not official OpenCL conformance, not a product ICD, not a Vivante-compatible OpenCL stack, and not a claim that the device passes clGetDeviceInfo CTS.

## Inputs and Outputs

- Input proxy evidence: `artifacts/rank_01_vivante_3d_gpgpu_ip/demo/outputs/device_tiers.json`
- Input host/runtime evidence: `artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_host_api_shim_report.json`
- Output JSON: `artifacts/rank_01_vivante_3d_gpgpu_ip/opencl_conformance/opencl_device_info_table.json`

## Status Vocabulary

- `supported_proxy`: Local proxy evidence reports a deterministic value, but this is not an OpenCL conformance result.
- `reported_not_claimed`: A conservative query value is defined to avoid overclaiming optional functionality.
- `unsupported_optional`: The feature is optional or extension-scoped and is not advertised by the proxy.
- `unsupported_required_gap`: The query is important for CTS/device-info readiness but lacks enough implementation evidence.
- `not_applicable`: The query does not apply to the selected clean-room proxy scope.

## Query Categories

| Category | Count |
| --- | ---: |
| `atomics_svm` | 6 |
| `execution` | 4 |
| `extensions` | 2 |
| `fp_numeric` | 4 |
| `images` | 9 |
| `limits` | 7 |
| `memory` | 11 |
| `profile_version` | 9 |
| `queue` | 5 |

## Device Info Rows

| CL_DEVICE query | Category | Status | Reported value | Boundary |
| --- | --- | --- | --- | --- |
| `CL_DEVICE_TYPE` | `profile_version` | `supported_proxy` | `"CL_DEVICE_TYPE_GPU"` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_VENDOR_ID` | `profile_version` | `reported_not_claimed` | `0` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_NAME` | `profile_version` | `supported_proxy` | `"celviz-full-proxy"` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_VENDOR` | `profile_version` | `reported_not_claimed` | `"Celviz clean-room proxy"` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_PROFILE` | `profile_version` | `reported_not_claimed` | `"not_claimed"` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_VERSION` | `profile_version` | `reported_not_claimed` | `"OpenCL readiness taxonomy only"` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DRIVER_VERSION` | `profile_version` | `reported_not_claimed` | `"celviz-proxy-not-product-driver"` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_OPENCL_C_VERSION` | `profile_version` | `reported_not_claimed` | `"OpenCL C subset only"` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_EXTENSIONS` | `extensions` | `reported_not_claimed` | `""` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_EXTENSIONS_WITH_VERSION` | `extensions` | `reported_not_claimed` | `[]` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_NUMERIC_VERSION` | `profile_version` | `reported_not_claimed` | `0` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_MAX_COMPUTE_UNITS` | `limits` | `supported_proxy` | `16` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_MAX_WORK_ITEM_DIMENSIONS` | `limits` | `supported_proxy` | `3` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_MAX_WORK_GROUP_SIZE` | `limits` | `supported_proxy` | `256` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_MAX_WORK_ITEM_SIZES` | `limits` | `supported_proxy` | `[256, 256, 1]` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_MAX_CLOCK_FREQUENCY` | `limits` | `reported_not_claimed` | `0` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_ADDRESS_BITS` | `limits` | `supported_proxy` | `40` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_MAX_PARAMETER_SIZE` | `limits` | `supported_proxy` | `1024` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_MEM_BASE_ADDR_ALIGN` | `memory` | `supported_proxy` | `128` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_MIN_DATA_TYPE_ALIGN_SIZE` | `memory` | `supported_proxy` | `128` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_GLOBAL_MEM_SIZE` | `memory` | `supported_proxy` | `1073741824` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_MAX_MEM_ALLOC_SIZE` | `memory` | `supported_proxy` | `268435456` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_GLOBAL_MEM_CACHE_TYPE` | `memory` | `unsupported_required_gap` | `"CL_NONE"` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_GLOBAL_MEM_CACHELINE_SIZE` | `memory` | `reported_not_claimed` | `0` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_GLOBAL_MEM_CACHE_SIZE` | `memory` | `reported_not_claimed` | `0` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_LOCAL_MEM_TYPE` | `memory` | `reported_not_claimed` | `"CL_LOCAL"` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_LOCAL_MEM_SIZE` | `memory` | `supported_proxy` | `32768` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_ERROR_CORRECTION_SUPPORT` | `memory` | `reported_not_claimed` | `false` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_HOST_UNIFIED_MEMORY` | `memory` | `reported_not_claimed` | `false` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_IMAGE_SUPPORT` | `images` | `unsupported_optional` | `false` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_MAX_READ_IMAGE_ARGS` | `images` | `unsupported_optional` | `0` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_MAX_WRITE_IMAGE_ARGS` | `images` | `unsupported_optional` | `0` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_IMAGE2D_MAX_WIDTH` | `images` | `unsupported_optional` | `0` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_IMAGE2D_MAX_HEIGHT` | `images` | `unsupported_optional` | `0` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_IMAGE3D_MAX_WIDTH` | `images` | `unsupported_optional` | `0` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_IMAGE3D_MAX_HEIGHT` | `images` | `unsupported_optional` | `0` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_IMAGE3D_MAX_DEPTH` | `images` | `unsupported_optional` | `0` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_MAX_SAMPLERS` | `images` | `unsupported_optional` | `0` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_SINGLE_FP_CONFIG` | `fp_numeric` | `supported_proxy` | `["CL_FP_ROUND_TO_NEAREST"]` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_HALF_FP_CONFIG` | `fp_numeric` | `unsupported_optional` | `[]` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_DOUBLE_FP_CONFIG` | `fp_numeric` | `unsupported_optional` | `[]` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_ENDIAN_LITTLE` | `fp_numeric` | `supported_proxy` | `true` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_AVAILABLE` | `execution` | `supported_proxy` | `true` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_COMPILER_AVAILABLE` | `execution` | `reported_not_claimed` | `false` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_LINKER_AVAILABLE` | `execution` | `reported_not_claimed` | `false` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_EXECUTION_CAPABILITIES` | `execution` | `supported_proxy` | `["CL_EXEC_KERNEL"]` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_QUEUE_PROPERTIES` | `queue` | `supported_proxy` | `["CL_QUEUE_PROFILING_ENABLE"]` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_QUEUE_ON_HOST_PROPERTIES` | `queue` | `supported_proxy` | `["CL_QUEUE_PROFILING_ENABLE"]` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_QUEUE_ON_DEVICE_PROPERTIES` | `queue` | `unsupported_optional` | `[]` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_MAX_ON_DEVICE_QUEUES` | `queue` | `unsupported_optional` | `0` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_MAX_ON_DEVICE_EVENTS` | `queue` | `unsupported_optional` | `0` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_ATOMIC_MEMORY_CAPABILITIES` | `atomics_svm` | `unsupported_optional` | `[]` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_ATOMIC_FENCE_CAPABILITIES` | `atomics_svm` | `unsupported_optional` | `[]` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_SVM_CAPABILITIES` | `atomics_svm` | `unsupported_optional` | `[]` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_PREFERRED_PLATFORM_ATOMIC_ALIGNMENT` | `atomics_svm` | `reported_not_claimed` | `0` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_PREFERRED_GLOBAL_ATOMIC_ALIGNMENT` | `atomics_svm` | `reported_not_claimed` | `0` | device-info readiness only; not official OpenCL conformance or CTS pass |
| `CL_DEVICE_PREFERRED_LOCAL_ATOMIC_ALIGNMENT` | `atomics_svm` | `reported_not_claimed` | `0` | device-info readiness only; not official OpenCL conformance or CTS pass |

## Gate Shape

```json
{
  "id": "phase9_opencl_device_info_table",
  "stage": "phase-9 opencl device-info readiness",
  "command": "bash scripts/verify_celviz_gpgpu_opencl_device_info_table.sh",
  "required": false,
  "evidence": [
    "tools/celviz_gpgpu_ip/opencl_device_info_table.py",
    "docs/celviz-gpgpu-ip/PHASE9_OPENCL_DEVICE_INFO_TABLE.md",
    "artifacts/rank_01_vivante_3d_gpgpu_ip/opencl_conformance/opencl_device_info_table.json"
  ],
  "pass_condition": "The generated table classifies CL_DEVICE_* profile/version/extensions/limits/memory/image/atomics/SVM fields with support status, evidence, CTS orientation, and no-overclaim boundaries. Passing this gate does not claim official OpenCL conformance or CTS pass."
}
```
