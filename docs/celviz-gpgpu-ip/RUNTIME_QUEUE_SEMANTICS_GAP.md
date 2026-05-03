# Runtime Queue Semantics Gate

Generated: `2026-05-03T05:51:17+00:00`

Status: `pass`

This focused gate extends the runtime queue semantics evidence. It records the current in-order queue behavior, explicit unsupported out-of-order rejection, and the remaining barrier/marker/user-event/callback/profiling/wait-list gaps.

It is clean-room proxy evidence only. It does not claim official OpenCL conformance, a production ICD/runtime, a Linux kernel DRM driver, GEM/syncobj ABI compatibility, or proprietary Vivante compatibility.

## Summary

- `queue_count`: `1`
- `kernel_dispatches`: `4`
- `queue_ids`: `[0]`
- `linux_fence_waits`: `2`
- `linux_events_readable`: `4`
- `unsupported_rejections`: `1`
- `gap_rows`: `4`
- `semantics_rows`: `4`

## Semantics Rows

| ID | Status | Evidence | Gap |
| --- | --- | --- | --- |
| `in_order_queue` | `covered` | queue_count=1; queue_ids=[0]; ordered_sequences=True; driver_pending=0 | multi-queue in-order ordering is not covered; cross-queue dependencies require future wait-list or timeline semantics |
| `unsupported_out_of_order_rejection` | `rejected` | reject_out_of_order_queue test row has ENOTSUP | out-of-order scheduling, dependency graph execution, and command reordering are not implemented |
| `barrier_marker_user_event_gap` | `gap_recorded` | reject_marker_barrier_user_event test row has ENOTSUP | OpenCL marker objects are not modeled; OpenCL barrier wait-list semantics are not modeled; OpenCL user-created events are not modeled |
| `callbacks_profiling_wait_list_gap` | `gap_recorded` | reject_callback_registration test row has ENOTSUP; reject_profiling_timestamps test row has ENOTSUP; reject_event_wait_list_dependency test row has ENOTSUP | event callbacks are not implemented; profiling timestamps are not productized; explicit wait-list dependencies are not implemented |

## Executable Checks

- `runtime_commands_schema`: `pass`
- `opencl_subset_evidence_pass`: `pass`
- `linux_runtime_evidence_pass`: `pass`
- `driver_submission_evidence_pass`: `pass`
- `phase9_driver_os_input_pass`: `pass`
- `in_order_single_queue_sequences`: `pass`
- `linux_events_and_fences_observed`: `pass`
- `out_of_order_rejection_present`: `pass`
- `barrier_marker_user_event_gap_present`: `pass`
- `callbacks_profiling_wait_list_gap_present`: `pass`
- `opencl_gap_map_pass`: `pass`
- `clean_room_no_conformance_claim`: `pass`

## Command

```sh
bash scripts/verify_celviz_gpgpu_runtime_queue_semantics.sh
```

Generated JSON:

`artifacts/rank_01_vivante_3d_gpgpu_ip/verification/runtime_queue_semantics_gate.json`
