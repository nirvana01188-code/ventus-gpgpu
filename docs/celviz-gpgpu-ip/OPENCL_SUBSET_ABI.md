# Celviz GPGPU IP OpenCL Subset ABI

Status: first-stage clean-room subset evidence.

This document describes the first-stage OpenCL-like compiler/runtime ABI
evidence added under `tools/celviz_gpgpu_ip/opencl_subset.py`.  The scope is
deliberately narrow: it parses a constrained OpenCL C source subset, emits
kernel ABI metadata, and connects that metadata to the existing Celviz runtime
command JSON proxy.  It is not OpenCL 3.0 conformance, SPIR-V support, a Vivante
compiler, a proprietary command stream, SDK, firmware, or driver ABI.

## Tool Entry Points

Run the built-in evidence demo:

```sh
python3 tools/celviz_gpgpu_ip/opencl_subset.py \
  --output-dir artifacts/rank_01_vivante_3d_gpgpu_ip/demo/opencl_subset \
  demo
```

Compile only the built-in subset kernels and runtime command JSON:

```sh
python3 tools/celviz_gpgpu_ip/opencl_subset.py \
  --output-dir artifacts/rank_01_vivante_3d_gpgpu_ip/demo/opencl_subset \
  compile-builtins
```

Verify a generated evidence file:

```sh
python3 tools/celviz_gpgpu_ip/opencl_subset.py \
  --output-dir artifacts/rank_01_vivante_3d_gpgpu_ip/demo/opencl_subset \
  verify
```

Compile a single exploratory `.cl` file with inferred placeholder buffers:

```sh
python3 tools/celviz_gpgpu_ip/opencl_subset.py \
  --output-dir artifacts/rank_01_vivante_3d_gpgpu_ip/demo/opencl_subset/single \
  compile path/to/kernel.cl --global-size 64 1 1 --local-size 64 1 1
```

Single-source mode is for parser smoke tests.  The built-in demo is the focused
ABI evidence path because it carries explicit buffer addresses, sizes, launch
geometry, scalar values, and precision metadata.

## Covered Kernels

| Workload | Kernel name | Launch | Local size | Precision | Notes |
| --- | --- | ---: | ---: | --- | --- |
| Vector add | `vector_add` | `1024 x 1 x 1` | `64 x 1 x 1` | FP32 | Three global float buffers plus `uint n`. |
| GEMM | `gemm` | `64 x 64 x 1` | `16 x 16 x 1` | FP32 | Direct matrix multiply, global buffers plus `m/n/k`. |
| Convolution | `conv2d` | `128 x 128 x 1` | `16 x 16 x 1` | FP32 | Direct 3x3 buffer convolution. |
| Image filter | `image_filter` | `256 x 128 x 1` | `16 x 16 x 1` | FP32 | RGBA buffer math using `uchar4`; no OpenCL image objects or samplers. |

The request's `conv` target is represented as `conv2d` in the generated ABI to
make the 2D direct-convolution shape explicit.

## Generated Artifacts

The demo writes:

| Path | Purpose |
| --- | --- |
| `artifacts/rank_01_vivante_3d_gpgpu_ip/demo/opencl_subset/src/*.cl` | Clean-room subset source fixtures. |
| `artifacts/rank_01_vivante_3d_gpgpu_ip/demo/opencl_subset/abi/*.kernel_abi.json` | Per-kernel ABI metadata. |
| `artifacts/rank_01_vivante_3d_gpgpu_ip/demo/opencl_subset/runtime_commands.json` | Runtime command ABI JSON with one `kernel_dispatch` per kernel. |
| `artifacts/rank_01_vivante_3d_gpgpu_ip/demo/opencl_subset/runtime_proxy/runtime_status.json` | Existing runtime proxy status evidence. |
| `artifacts/rank_01_vivante_3d_gpgpu_ip/demo/opencl_subset/runtime_proxy/runtime_metrics.json` | Existing runtime proxy metrics evidence. |
| `artifacts/rank_01_vivante_3d_gpgpu_ip/demo/opencl_subset/opencl_subset_evidence.json` | Summary checks and links for this first-stage subset. |
| `artifacts/rank_01_vivante_3d_gpgpu_ip/demo/opencl_subset/opencl_subset_check.log` | Human-readable pass/fail log. |

