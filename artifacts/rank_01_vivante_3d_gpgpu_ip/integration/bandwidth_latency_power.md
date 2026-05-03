# Bandwidth, Latency, Shader Scaling, And Power Proxy Evidence

Date: 2026-05-02

Status: proxy model implemented; RTL-backed bandwidth, cycle latency, and
silicon PPA remain unproven.

This file defines the S5 integration framework for AXI bandwidth, kernel
latency proxy, shader-unit scaling, and power/energy proxy evidence for the
Rank 1 Celviz GPGPU IP package.

## Claim Boundary

Allowed:

- Clean-room proxy estimates and measured local logs when present.
- Workload byte counts, FP32 operation counts, hashes, and pass status from the
  S1 compute model.
- Public shader-unit tier metadata with explicit non-equivalence caveats.
- Future Ventus RTL/simulator counters if commands and logs are attached.

Not allowed:

- Production power, area, timing, thermal, or PPA claims.
- Silicon signoff, tapeout readiness, STA/CDC/DFT closure, or foundry-ready
  claims.
- Vivante performance equivalence.
- Official OpenCL/OpenCV conformance.

## Current Model Metrics

Current S1 run evidence:

```text
artifact_root=artifacts/rank_01_vivante_3d_gpgpu_ip/model
status=pass
total_fp32_ops=722
total_integer_ops=576
total_bytes_touched=1652
fp16_path=deterministic_binary16_proxy_for_vector_add_gemm_convolution
```

Per-workload model metrics from `model/run.log`:

| Workload | Precision path | FP32 ops | Bytes read | Bytes written | Current status |
| --- | --- | ---: | ---: | ---: | --- |
| `vector_add` | FP32 | 32 | 256 | 128 | pass |
| `gemm_proxy` | FP32 | 240 | 216 | 80 | pass |
| `convolution_proxy` | FP32 | 450 | 232 | 100 | pass |
| `image_filter` | u8 | 0 | 64 | 64 | pass |
| `memory_copy` | byte | 0 | 256 | 256 | pass |

These are software-model counts. They are useful for integration sizing and
latency-proxy formulas, but they are not measured RTL cycle counts.

## Generated Proxy Performance Evidence

Worker 5 added and ran the standard-library proxy performance model:

```sh
python3 tools/celviz_gpgpu_ip/perf_model.py --print-summary
```

Generated outputs:

```text
artifacts/rank_01_vivante_3d_gpgpu_ip/integration/perf_model_run.log
artifacts/rank_01_vivante_3d_gpgpu_ip/integration/perf_model_metrics.json
```

Run-log summary:

```text
schema=celviz.gpgpu.proxy_perf_model.v1
workload_source=artifacts/rank_01_vivante_3d_gpgpu_ip/model/metrics.json
tier_source=model_metrics_public_shader_unit_scaling
workload_count=5
tier_count=9
tier_validation_status=pass
tier_validation_selected_tiers=CC8000L,CC8000,CC8400
estimate_count=45
fastest_tier_by_proxy_cycles=CC8400 cycles=476
slowest_tier_by_proxy_cycles=CC8000L cycles=509
status=pass
```

The generated `pass` status means the proxy model executed and emitted
well-formed evidence. It does not mean RTL bandwidth, cycle-accurate latency,
real power, API conformance, or silicon PPA is proven.

Top-level tier summary from `perf_model_metrics.json`:

