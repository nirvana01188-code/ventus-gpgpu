# S3 Verification Evidence

Status: pass for the current Rank 1 compute model, runtime demo,
control-plane configuration evidence, E1 command/evidence fixtures, E2 RTL
control-plane source hooks, E3 native runtime evidence, E4 demo/model evidence,
E5 verification coverage evidence, and present source hooks. The harness also
performs strict checks on optional richer evidence when those files are present.

This directory defines the Rank 1/S3 verification entry for the Celviz GPGPU IP
work package. The target is Vivante 3D GPGPU IP acceptance evidence built on the
open-source Ventus GPGPU framework. The harness is intentionally local and
clean-room: it does not fetch packages, contact services, or claim proprietary
Vivante conformance.

## Verification Scope

The S3 suite covers the Rank 1 acceptance points that must be visible across a
local compute model, runtime, and control-plane shell:

| ID | Component boundary | Test area | Required observation | Current state |
| --- | --- | --- | --- | --- |
| R01-S3-V001 | compute model | Vector add | Deterministic vector add workload reports `vector_add` with checked output data. | pass |
| R01-S3-V002 | compute model | GEMM/convolution/image filter | Matrix/tensor and image-style kernels report `gemm_convolution_image_filter` with expected output checksums or numeric tolerances. | pass |
| R01-S3-V003 | runtime | Memory copy | Host-to-device, device-to-host, and device-to-device movement reports `memory_copy` with byte counts and data integrity checks. | pass |
| R01-S3-V004 | compute model/runtime | Shader-unit scaling | Different shader-unit or compute-lane counts report `shader_unit_scaling` and preserve deterministic results. | pass |
| R01-S3-V005 | compute model | FP16/FP32 paths | Half and single precision paths report `fp16_fp32_paths`, including tolerance metadata for FP16. | pass |
| R01-S3-V006 | runtime/control plane | Command submission | Queue submission, fence, completion, and status polling report `command_submission`. | pass |
| R01-S3-V007 | control plane | Interrupts | Completion and fault interrupt paths report `interrupts` with recoverable status. | pass |
| R01-S3-V008 | control plane/runtime | AXI traffic | Command, data, and response traffic counters report `axi_traffic`. | pass |
| R01-S3-V009 | compute model/runtime/control plane | Throughput scaling by tier | Small, mid, and high tiers report `throughput_scaling_by_tier` with monotonic or explained throughput behavior. | pass |
| R01-S3-V010 | S3 entry script | Harness behavior | Missing components are reported as pending with exit status 0; present components are run and checked for all required tokens. | implemented |
| R01-S3-V011 | optional richer evidence | Present-file strictness | Optional JSON/log evidence is skipped if absent, but present files must parse cleanly and not report fail/error status. | pass |
| R01-S3-V012 | optional richer evidence | FP16 proxy outputs | Present `fp16_proxy` objects must include status/method and well-formed samples when supplied. | pass |
| R01-S3-V013 | runtime | Queue phases | Runtime demo logs must match `kernel_count` to `kernel[n]` queue entries when present. | pass |
| R01-S3-V014 | control plane | Interrupt/error/reset tokens | Control-plane evidence must expose interrupt, error, and reset vocabulary when present. | pass |
| R01-S3-V015 | control plane/runtime | AXI/APB transaction counters | Present AXI/APB counter evidence must parse and be non-failing; AXI is present, APB remains optional. | pass |
| R01-S3-V016 | compute model | Throughput monotonicity cues | Shader-unit tier metadata is sorted by shader-unit count before checking FP16/FP32 operation rates for non-decreasing cues. | pass |
| R01-S3-V017 | Ventus source hook | AXI4Lite2CTA Celviz registers/counters | If `AXI4Lite2CTA.scala` contains a Celviz marker, the harness requires a real source-level AXI4-Lite module hook with Celviz-named register/counter storage and AXI channel logic. | pass |
| R01-S3-V018 | Ventus source hook | AXI4Lite2CTA CSR plumbing | If `AXI4Lite2CTA.scala` contains a Celviz marker, the harness requires command doorbell, interrupt, error, completion, and AXI/APB counter CSRs wired to register storage and channel events. | pass |
| R01-S3-V019 | Ventus source hook | CTA scheduler debug counters | If `cta_scheduler.scala` contains a Celviz marker, the harness requires Celviz-named debug counter storage tied to CTA scheduler valid/ready/fire or completion paths. | pass |
| R01-S3-V020 | Ventus source hook | Warp scheduler debug counters | If `warp_schedule.scala` contains a Celviz marker, the harness requires Celviz-named debug counter storage tied to warp request/response/control/ready paths. | pass |
| R01-S3-V021 | sim-verilator source hook | Celviz runtime proxy header/API | If the sim-verilator runtime files contain a Celviz marker, the harness requires public Celviz runtime proxy API declarations, a proxy type, and C/C++ API hooks into rtlsim enqueue/copy/status paths. | pass |
| R01-S3-V022 | optional source hooks | Marker-triggered strictness | Source hook checks are optional while absent, but any source file that advertises Celviz must contain real hook code rather than comments or inert labels only. | pass |
| R01-S3-V023 | tools source hook | Runtime CLI hooks | If `tools/celviz_gpgpu_ip/runtime_cli.py` is present, the harness requires argparse entry points, kernel-demo validation, queue trace output, status output, and compute-model subprocess wiring. | pass |
| R01-S3-V024 | source evidence hygiene | Implementation files only | Source hook checks may only use implementation files such as Scala, C/C++, headers, and Python; docs and verification prose cannot satisfy hook evidence. | pass |
| R01-S3-V025 | native runtime ABI source hook | Native queue snapshot | `scripts/check_celviz_gpgpu_sources.sh` requires C ABI declarations/implementation and Python ctypes binding for `celviz_gpgpu_runtime_proxy_get_queue_snapshot`, plus runtime output wiring into `native_proxy_snapshot.queues`. | pass |
| R01-S3-V026 | native runtime ABI source hook | Native pending count | The source checker requires `celviz_gpgpu_runtime_proxy_get_pending_count` in the C ABI, a C++ implementation backed by runtime state, a Python ctypes `c_uint64` binding, and `native_proxy_snapshot.pending_count`. | pass |
| R01-S3-V027 | native runtime ABI source hook | Named fences | The source checker requires named-fence C ABI declarations, C++ `named_fences` storage, signal/wait implementations, Python ctypes bindings, and command execution calls for signal/wait paths. | pass |
| R01-S3-V028 | native runtime ABI source hook | Submit fill | The source checker requires `celviz_gpgpu_runtime_proxy_submit_fill` in the C ABI, a C++ DMA-fill implementation that writes through `ventus_rtlsim_pmemcpy_h2d`, Python ctypes binding, and runtime command execution calls. | pass |
| R01-S3-V029 | native runtime acceptance source hook | Native proxy snapshot | The source checker requires runtime code to collect native command results and emit `native_proxy_snapshot` with queue snapshots, metrics, and pending count when a native bridge is available. | pass |
| R01-S3-V030 | native runtime acceptance source hook | Native runtime acceptance | The command wrapper runs the source checker before S3 verification; the checker reports `native_runtime_acceptance` only from implementation files and rejects docs/verification paths for hook evidence. | pass |
| R01-E1-V001 | runtime/control plane fixture | DMA and host/device movement | `rtl/control_plane_demo.json` includes `host_to_device`, `device_to_host`, `dma_fill`, and `dma_copy` commands with completion writebacks and counter capture expectations. | pass |
| R01-E1-V002 | runtime/control plane fixture | Queue lifecycle | The command fixture exercises queues 0, 1, and 2, and records expected submitted/retired/head/tail/error observations in `e1_runtime_abi_expectations`. | pass |
| R01-E1-V003 | runtime/control plane fixture | Named fences | The command stream signals and waits on `copy_ready` and `staging_copy_ready`, then checks an expected `never_signaled` timeout path. | pass |
| R01-E1-V004 | runtime/control plane fixture | Status polling | Commands annotate expected queued/complete/error/sticky-error polling transitions, and the fixture points status evidence at completion records, status registers, counter snapshots, and interrupt events. | pass |
| R01-E1-V005 | runtime/control plane fixture | Expected error injection | The stream includes expected scheduler, MMU, and fence-wait errors so negative ABI paths pass only when the expected error code is observed. | pass |
| R01-E2-V001 | RTL control-plane source hook | AXI CSR command and queue progress | `scripts/check_celviz_gpgpu_sources.sh` requires AXI4-Lite command, doorbell, completion, IRQ, error, APB, and AXI counter CSRs in `AXI4Lite2CTA.scala`. | pass |
| R01-E2-V002 | RTL control-plane source hook | Doorbell, IRQ, and error flow | The source checker requires doorbell accept/busy behavior, completion IRQs, error IRQs, IRQ pending state, and IRQ/error event counters. | pass |
| R01-E2-V003 | RTL scheduler source hook | Scheduler handoff counters | CTA scheduler source must expose host workgroup accept/done counters, CU wavefront dispatch/done counters, and allocation busy cycle counting. | pass |
| R01-E2-V004 | RTL debug observability source hook | Debug preservation | Top-level, CTA, and warp scheduler debug bundles and counter outputs must be wired through active RTL and protected with `dontTouch`. | pass |
| R01-E3-V001 | Verilator/native runtime artifact | Runtime build or relink | `scripts/build_celviz_gpgpu_runtime.sh --auto` completes and reports a local `libVentusRTL.so` path under `/tmp/ventus-gpgpu-celviz-build`. | pass |
| R01-E3-V002 | Native runtime binding | `--require-runtime` C ABI bind | `runtime_cli.py --commands rtl/control_plane_demo.json --require-runtime` binds the shared library with `runtime_bridge=ctypes_bound`, `dry_run=false`, and `rtlsim_library_bound=true`. | pass |
| R01-E3-V003 | Native queue and metric snapshots | Queue/metrics observability | E3 metadata records native queue snapshots, pending count, queue totals, runtime metrics, and native acceptance categories for DMA copy, DMA fill, and fences. | pass |
| R01-E4-V001 | demo/model evidence | Workload coverage | Kernel-demo and model artifacts cover `vector_add`, GEMM, convolution/image-filter, and `memory_copy` evidence. | pass |
| R01-E4-V002 | demo/model evidence | FP16/FP32 paths | Model artifacts prove FP32 operation metadata and FP16 proxy execution/tolerance metadata for vector add and GEMM, with convolution/image-filter FP16 metadata recorded. | pass |
| R01-E4-V003 | demo/model evidence | Tier scaling | Demo and model tier metadata are sorted by shader-unit count and checked for monotonic FP16/FP32 operation scaling. | pass |
| R01-E4-V004 | runtime demo evidence | Buffer bindings | Kernel demo and runtime `buffer_binds.json` prove global read/write buffer bindings for every demo workload. | pass |
| R01-E4-V005 | runtime demo evidence | Dispatch/readback/golden compare | Queue trace proves submit/wait/readback phases with success completion and readback hashes matching golden summary/output hashes. | pass |
| R01-E5-V001 | verification/control plane | Command submission closure | `test_commands.sh` checks the 19-command control-plane stream, queue submitted/retired closure, and per-queue state snapshots. | pass |
| R01-E5-V002 | verification/control plane | Interrupt coverage | Completion and error interrupt events are both present, with counters `completion_interrupts=13` and `error_interrupts=3` in current metrics. | pass |
| R01-E5-V003 | verification/control plane | AXI traffic coverage | APB/AXI read/write counters and byte counters are asserted from `rtl/control_plane_metrics.json`. | pass |
| R01-E5-V004 | verification/control plane | Reset behavior | The boot reset command is checked for one reset event and the `reset_behavior` evidence token. | pass |
| R01-E5-V005 | verification/runtime ABI | Invalid descriptors | Expected negative descriptors cover `ERR_SCHEDULER_FAULT`, `ERR_MMU_FAULT`, and `ERR_FENCE_WAIT`; these are pass conditions only when the expected errors are observed. | pass |
| R01-E5-V006 | verification/runtime ABI | DMA bounds and alignment | Valid DMA/H2D/D2H commands must be 16-byte aligned and inside declared memory regions; the MMU-fault descriptor must be out of range. | pass |
| R01-E5-V007 | verification/demo/model | Throughput scaling by configured tier | Runtime demo tiers and model shader-unit tiers are checked for monotonic FP16/FP32 operation-rate metadata after shader-unit sorting. | pass |

