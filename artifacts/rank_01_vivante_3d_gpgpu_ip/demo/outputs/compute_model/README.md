# S1 Compute Golden Model Evidence

Status: implemented.

This directory contains the standard-library-only S1 compute golden model for
Rank 1 Vivante 3D GPGPU IP / Celviz GPGPU IP. The evidence is compute-oriented:
vector add, GEMM proxy, convolution/image-filter proxy, u8 image filtering, and
memory copy. It intentionally does not model a 3D graphics workload.

The model is a clean-room software oracle built inside the Ventus GPGPU
repository. It does not import or claim equivalence to proprietary Vivante RTL,
firmware, SDK, compiler, driver, command stream, or conformance behavior.

## Run

From the repository root:

```sh
python3 tools/celviz_gpgpu_ip/compute_model.py
```

Optional metrics dump:

```sh
python3 tools/celviz_gpgpu_ip/compute_model.py --print-metrics
```

The default artifact root is:

```text
artifacts/rank_01_vivante_3d_gpgpu_ip/model
```

## Fixed Workloads

- `vector_add`: deterministic FP32 elementwise add over 32 elements.
- `gemm_proxy`: deterministic FP32 4x6 by 6x5 matrix multiply.
- `convolution_proxy`: deterministic FP32 3x3 image-filter proxy over a 7x7
  single-channel image, producing a 5x5 output.
- `image_filter`: deterministic executable 8x8 u8 3x3 box-filter workload.
- `memory_copy`: deterministic byte copy and SHA-256 equality check.

The FP32 path uses Python floats rounded through IEEE-754 binary32 storage at
each modeled arithmetic step. FP16 evidence is now executed as a conservative
proxy for `vector_add`, `gemm_proxy`, and `convolution_proxy`: operands,
multiply results, additions, and final outputs are rounded through
standard-library IEEE-754 binary16 storage at each modeled FP16 operation. None
of these paths claims a Vivante ISA, compiler, driver, firmware, RTL,
exception, denormal, timing, or conformance model.

## Public Shader-Unit Scaling Table

Source: VeriSilicon Vivante 3D GPGPU IP public product table,
`https://www.verisilicon.com/cn/IPPortfolio/Vivante3DGPGPUIP`.

| Tier | Public shader units, vec1 equivalent | FP32 ops/cycle | FP16 ops/cycle |
| --- | ---: | ---: | ---: |
| CC8000L | 16 | 32 | 64 |
| CC8000 | 32 | 64 | 128 |
| CC8200 | 128 | 128 | 256 |
| CC8400 | 256 | 512 | 1024 |
| CC8400-MP2 | 512 | 1024 | 2048 |
| CC8400-MP4 | 1024 | 2048 | 4096 |
| CC8800 | 512 | 1024 | 2048 |
| CC8800-MP2 | 1024 | 2048 | 4096 |
| CC8800-MP4 | 2048 | 4096 | 8192 |

These rows are public capability metadata, not measured local RTL performance.

## Generated Evidence

Running the command writes:

- `run.log`: command trace, workload pass/fail summary, output locations, and
  pass status.
- `metrics.json`: public tier table, FP32/FP16 proxy notes, workload metrics,
  operation counts, byte traffic, hashes, and pass status.
- `outputs/vector_add.json`: vector inputs/outputs and checksum.
- `outputs/gemm_proxy.json`: matrix inputs/outputs and checksum.
- `outputs/convolution_proxy.json`: image-filter proxy output and checksum.
- `outputs/image_filter.json`: u8 box-filter output and checksum.
- `outputs/memory_copy.json`: memory copy bytes and source/destination hashes.
- `outputs/simt_execution.json`: clean-room SIMT execution evidence with
  wavefront scheduling, register-file reads/writes, ALU ops, LSU ops,
  scoreboard hazards, and barrier events for vector add, GEMM, convolution,
  and image filter.
- `outputs/shader_unit_scaling.json`: public tier metadata table.
- `outputs/hashes.txt`: SHA-256 hashes for generated JSON evidence files.

## Scope Notes

This is S1 acceptance evidence for a Celviz GPGPU IP compute proxy using the
Ventus GPGPU repository as the implementation frame. Celviz remains the tooling
namespace; this repository does not vendor Celviz or proprietary vendor
collateral. Clean-room scope: public-information-derived compute proxy; no proprietary Vivante RTL, firmware, SDK, compiler, driver, command-stream, or conformance claim.
