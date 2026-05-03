# Phase 9 Memory Object Flags Gates

Status: memory object flags/map/unmap/sub-buffer readiness gate completed for clean-room proxy evidence.

Run:

```sh
bash scripts/verify_celviz_gpgpu_phase9_memory_object_flags.sh
```

Generated evidence:

- `artifacts/rank_01_vivante_3d_gpgpu_ip/verification/phase9_memory_object_flags_map_gate.json`
- `artifacts/rank_01_vivante_3d_gpgpu_ip/verification/phase9_memory_object_flags_completion_columns.json`

Boundary: Phase 9 clean-room memory-object flags/map/unmap/sub-buffer readiness gate; not official OpenCL conformance, not Khronos CTS, not a production ICD, not a stable UAPI, not proprietary Vivante compatibility, and not driver or silicon signoff.

## Summary

- Flags covered: `5`
- Operation gates: `3`
- Negative cases: `9`
- Official conformance claim: `false`

## Completion Columns

| Kind | Name | Readiness | Completion |
| --- | --- | --- | --- |
| `flag` | `CL_MEM_READ_WRITE` | `ready_proxy` | `complete_for_proxy_gate` |
| `flag` | `CL_MEM_READ_ONLY` | `ready_proxy` | `complete_for_proxy_gate` |
| `flag` | `CL_MEM_WRITE_ONLY` | `ready_proxy` | `complete_for_proxy_gate` |
| `flag` | `CL_MEM_COPY_HOST_PTR` | `ready_proxy` | `complete_for_proxy_gate` |
| `flag` | `CL_MEM_USE_HOST_PTR` | `ready_proxy` | `complete_for_proxy_gate` |
| `operation` | `map/unmap` | `ready_proxy` | `complete_for_proxy_gate` |
| `operation` | `sub-buffer` | `ready_proxy` | `complete_for_proxy_gate` |
| `operation` | `bounds negative tests` | `ready_proxy` | `complete_for_proxy_gate` |

## Checks

- `all_requested_flags_covered`: `true`
- `read_write_kernel_roundtrip`: `true`
- `read_only_copy_host_ptr_snapshot`: `true`
- `write_only_rejects_kernel_read`: `true`
- `use_host_ptr_alias_visible`: `true`
- `map_unmap_positive_and_negative`: `true`
- `sub_buffer_positive_and_negative`: `true`
- `bounds_negative_tests_present`: `true`
- `negative_cases_all_expected`: `true`
