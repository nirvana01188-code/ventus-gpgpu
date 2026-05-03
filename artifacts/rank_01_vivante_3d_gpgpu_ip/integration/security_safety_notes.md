# Security And Safety Notes

Date: 2026-05-02

Status: `pass_proxy`.

This file records non-goals and risk boundaries for the Rank 1 Celviz GPGPU IP
clean-room proxy. It is intentionally conservative: E5 provides functional
robustness evidence for invalid descriptors, DMA bounds/alignment checks,
interrupt clear, and reset recovery, but it does not create a product security,
safety, certification, or signoff claim.

## Claim Boundary

This work package does not claim:

- Safety certification.
- ASIL, ISO 26262, IEC 61508, DO-254, or similar process compliance.
- Secure boot, trusted execution, protected content, DRM, key isolation, or
  anti-tamper behavior.
- Side-channel resistance.
- Multi-tenant isolation.
- Production MMU security.
- Silicon signoff, tapeout readiness, or product qualification.
- Official OpenCL/OpenCV/API conformance.
- Proprietary Vivante security, safety, firmware, driver, or hardware
  behavior.

Explicit E6-B non-goals:

| Non-goal | Reason |
| --- | --- |
| Security certification | The evidence is functional proxy verification only; no threat model, secure development lifecycle, penetration test, or certification process is supplied. |
| Safety certification | Reset and interrupt smoke tests are not diagnostic coverage, FMEDA/FMEA, ASIL evidence, or safety mechanism proof. |
| DMA security boundary | Bounds/alignment checks reject local proxy descriptors; they do not prove containment against a malicious host, hostile kernel, IOMMU bypass, or arbitrary physical memory access. |
| Interrupt-controller security | Interrupt status/clear observability does not establish privilege separation, masking policy security, firmware behavior, or side-channel resistance. |
| Reset-domain signoff | Reset recovery logs do not establish reset-domain crossings, metastability handling, DFT/scan behavior, or silicon reset/timing signoff. |
| Clock signoff | Proxy cycle estimates and single-clock assumptions do not establish CDC, STA, frequency, voltage, power, or implementation closure. |

## Security-Relevant Architecture Hooks

| Hook | Clean-room use | Limitation |
| --- | --- | --- |
| MMU/TLB/ASID structures | Proxy address-translation, context, and fault tests. | Not a certified or product security boundary. |
| Descriptor validation | Catch malformed OpenCL-like descriptors before execution. | Does not prove hostile-driver or hostile-kernel containment. |
| Fault status | Record invalid descriptor, unsupported feature, timeout, or MMU/fault proxy. | Not a complete threat model. |
| Reset path | Recover from selected proxy faults. | Not fault-containment certification. |
| Interrupt mask/status/clear | Observe completion and recoverable fault paths. | Not an interrupt-controller security claim. |

Current E5 security-relevant proxy evidence:

| Evidence item | Source | Observed value | Accepted meaning | Forbidden inference |
| --- | --- | --- | --- | --- |
| Invalid descriptor rejection | `rtl/e5_outputs/negative_boundary_check.log` and `negative_boundary_evidence.json` | `invalid_descriptors=5`; bad magic, bad version, bad length, unsupported opcode, and bad queue are covered. | Malformed local descriptors produce expected proxy error records. | Hostile driver containment, ABI security, or production input hardening. |
| DMA bounds checks | `rtl/e5_outputs/negative_boundary_check.log` and `negative_boundary_evidence.json` | `dma_bounds_alignment=5`; range and alignment bits are observed. | Local proxy catches selected out-of-range or unaligned DMA descriptors. | DMA isolation for arbitrary physical memory or IOMMU-grade protection. |
| Fault/error interrupt path | `rtl/control_plane_metrics.json` | `error_interrupts=3`, `interrupt_clears=16`; E5 expected errors include scheduler fault, MMU/DMA bounds fault, and fence wait timeout. | Recoverable proxy faults are observable and clearable. | Interrupt-controller security, firmware behavior, or privilege isolation. |
| Reset recovery | `rtl/control_plane_metrics.json.runtime_control_evidence.reset_recovery` | Reset asserted; queue idle after reset; interrupt and fault status clear; post-reset smoke pass. | Selected proxy faults can be cleared before known-good work resumes. | Safety-rated fault containment or silicon reset-domain signoff. |
| Negative-boundary reset flush | `rtl/e5_outputs/negative_boundary_evidence.json` | Two reset pending/active scenarios; sticky error and pending state clear after reset. | Pending DMA and active dispatch flush behavior is documented at proxy level. | DFT, scan, CDC, STA, or tapeout readiness. |

