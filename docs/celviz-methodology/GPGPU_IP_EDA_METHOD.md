# Celviz GPGPU IP EDA Methodology

Status: reusable method library for clean-room GPGPU IP execution.

This method captures the repeatable EDA flow used to turn a public product
blueprint and an open-source implementation base into machine-checked IP
evidence. It is written for reuse by Celviz so future IP work does not rebuild
the same gates, reports, and claim boundaries from scratch.

## 1. Blueprint Boundary

Use public product material only as a product-dimension blueprint. Keep all
active implementation evidence inside the clean-room project root. Never claim
proprietary RTL, firmware, driver, SDK, ISA, compiler, or command-stream
compatibility unless that evidence is actually owned and licensed.

Required gates:

- active evidence root allowlist
- forbidden historical/superseded root scan
- clean-room scope string in every generated report
- explicit non-goals in docs and JSON

## 2. Architecture Decomposition

Break the GPU into stable lanes before implementation:

- compute core: warp or wavefront, register file, ALU, LSU, scoreboard, barrier
- programming model: OpenCL-like subset before broader API claims
- memory system: global, local, constant, DMA, scratchpad, cache/coalescing proxy
- runtime and driver: queue, submit, fence, event, error, pending lifecycle
- verification: functional bins, structural observations, negative contracts
- PPA: proxy first, synthesis readiness second, signoff only with real tools

## 3. Source Hooks

Hardware changes must expose machine-readable source hooks:

- RTL/debug counters and `dontTouch` observability where appropriate
- runtime ABI symbols and native binding checks
- source-check regex gates for every intentional hook
- no artifact-only evidence for implementation claims

## 4. Acceptance Matrix

Every phase must have a command, evidence paths, required observations, pass
condition, and non-goals. The matrix is the executable contract. If a new phase
adds evidence, it must also add coverage bins and a full acceptance entry.

## 5. Functional Coverage vs Structural Coverage

Functional/acceptance coverage and RTL structural coverage are separate.

- Functional coverage can be 100% when every declared acceptance bin passes.
- Verilator line, branch, toggle, and source coverage are observations unless
  the structural closure target is explicitly met.
- Do not convert structural observations into a 100% functional claim.

## 6. Verilator Supplemental Lane

Use Verilator to raise RTL execution evidence with:

- directed command tests
- random command tests
- fault injection
- long-run stress
- coverage report JSON plus raw coverage artifacts

If toggle data is unavailable, report `toggle_status=unavailable` rather than
inventing closure.

## 7. Runtime ABI Lane

Runtime evidence must prove:

- dry-run command semantics
- native runtime binding when a library is available
- queue lifecycle closes with pending count zero
- completion and error interrupts/events are visible
- ABI symbols are exported and checked

## 8. Micro-op Execution Lane

Lowering evidence is not enough. The method requires an executable IR lane:

- lower kernels to micro-ops
- execute micro-ops through a deterministic interpreter
- generate memory traces
- compare result hashes against an oracle
- carry clean-room scope and non-goal text

## 9. Worker Decomposition

Parallel work should use disjoint write scopes:

- compiler IR
- memory trace integration
- driver submission model
- synthesis readiness
- methodology documentation
- total integration

Each worker reports changed files, command results, and metrics. Integration
must review worker output rather than overwrite unrelated work.

## 10. Artifact Gates

Every generated report should include:

- schema
- generated timestamp
- clean-room scope
- status
- checks array
- summary metrics
- evidence artifact paths

The full acceptance wrapper should run phase gates before the final coverage
aggregation.

## 11. No-overclaim Wording

Allowed wording:

- Ventus-based Celviz clean-room GPGPU IP proxy
- OpenCL-like subset evidence
- functional/acceptance bins
- supplemental Verilator coverage observation
- synthesis readiness proxy

Disallowed wording without stronger evidence:

- Vivante-compatible IP
- official OpenCL conformance
- production Linux kernel driver
- RTL structural coverage closure
- timing, power, physical, or silicon signoff

## 12. Reuse Checklist

For a new IP target, instantiate this method in order:

1. Create clean-room blueprint boundary docs.
2. Add source hook checks.
3. Build deterministic oracle workloads.
4. Build runtime command ABI.
5. Add RTL/control observability.
6. Add negative contracts.
7. Add Verilator supplemental artifacts.
8. Add cross-layer integration.
9. Add lowering and executable IR.
10. Add coverage aggregation.
11. Add synthesis readiness.
12. Run full acceptance and keep claim boundaries explicit.

## 13. Bootstrap Package

Celviz keeps this method as a reusable package, not only as prose:

- `docs/celviz-methodology/templates/gpgpu_acceptance_template.json`
  contains the phase sequence, gate templates, required report fields, and
  claim-boundary template.
- `tools/celviz_eda_methodology/bootstrap_gpgpu_methodology.py` renders a
  starter acceptance skeleton for a new IP slug.
- `tools/celviz_eda_methodology/verify_methodology_manifest.py` checks that the
  methodology document, manifest, template, bootstrap tool, and no-overclaim
  rules are all present.

Example bootstrap command:

```sh
python3 tools/celviz_eda_methodology/bootstrap_gpgpu_methodology.py \
  --ip-slug next_gpgpu_ip \
  --output artifacts/celviz-methodology/next_gpgpu_ip_acceptance_matrix.json
```

The generated skeleton is not completion evidence. It is a starting contract
that a new project must fill with real source hooks, reports, phase gates, and
coverage bins.

## 14. Template Library

The reusable package carries starter files for the EDA mechanics that otherwise
get rebuilt in every GPU/IP effort:

- `docs/celviz-methodology/templates/boundary_check_template.sh` is the
  clean-room evidence boundary gate. Instantiate it first so historical,
  superseded, or vendor-owned roots cannot become active evidence by accident.
- `docs/celviz-methodology/templates/source_check_template.py` is the source
  hook gate. Fill it with RTL/runtime/compiler regexes for warp, register
  file, ALU, LSU, scoreboard, barrier, queue, fence, event, and driver paths.
- `docs/celviz-methodology/templates/phase_gate_template.py` verifies the
  standard report shape for one phase: schema, timestamp, clean-room scope,
  status, checks, and summary.
- `docs/celviz-methodology/templates/coverage_100_template.py` is the starting
  point for functional/acceptance coverage aggregation. It deliberately keeps
  structural RTL coverage, synthesis, timing, power, DFT, physical, and silicon
  signoff outside the 100 percent functional claim.

When a new GPU IP project starts, bootstrap the acceptance matrix, copy the
needed templates into the new tool/script namespace, replace placeholders with
project-specific evidence paths, and immediately add the resulting commands to
the full acceptance wrapper. The method is considered reusable only when the
bootstrap command and template checks are part of machine verification.
