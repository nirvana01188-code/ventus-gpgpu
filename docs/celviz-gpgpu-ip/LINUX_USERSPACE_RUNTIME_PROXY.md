# Linux Userspace Runtime Proxy

Status: first-stage driver and system integration proxy.

This stage models the userspace side of a Linux GPU runtime and a DRM-like
submission proxy for the Celviz GPGPU IP target. It is intentionally a
clean-room non-driver boundary. The evidence demonstrates expected OS-facing
semantics, but it does not implement or claim a Linux kernel DRM driver, kernel
ioctl ABI, GEM object ABI, firmware ABI, upstream kernel support, or proprietary
Vivante compatibility.

## Modeled Path

The focused proxy covers:

- render-device open using a modeled `/dev/dri/renderD128` node
- context creation
- buffer object allocation
- CPU map and GPU virtual-address map
- queue creation
- DRM-like submit descriptor handoff
- output fence creation, signal, and wait
- eventfd/epoll-style readable event polling
- successful completion path
- permission/error completion path

The submit operation records a mock ioctl name:

```text
DRM_IOCTL_CELVIZ_GPGPU_SUBMIT_PROXY
```

That name is evidence vocabulary only. It is not a kernel UAPI definition.

## Files

Tooling:

```text
tools/celviz_gpgpu_ip/linux_runtime_proxy.py
tools/celviz_gpgpu_ip/verify_linux_runtime_proxy.py
```

Generated evidence:

```text
artifacts/rank_01_vivante_3d_gpgpu_ip/os_runtime/linux_runtime_fixture.json
artifacts/rank_01_vivante_3d_gpgpu_ip/os_runtime/linux_runtime_evidence.json
artifacts/rank_01_vivante_3d_gpgpu_ip/os_runtime/linux_runtime_check.log
```

## Focused Verification

From the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/celviz_gpgpu_ip/verify_linux_runtime_proxy.py
```

Expected result:

```text
celviz_gpgpu_linux_runtime_proxy_verify: pass
```

The verifier checks that evidence includes device/context open, BO alloc/map,
GPU VA mapping, submit completion, fence wait/signal, event polling, completion
error handling, retired queues with no pending work, and the explicit
non-driver boundary marker.
