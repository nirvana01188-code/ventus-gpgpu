# Celviz GPGPU IP Memory System Phase 1

This directory contains focused clean-room memory-system evidence for Rank 1 GPGPU IP work.

Covered semantics:

- global memory: DMA-visible mutable device memory
- local memory: per-workgroup scratchpad proxy
- constant memory: read-only kernel-loadable memory
- cache proxy: deterministic line-presence hit/miss evidence
- coalescing proxy: lane segment grouping evidence
- unified events: DMA copy/fill and kernel load/store share one ordered event schema
- negative cases: bounds, alignment, and constant-store rejection

Primary evidence: `memory_system_phase1_evidence.json`

Scope: clean-room functional proxy only; no proprietary Vivante RTL, firmware, driver, SDK, compiler, cache microarchitecture, timing, PPA, or conformance claim.
