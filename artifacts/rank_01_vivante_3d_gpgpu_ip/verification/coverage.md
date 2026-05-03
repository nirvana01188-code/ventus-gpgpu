# Rank 1 S3 Verification Coverage

Status: pass for the current local compute model, runtime demo,
control-plane configuration evidence, E1 command/evidence fixtures, E2 RTL
control-plane source hooks, E3 native runtime evidence, E4 demo/model evidence,
E5 verification coverage evidence, and present source hooks. Missing future
optional evidence is reported as skipped; malformed present optional evidence
fails the run.

## Coverage Matrix

| Coverage item | Acceptance anchor | Planned stimulus | Expected check | Evidence source | State |
| --- | --- | --- | --- | --- | --- |
| Vector add | Rank 1 requires basic data-parallel compute evidence. | Run a deterministic vector add kernel across at least one baseline tier. | Output includes `vector_add` plus checked result metadata. | Compute model stdout, `metrics.json`, or `run.log`. | pass |
| GEMM/convolution/image filter | Rank 1 requires representative tensor and image-filter compute paths. | Run GEMM, convolution, or image-filter kernels with deterministic inputs. | Output includes `gemm_convolution_image_filter` plus checksum or tolerance data. | Compute model evidence. | pass |
| Memory copy | Runtime must move host/device/device data without corruption. | Exercise H2D, D2H, and D2D copy paths with byte-count checks. | Output includes `memory_copy` and integrity status. | Runtime evidence. | pass |
| Shader-unit scaling | Scaling must be visible as shader-unit or compute-lane count changes. | Run the same workload across multiple shader-unit configurations. | Output includes `shader_unit_scaling`; results remain stable while counters change. | Compute model/runtime evidence. | pass |
| FP16/FP32 paths | Numeric paths must cover half and single precision. | Run FP16 and FP32 variants of vector/tensor workloads. | Output includes `fp16_fp32_paths` and tolerance metadata. | Compute model evidence. | pass |
| Command submission | Runtime/control plane must accept work descriptors. | Submit at least one command queue packet and poll fence/completion status. | Output includes `command_submission`. | Runtime/control-plane evidence. | pass |
| Interrupts | Control plane must report completion and fault interrupt behavior. | Trigger completion and recoverable fault interrupt paths. | Output includes `interrupts` and recoverable status details. | Control-plane evidence. | pass |
| AXI traffic | SoC integration must expose command/data traffic. | Count AXI-lite control and AXI data transactions during work submission. | Output includes `axi_traffic` with read/write counters. | Control-plane/runtime evidence. | pass |
| Throughput scaling by tier | Rank 1 tiers must show throughput scaling or documented plateaus. | Run vector/tensor/image workloads across small, mid, and high tier profiles. | Output includes `throughput_scaling_by_tier` with monotonic or explained throughput. | Cross-component evidence. | pass |
| Harness pending/pass/fail semantics | S3 entry must be safe for parallel development. | Run `test_commands.sh` before and after components are added. | Missing components are pending exit 0; present broken components fail. | `scripts/verify_celviz_gpgpu_ip.sh`; `test_results.log`. | pass |
| FP16 proxy outputs | FP16 path is currently proxy metadata, not a real FP16 execution engine. | Parse present workload JSON and metrics. | Present `fp16_proxy` objects have status/method and valid optional samples. | Model output JSON. | pass |
| Runtime queue phases | Runtime queue evidence must be internally consistent. | Parse `demo/run.log` and `demo/outputs/summary.json`. | `kernel_count` matches logged `kernel[n]` entries and summary kernels. | Runtime demo log/output JSON. | pass |
| Interrupt/error/reset tokens | Control plane must expose completion, fault, and reset vocabulary. | Parse control config, smoke log, and register map text. | Tokens for interrupt, error, and reset are present. | RTL control-plane evidence. | pass |
| AXI/APB transaction counters | Counter evidence may land incrementally. | Scan present control/runtime metrics and logs. | AXI evidence is present; APB is accepted when present and skipped when absent. | Control-plane/runtime evidence. | pass |
| Throughput monotonicity cues | Public tier metadata is not in strict size order by product family. | Sort tiers by shader-unit count before checking ops/cycle. | FP16/FP32 operation-rate cues are non-decreasing after sorting. | Model scaling JSON/metrics. | pass |
| AXI4Lite2CTA Celviz source hooks | Optional source hook must be real when advertised. | Scan `ventus/src/axi/AXI4Lite2CTA.scala` for a Celviz marker. | Marker absent is skipped; marker present requires Celviz-named register/counter storage and AXI4-Lite channel logic after comments are stripped. | S3 harness source scan. | pass |
| AXI4Lite2CTA CSR plumbing | Optional CSR hook must be real when advertised. | Scan `ventus/src/axi/AXI4Lite2CTA.scala` for a Celviz marker. | Marker present requires command doorbell, interrupt, error, completion, and AXI/APB counter CSRs wired to register storage and channel events. | S3 harness source scan. | pass |
| CTA scheduler debug counters | Optional source hook must be real when advertised. | Scan `ventus/src/cta/cta_scheduler.scala` for a Celviz marker. | Marker absent is skipped; marker present requires Celviz-named debug counter storage tied to CTA scheduler handshake/completion paths. | S3 harness source scan. | pass |
| Warp scheduler debug counters | Optional source hook must be real when advertised. | Scan `ventus/src/pipeline/warp_schedule.scala` for a Celviz marker. | Marker absent is skipped; marker present requires Celviz-named debug counter storage tied to warp scheduler request/response/control/ready paths. | S3 harness source scan. | pass |
| sim-verilator Celviz runtime proxy API | Optional runtime proxy API must be real when advertised. | Scan `sim-verilator/ventus_rtlsim.*` and `sim-verilator/celviz_gpgpu_runtime_proxy.h`. | Marker absent is skipped; marker present requires public API declarations, proxy type storage, and hooks into rtlsim enqueue, copy, and status paths. | S3 harness source scan. | pass |
| tools runtime CLI hooks | Runtime command-line hook must be real when present. | Scan `tools/celviz_gpgpu_ip/runtime_cli.py`. | Requires argparse options, kernel-demo validation, queue trace/status JSON output, and compute-model subprocess wiring. | S3 harness source scan. | pass |
| Source-level hook strictness | Future source work must not pass with marker-only comments. | Strip comments before matching real hook patterns. | Missing optional hooks are skipped; Celviz-marked files without real source hooks fail. | S3 harness. | pass |
| Implementation-only source evidence | Source hooks must not be satisfied by documentation. | Restrict source-hook paths to implementation suffixes and reject docs/verification paths. | `.md`, docs directories, and verification prose cannot satisfy source hook proof. | S3 harness source scan. | pass |
| Optional present-file strictness | Future workers can add files without weakening S3. | Parse optional JSON/log evidence if present. | Missing optional files are skipped; malformed present files fail. | S3 harness. | pass |
| E1 runtime command stream fixture | Runtime ABI evidence must be runnable without source edits. | Run `runtime_cli.py --commands rtl/control_plane_demo.json --dry-run` through the existing acceptance path. | Command stream parses under the current control-plane schema and reports pass with expected negative errors. | `rtl/control_plane_demo.json`; runtime dry-run metrics. | pass |
| E1 DMA fill/copy/H2D/D2H | Memory movement should cover runtime command categories, not only kernel-demo memory copy. | Submit `host_to_device`, `dma_fill`, `dma_copy`, and `device_to_host` commands with completion writebacks. | Completion records show successful movement commands and counters capture bytes/read/write traffic. | Control-plane and runtime command-stream metrics. | pass |
| E1 queue lifecycle observability | ABI evidence should show queue state transitions across multiple queues. | Exercise queues 0, 1, and 2 with command submission, fence synchronization, snapshots, and expected errors. | Queue state records submitted, retired, head, tail, and error counts; expected errors remain isolated to negative commands. | `e1_runtime_abi_expectations.queue_lifecycle`; metrics queue state. | pass |
| E1 named fence wait/signal | Runtime ABI should cover named fence success and timeout paths. | Signal and wait on `copy_ready` and `staging_copy_ready`, then wait on `never_signaled`. | Successful waits observe the requested values; timeout returns expected `ERR_FENCE_WAIT`. | Completion records and final fence map. | pass |
| E1 status polling and expected errors | Polling expectations must distinguish complete work from intentional failures. | Annotate queued/complete/error/timeout/sticky-error expectations and inject scheduler, MMU, and fence errors. | Fixture passes only when `ERR_SCHEDULER_FAULT`, `ERR_MMU_FAULT`, and `ERR_FENCE_WAIT` match the expected errors. | Command fixture metadata and completion records. | pass |
| E2 RTL control-plane CSR gate | RTL control-plane acceptance must be grounded in active implementation files. | Run `bash scripts/check_celviz_gpgpu_sources.sh`. | `AXI4Lite2CTA.scala` contains command, queue doorbell/progress, completion, IRQ, error, APB, and AXI counter CSRs. | Source checker; `ventus/src/axi/AXI4Lite2CTA.scala`. | pass |
| E2 doorbell/IRQ/error flow | Doorbell and completion/fault behavior must be observable at the CSR source level. | Scan write, response, and read paths in `AXI4Lite2CTA.scala`. | Doorbell accept/busy, completion IRQ, error IRQ, IRQ pending, IRQ counter, and error counter paths are present. | Source checker; `ventus/src/axi/AXI4Lite2CTA.scala`. | pass |
| E2 APB/AXI counters | SoC-facing control traffic must be counted and preserved. | Scan AXI4-Lite read/write handshake paths. | APB/AXI read/write counters and read/write fire pulses are present and `dontTouch`-protected. | Source checker; `ventus/src/axi/AXI4Lite2CTA.scala`. | pass |
| E2 scheduler handoff counters | RTL scheduler evidence must cover host-to-CTA and CTA-to-CU handoffs. | Scan CTA scheduler handshake paths. | Host workgroup accept/done counters, CU wavefront dispatch/done counters, and allocation busy cycle counts are wired to debug output. | Source checker; `ventus/src/cta/cta_scheduler.scala`. | pass |
| E2 debug observability and dontTouch | Debug evidence must survive through the top-level and scheduler hierarchy. | Scan top, pipe, and warp scheduler debug wiring. | Top-level GPGPU debug, CTA debug, warp debug, masks, counters, and `dontTouch` preservation are present. | Source checker; `ventus/src/top/GPGPU_top.scala`, `ventus/src/pipeline/warp_schedule.scala`, `ventus/src/pipeline/pipe.scala`. | pass |
| E3 native runtime build/relink | Native runtime evidence must show a buildable or relinkable Verilator proxy artifact. | Run `bash scripts/build_celviz_gpgpu_runtime.sh --auto` against the local temporary build root. | Command exits 0 and reports `CELVIZ_GPGPU_RUNTIME_LIB` for `libVentusRTL.so`. | `rtl/smoke.log`; `rtl/e3_native_runtime_evidence.json`. | pass |
| E3 require-runtime binding | Runtime CLI must fail closed when native binding is requested and succeed when the shared library is present. | Run `runtime_cli.py --commands rtl/control_plane_demo.json --runtime-lib ... --require-runtime`. | Output records `runtime_bridge=ctypes_bound`, `dry_run=false`, `rtlsim_library_bound=true`, and native runtime acceptance pass. | `rtl/smoke.log`; `rtl/e3_native_runtime_evidence.json`; temporary `/tmp/ventus-gpgpu-celviz-e3/` outputs. | pass |
| E3 queue and metric snapshots | Native runtime evidence must expose queue/pending/metric observability. | Read runtime C ABI snapshots after the command stream executes. | Snapshot records 3 native queues, 9 submitted, 9 retired, 0 pending, byte counters, DMA counters, fence counters, interrupt counters, reset count, and expected negative-path counters. | `rtl/e3_native_runtime_evidence.json`. | pass |
| E4 workload coverage | Demo/model evidence must prove compute, tensor, image, and memory workloads. | Parse kernel demo, generated runtime outputs, model outputs, and the temporary `$TMP/e4_kernel_demo.json` fixture created by acceptance when convolution has not yet landed in the checked-in demo fixture. | `vector_add`, `gemm_proxy`, `convolution_proxy`/`image_filter`, and `memory_copy` are present and passing. | `demo/kernel_demo.json`; `$TMP/e4_kernel_demo.json`; `demo/outputs/*.json`; `model/outputs/*.json`. | pass |
| E4 FP16/FP32 paths | Demo/model evidence must preserve numeric precision metadata. | Parse model metrics and workload outputs. | FP32 operation counts and FP16 proxy/tolerance metadata exist for vector add and GEMM; image/convolution FP16 metadata is present. | `model/metrics.json`; `model/outputs/vector_add.json`; `model/outputs/gemm_proxy.json`; `model/outputs/convolution_proxy.json`. | pass |
| E4 tier scaling | Demo/model evidence must show scaling cues across public proxy tiers. | Sort demo and model tiers by shader-unit count. | FP16 and FP32 ops/cycle are monotonic after sorting, with at least four runtime tiers. | `demo/outputs/device_tiers.json`; `model/outputs/shader_unit_scaling.json`. | pass |
| E4 buffer bindings | Runtime demo evidence must bind buffers explicitly. | Parse kernel args, `buffer_binds.json`, and queue submit events. | Every workload has global read/write buffer bindings backed by declared buffers. | `demo/kernel_demo.json`; `demo/outputs/buffer_binds.json`; `demo/outputs/queue_trace.json`. | pass |
| E4 dispatch/readback/golden compare | Runtime demo evidence must prove completed work and checked results. | Parse queue trace, summary hashes, and per-workload output files. | Every workload has submit/wait/readback events, readback SHA matches the summary golden hash, vector add matches expected data, and memory-copy source/result hashes match. | `demo/outputs/queue_trace.json`; `demo/outputs/summary.json`; `demo/outputs/vector_add.json`; `demo/outputs/memory_copy.json`. | pass |
| E5 command submission closure | Verification coverage must make queue submission closure explicit. | Run the E5 probe in `verification/test_commands.sh` against control-plane demo and metrics JSON. | The current command stream has 19 submitted commands, 19 completed commands, and every queue snapshot has `submitted == retired`. | `rtl/control_plane_demo.json`; `rtl/control_plane_metrics.json`; `verification/test_results.log`. | pass |
| E5 interrupts | Verification coverage must distinguish normal completion from fault signaling. | Parse interrupt counters and interrupt event kinds. | Completion and error interrupt event kinds are present; counters are non-zero and currently report 13 completion interrupts and 3 expected error interrupts. | `rtl/control_plane_metrics.json`; `verification/test_results.log`. | pass |
| E5 AXI traffic | Verification coverage must prove traffic counters are not merely prose tokens. | Parse `evidence_tokens.axi_traffic`, APB/AXI counters, and byte counters. | AXI read/write transactions are non-zero and byte counters currently report 736 read bytes and 2272 written bytes. | `rtl/control_plane_metrics.json`; `rtl/control_plane_run.log`; `verification/test_results.log`. | pass |
| E5 reset behavior | Verification coverage must prove reset is exercised and observable. | Parse reset command, reset evidence token, and reset counter. | Exactly one reset is recorded and the reset completion message clears queues, sticky status, fences, interrupts, and completion records. | `rtl/control_plane_demo.json`; `rtl/control_plane_metrics.json`; `rtl/control_plane_run.log`. | pass |
| E5 invalid descriptors | Verification coverage must include negative descriptors as expected pass cases. | Parse command descriptors with `expect_error`. | Expected negative descriptors cover `ERR_SCHEDULER_FAULT`, `ERR_MMU_FAULT`, and `ERR_FENCE_WAIT`; any mismatch fails the probe. | `rtl/control_plane_demo.json`; `rtl/control_plane_metrics.json`; `verification/test_results.log`. | pass |
| E5 DMA bounds and alignment | Verification coverage must assert both valid DMA shape and a bounds negative path. | Check valid DMA/H2D/D2H commands for 16-byte alignment and declared memory-region containment, then check the MMU negative descriptor is out of range. | Six valid movement commands are aligned/in range, and one expected MMU-fault descriptor is out of range. | `rtl/control_plane_demo.json`; `rtl/control_plane_metrics.json`; `verification/test_results.log`. | pass |
| E5 throughput scaling by configured tier | Verification coverage must pin throughput scaling to configured proxy tiers. | Parse runtime tier metadata and model shader-unit scaling metadata. | Runtime tiers include at least nano/micro/small/full rows; FP16/FP32 operation-rate metadata is monotonic after sorting by shader-unit count. | `demo/outputs/device_tiers.json`; `model/outputs/shader_unit_scaling.json`; `verification/test_results.log`. | pass |

