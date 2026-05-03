# Phase9 OpenCL Conformance Readiness

This phase pushes Celviz GPGPU IP toward the official OpenCL conformance path without claiming Khronos CTS pass.

## Claim Boundary

Phase-9 OpenCL conformance-readiness for a clean-room Ventus-based Celviz GPGPU IP proxy. This is CTS-oriented gap and local readiness evidence only: not Khronos CTS, not official OpenCL conformance, not a product ICD, not a production Linux kernel/DRM driver, not RTL structural coverage 100%, and not synthesis/STA/power/DFT/physical/silicon signoff.

## Official Anchors

- Khronos OpenCL Registry: https://registry.khronos.org/OpenCL/ (authoritative OpenCL API/C/extension specification index)
- OpenCL 3.0 unified API specification: https://registry.khronos.org/OpenCL/specs/3.0-unified/html/OpenCL_API.html (platform, execution, memory, synchronization, host API, and device query semantics)
- OpenCL 3.0 unified C specification: https://registry.khronos.org/OpenCL/specs/3.0-unified/html/OpenCL_C.html (OpenCL C language, address spaces, types, builtins, atomics, and barriers)
- Khronos OpenCL-CTS: https://github.com/KhronosGroup/OpenCL-CTS (official open-source conformance test suite repository)
- Khronos conformant products/adopters: https://www.khronos.org/conformance/adopters/conformant-products/opencl (public adopter/product conformance publication path)

## Readiness Matrix

### platform_device_info
- Status: partial
- Evidence: artifacts/rank_01_vivante_3d_gpgpu_ip/demo/outputs/device_tiers.json, artifacts/rank_01_vivante_3d_gpgpu_ip/demo/outputs/kernel_metrics.json
- Blocker: OpenCL 3.0 profile/version/extensions/device-info tables and optional-feature queries are incomplete.
- Next executable test: Generate device-info golden table and reject unsupported CL_DEVICE_* queries deterministically.
- CTS orientation: api/test_cl_get_device_info style coverage

### context_queue_program_kernel_mem_api
- Status: partial
- Evidence: artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_icd_runtime_contract.json
- Blocker: No stable ICD handles, reference counts, object ownership, or complete OpenCL error-code mapping.
- Next executable test: Run host API lifecycle contract tests for context/queue/buffer/program/kernel/event create/release.
- CTS orientation: api object lifecycle CTS groups

### opencl_c_language_subset
- Status: partial
- Evidence: artifacts/rank_01_vivante_3d_gpgpu_ip/demo/opencl_subset/opencl_subset_evidence.json, artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_subset_conformance_tests.json
- Blocker: The compiler accepts a first-stage subset only: one kernel per source and limited grammar/types/builtins.
- Next executable test: Extend parser/lowering case by case from vector add, GEMM, conv2d, image filter to CTS-shaped fixtures.
- CTS orientation: compiler and kernel language CTS groups

### builtins_math_precision
- Status: absent
- Evidence: artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_subset_conformance_tests.json
- Blocker: Math builtins, transcendental precision, denorm/rounding behavior, and conformance tolerances are not implemented.
- Next executable test: Add integer/float builtin fixture families plus ULP/tolerance golden checks before enabling math CTS lanes.
- CTS orientation: math_brute_force and builtin coverage families

### atomics_memory_order
- Status: absent
- Evidence: artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_subset_conformance_tests.json
- Blocker: Atomic operations are intentionally rejected in the current subset; memory-order scopes are not modeled.
- Next executable test: Add local/global atomic op micro-tests behind an explicit feature flag, then map to scoreboard/LSU semantics.
- CTS orientation: atomics and memory model CTS groups

### images_samplers
- Status: absent
- Evidence: artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_subset_conformance_tests.json
- Blocker: image*_t and sampler_t are rejected; no image object storage, formats, addressing, or filtering semantics.
- Next executable test: Keep image/sampler negative tests green; only open implementation after memory object model supports images.
- CTS orientation: image read/write/sampler CTS groups

### memory_address_spaces
- Status: partial
- Evidence: artifacts/rank_01_vivante_3d_gpgpu_ip/memory/memory_event_trace.json, artifacts/rank_01_vivante_3d_gpgpu_ip/verification/phase6_memory_trace_integration_report.json
- Blocker: Address spaces are parsed and traced but cache/scratchpad/coherency/local lifetime rules are not spec-complete.
- Next executable test: Add local memory lifetime/barrier tests and constant memory read-only violation tests.
- CTS orientation: memory object, buffer, local memory, and barrier CTS groups

### events_fences_queue_semantics
- Status: partial
- Evidence: artifacts/rank_01_vivante_3d_gpgpu_ip/driver_submission/fence_event_lifecycle.json, artifacts/rank_01_vivante_3d_gpgpu_ip/driver_submission/driver_submission_report.json
- Blocker: Proxy fence/event semantics exist; OpenCL event wait lists, callbacks, profiling, and out-of-order queues are incomplete.
- Next executable test: Add event dependency DAG tests with success/fault propagation and queue drain checks.
- CTS orientation: event, queue, and synchronization CTS groups

### error_negative_behavior
- Status: partial
- Evidence: artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_subset_conformance_tests.json, artifacts/rank_01_vivante_3d_gpgpu_ip/rtl/e5_outputs/negative_boundary_evidence.json
- Blocker: Local subset rejects known unsupported features but does not yet map all failures to OpenCL error codes.
- Next executable test: Create an OpenCL-style error code matrix for bad args, bad objects, bad geometry, and unsupported features.
- CTS orientation: api negative tests

### icd_runtime_integration
- Status: proxy
- Evidence: artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_icd_runtime_contract.json
- Blocker: Current runtime is a CLI/proxy bridge, not a Khronos ICD vendor library.
- Next executable test: Build a mock libOpenCL vendor shim once host API contract tests are stable.
- CTS orientation: ICD loader and CTS harness integration

### driver_os_integration
- Status: proxy
- Evidence: artifacts/rank_01_vivante_3d_gpgpu_ip/os_runtime/linux_runtime_evidence.json, artifacts/rank_01_vivante_3d_gpgpu_ip/verification/phase8_work_package_artifacts/drm_uapi_contract.json
- Blocker: No production kernel DRM driver, GEM BO model, ioctl ABI, syncobj, scheduler, or hang recovery.
- Next executable test: Promote DRM-like submission proxy tests to ioctl-shaped fixtures before kernel-driver implementation.
- CTS orientation: runtime/driver behavior under CTS process model

### rtl_structural_coverage_signoff
- Status: partial
- Evidence: artifacts/rank_01_vivante_3d_gpgpu_ip/verification/verilator_coverage/verilator_coverage_report.json, artifacts/rank_01_vivante_3d_gpgpu_ip/synthesis/synthesis_readiness_report.json
- Blocker: Functional/acceptance coverage is 100%, but structural RTL line/branch/toggle and signoff closure are not 100%.
- Next executable test: Add directed/random/fault/stress RTL structural coverage gates and signoff input checks without redefining functional coverage.
- CTS orientation: implementation-quality prerequisite before official submission

## Generated Artifacts

- opencl_subset_conformance_tests: artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_subset_conformance_tests.json
- opencl_icd_runtime_contract: artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_icd_runtime_contract.json
- phase9_opencl_readiness_gates: artifacts/rank_01_vivante_3d_gpgpu_ip/verification/phase9_opencl_readiness_gates.json
- opencl_cts_readiness_matrix: artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_cts_readiness_matrix.json