## Harness Contract

`scripts/verify_celviz_gpgpu_ip.sh` first checks that this verification
directory contains the stable token matrix. It then probes for three local
component boundaries:

```text
compute_model
runtime
control_plane
```

The preferred artifact locations are:

```text
artifacts/rank_01_vivante_3d_gpgpu_ip/model/compute_model
artifacts/rank_01_vivante_3d_gpgpu_ip/runtime
artifacts/rank_01_vivante_3d_gpgpu_ip/control_plane
```

The script also accepts adjacent artifact locations such as `model/`, `demo/`,
`rtl/`, and future `tools/celviz_gpgpu_ip/` helpers. If any of the three
component boundaries is absent, the result is:

```text
celviz_gpgpu_ip_verification: pending
```

with exit status 0. This lets parallel workers land model/runtime/control-plane
work independently without turning missing future evidence into a false failure.

When all three boundaries exist, each boundary must expose one local entry point
such as `test_commands.sh`, `verify.sh`, `run_tests.sh`, `run.sh`, `main.py`,
`verify.py`, `run_tests.py`, `runtime.py`, or `control_plane.py`. The harness
runs shell entry points with `bash` and Python entry points with `python3`.

## Required Output Tokens

Present components must collectively emit these stable tokens to stdout/stderr
or to local JSON/log evidence files under the Rank 1 artifact tree:

