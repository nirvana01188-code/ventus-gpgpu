# Phase 8 DRM-Like UAPI Contract

Status: `pass`

DRM-like contract draft only; not a production Linux kernel/DRM driver

```json
{
  "checks": [
    {
      "evidence": {
        "status": "pass"
      },
      "name": "driver_submission_proxy_pass",
      "pass": true
    },
    {
      "evidence": {
        "status": "pass"
      },
      "name": "linux_runtime_proxy_pass",
      "pass": true
    },
    {
      "evidence": {
        "object_count": 5
      },
      "name": "uapi_objects_mapped",
      "pass": true
    }
  ],
  "claim_boundary": "DRM-like contract draft only; not a production Linux kernel/DRM driver",
  "schema": "celviz.gpgpu.phase8.drm_uapi_contract.v1",
  "status": "pass",
  "uapi_objects": [
    {
      "kernel_missing": [
        "real /dev/dri node ownership",
        "ioctl number allocation",
        "capability query UAPI"
      ],
      "name": "device",
      "proxy_evidence": "linux_runtime_evidence device open/context lifecycle"
    },
    {
      "kernel_missing": [
        "GEM handle lifetime",
        "mmap offsets",
        "dma-buf import/export",
        "IOMMU integration"
      ],
      "name": "buffer_object",
      "proxy_evidence": "BO create/map/GPU VA semantics in userspace fixture"
    },
    {
      "kernel_missing": [
        "scheduler entity",
        "preemption policy",
        "hang recovery"
      ],
      "name": "queue",
      "proxy_evidence": "driver_submission queue lifecycle and no-pending closure"
    },
    {
      "kernel_missing": [
        "syncobj/timeline ABI",
        "poll/select wakeups",
        "cross-process sharing"
      ],
      "name": "fence_event",
      "proxy_evidence": "fence/event lifecycle and error paths"
    },
    {
      "kernel_missing": [
        "copy_from_user validation",
        "command parser hardening",
        "security review"
      ],
      "name": "command_submission",
      "proxy_evidence": "kernel dispatch alignment plus error-path proxy"
    }
  ]
}
```
