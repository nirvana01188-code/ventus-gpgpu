# Phase9 Productization Gates

productization readiness gates only; not product signoff or official OpenCL conformance

## Gates

### memory_model_global_local_constant
- Domain: memory
- Required artifacts: artifacts/rank_01_vivante_3d_gpgpu_ip/memory/memory_event_trace.json, artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_subset_conformance_tests.json
- Pass condition: global/local/constant fixtures compile and unsupported image/sampler/atomic cases reject deterministically
- Next action: add barrier/local lifetime and constant read-only violation directed tests

### cache_scratchpad_coalescing
- Domain: memory_performance
- Required artifacts: artifacts/rank_01_vivante_3d_gpgpu_ip/verification/phase7_coalescing_score_report.json
- Pass condition: coalescing evidence remains proxy-labeled and ties to memory event traces
- Next action: add cache/scratchpad hit/miss and coalesced transaction counters

### dma_kernel_access_unification
- Domain: runtime_memory
- Required artifacts: artifacts/rank_01_vivante_3d_gpgpu_ip/rtl/control_plane_demo.json, artifacts/rank_01_vivante_3d_gpgpu_ip/demo/opencl_subset/runtime_commands.json
- Pass condition: DMA copy/fill and kernel memory access share region bounds and fault handling
- Next action: create shared memory-region validator for DMA and NDRange dispatch paths

### queue_fence_event_semantics
- Domain: driver_runtime
- Required artifacts: artifacts/rank_01_vivante_3d_gpgpu_ip/driver_submission/fence_event_lifecycle.json
- Pass condition: queue drain, fence wait, event status, and fault paths are observed
- Next action: add OpenCL wait-list DAG and callback/profiling placeholders

### rtl_structural_uplift
- Domain: rtl_verification
- Required artifacts: artifacts/rank_01_vivante_3d_gpgpu_ip/verification/verilator_coverage/verilator_coverage_report.json
- Pass condition: structural metrics are reported separately from 100% functional acceptance coverage
- Next action: add directed reset/IRQ/scoreboard/LSU/branch tests and random/fault/stress seeds

### synthesis_sta_power_dft_physical
- Domain: signoff
- Required artifacts: artifacts/rank_01_vivante_3d_gpgpu_ip/synthesis/synthesis_readiness_report.json, artifacts/rank_01_vivante_3d_gpgpu_ip/ppa/ppa_proxy_report.json
- Pass condition: signoff inputs are named and proxy PPA remains separated from signed-off PPA
- Next action: attach target library/SDC/SAIF/DFT/floorplan inputs when a technology target exists