```text
vector_add
gemm_convolution_image_filter
memory_copy
shader_unit_scaling
fp16_fp32_paths
command_submission
interrupts
axi_traffic
throughput_scaling_by_tier
```

The token names are deliberately stable so later implementations can evolve
from a pure compute model to a runtime-backed RTL/control-plane shell without
changing the S3 acceptance interface.

## Optional Rich Evidence

The harness now scans richer evidence when it is available:

```text
fp16_proxy_outputs
runtime_queue_phases
interrupt_error_reset_tokens
axi_apb_transaction_counters
throughput_monotonicity_cues
source_hook_axi4lite2cta_register_counters
source_hook_axi4lite2cta_csr_plumbing
source_hook_cta_scheduler_debug_counters
source_hook_warp_scheduler_debug_counters
source_hook_sim_verilator_runtime_proxy_api
source_hook_tools_runtime_cli_hooks
source_level_hook_strictness
source_hook_implementation_files_only
celviz_gpgpu_source_check
native_runtime_abi_header
native_runtime_abi_implementation
native_runtime_python_bridge
native_queue_snapshot
native_pending_count
native_named_fence
native_submit_fill
native_proxy_snapshot
native_runtime_acceptance
e1_runtime_command_stream_fixture
e1_dma_fill_copy_h2d_d2h
e1_queue_lifecycle_observability
e1_named_fence_wait_signal
e1_status_polling_expectations
e1_expected_error_injection
e2_rtl_control_plane_axi_csr_gate
e2_rtl_control_plane_doorbell_irq_error_flow
e2_rtl_control_plane_apb_axi_counter_flow
e2_scheduler_handoff_counters
e2_rtl_debug_observability_top
e2_rtl_debug_observability_warp
e3_native_runtime_build_or_relink
e3_require_runtime_bind
e3_native_queue_metric_snapshots
e4_demo_model_evidence
e4_kernel_demo_fixture
e4_vector_add_golden_compare
e4_gemm_convolution_image_filter
e4_memory_copy_golden_compare
e4_fp16_fp32_paths
e4_tier_scaling
e4_buffer_bindings
e4_dispatch_readback_golden_compare
e5_verification_coverage
e5_command_submission
e5_interrupts
e5_axi_traffic
e5_reset_behavior
e5_invalid_descriptors
e5_dma_bounds_alignment
e5_tier_throughput_scaling
optional_present_file_strictness
```

