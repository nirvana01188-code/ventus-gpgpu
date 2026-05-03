# Runtime Queue Demo

Status: implemented for S4 runtime/demo evidence.

This document describes the OpenCL-like command queue path added for the active
Rank 1 Celviz GPGPU IP target. The target is GPGPU compute, not 3D graphics.
Celviz is used as the architecture decomposition methodology; the implementation
lives in the Ventus GPGPU repository.

## Scope Boundary

The runtime queue demo is clean-room and intentionally non-conformant. It does
not implement or claim:

- OpenCL conformance.
- Vivante command-stream compatibility.
- Proprietary firmware, SDK, compiler, driver, or ABI compatibility.
- RTL timing, silicon PPA, tapeout readiness, or certification evidence.
- 3D graphics pipeline behavior such as raster, texture, framebuffer, display,
  or scanout.

## Proxy Devices

The CLI can list proxy devices:

```sh
python3 tools/celviz_gpgpu_ip/runtime_cli.py --list-devices
```

The current S4 demo selects `celviz-micro-proxy`, mapped to the public
`CC8000`-class metadata surface. The device table records runtime tier,
public-reference tier, vec1 shader-unit count, FP32/FP16 ops-per-cycle metadata,
queue count, and address width. These are public/proxy capability rows, not
measured local RTL performance.

## Queue And Buffer Model

`kernel_demo.json` now declares:

- `queues`: command queues with stable IDs, device binding, properties, and
  software-proxy mode.
- `buffers`: host-visible global buffers with size, access mode, and binding
  metadata.
- `kernels[*].queue_id`: the queue used for each dispatch.
- `kernels[*].args[*].buffer_id`: buffer binding metadata for global arguments.

The active demo uses one in-order profiling queue:

```text
queue0 -> celviz-micro-proxy
```

Each kernel emits three queue phases:

```text
submit -> wait -> readback
```

The phase trace is generated in:

```text
artifacts/rank_01_vivante_3d_gpgpu_ip/demo/outputs/queue_trace.json
```

The buffer binding summary is generated in:

```text
artifacts/rank_01_vivante_3d_gpgpu_ip/demo/outputs/buffer_binds.json
```

## Per-Kernel Metrics

The runtime probes the S1 compute golden model and reads its `metrics.json` when
available. For each S4 kernel, it records:

- command queue ID
- work-item count
- work-group count
- FP32 operation count from the S1 model where a matching workload exists
- bytes read, written, and touched from the S1 model where available
- estimated compute cycles from public/proxy FP32 ops-per-cycle metadata
- estimated memory cycles from a simple software proxy bandwidth rule
- estimated cycles as the larger compute/memory proxy count
- estimated FP32 ops/cycle and bytes/cycle

The `image_filter` runtime kernel maps to the S1 `convolution_proxy` workload
for metrics. The `memory_copy` runtime kernel has zero FP32 ops and is estimated
from byte traffic only.

Metrics are generated in:

```text
artifacts/rank_01_vivante_3d_gpgpu_ip/demo/outputs/kernel_metrics.json
```

These numbers are scheduling and throughput-planning evidence only. They are
not RTL timing results and should not be used as silicon performance claims.

## Run

From the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/celviz_gpgpu_ip/runtime_cli.py --kernel-demo artifacts/rank_01_vivante_3d_gpgpu_ip/demo/kernel_demo.json
```

Expected high-level result:

```text
status=pass
completion_status=complete
phase_model=submit,wait,readback
```

Generated runtime evidence:

- `demo/run.log`
- `demo/outputs/status.json`
- `demo/outputs/summary.json`
- `demo/outputs/device_tiers.json`
- `demo/outputs/buffer_binds.json`
- `demo/outputs/queue_trace.json`
- `demo/outputs/kernel_metrics.json`
- deterministic per-kernel readback files for vector add, GEMM proxy, image
  filter, and memory copy
