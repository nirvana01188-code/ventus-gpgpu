# S4 OpenCL-like Runtime Demo

Status: implemented.

This demo is the Rank 1 Celviz GPGPU IP S4 userspace runtime evidence.  The
runtime CLI is standard-library-only and reads `kernel_demo.json`, validates the
OpenCL-like kernel list, validates the selected tier, validates queue and buffer
binding metadata, probes the companion `compute_model.py`, and then emits
deterministic demo outputs when the compute model exists.

Scope: this is a clean-room OpenCL-like runtime proxy. It is intentionally
non-conformant and does not claim compatibility with proprietary Vivante command
streams, firmware, SDKs, drivers, or certification suites.

Run from the repository root:

```sh
python3 tools/celviz_gpgpu_ip/runtime_cli.py --kernel-demo artifacts/rank_01_vivante_3d_gpgpu_ip/demo/kernel_demo.json
```

List proxy devices and public tier metadata:

```sh
python3 tools/celviz_gpgpu_ip/runtime_cli.py --list-devices
```

Fallback result if the compute model worker has not landed yet:

- The command exits with status 0.
- `artifacts/rank_01_vivante_3d_gpgpu_ip/demo/run.log` is generated.
- `artifacts/rank_01_vivante_3d_gpgpu_ip/demo/outputs/status.json` records
  `status: pending`.

Expected implemented result:

- The command exits with status 0.
- The runtime validates four kernels: `vector_add`, `gemm_proxy`,
  `image_filter`, and `memory_copy`.
- The runtime validates `queue0`, buffer IDs, argument buffer binds, address
  spaces, and access modes.
- The runtime probes the compute model and writes per-kernel outputs under
  `artifacts/rank_01_vivante_3d_gpgpu_ip/demo/outputs/`.
- `outputs/device_tiers.json` lists proxy runtime devices and public reference
  tiers.
- `outputs/buffer_binds.json` records kernel argument to buffer metadata.
- `outputs/queue_trace.json` records `submit`, `wait`, and `readback` phases
  for each kernel with completion status.
- `outputs/kernel_metrics.json` records per-kernel estimated cycles and
  throughput from existing S1 compute-model metrics when available.
- `outputs/summary.json` reports `status: pass` when all deterministic kernel
  checks match.

The kernel demo is intentionally fixed to the S4 workload:

- `tier`: `micro`
- `language`: `opencl-c-subset`
- `queue`: `queue0`, in-order, profiling-enabled software proxy
- `kernels`: vector add, GEMM proxy, image filter, and memory copy
- `validation`: tier ordering, kernel name coverage, work sizes, local-size
  divisibility, argument list shape, address-space labels, queue IDs, buffer
  IDs, and access labels

The cycle and throughput figures are estimates derived from public/proxy tier
metadata and S1 compute-model operation/byte counts. They are not RTL timing,
driver behavior, silicon PPA, OpenCL conformance, or vendor compatibility
evidence.