Optional evidence remains optional while other workers land new files. If a
file is present, however, it is strict: JSON must parse, logs must be non-empty,
explicit `fail`/`error` status fields fail the run, runtime queue counts must
match logged kernel entries, and throughput metadata must be monotonic after
sorting by shader-unit count.

Source hook checks follow the same present-file rule with an extra marker gate:
the harness scans the canonical Ventus and sim-verilator files, and only applies
strict real-code pattern checks when those files contain a case-insensitive
`Celviz` marker. Comments are stripped before matching hook patterns, so a
source marker without actual register, counter, or API code fails the run.
Hook evidence is restricted to implementation files (`.scala`, C/C++ headers
and sources, and `.py` tools); documentation, docs directories, and verification
prose are rejected for source-hook proof.

The command wrapper also runs `scripts/check_celviz_gpgpu_sources.sh` before the
main S3 harness. That source checker validates the native runtime ABI directly
against implementation files:

```text
sim-verilator/celviz_gpgpu_runtime_proxy.h
sim-verilator/ventus_rtlsim.cpp
tools/celviz_gpgpu_ip/runtime_proxy.py
```

It covers queue snapshot, pending count, named fence signal/wait, submit-fill,
Python ctypes bindings, `native_proxy_snapshot`, and the aggregate
`native_runtime_acceptance` source hook. These checks intentionally do not use
README files, docs, or verification prose as evidence.