## Safety-Relevant Architecture Hooks

| Hook | Clean-room use | Limitation |
| --- | --- | --- |
| Deterministic model outputs | Regression evidence for fixed workloads. | Not diagnostic coverage. |
| Post-reset smoke command | Basic recovery evidence. | Not latent-fault metric or safety mechanism proof. |
| Error taxonomy | Human-readable triage for verification. | Not FMEDA/FMEA evidence. |
| Watchdog or timeout proxy | Future recoverable-fault stimulus. | Not safety-rated watchdog design. |

Current E5 safety-relevant proxy evidence:

| Evidence item | Source | Observed value | Accepted meaning | Forbidden inference |
| --- | --- | --- | --- | --- |
| Post-reset smoke | `rtl/control_plane_metrics.json.runtime_control_evidence.reset_recovery` and `rtl/e5_verification_demo.json` | `post_reset_smoke_status=pass`; E5 fixture resets at sequence 10 and runs `e5-post-reset-smoke-fill` at sequence 11. | A known-good proxy command runs after reset recovery. | Safety mechanism coverage or latent-fault detection. |
| Interrupt clear after faults | `rtl/control_plane_metrics.json.interrupt_events` | Clear events are paired with completion/error interrupt events; `interrupt_clears=16`. | Local control-plane state can acknowledge observed completion/fault notifications. | Certified interrupt handling or fault-tolerant architecture. |
| Timeout/fence fault | `rtl/control_plane_run.log`, sequence 19 | Expected `ERR_FENCE_WAIT` timeout is recorded and clearable. | A recoverable timeout stimulus exists in the proxy taxonomy. | Safety-rated watchdog design. |
| Verification gate | `verification/test_results.log` | `e5_verification_coverage: pass`, including reset behavior, invalid descriptors, DMA bounds/alignment, and interrupts. | The active clean-room artifact gate accepts the robustness evidence. | Product qualification, API conformance, or silicon signoff. |

## Threats Not Covered

- Malicious kernel code.
- Malicious host driver.
- Cross-process or cross-VM isolation.
- DMA containment against arbitrary physical memory.
- Cache timing or power side channels.
- Fault injection resistance.
- Rowhammer or memory-system attacks.
- Secure firmware update or rollback protection.
- Protected media or confidential-compute workloads.

## Evidence Handling Rules

1. Record malformed descriptors and recoverable faults as verification evidence,
   not as security certification.
2. Treat MMU and ASID evidence as functional proxy evidence unless a dedicated
   security analysis exists.
3. Keep public product labels separate from local implementation claims.
4. Do not infer security from deterministic model hashes.
5. Do not infer safety from reset or interrupt smoke tests.

## Current Status

| Area | State | Notes |
| --- | --- | --- |
| Descriptor validation | `pass_proxy` | Runtime demo validates descriptors; E5 negative-boundary evidence adds 5 invalid descriptor cases. |
| MMU/fault evidence | `pass_proxy` | Control-plane and E5 evidence record expected MMU/DMA bounds, scheduler, and fence-wait faults. |
| DMA bounds/alignment | `pass_proxy` | E5 negative-boundary evidence records range and alignment coverage; valid DMA commands remain aligned/in-bounds. |
| Reset recovery | `pass_proxy` | E5 records boot reset, post-fault reset plus smoke, and two pending/active flush cases. |
| Interrupt recovery | `pass_proxy` | E5 records 13 completion interrupts, 3 error interrupts, and 16 clears. |
| Clock/reset assumptions | `pass_proxy` | Single proxy clock and cycle-domain performance assumptions are disclosed; no CDC/STA claim is made. |
| Safety certification | `forbidden` | Outside this clean-room proxy package. |
| Product security claim | `forbidden` | Outside this clean-room proxy package. |

