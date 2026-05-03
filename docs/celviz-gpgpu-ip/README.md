# Celviz GPGPU IP

This folder is the active Rank 1 work package for bringing the public
`Vivante 3D GPGPU IP` blueprint into the open-source `ventus-gpgpu` project as
`Celviz GPGPU IP`.

## Active Target

`Celviz GPGPU IP` is the current active target.

This package replaces the earlier local focus on `Celviz 3D GPU IP`. Rank 1 is
about GPGPU compute behavior: OpenCL-like kernels, shader-unit scaling,
command submission, DMA, scheduler behavior, memory movement, FP16/FP32 paths,
interrupts, AXI traffic, and measurable proxy integration evidence.

Rank 12 3D graphics work is preserved only as history and reference. Triangle,
texture, framebuffer, scanout, blit, and other graphics-only evidence must not
be routed into active GPGPU acceptance.

The active acceptance entrypoint is:

```text
./scripts/accept_celviz_gpgpu_ip.sh
```

That script and the local Rank 1 blueprint are the active routing references;
the superseded Rank 12 package is not an alternate acceptance path.

## Public Anchor

- IP: `Vivante 3D GPGPU IP`
- Rank: `1`
- Track: `T0 AI Compute`
- Source blueprint: `blueprints/03_Vivante3DGPGPUIP.md`
- Source execution blueprint:
  `/Users/nirvana/Desktop/codextest/verisilicon-ip-blueprints/ip_execution/rank_01_vivante_3d_gpgpu_ip.md`
- Local execution blueprint:
  `docs/celviz-gpgpu-ip/RANK01_VIVANTE_3D_GPGPU_IP_BLUEPRINT.md`
- Active acceptance entrypoint: `./scripts/accept_celviz_gpgpu_ip.sh`
- Artifact root: `artifacts/rank_01_vivante_3d_gpgpu_ip/`

The public facts used here are limited to the official public-product anchors:
CC8000/CC8X00 family positioning, OpenCL 1.1/1.2/3.0 and OpenCV support, public
shader-unit tiers, and public FP32/FP16 operations-per-cycle tiers.

## Clean-Room Boundary

This package is a public-information-derived proxy execution plan for Ventus
and Celviz work. It is not a VeriSilicon specification, Vivante RTL, vendor
firmware, SDK, compiler, conformance result, hard macro, or silicon signoff
package.

Any requirement that needs licensed vendor collateral must be marked
`blocked` or `unproven` until the actual collateral and evidence are available.

## Files

- `ACTIVE_TARGET.md`: single source of truth for the current active target.
- `RANK01_VIVANTE_3D_GPGPU_IP_BLUEPRINT.md`: local Rank 1 blueprint adapted for
  this repository.
- `CELVIZ_GPGPU_IP_EXECUTION.md`: S0-S5 execution plan for Celviz GPGPU IP.
- `../celviz-gpu-ip/SUPERSEDED_BY_GPGPU.md`: Rank 12 preservation notice; it is
  historical reference, not active acceptance scope.

## Stage Summary

| Stage | Purpose |
| --- | --- |
| S0 | Freeze public facts, clean-room scope, interfaces, workloads, and non-goals. |
| S1 | Build golden compute models for vector add, GEMM, convolution, image filter, and memory copy. |
| S2 | Implement command processor, DMA, scheduler, register map, and memory model skeletons. |
| S3 | Add FP16/FP32, command, interrupt, AXI, and throughput-scaling tests. |
| S4 | Provide an OpenCL-like CLI demo with inspectable outputs. |
| S5 | Record bandwidth, latency, power, reset, and interrupt evidence at proxy level. |

## Evidence Root

Execution evidence for this Rank 1 package lives under:

```text
artifacts/rank_01_vivante_3d_gpgpu_ip/
```

This package starts by defining S0 scope, acceptance criteria, and the
criteria-to-evidence map while preserving S1/S3/S4 artifacts that parallel
workers may add under the same root.
