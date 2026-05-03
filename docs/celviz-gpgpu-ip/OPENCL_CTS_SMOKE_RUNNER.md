# OpenCL CTS Smoke Runner

Generated: `2026-05-03T06:13:05+00:00`

Status: `pass`

This is a CTS-oriented smoke manifest. It does not run Khronos OpenCL CTS and does not claim official OpenCL conformance.

- `khronos_cts_executed`: `False`
- `official_cts_pass`: `False`
- `official_opencl_conformance_claimed`: `False`

## Scope

CTS-oriented smoke manifest only; this runner does not execute Khronos OpenCL CTS, does not produce official OpenCL conformance evidence, does not claim a production ICD/runtime, and does not claim Vivante-compatible compiler, firmware, SDK, or command-stream behavior.

## Smoke Items

| ID | Category | Pass | Gate Binding | Evidence |
| --- | --- | --- | --- | --- |
| `cts_smoke_device_info` | `device_info` | `True` | verify_celviz_gpgpu_opencl_device_info_table.sh / opencl_device_info_table.py | `artifacts/rank_01_vivante_3d_gpgpu_ip/opencl_conformance/opencl_device_info_table.json` (pass) |
| `cts_smoke_build_errors` | `build_errors` | `True` | verify_celviz_gpgpu_opencl_build_error_code_matrix.sh / opencl_build_error_code_matrix.py | `artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_build_error_code_matrix.json` (pass) |
| `cts_smoke_buffer_flags` | `buffer_flags` | `True` | verify_celviz_gpgpu_phase9_memory_object_flags.sh / phase9_memory_object_flags_gate.py | `artifacts/rank_01_vivante_3d_gpgpu_ip/verification/phase9_memory_object_flags_map_gate.json` (pass) |
| `cts_smoke_events` | `events` | `True` | verify_celviz_gpgpu_opencl_event_waitlist_profiling.sh / opencl_event_waitlist_profiling_gate.py | `artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_event_waitlist_profiling_report.json` (pass) |
| `cts_smoke_queue` | `queue` | `True` | verify_celviz_gpgpu_runtime_queue_semantics.sh / runtime_queue_semantics_gate.py | `artifacts/rank_01_vivante_3d_gpgpu_ip/verification/runtime_queue_semantics_gate.json` (pass) |
| `cts_smoke_four_kernels` | `kernels` | `True` | verify_celviz_gpgpu_opencl_host_api_shim.sh, verify_celviz_gpgpu_microop_execution.sh, opencl_subset.py | `artifacts/rank_01_vivante_3d_gpgpu_ip/demo/opencl_subset/opencl_subset_evidence.json` (pass)<br>`artifacts/rank_01_vivante_3d_gpgpu_ip/microop_execution/microop_execution_report.json` (pass) |

## Kernel Smoke

| Kernel | Pass | Global Size | Local Size | Precision |
| --- | --- | --- | --- | --- |
| `vector_add` | `True` | `[1024, 1, 1]` | `[64, 1, 1]` | `fp32` |
| `gemm` | `True` | `[64, 64, 1]` | `[16, 16, 1]` | `fp32` |
| `conv2d` | `True` | `[128, 128, 1]` | `[16, 16, 1]` | `fp32` |
| `image_filter` | `True` | `[256, 128, 1]` | `[16, 16, 1]` | `fp32` |

## Command

```sh
bash scripts/verify_celviz_gpgpu_opencl_cts_smoke.sh
```

Generated JSON:

`artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_cts_smoke_runner.json`