| Tier | Shader units, vec1 public metadata | Total proxy cycles | FP32 ops/cycle proxy | Compute ops/cycle proxy | AXI pressure bytes/cycle proxy | Aggregate power index proxy | Bottleneck summary |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| CC8000L | 16 | 509 | 1.418468 | 2.550098 | 3.756385 | 3.746699 | 3 memory-bound, 2 compute-bound |
| CC8000 | 32 | 485 | 1.488660 | 2.676289 | 3.942268 | 3.930619 | 4 memory-bound, 1 compute-bound |
| CC8200 | 128 | 478 | 1.510460 | 2.715481 | 4.000000 | 3.987741 | 4 memory-bound, 1 compute-bound |
| CC8400 | 256 | 476 | 1.516807 | 2.726891 | 4.016807 | 4.004370 | 5 memory-bound |
| CC8400-MP2 | 512 | 476 | 1.516807 | 2.726891 | 4.016807 | 4.004370 | 5 memory-bound |
| CC8400-MP4 | 1024 | 476 | 1.516807 | 2.726891 | 4.016807 | 4.004370 | 5 memory-bound |
| CC8800 | 512 | 476 | 1.516807 | 2.726891 | 4.016807 | 4.004370 | 5 memory-bound |
| CC8800-MP2 | 1024 | 476 | 1.516807 | 2.726891 | 4.016807 | 4.004370 | 5 memory-bound |
| CC8800-MP4 | 2048 | 476 | 1.516807 | 2.726891 | 4.016807 | 4.004370 | 5 memory-bound |

The plateau after CC8400 is expected under the current assumptions because the
fixed workload set becomes memory dominated. This is a modeling result, not a
claim about Vivante silicon.

## Machine-Checkable E5-E Tier Evidence

`perf_model_metrics.json.tier_validation` records the E5-E closure checks. The
selected monotonic ladder is `CC8000L -> CC8000 -> CC8400`, giving at least
three public-style tiers while avoiding the expected memory-dominated plateau
above CC8400.

| Check | Metric | Direction | Values | Status |
| --- | --- | --- | --- | --- |
| Minimum tier count | selected tiers | at least 3 | `CC8000L, CC8000, CC8400` | pass |
| Throughput/tier | `aggregate_compute_ops_per_cycle_proxy` | strictly increasing | `2.550098, 2.676289, 2.726891` | pass |
| AXI byte pressure fields | payload/control/pressure fields | present and positive | `total_payload_bytes`, `total_control_bytes_proxy`, `total_axi_pressure_bytes_proxy` | pass |
| AXI byte pressure | `aggregate_axi_pressure_bytes_per_cycle_proxy` | strictly increasing | `3.756385, 3.942268, 4.016807` | pass |
| Latency proxy | `latency_proxy_cycles` | strictly decreasing | `509, 485, 476` | pass |
| Power proxy | `aggregate_power_index_proxy` | strictly increasing | `3.746699, 3.930619, 4.004370` | pass |

The same evidence is emitted in `perf_model_run.log` as
`tier_validation_check` lines for simple log scanning.

## AXI Bandwidth Framework

Required future counters:

| Counter | Description | Source expectation |
| --- | --- | --- |
| `axi_lite_writes` | MMIO writes for descriptor setup, doorbell, interrupt clear, and status control. | Control-plane log. |
| `axi_lite_reads` | MMIO reads for status, fence, fault, and counter polling. | Control-plane log. |
| `axi_data_read_bytes` | AXI memory payload bytes read by kernel execution. | RTL/sim memory or model counter. |
| `axi_data_write_bytes` | AXI memory payload bytes written by kernel execution. | RTL/sim memory or model counter. |
| `axi_data_read_bursts` | Read burst count if exposed by the adapter/testbench. | AXI monitor. |
| `axi_data_write_bursts` | Write burst count if exposed by the adapter/testbench. | AXI monitor. |
| `cache_miss_events` | L1/L2 miss or refill proxy if available. | Ventus cache counters/logs. |

Bandwidth formulas:

```text
payload_bytes = axi_data_read_bytes + axi_data_write_bytes
effective_bytes_per_cycle = payload_bytes / kernel_cycles
control_bytes = 4 * (axi_lite_reads + axi_lite_writes)
control_to_payload_ratio = control_bytes / max(payload_bytes, 1)
```

Until `kernel_cycles` and AXI monitors exist, the model byte counts are
integration planning data, not pass/fail bandwidth evidence.

The proxy performance model estimates AXI data pressure from workload
`bytes_read` and `bytes_written`, and estimates AXI4-Lite control pressure from
fixed descriptor/status/clear transaction counts. These estimates are now
recorded in `perf_model_metrics.json`; they are still not RTL AXI monitor logs.