## E2 RTL Control-Plane Source Gate

E2 is an implementation-source acceptance lane for the RTL control plane. It is
covered by `scripts/check_celviz_gpgpu_sources.sh`, and the acceptance matrix
records it as `e2_rtl_control_plane_source_gate`. The gate uses active RTL
implementation files only:

```text
ventus/src/axi/AXI4Lite2CTA.scala
ventus/src/cta/cta_scheduler.scala
ventus/src/top/GPGPU_top.scala
ventus/src/pipeline/warp_schedule.scala
ventus/src/pipeline/pipe.scala
```

The AXI4-Lite portion checks command, doorbell, completion, IRQ, error, APB,
and AXI counter CSRs. The current RTL does not expose separate queue head/tail
registers; queue progress is accepted through the doorbell status/count plus
command and completion counters, while E1 runtime ABI evidence owns head/tail
queue snapshots. The scheduler portion checks host workgroup and CU wavefront
handoff counters. The observability portion checks top-level and warp scheduler
debug bundles, counter wiring, masks, and `dontTouch` preservation.

## E3 Native Runtime Evidence

E3 is an artifacts/evidence lane. It records that the native Verilator runtime
proxy can build or relink, bind through the Python runtime CLI with
`--require-runtime`, and expose native queue and metric snapshots. It does not
edit runtime implementation files and does not use documentation as source hook
proof.

The recorded E3 commands are:

```sh
bash scripts/build_celviz_gpgpu_runtime.sh --auto

python3 tools/celviz_gpgpu_ip/runtime_cli.py \
  --commands artifacts/rank_01_vivante_3d_gpgpu_ip/rtl/control_plane_demo.json \
  --runtime-lib /tmp/ventus-gpgpu-celviz-build/sim-verilator/build/libVentusRTL/debug/libVentusRTL.so \
  --require-runtime \
  --output-dir /tmp/ventus-gpgpu-celviz-e3 \
  --run-log /tmp/ventus-gpgpu-celviz-e3/runtime_run.log \
  --print-status
```

The distilled evidence is stored in
`artifacts/rank_01_vivante_3d_gpgpu_ip/rtl/e3_native_runtime_evidence.json`.
The run observed `runtime_bridge=ctypes_bound`, `dry_run=false`, and
`rtlsim_library_bound=true`; native queue snapshots covered 3 queues, 9
submitted commands, 9 retired commands, and 0 pending commands. Native metrics
recorded DMA copy/fill, named-fence, byte-count, interrupt, reset, MMU-fault,
and queue-error counters. Negative-path records are expected proxy tests, not
unexpected runtime failures.

E3 evidence remains clean-room/proxy-only. It is not official Vivante
conformance, proprietary command-stream compatibility, OpenCL conformance, RTL
timing signoff, or silicon signoff.

## E4 Demo/Model Evidence

E4 is a fast demo/model evidence lane. It is covered by
`scripts/check_celviz_gpgpu_sources.sh` for checked-in artifacts and by
`scripts/accept_celviz_gpgpu_ip.sh` after `runtime_kernel_demo` for freshly
generated outputs. It does not edit tools, RTL, or simulator implementation
files.

The E4 checker parses:

```text
artifacts/rank_01_vivante_3d_gpgpu_ip/demo/kernel_demo.json
artifacts/rank_01_vivante_3d_gpgpu_ip/demo/outputs/summary.json
artifacts/rank_01_vivante_3d_gpgpu_ip/demo/outputs/kernel_metrics.json
artifacts/rank_01_vivante_3d_gpgpu_ip/demo/outputs/buffer_binds.json
artifacts/rank_01_vivante_3d_gpgpu_ip/demo/outputs/device_tiers.json
artifacts/rank_01_vivante_3d_gpgpu_ip/demo/outputs/queue_trace.json
artifacts/rank_01_vivante_3d_gpgpu_ip/model/metrics.json
artifacts/rank_01_vivante_3d_gpgpu_ip/model/outputs/*.json
```

