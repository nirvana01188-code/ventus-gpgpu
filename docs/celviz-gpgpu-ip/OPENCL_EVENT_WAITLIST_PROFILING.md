# OpenCL Event Wait-List And Profiling Gate

Status: executable proxy gate, not official OpenCL conformance.

This gate sits next to the clean-room OpenCL host API shim and validates the
event semantics that were previously called out as missing: event dependency
DAGs, wait-list validation, profiling timestamps, and failure propagation.

Run it with:

```sh
scripts/verify_celviz_gpgpu_opencl_event_waitlist_profiling.sh
```

The generated report is:

```text
artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_event_waitlist_profiling_report.json
```

## Modeled API Surface

- `clEnqueueWriteBuffer`
- `clEnqueueMarkerWithWaitList`
- `clEnqueueNDRangeKernel`
- `clEnqueueReadBuffer`
- `clWaitForEvents`
- `clGetEventProfilingInfo`

The model is deterministic and proxy-only.  It is not a Khronos ICD, not
`libOpenCL`, not CTS evidence, not official OpenCL conformance, not a production
Linux driver, and not proprietary Vivante compatibility.

## Gate Coverage

The gate builds a small in-order event DAG:

```text
write_a ┐
        ├─ marker_join ─ fault ─ propagated_failure
write_b ┘

write_a ┐
        ├─ kernel ─ readback
write_b ┘
```

For each modeled event it emits proxy profiling timestamps:

```text
queued <= submit <= start <= end
```

For successful dependencies, the dependent command's `submit` timestamp must be
greater than or equal to each completed wait event's `end` timestamp.

## Wait-List Validation

The executable gate rejects:

- Unknown event handles with `CL_INVALID_EVENT_WAIT_LIST`
- Duplicate event handles with `CL_INVALID_EVENT_WAIT_LIST`
- Events from a different context with `CL_INVALID_CONTEXT`

Rejected wait-lists do not allocate a new event and do not mutate the completed
DAG.

## Failure Propagation

The gate injects one proxy command failure and then enqueues a dependent command
that waits on the failed event.  The dependent command records:

```text
CL_EXEC_STATUS_ERROR_FOR_EVENTS_IN_WAIT_LIST
```

This gives the host API shim a concrete artifact for wait-list failure
propagation without claiming full OpenCL event semantics, callbacks, profiling
clock behavior, or out-of-order queue support.