## Kernel ABI Metadata

Each `*.kernel_abi.json` file uses
`schema = celviz.gpgpu.opencl_subset.kernel_abi.v1` and includes:

- Kernel identity: `name`, `kernel_id`, `source_sha256`, and clean-room scope.
- Argument ABI: `args[]` records with `name`, scalar/vector type, pointer flag,
  OpenCL address space, access mode, size, and ABI offset.
- Memory ABI: `buffers[]`, `metadata.buffer_base`, `metadata.buffer_size`, and
  `metadata.buffer_allocsize`.
- Launch ABI: `global_size`, `local_size`, `workgroup_count`, `work_items`,
  `metadata.kernel_size`, `metadata.wf_size`, and `metadata.wg_size`.
- Resource hints: `metadata.ldsSize`, `metadata.pdsSize`, `metadata.sgprUsage`,
  and `metadata.vgprUsage`.
- Precision: `precision` and `required_fp_mode`, currently FP32 for the built-in
  workload set.

The emitted `metadata` object is shaped for `runtime_proxy.normalize_metadata_record`
and is embedded directly into each runtime `kernel_dispatch` command as
`ventus_metadata`.

## Runtime Command ABI Link

`runtime_commands.json` uses `schema = celviz.gpgpu.runtime_commands.v1`.  The
demo emits one command per kernel:

- `opcode = kernel_dispatch`
- `grid = global_size`
- `local = local_size`
- `arg_buffer = metadata.metaDataBaseAddr`
- `arg_bytes = arg_size_bytes`
- `required_fp_mode = precision`
- `ventus_metadata = metadata`

The `demo` subcommand then calls `runtime_proxy.run_to_files(..., dry_run=True)`.
That validates the command ABI through the existing control-plane/runtime proxy
without requiring a compiled rtlsim shared library.

## Supported Source Subset

The parser accepts one kernel per source file with this shape:

```c
__kernel void name(args...) {
  ...
}
```

Supported argument forms:

- `__global`, `__local`, `__constant`, and implicit `__private` scalar values.
- Pointer arguments with an explicit address space.
- Scalar types `char`, `uchar`, `short`, `ushort`, `int`, `uint`, `long`,
  `ulong`, `half`, and `float`.
- Vector widths `2`, `3`, `4`, `8`, and `16`, such as `uchar4` or `float4`.

Supported built-ins are limited to:

- `get_global_id`
- `get_local_id`
- `get_group_id`
- `get_global_size`
- `get_local_size`
- `barrier`

The compiler checks launch geometry divisibility, local workgroup size at or
below 256 work-items, pointer buffer metadata, scalar metadata, address-space
declarations, argument ABI offsets, and runtime command schema linkage.

## Non-Conformant Boundaries

This first stage deliberately rejects or does not implement:

- OpenCL 3.0 conformance, ICD behavior, command queues, contexts, program
  objects, build options, or official CTS coverage.
- SPIR-V, LLVM IR, binary code generation, optimization, linking, or device ISA
  emission.
- OpenCL image objects, samplers, pipes, device-side enqueue, events, printf,
  subgroup built-ins, workgroup reductions, generic atomics, or double
  precision.
- Vendor command streams, Vivante firmware interfaces, proprietary drivers,
  SDK ABI, kernel binaries, or performance claims.
- Full C preprocessing, include handling, macro expansion, multiple kernels per
  file, arbitrary function calls, or arbitrary pointer alias analysis.

The intended evidence claim is therefore narrow: the repository now has a
deterministic clean-room path from four representative OpenCL-like subset
kernels to kernel ABI metadata and runtime command ABI JSON, with a focused
verification command.