For the full acceptance wrapper, E4 first writes a temporary
`$TMP/e4_kernel_demo.json`. If the checked-in kernel demo has not yet been
regenerated with `convolution_proxy`, that temporary fixture adds the
convolution kernel and its global read/write buffers for the runtime CLI only.
The checked-in demo artifact is left untouched so parallel fixture workers can
own it.

The pass condition is deliberately concrete: the demo must declare and run
`vector_add`, `gemm_proxy`, `image_filter`, and `memory_copy`, and the
acceptance wrapper must also run/check `convolution_proxy`; every workload must
have global read/write buffer bindings; queue trace events must cover submit,
wait, and readback with success completion; readback hashes must match the
summary golden hashes; vector add must compare result to expected data; and
memory copy must compare source and result hashes. The model side must report
FP32 operation metadata, FP16 proxy/tolerance metadata for vector add and GEMM,
convolution proxy evidence aliased to `image_filter`, memory-copy byte/hash
evidence, and monotonic tier scaling metadata.

E4 remains clean-room/proxy-only. It is not official Vivante conformance,
proprietary command-stream compatibility, OpenCL conformance, RTL timing
signoff, or silicon signoff.

## E5 Verification Coverage Evidence

E5 is a verification-evidence lane. It does not add implementation behavior;
instead, `verification/test_commands.sh` runs a targeted local probe before the
S3 harness and records explicit pass/fail lines in `test_results.log`.

The E5 probe reads:

```text
artifacts/rank_01_vivante_3d_gpgpu_ip/rtl/control_plane_demo.json
artifacts/rank_01_vivante_3d_gpgpu_ip/rtl/control_plane_metrics.json
artifacts/rank_01_vivante_3d_gpgpu_ip/demo/outputs/device_tiers.json
artifacts/rank_01_vivante_3d_gpgpu_ip/model/outputs/shader_unit_scaling.json
```

The pass condition is deliberately concrete:

- Command submission passes only when the current 19-command stream has
  matching submitted/completed counts and every recorded queue has
  `submitted == retired`.
- Interrupt coverage passes only when both completion and error interrupt
  events are present and their counters are non-zero.
- AXI coverage passes only when `axi_traffic` is true and read/write
  transaction counters plus byte counters are present.
- Reset coverage passes only when the reset evidence token is true and exactly
  one reset is recorded for the current stream.
- Invalid-descriptor coverage passes only when the expected negative descriptor
  set contains `ERR_SCHEDULER_FAULT`, `ERR_MMU_FAULT`, and `ERR_FENCE_WAIT`.
- DMA bounds/alignment coverage passes only when valid DMA/H2D/D2H commands are
  16-byte aligned and inside declared memory regions, and the MMU negative
  descriptor is out of range.
- Throughput tier coverage passes only when runtime tier metadata has at least
  four configured tiers and FP16/FP32 operation-rate fields are monotonic after
  sorting by shader-unit count.

The latest recorded local result in `test_results.log` is:

```text
e5_verification_coverage: pass
  - e5_command_submission=pass submitted=19 completed=19 queues=3
  - e5_interrupts=pass completion_interrupts=13 error_interrupts=3
  - e5_axi_traffic=pass read_tx=5 write_tx=16 bytes_read=736 bytes_written=2272
  - e5_reset_behavior=pass resets=1
  - e5_invalid_descriptors=pass expected_errors=ERR_FENCE_WAIT,ERR_MMU_FAULT,ERR_SCHEDULER_FAULT
  - e5_dma_bounds_alignment=pass valid_dma_commands=6 negative_mmu_descriptors=1
  - e5_tier_throughput_scaling=pass runtime_tiers=4 model_tiers=9
```

The same latest run also reports `celviz_gpgpu_source_check: pass` and
`celviz_gpgpu_ip_verification: pass`, with the E5 strict optional evidence
tokens present in the S3 harness summary.

E5 remains clean-room/proxy-only. It is not official Vivante conformance,
proprietary command-stream compatibility, OpenCL conformance, RTL timing
signoff, measured throughput, or silicon signoff.

## E8 Supplemental Verilator Coverage Gate

E8 is a supplemental Verilator coverage lane for the clean-room Ventus/Celviz
GPGPU proxy. It is intentionally separate from E5 functional verification:
Verilator source/toggle/line coverage describes structural RTL exercise in the
generated model, while functional coverage describes whether the declared
clean-room proxy behavior was observed and checked.

