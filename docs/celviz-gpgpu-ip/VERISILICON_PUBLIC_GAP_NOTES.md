# Celviz GPGPU vs Public VeriSilicon/Vivante GPU IP Gap Notes

This note is based only on public-facing product information and local Celviz evidence. It does not claim proprietary Vivante compatibility.

## Public target signals

Public VeriSilicon/Vivante GPU IP materials describe product GPU IP families with OpenCL/OpenCV/GPGPU positioning, scalable shader-unit tiers, multi-OS software stacks, and production integration support.

## Current Celviz state

Celviz is a clean-room Ventus-based GPGPU IP prototype with:

- SIMT/RTL debug fabric and runtime proxy evidence.
- OpenCL-like C subset for vector_add, GEMM, conv2d, and image_filter.
- Compiler IR, kernel lowering, micro-op execution, and memory traces.
- Linux userspace/DRM-like submission proxy.
- Phase9 conformance-readiness gates.
- Functional/acceptance coverage at 446/446 after the OpenCL host API shim.

## Remaining gaps against a product GPU IP stack

- Official OpenCL conformance: not run or passed; CTS package/harness/product submission remains future work.
- Production ICD/runtime: this change adds an executable host API shim, but not a Khronos ICD loader integration or libOpenCL implementation.
- Full OpenCL C/runtime semantics: images, samplers, atomics, SVM, pipes, device-side enqueue, full math precision, callbacks, profiling, out-of-order queues, and full device info remain incomplete or absent.
- Production Linux driver: current path is userspace/DRM-like proxy, not a kernel DRM/GEM/syncobj driver.
- RTL structural closure: functional acceptance is 100%, but Verilator structural line/branch/toggle closure is not 100%.
- Product signoff: target-library synthesis, STA, power, DFT, physical implementation, and silicon signoff remain blocked.
- Performance proof: Phase7 numbers are proxy evidence, not cycle-accurate/silicon PPA.

## Newly closed gap in this step

The OpenCL host API path moved from a contract-only artifact to an executable lifecycle shim:

- Platform/device query.
- Context and in-order queue creation.
- Buffer allocation and write/read events.
- Program source, build, kernel lookup, kernel argument binding.
- NDRange dispatch through existing runtime proxy.
- Event wait, finish, and release lifecycle.
- Negative OpenCL-style error-code cases.

Boundary: this is still conformance-readiness, not official conformance.
