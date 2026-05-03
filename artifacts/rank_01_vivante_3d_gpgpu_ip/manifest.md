# Manifest: Rank 1 Vivante 3D GPGPU IP

## Identity

| Field | Value |
| --- | --- |
| Rank | 1 |
| Public IP anchor | Vivante 3D GPGPU IP |
| Local active target | Celviz GPGPU IP |
| Track | T0 AI Compute |
| Stage path | S0-S5 |
| Repository | ventus-gpgpu |
| Documentation root | `docs/celviz-gpgpu-ip/` |
| Artifact root | `artifacts/rank_01_vivante_3d_gpgpu_ip/` |
| Source blueprint | `blueprints/03_Vivante3DGPGPUIP.md` |
| Source execution blueprint | `ip_execution/rank_01_vivante_3d_gpgpu_ip.md` |

## Active Target Statement

`Celviz GPGPU IP` is the active target for this Rank 1 package.

This manifest intentionally does not mark `Celviz 3D GPU IP` as active. Rank 12
graphics artifacts may coexist elsewhere in the repository for historical
reference only, but they do not provide active acceptance evidence and do not
control this Rank 1 GPGPU package.

Active acceptance evidence for this package must point to Rank 1 GPGPU artifact
paths or source implementation paths used by the Rank 1 clean-room proxy.

## Public Anchors

- CC8000/CC8X00 family.
- OpenCL 1.1/1.2/3.0 support in the public table.
- OpenCV support in the public table.
- Public shader-unit tiers from 16 to 2048 vec1-equivalent shader units.
- Public FP32/FP16 operations-per-cycle tiers from 32/64 to 4096/8192.

## Clean-Room Scope

Allowed proxy outputs:

- Public-scope documents.
- Golden compute models.
- Command processor, DMA, scheduler, register-map, and memory-model skeletons.
- FP16/FP32, command, interrupt, AXI, and throughput tests.
- OpenCL-like CLI demos.
- Bandwidth, latency, power, reset, and interrupt evidence at proxy level.

Excluded outputs:

- Proprietary VeriSilicon/Vivante RTL, firmware, SDK, compiler, driver, hard
  macro, conformance data, certification, and silicon signoff claims.

## Stage Evidence Index

| Stage | Status | Evidence |
| --- | --- | --- |
| S0 | seeded | `manifest.md`, `criteria_to_evidence.csv`, `spec/public_scope.md` |
| S1 | present for review | `model/README.md`, `model/run.log`, `model/metrics.json`, `model/outputs/` |
| S2 | present for review | `rtl/README.md`, `rtl/smoke.log`, `rtl/register_map.md`, `rtl/control_plane_config.json` |
| S3 | present for review | `verification/README.md`, `verification/test_commands.sh`, `verification/test_results.log`, `verification/coverage.md` |
| S4 | present for review | `demo/README.md`, `demo/kernel_demo.json`, `demo/run.log`, `demo/outputs/` |
| S5 | unproven | expected under `integration/` |

## Standard Validation Command

The upstream execution blueprint names:

```sh
make verify-t0
```

or:

```sh
./verification/run_t0.sh
```

These commands are target validation anchors. They are not complete package
evidence until implemented and captured in logs for this package.
