# S2 GPGPU RTL And Control-Plane Evidence

Status: GPGPU-only proxy-shell blueprint drafted.

This folder records Worker 5 S2 control-plane and RTL-shell evidence for
Celviz GPGPU IP under the Rank 1 Vivante 3D GPGPU IP direction. The artifact is
clean-room and compute-focused: command processor, kernel dispatch queues, DMA,
scheduler controls, shader-unit tier scaling, FP16/FP32 mode, AXI counters,
interrupt/status/error handling, and MMU-fault reporting.

## Scope

The allowed surface is the GPGPU command runtime/control plane. This directory
does not define 3D graphics registers, raster state, texture sampling state,
viewport state, scanout/display state, or proprietary driver compatibility.

## Artifacts

| Artifact | Purpose |
| --- | --- |
| `docs/celviz-gpgpu-ip/COMMAND_RUNTIME_ABI.md` | Defines packet header, opcodes, kernel dispatch, DMA, scheduler payloads, memory model, completions, and errors. |
| `artifacts/rank_01_vivante_3d_gpgpu_ip/rtl/register_map.md` | Defines the GPGPU-only MMIO register map. |
| `artifacts/rank_01_vivante_3d_gpgpu_ip/rtl/control_plane_config.json` | Machine-readable S2 config for queues, tiers, opcodes, scheduler, shader modes, interrupts, errors, and evidence tokens. |
| `artifacts/rank_01_vivante_3d_gpgpu_ip/rtl/e3_native_runtime_evidence.json` | E3 evidence summary for Verilator/native runtime relink, `--require-runtime` binding, and queue/metric snapshots. |
| `artifacts/rank_01_vivante_3d_gpgpu_ip/rtl/smoke.log` | JSON validation and artifact smoke record. |

## Covered Control Plane

- Command processor identity, ABI versioning, queue base/size/head/tail,
  doorbell, completion status, and queue priority.
- Kernel dispatch queue and direct-control dispatch registers for smoke tests.
- DMA copy/fill registers with byte count, stride, fill pattern, status, and
  fault reporting.
- Workgroup and warp scheduler configuration, issue policy, fairness window,
  halt/preemption boundary metadata, and watchdog.
- Shader-unit tier scaling from one to two to four shader units.
- FP16, FP32, and mixed FP16/FP32 mode selection.
- AXI read/write byte counters, read/write beat counters, stall counters,
  dispatch counters, DMA counters, fault counters, and error counters.
- Interrupt, global status, sticky error capture, error clear, MMU translation
  control, and MMU fault address/context capture.

## Tier Summary

| Tier | Queues | Shader units | S2 purpose |
| --- | ---: | ---: | --- |
| `gpgpu_nano` | 1 | 1 | Minimal queue, FP32 kernel dispatch, DMA copy/fill, completion interrupt. |
| `gpgpu_nano_ultra` | 2 | 2 | Scheduler controls, FP16/FP32 modes, AXI counters, MMU faults. |
| `gpgpu_nano_ultra31` | 4 | 4 | Richest evidence tier with per-unit scaling, watchdog, and injection hooks. |

## Validation

The JSON config is validated with:

```sh
python3 -m json.tool artifacts/rank_01_vivante_3d_gpgpu_ip/rtl/control_plane_config.json
```

The expected result is successful pretty-print parsing with exit code `0`.

## E3 Native Runtime Evidence

E3 records a clean-room proxy native-runtime bind without changing runtime
implementation files. The evidence run used an existing Verilated core under
`/tmp/ventus-gpgpu-celviz-build` and completed the runtime relink command:

```sh
bash scripts/build_celviz_gpgpu_runtime.sh --auto
```

Observed output:

```text
CELVIZ_GPGPU_RUNTIME_LIB=/tmp/ventus-gpgpu-celviz-build/sim-verilator/build/libVentusRTL/debug/libVentusRTL.so
```

The runtime command stream was then bound through the native C ABI with
`--require-runtime`:

```sh
python3 tools/celviz_gpgpu_ip/runtime_cli.py \
  --commands artifacts/rank_01_vivante_3d_gpgpu_ip/rtl/control_plane_demo.json \
  --runtime-lib /tmp/ventus-gpgpu-celviz-build/sim-verilator/build/libVentusRTL/debug/libVentusRTL.so \
  --require-runtime \
  --output-dir /tmp/ventus-gpgpu-celviz-e3 \
  --run-log /tmp/ventus-gpgpu-celviz-e3/runtime_run.log \
  --print-status
```

The E3 run completed with `runtime_bridge=ctypes_bound`, `dry_run=false`, and
`rtlsim_library_bound=true`. The distilled evidence is recorded in
`e3_native_runtime_evidence.json`; the full generated runtime log, metrics, and
status files remain in `/tmp/ventus-gpgpu-celviz-e3` so the artifact tree stays
small and proxy-only.

Recorded E3 snapshots:

- 19 control-plane commands submitted and completed, including 3 expected
  negative-path commands.
- 3 native runtime queues observed through
  `celviz_gpgpu_runtime_proxy_get_queue_snapshot`, with 9 submitted, 9 retired,
  and 0 pending native commands.
- Native metric snapshot recorded 7 DMA copies, 2 DMA fills, 2 fence signals,
  3 fence waits, 1 reset, 512 bytes read, 896 bytes written, and 1408 bytes
  moved.
- Native runtime acceptance passed for DMA copy, DMA fill, named fences, queue
  lifecycle, status polling, last-event capture, and expected error injection.

This is not official Vivante conformance, proprietary command-stream
compatibility, OpenCL conformance, RTL timing signoff, or silicon signoff.