## Readiness Gates

| Gate | Required before marking pass | Current disposition |
| --- | --- | --- |
| S3 harness exists | `scripts/verify_celviz_gpgpu_ip.sh` is present and runnable. | pass |
| Command wrapper exists | `verification/test_commands.sh` calls the harness and writes `test_results.log`. | pass |
| Stable token contract exists | README, coverage, and command wrapper list all Rank 1 required tokens. | pass |
| Compute model exists | A local `compute_model` or accepted model boundary exists with a runnable entry point. | pass |
| Runtime exists | A local `runtime` or accepted demo/runtime boundary exists with a runnable entry point. | pass |
| Control plane exists | A local `control_plane` or accepted RTL/control boundary exists with a runnable entry point. | pass |
| Execution output is checkable | Combined component output contains all required stable tokens. | pass |
| Optional evidence strictness | Present optional JSON/log/control-plane evidence is well formed. | pass |
| E1 command fixture compatibility | `runtime_cli.py --commands` accepts `rtl/control_plane_demo.json` in dry-run mode. | pass |
| E2 RTL source gate compatibility | `scripts/check_celviz_gpgpu_sources.sh` accepts the E2 RTL control-plane source hooks without requiring RTL implementation edits. | pass |
| E3 native runtime evidence | Native build/relink, `--require-runtime` binding, and queue/metric snapshots are recorded without runtime implementation edits. | pass |
| E4 demo/model evidence | Checked-in artifacts and freshly generated runtime demo outputs prove workloads, FP16/FP32 metadata, tier scaling, buffer bindings, and dispatch/readback/golden compares. | pass |
| E5 verification coverage evidence | `test_commands.sh` proves command submission, interrupts, AXI traffic, reset behavior, invalid descriptors, DMA bounds/alignment, and tier throughput scaling from current artifacts, then completes source check and S3 verification. | pass |

## Pass, Pending, And Fail Rules

`pass` means every required Rank 1 component boundary exists, runs locally, exits
successfully, collectively emits all required S3 tokens, and any present optional
rich evidence is well formed.

`pending` means one or more of `compute_model`, `runtime`, or `control_plane` is
not present yet. This is an expected state while workers land those components
in parallel, and it exits 0.

`fail` means present required evidence is malformed or non-runnable: a component
exists without an entry point, a component exits non-zero, JSON evidence cannot
be parsed, required tokens are absent after all present components run, runtime
queue counts are inconsistent, explicit fail/error status appears, or present
optional evidence is malformed. For E5, the command wrapper also fails when the
targeted evidence probe cannot prove command submission closure,
completion/error interrupts, AXI/APB traffic counters, reset behavior, expected
invalid descriptors, DMA bounds/alignment, or configured-tier throughput
monotonicity.

The command wrapper writes the complete transcript to:

```text
artifacts/rank_01_vivante_3d_gpgpu_ip/verification/test_results.log
```

## Required Output Tokens

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

These names describe clean-room proxy evidence only. They do not represent
official Vivante conformance or proprietary implementation behavior.