## Residual Future Evidence

Future workers can improve confidence without changing the claim boundary by
adding:

- RTL-backed reset-domain and CDC observations, clearly labeled as implementation
  evidence rather than security or safety signoff.
- More MMU/fault proxy tests with explicit address, permission, queue, and
  command id fields.
- Interrupt mask/enable negative tests in addition to status/clear tests.
- Repeated reset-after-fault smoke tests across multiple queues and workloads.
- Hostile-input fuzzing, only if it is labeled as robustness testing and not as
  a security certification.

These would strengthen functional robustness evidence only. They would still
not establish product security or safety certification.

## Functional Robustness Gate

The S5 gate may cite security/safety evidence only as functional robustness.
Acceptable evidence:

| Evidence | Accepted meaning | Forbidden inference |
| --- | --- | --- |
| Invalid descriptor fault | The proxy rejects a malformed local descriptor. | Hostile driver containment or product security. |
| Out-of-range buffer fault | The proxy bounds check fired in a local test. | DMA isolation for arbitrary physical memory. |
| MMU/fault proxy code | A local fault taxonomy and status path exists. | Production MMU security. |
| Reset-after-fault pass | The proxy can recover from a selected test fault. | Safety-rated fault containment. |
| Interrupt mask/clear test | Completion/fault notification is observable. | Certified interrupt-controller behavior. |

Required robustness tokens before S5 pass:

```text
invalid_descriptor_rejected
fault_code
fault_interrupt
post_fault_smoke_status=pass
claim_scope=functional_proxy_only
```

Current E5/E6-B token disposition:

| Token | Current source | Result |
| --- | --- | --- |
| `invalid_descriptor_rejected` | `negative_boundary_check.log`: `invalid_descriptors=5`. | `pass_proxy` |
| `fault_code` | `control_plane_metrics.json.completion_records` and E5 negative-boundary error records include expected error names/codes. | `pass_proxy` |
| `fault_interrupt` | `control_plane_metrics.json.counters.error_interrupts=3`. | `pass_proxy` |
| `interrupt_clear` | `control_plane_metrics.json.counters.interrupt_clears=16`. | `pass_proxy` |
| `dma_bounds_alignment` | `negative_boundary_check.log`: `dma_bounds_alignment=5`; observed `range_error,alignment_error`. | `pass_proxy` |
| `post_fault_smoke_status=pass` | E5 post-fault reset plus post-reset smoke fixture, and reset recovery token `post_reset_smoke_status=pass`. | `pass_proxy` |
| `claim_scope=functional_proxy_only` | This file, `integration/README.md`, `verification/acceptance_matrix.json`, and E5 logs. | `pass_proxy` |

Any future document that uses safety or security language must also carry the
claim boundary from this file.

## E6-B Audit Summary

E6-B is satisfied at `pass_proxy` level because the current evidence package
links the reset/interrupt/security-sensitive negative paths to machine-readable
or line-oriented logs:

| E6-B item | Evidence path | Result |
| --- | --- | --- |
| Reset recovery | `rtl/control_plane_metrics.json`, `rtl/control_plane_run.log`, `rtl/e5_verification_demo.json`, `rtl/e5_outputs/negative_boundary_evidence.json`. | `pass_proxy` |
| Interrupt clear | `rtl/control_plane_metrics.json` and `verification/test_results.log`. | `pass_proxy` |
| Invalid descriptor | `rtl/e5_outputs/negative_boundary_check.log` and `negative_boundary_evidence.json`. | `pass_proxy` |
| DMA bounds/alignment | `rtl/e5_outputs/negative_boundary_check.log`, `negative_boundary_evidence.json`, and E5 verification fixture. | `pass_proxy` |
| Post-reset smoke | E5 post-fault reset plus smoke fixture and reset recovery metric. | `pass_proxy` |
| Clock proxy assumptions | `integration/reset_clock_interrupt.md` and `integration/perf_model_metrics.json`. | `pass_proxy` |
| Explicit non-goals / non-signoff | Claim boundary and non-goal tables in this file. | `pass_proxy` |
