# Active Target: Celviz GPGPU IP

## Current Active Target

The active target for this Ventus project is:

```text
Celviz GPGPU IP
```

This means current Rank 1 work is scoped to the public `Vivante 3D GPGPU IP`
blueprint and the local clean-room proxy package under:

```text
docs/celviz-gpgpu-ip/
artifacts/rank_01_vivante_3d_gpgpu_ip/
```

## Explicit Retargeting Decision

The active target is no longer `Celviz 3D GPU IP`.

Earlier Rank 12 `Celviz 3D GPU IP` files may remain in the repository as
historical or parallel work, but they are not the controlling target for this
Rank 1 package. New Rank 1 decisions, evidence, and acceptance gates should
refer to `Celviz GPGPU IP`.

Rank 12 is preserved for history, process reference, and comparison only.
Graphics-only evidence from Rank 12 must not be counted as active Rank 1 GPGPU
acceptance, even when it has useful style, artifact, or reporting patterns.

## Rank 1 Identity

| Field | Value |
| --- | --- |
| Rank | 1 |
| Local target name | Celviz GPGPU IP |
| Public IP anchor | Vivante 3D GPGPU IP |
| Track | T0 AI Compute |
| Stage path | S0-S5 |
| Source blueprint | `blueprints/03_Vivante3DGPGPUIP.md` |
| Source execution blueprint | `ip_execution/rank_01_vivante_3d_gpgpu_ip.md` |
| Local execution blueprint | `docs/celviz-gpgpu-ip/RANK01_VIVANTE_3D_GPGPU_IP_BLUEPRINT.md` |
| Active acceptance entrypoint | `./scripts/accept_celviz_gpgpu_ip.sh` |
| Artifact root | `artifacts/rank_01_vivante_3d_gpgpu_ip/` |

## Acceptance Routing

Active GPGPU acceptance routes through the Rank 1 artifact root, local
blueprint, and one-key entrypoint:

```text
docs/celviz-gpgpu-ip/RANK01_VIVANTE_3D_GPGPU_IP_BLUEPRINT.md
artifacts/rank_01_vivante_3d_gpgpu_ip/
./scripts/accept_celviz_gpgpu_ip.sh
```

Rank 12 graphics artifacts may be linked as superseded background, but they are
excluded from active GPGPU acceptance. They are not substitutes for Rank 1
compute, scheduler, memory, AXI, FP16/FP32, command, interrupt, or throughput
evidence.

## Control Rule

When a document, manifest, test, demo, or evidence row conflicts between
`Celviz GPGPU IP` and `Celviz 3D GPU IP`, Rank 1 GPGPU wording controls for the
paths in this package.

The correct terms are:

- `Celviz GPGPU IP` for the local clean-room target.
- `Vivante 3D GPGPU IP` for the public source anchor.
- `rank_01_vivante_3d_gpgpu_ip` for the artifact package.

Avoid using `Celviz 3D GPU IP` as the active target in Rank 1 files.
