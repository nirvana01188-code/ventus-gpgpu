# Celviz GPGPU Verilator Supplemental Phase 1

This directory owns the first supplemental verification lane for raising RTL
structural coverage after the existing functional-coverage gate reached 100%.
It intentionally does not edit the shared acceptance matrix or the full
Verilator coverage wrapper.

## Fast Gate

Run from the repository root:

```bash
bash scripts/tools/artifacts/run_celviz_gpgpu_verilator_supplemental_phase1.sh
```

The fast gate generates four fixture classes and executes them with the
existing clean-room control-plane simulator:

- `directed`: deterministic control/data-path exercises for queue, DMA,
  fence, scheduler, FP mode, kernel dispatch, interrupt clear, and counter
  snapshot paths.
- `random`: seeded random command stream, default seed `20260502`, covering
  mixed queues/opcodes and completion/counter combinations.
- `fault`: expected negative paths for bad DMA alignment, DMA MMU fault,
  kernel arg MMU fault, scheduler fault, fence timeout, unsupported opcode,
  bad queue, and reset recovery.
- `stress`: long-run retirement fixture, default 96 iterations and 224
  commands, for queue head/tail movement, repeated DMA traffic, fences, and
  periodic kernel dispatches.

Default evidence is written under:

```text
artifacts/rank_01_vivante_3d_gpgpu_ip/verification/verilator_supplemental_phase1/
```

Key files:

- `phase1_supplemental_evidence.json`: summary, target-hit matrix, observed
  metrics, fixture manifest, run records, and full-coverage integration plan.
- `fixtures/*.json`: replayable command-stream fixtures for future slow
  coverage-enabled Verilator runs.
- `runs/*.metrics.json`: per-suite control-plane metrics.
- `runs/*.log`: per-suite execution logs.

## Observed Quick-Gate Metrics

The checked-in evidence from the initial run reports:

- structural target hits: `24/24`
- total commands: `295`
- kernel dispatches: `10`
- DMA copies: `102`
- DMA fills: `103`
- completion interrupts: `85`
- error interrupts: `7`
- MMU faults: `2`
- scheduler faults: `1`
- DMA alignment errors: `1`

These are proxy/fixture metrics used to guide structural coverage uplift. They
are not RTL line/toggle/branch coverage claims and are not silicon signoff.

## Full-Coverage Integration Plan

1. Replay generated `fixtures/*.json` through the coverage-enabled Verilator
   runtime lane once the mainline wrapper worker wires supplemental fixtures
   into the slow path.
2. Compare LCOV line/branch/toggle deltas by source module against the current
   Verilator coverage bundle.
3. Promote suites with positive structural deltas into the shared full wrapper
   after integration review.
4. Keep this fast gate deterministic so fixture drift is caught without
   requiring a slow rebuild.