The E8 matrix entry names this run script:

```sh
bash scripts/run_celviz_gpgpu_verilator_coverage.sh \
  --output-dir artifacts/rank_01_vivante_3d_gpgpu_ip/verification/verilator_coverage
```

Existing E8 artifacts can be checked without rebuilding the Verilated model:

```sh
bash scripts/verify_celviz_gpgpu_verilator_coverage.sh \
  --output-dir artifacts/rank_01_vivante_3d_gpgpu_ip/verification/verilator_coverage
```

The full local acceptance wrapper runs the main E0-E7 suite and then validates
the existing E8 coverage bundle:

```sh
bash scripts/accept_celviz_gpgpu_ip_full.sh
```

To regenerate E8 before the full check, use:

```sh
bash scripts/accept_celviz_gpgpu_ip_full.sh --rerun-e8
```

The full wrapper also regenerates the aggregate 100% functional/acceptance
verification coverage report:

```sh
bash scripts/verify_celviz_gpgpu_coverage_100.sh
```

This report requires every declared clean-room verification bin to pass across
E1 command stream coverage, E3 native runtime evidence, E4 kernel/golden/model
coverage, E5 control-plane and negative-boundary coverage, E6 integration
checks, E7 one-key acceptance markers, and E8 Verilator functional bins. RTL
structural line/source/toggle coverage remains a separate observation and is
not converted into a 100% claim.

Phase-2 hardening evidence is also checked by the full wrapper:

```sh
bash scripts/verify_celviz_gpgpu_phase2.sh --run-focused
```

The phase-2 gate covers six focused lanes: SIMT compute-core execution evidence,
OpenCL-like subset kernel ABI evidence, global/local/constant memory-system
evidence, Linux userspace DRM-like runtime proxy evidence, supplemental
directed/random/fault/stress RTL-verification fixture evidence, and
synthesis/PPA proxy evidence. Each lane remains clean-room/proxy-scoped and does
not claim proprietary Vivante compatibility, OpenCL conformance, Linux kernel
driver completion, RTL structural coverage closure, synthesis signoff, or
silicon readiness.

Phase-3 cross-layer evidence checks that the phase-2 lanes line up as one stack:

```sh
bash scripts/verify_celviz_gpgpu_phase3.sh
```

The cross-layer gate maps OpenCL-like kernel ABI names to runtime command
dispatches and SIMT workload names, confirms ABI metadata and global argument
coverage, checks SIMT LSU activity against memory load/store/DMA evidence,
checks runtime command completion against Linux userspace submit/fence/event
evidence, and ties supplemental RTL-verification targets plus PPA proxy evidence
back to the same clean-room scope.

Phase-4 kernel lowering evidence adds a deterministic clean-room micro-op layer:

```sh
bash scripts/verify_celviz_gpgpu_phase4.sh
```

This lowers each OpenCL-like subset kernel ABI into Celviz micro-ops such as
kernel prologue, work-item ID read, bounds predicate, address calculation,
global loads, ALU operations, loop markers, optional barrier, global stores, and
completion writeback. The integration gate checks those lowered kernels against
runtime dispatches, SIMT workload names, memory load/store/DMA evidence, and the
phase-3 cross-layer report. It is still not a production compiler backend, ISA
compatibility claim, SPIR-V/LLVM flow, or proprietary command-stream claim.

The expected artifact bundle is:

```text
artifacts/rank_01_vivante_3d_gpgpu_ip/verification/verilator_coverage/coverage.dat
artifacts/rank_01_vivante_3d_gpgpu_ip/verification/verilator_coverage/coverage.info
artifacts/rank_01_vivante_3d_gpgpu_ip/verification/verilator_coverage/report/index.html
artifacts/rank_01_vivante_3d_gpgpu_ip/verification/verilator_coverage/report/dut.v
artifacts/rank_01_vivante_3d_gpgpu_ip/verification/verilator_coverage/run.log
artifacts/rank_01_vivante_3d_gpgpu_ip/verification/verilator_coverage/verilator_coverage_report.json
```

`coverage.dat` is the raw Verilator coverage database emitted by the simulated
model, and `coverage.info` plus `report/index.html` are derived structural
coverage views. `run.log` must record the Verilator coverage command, output
paths, workload or command fixture used, functional coverage bin summary, and
the clean-room/no-overclaim boundary.