## Kernel Latency Proxy

Latency proxy fields:

| Field | Meaning |
| --- | --- |
| `model_steps` | Deterministic software model loop or operation count. |
| `fp32_ops` | Counted FP32 operations for arithmetic workloads. |
| `bytes_touched` | Read plus write bytes for memory pressure. |
| `kernel_cycles` | Future RTL/simulator cycle count. |
| `queue_to_start_cycles` | Future control-plane scheduling latency. |
| `start_to_complete_cycles` | Future execution latency. |
| `completion_to_interrupt_cycles` | Future interrupt propagation latency. |

Proxy formulas:

```text
ops_per_model_byte = fp32_ops / max(bytes_touched, 1)
latency_proxy_score = fp32_ops + memory_weight * bytes_touched
rtl_kernel_latency_cycles = start_to_complete_cycles
end_to_end_latency_cycles = queue_to_start_cycles + start_to_complete_cycles + completion_to_interrupt_cycles
```

The `latency_proxy_score` is only a ranking aid across deterministic workloads.
It is not a cycle-accurate Vivante latency metric.

## Shader-Unit Scaling

Current public tier metadata is stored in:

```text
artifacts/rank_01_vivante_3d_gpgpu_ip/model/outputs/shader_unit_scaling.json
artifacts/rank_01_vivante_3d_gpgpu_ip/model/metrics.json
```

The current tier table records public labels from the Vivante 3D GPGPU IP
product table. These rows are metadata for clean-room scaling experiments, not
measured local RTL performance.

Required future scaling evidence:

| Evidence | Requirement |
| --- | --- |
| Same-workload stability | Workload output hash remains stable across profiles. |
| Throughput proxy | Normalized ops/cycle or ops/model-step changes with tier profile. |
| Occupancy | Active workgroups, active warps, register pressure, LDS/shared memory pressure. |
| Stall breakdown | Scheduler, dependency, memory, cache, and queue stalls when available. |
| Bottleneck note | Each non-monotonic result has an explicit reason or is marked unresolved. |

Do not equate Ventus SMs, threads, warps, or lanes directly to Vivante shader
units. Any mapping must list assumptions such as active SM count, lanes per SM,
issue slots, precision width factor, and utilization.

## Power And Energy Proxy

Power status: proxy index implemented; measured power remains unavailable.

Allowed proxy fields:

| Field | Meaning |
| --- | --- |
| `activity_units` | Weighted sum of FP32 ops, memory bytes, MMIO accesses, and interrupt events. |
| `energy_proxy_units` | Activity units multiplied by documented weights. |
| `energy_per_workload_proxy` | Relative comparison among deterministic workloads. |
| `power_proxy_units` | Energy proxy divided by model steps or RTL cycles if present. |

Initial proxy equation:

```text
energy_proxy_units =
  fp32_ops * fp32_weight +
  bytes_read * read_byte_weight +
  bytes_written * write_byte_weight +
  axi_lite_transactions * mmio_weight +
  interrupt_events * interrupt_weight
```

The generated model records the weights in
`perf_model_metrics.json.assumptions.activity_weights`. Without measured
voltage, frequency, capacitance, toggle activity, or implementation data, this
remains a relative proxy only.

## Evidence Needed Before Pass

| Gate | Required before pass |
| --- | --- |
| AXI traffic | Control-plane or RTL/sim log with AXI4-Lite and AXI data counters. |
| Kernel latency | Run log with cycle or timestamp fields for queue, start, complete, and interrupt. |
| Shader scaling | Same workload executed or modeled across multiple profiles with stable outputs and scaling metrics. Proxy model evidence exists; measured scaling remains pending. |
| Power proxy | Explicit weights, activity counts, and caveat language in a generated metrics file. This proxy gate is started/pass for model execution, not for real power. |
| RTL-backed bandwidth | Real Ventus simulation command and log, not just software model byte counts. |
