# Celviz GPGPU IP Proxy Performance Model

Date: 2026-05-02

Status: implemented as proxy evidence.

## Purpose

`tools/celviz_gpgpu_ip/perf_model.py` creates S5/S6-style proxy performance
and bandwidth evidence for the active Rank 1 Celviz GPGPU IP package. It is
compute-oriented and uses the existing S1 model metrics when available.

This is not a 3D graphics performance model. It does not use Rank 12 triangle,
texture, framebuffer, scanout, or graphics API evidence.

## Inputs

Default input:

```text
artifacts/rank_01_vivante_3d_gpgpu_ip/model/metrics.json
```

The tool reads:

- Workload names.
- FP32 operation counts.
- Bytes read and written.
- Precision path labels.
- Public CC8000/CC8X00 shader-unit and FP32/FP16 operations-per-cycle tier
  metadata already documented by the compute model.

If the metrics file is absent, the tool falls back to the same public tier
table and the fixed Rank 1 workload counts documented in this repo. The fallback
is still proxy evidence only.

## Outputs

Default outputs:

```text
artifacts/rank_01_vivante_3d_gpgpu_ip/integration/perf_model_metrics.json
artifacts/rank_01_vivante_3d_gpgpu_ip/integration/perf_model_run.log
```

The JSON contains:

- Assumptions.
- Workload input metrics.
- Public tier metadata.
- Per-tier/per-workload estimates.
- Tier summaries.
- Limitations.

The log contains a compact run transcript and tier summaries for audit.

## Command

From the repository root:

```sh
python3 tools/celviz_gpgpu_ip/perf_model.py --print-summary
```

## Proxy Assumptions

The model uses fixed assumptions so later workers can review or replace them:

| Assumption | Default |
| --- | ---: |
| Compute utilization | 0.60 |
| Memory bus bytes per cycle | 32 |
| Memory efficiency | 0.70 |
| Launch overhead cycles | 64 |
| Completion overhead cycles | 16 |
| AXI-Lite setup writes | 8 |
| AXI-Lite status reads | 4 |
| AXI-Lite clear writes | 1 |
| AXI-Lite register bytes | 4 |

Activity weights for the power index:

| Activity | Weight |
| --- | ---: |
| FP32 op | 1.0 |
| Read byte | 0.20 |
| Write byte | 0.25 |
| AXI-Lite transaction | 8.0 |
| Cycle | 0.03 |

## Formulas

```text
usable_fp32_ops_per_cycle = public_fp32_ops_per_cycle * compute_utilization
usable_memory_bytes_per_cycle = memory_bus_bytes_per_cycle * memory_efficiency

compute_cycles_proxy = ceil(fp32_ops / usable_fp32_ops_per_cycle)
memory_cycles_proxy = ceil((bytes_read + bytes_written) / usable_memory_bytes_per_cycle)
kernel_body_cycles_proxy = max(compute_cycles_proxy, memory_cycles_proxy)
kernel_cycles_proxy = launch_overhead_cycles + kernel_body_cycles_proxy + completion_overhead_cycles

compute_ops_per_cycle_proxy = fp32_ops / kernel_cycles_proxy
bandwidth_bytes_per_cycle_proxy = (bytes_read + bytes_written) / kernel_cycles_proxy
memory_pressure_ratio = memory_cycles_proxy / max(kernel_body_cycles_proxy, 1)
compute_pressure_ratio = compute_cycles_proxy / max(kernel_body_cycles_proxy, 1)
```

Power index:

```text
activity_index_proxy =
  fp32_ops * fp32_op_weight +
  bytes_read * read_byte_weight +
  bytes_written * write_byte_weight +
  axi_lite_transactions * axi_lite_transaction_weight +
  kernel_cycles_proxy * cycle_weight

power_index_proxy = activity_index_proxy / kernel_cycles_proxy
```

The power index is a relative activity score. It has no watt, joule, voltage,
frequency, thermal, or implementation meaning.

## Claim Boundary

Allowed claims:

- Clean-room proxy cycle estimates.
- Proxy throughput and bandwidth pressure estimates.
- Relative activity/power-index comparisons.
- Public tier metadata as public metadata.
- Use of S1 software model bytes and FP32 operation counts.

Forbidden claims:

- Real silicon PPA.
- Vivante-equivalent performance.
- Official API conformance.
- Tapeout or signoff readiness.
- RTL timing closure.
- FP16 RTL performance.

## Current Evidence Status

The generated model is `pass` as proxy evidence when the tool exits 0 and writes
both output files. It does not close RTL-backed AXI bandwidth, cycle-accurate
latency, production power, or conformance gates.