The E8 pass condition is deliberately split:

- RTL structural coverage passes only as artifact production: the run must
  produce non-empty Verilator `coverage.dat` and `coverage.info`, plus a
  generated report and log. Source, line, and toggle percentages are reported
  as structural RTL exercise metrics.
- Functional coverage passes only when every declared clean-room functional bin
  is PASS, yielding an aggregate functional coverage result of 100%.
- A 100% functional coverage result does not mean 100% RTL line/toggle/source
  coverage. Conversely, high RTL structural coverage does not replace functional
  evidence.

The declared functional bins are command submission, queue lifecycle closure,
completion interrupt, error interrupt, AXI/APB traffic, reset behavior, invalid
descriptor errors, DMA bounds/alignment, memory copy/fill/H2D/D2H, vector-add
golden compare, GEMM/convolution/image-filter golden compare, FP16/FP32 paths,
and configured-tier scaling.

E8 remains clean-room/proxy-only. It is not licensed vendor collateral review,
proprietary Vivante command-stream compatibility, official Vivante conformance,
official OpenCL conformance, RTL timing closure, CDC/STA/DFT closure,
production PPA, or silicon signoff.

## E1 Runtime ABI Fixture Coverage

E1 fixture evidence is rooted in runnable JSON rather than runtime source
changes. `rtl/control_plane_demo.json` remains on
`celviz.gpgpu.control_plane_demo.v1`, which is accepted by both
`control_plane.py` and `runtime_cli.py --commands`. The stream now covers:

- DMA and runtime memory movement: `host_to_device`, `device_to_host`,
  `dma_fill`, and `dma_copy`.
- Queue lifecycle visibility across queues 0, 1, and 2, including expected
  submitted/retired/head/tail/error observations.
- Named-fence signal/wait paths for `copy_ready` and `staging_copy_ready`.
- Status polling expectations for queued, complete, error, timeout, and sticky
  error states, tied to completion records, status registers, counter
  snapshots, and interrupt events.
- Expected negative paths for scheduler fault, MMU fault, and fence wait
  timeout. These are intentional pass conditions only when the observed error
  code matches the fixture.

`demo/kernel_demo.json` references the command-stream fixture and exercises two
runtime queues in kernel-demo mode. `queue0` carries the compute kernels while
`queue1` carries the memory-copy runtime workload, so the runtime queue trace
continues to validate submit/wait/readback lifecycle phases without requiring
runtime source changes.

## Running

Use the local verification entry:

```sh
./scripts/verify_celviz_gpgpu_ip.sh
```

Or use the artifact command list, which also writes `test_results.log`:

```sh
./artifacts/rank_01_vivante_3d_gpgpu_ip/verification/test_commands.sh
```

Expected results:

- `pending` when `compute_model`, `runtime`, or `control_plane` is absent.
- `pass` when all three boundaries exist, run successfully, and collectively
  emit all required S3 tokens, with present optional evidence well formed.
- `fail` when a present boundary has no runnable entry point, exits non-zero,
  writes invalid JSON evidence, omits a required token, or present optional
  evidence is malformed. A source file that contains a Celviz marker but lacks
  the corresponding AXI4Lite2CTA register/counter, scheduler debug-counter, or
  sim-verilator runtime proxy API hook is also a failure. Native runtime ABI
  source hooks fail when queue snapshot, pending count, named fence,
  submit-fill, `native_proxy_snapshot`, or `native_runtime_acceptance` evidence
  is missing from implementation files. E2 fails when RTL implementation files
  no longer expose queue doorbell/progress CSRs, IRQ/error/APB/AXI counters,
  scheduler handoff counters, or `dontTouch`-preserved debug observability. E4
  fails when demo/model JSON evidence no longer covers the required workloads,
  FP16/FP32 paths, tier scaling, buffer bindings, dispatch/readback phases, or
  golden comparisons. E5 fails when the evidence probe cannot prove command
  submission closure, completion/error interrupts, AXI/APB traffic counters,
  reset token/counter behavior, expected invalid descriptors, aligned in-range
  DMA plus out-of-range MMU negative coverage, or configured-tier throughput
  monotonicity.

## Evidence Notes

This S3 plan is proxy-level validation for a clean-room Celviz GPGPU IP path.
Passing it does not claim equivalence to proprietary Vivante RTL, firmware,
drivers, shader compilers, SDKs, or official conformance suites.
