# Public Scope: Celviz GPGPU IP

## Scope Statement

This file freezes the public-information-derived S0 scope for Rank 1
`Celviz GPGPU IP`, anchored to public `Vivante 3D GPGPU IP` information.

The purpose is to guide clean-room Ventus/Celviz proxy work. This file is not a
VeriSilicon or Vivante specification and does not grant or imply access to
proprietary implementation details.

## Active Target

The active local target is:

```text
Celviz GPGPU IP
```

The active public anchor is:

```text
Vivante 3D GPGPU IP
```

The active artifact package is:

```text
artifacts/rank_01_vivante_3d_gpgpu_ip/
```

`Celviz 3D GPU IP` is not the active target for this Rank 1 package.

## Boundary To Historical Graphics Work

Historical graphics-only material from the earlier Rank 12 package is reference
context only. It must not be cited as active evidence for Rank 1 GPGPU
acceptance, and it cannot satisfy any S0-S5 criterion in this package.

Active acceptance evidence must be rooted in this Rank 1 GPGPU artifact package
or in source implementation paths used by the Rank 1 clean-room proxy.

## Public Facts Captured

- The public product family is described as CC8000/CC8X00.
- The public table lists OpenCL 1.1/1.2/3.0 support.
- The public table lists OpenCV support.
- The public table lists shader-unit tiers from 16 to 2048 vec1-equivalent
  shader units.
- The public table lists FP32/FP16 operations-per-cycle tiers from 32/64 to
  4096/8192.
- Public positioning describes scalable GPGPU compute across low-power
  embedded devices through high-performance servers.

## Clean-Room Proxy Interfaces

The proxy integration may define and test:

- Host command front end.
- Command processor.
- DMA.
- Scheduler.
- Register map.
- Memory model.
- AXI-like memory traffic.
- APB/AHB-like control plane.
- Interrupt signaling.
- Clock, reset, and power assumptions.
- OpenCL-like CLI runtime surface.

These interfaces are local proxy abstractions for Ventus/Celviz work. They are
not claims about the proprietary vendor implementation.

## S0-S5 Workloads And Evidence

| Stage | Required scope |
| --- | --- |
| S0 | Freeze public facts, active target, clean-room proxy scope, interfaces, workloads, and non-goals. |
| S1 | Model vector add, GEMM, convolution, image filter, and memory copy. |
| S2 | Build command processor, DMA, scheduler, register map, and memory model skeletons. |
| S3 | Test FP16, FP32, command submission, interrupts, AXI traffic, and throughput scaling. |
| S4 | Demonstrate an OpenCL-like CLI flow with kernel selection, command dispatch, and result readback. |
| S5 | Record bandwidth, latency, power, reset, and interrupt evidence at proxy level. |

## Non-Goals And Blocked Claims

The Rank 1 proxy package must not claim:

- Proprietary VeriSilicon/Vivante RTL equivalence.
- Vendor firmware, SDK, compiler, or driver compatibility.
- Official OpenCL, OpenCV, AXI, security, safety, or standards conformance.
- Silicon PPA, STA, DFT, CDC/RDC, low-power, ISO 26262, or tapeout signoff.
- Any hidden public-table interpretation beyond the captured public facts.

If future work needs licensed vendor collateral, the relevant
`criteria_to_evidence.csv` row must be marked `blocked` until the actual
collateral and review evidence are present.

## Acceptance Baseline

S0 is considered seeded when the manifest, criteria map, active target, and
public scope documents exist and consistently name `Celviz GPGPU IP` as the
active target.

S1-S5 are not complete until their implementation artifacts, commands, logs,
metrics, and review notes exist and are mapped in `criteria_to_evidence.csv`.
