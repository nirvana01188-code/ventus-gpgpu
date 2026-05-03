#!/usr/bin/env python3
"""Phase 9 memory conformance-readiness productization gate.

This generator closes the list of memory-system productization gates without
claiming official OpenCL conformance. It consumes existing clean-room evidence
where present and emits:

* a JSON readiness gate report,
* a completion-columns JSON file, and
* docs/celviz-gpgpu-ip/PHASE9_PRODUCTIZATION_GATES.md.

The gate covers global/local/constant/private/image/sampler/atomics plus
coalescing/cache/scratchpad/DMA under one unified access-model checklist.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA = "celviz.gpgpu.phase9_memory_conformance_gate.v1"
COMPLETION_SCHEMA = "celviz.gpgpu.phase9_memory_completion_columns.v1"
DEFAULT_ARTIFACT_ROOT = Path("artifacts/rank_01_vivante_3d_gpgpu_ip")
DEFAULT_REPORT = DEFAULT_ARTIFACT_ROOT / "verification/phase9_memory_conformance_readiness_gate.json"
DEFAULT_COMPLETION = DEFAULT_ARTIFACT_ROOT / "verification/phase9_memory_conformance_completion_columns.json"
DEFAULT_DOC = Path("docs/celviz-gpgpu-ip/PHASE9_MEMORY_CONFORMANCE_GATES.md")
DEFAULT_LOG = DEFAULT_ARTIFACT_ROOT / "verification/phase9_memory_conformance_gate.log"
CLEAN_ROOM_SCOPE = (
    "Phase 9 memory conformance-readiness gate for clean-room Celviz GPGPU IP "
    "proxy evidence; not official OpenCL conformance, Khronos CTS pass, "
    "proprietary Vivante compatibility, production driver readiness, cache/LSU "
    "microarchitecture signoff, timing/PPA signoff, or silicon signoff"
)
UNIFIED_ACCESS_MODEL = {
    "event_contract": "one ordered access record shape for DMA, kernel, cache/coalescing proxy, and negative cases",
    "address_space_contract": "each access names address_space, operation, offset/address, size, status, and claim boundary",
    "negative_contract": "bounds/alignment/read-only/unsupported surfaces must be explicit gate rows",
    "productization_rule": "ready_proxy rows may support clean-room readiness only; gap rows block conformance claims",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def bool_check(checks: Any, name: str) -> bool:
    if not isinstance(checks, list):
        return False
    return any(isinstance(item, Mapping) and item.get("name") == name and item.get("pass") is True for item in checks)


def status_of(payload: Mapping[str, Any]) -> str:
    status = payload.get("status")
    if isinstance(status, str):
        return status
    summary = payload.get("summary")
    if isinstance(summary, Mapping) and isinstance(summary.get("status"), str):
        return str(summary["status"])
    return "missing"


def evidence_ref(path: Path) -> str:
    return path.as_posix()


def surface_row(
    *,
    surface: str,
    readiness: str,
    completion: str,
    unified_model: str,
    current_evidence: Sequence[str],
    gate: str,
    blockers: Sequence[str],
    next_actions: Sequence[str],
) -> dict[str, Any]:
    return {
        "surface": surface,
        "readiness": readiness,
        "completion": completion,
        "unified_access_model": unified_model,
        "current_evidence": list(current_evidence),
        "productization_gate": gate,
        "blockers": list(blockers),
        "next_actions": list(next_actions),
    }


def build_report(artifact_root: Path) -> dict[str, Any]:
    memory_path = artifact_root / "memory/memory_system_phase1_evidence.json"
    memory_trace_path = artifact_root / "memory/memory_event_trace.json"
    phase6_path = artifact_root / "verification/phase6_memory_trace_integration_report.json"
    streaming_path = artifact_root / "verification/phase7_memory_streaming_report.json"
    coalescing_path = artifact_root / "verification/phase7_coalescing_score_report.json"
    opencl_gap_path = artifact_root / "verification/opencl_conformance_gap_map.json"

    memory = load_json(memory_path)
    phase6 = load_json(phase6_path)
    streaming = load_json(streaming_path)
    coalescing = load_json(coalescing_path)
    opencl_gap = load_json(opencl_gap_path)
    memory_checks = memory.get("checks", [])
    semantics = memory.get("semantics", {})
    scenario = memory.get("scenario", {})
    summary = memory.get("summary", {})
    categories = summary.get("categories", {}) if isinstance(summary, Mapping) else {}
    operations = summary.get("operations", {}) if isinstance(summary, Mapping) else {}

    memory_pass = status_of(memory) == "pass"
    phase6_pass = status_of(phase6) == "pass"
    streaming_pass = status_of(streaming) == "pass"
    coalescing_pass = status_of(coalescing) == "pass"
    opencl_gap_pass = status_of(opencl_gap) == "pass"

    global_ready = memory_pass and phase6_pass and bool_check(memory_checks, "global_memory_h2d_visible_to_kernel")
    local_ready = memory_pass and bool_check(memory_checks, "local_scratchpad_roundtrip")
    constant_ready = memory_pass and bool_check(memory_checks, "constant_reads_are_read_only_and_cacheable_proxy")
    dma_ready = memory_pass and int(categories.get("dma", 0) or 0) >= 3 and {"copy", "fill"}.issubset(set(operations))
    coalescing_ready = memory_pass and coalescing_pass and bool_check(memory_checks, "coalescing_reduces_transactions")
    cache_ready = memory_pass and constant_ready and "cache" in semantics
    scratchpad_ready = local_ready and "scratchpad_local" in scenario

    rows = [
        surface_row(
            surface="global",
            readiness="ready_proxy" if global_ready else "readiness_gap",
            completion="complete_for_proxy_gate" if global_ready else "incomplete",
            unified_model="DMA-visible mutable global memory with kernel load/store and negative bounds/alignment coverage",
            current_evidence=[evidence_ref(memory_path), evidence_ref(memory_trace_path), evidence_ref(phase6_path)],
            gate="H2D/D2H/DMA fill plus kernel load/store visibility must pass through unified access events",
            blockers=[] if global_ready else ["global memory evidence did not pass"],
            next_actions=["extend from proxy traces to RTL LSU/cache traces before conformance claim"],
        ),
        surface_row(
            surface="local",
            readiness="ready_proxy" if local_ready else "readiness_gap",
            completion="complete_for_proxy_gate" if local_ready else "incomplete",
            unified_model="per-workgroup local memory represented as scratchpad access events",
            current_evidence=[evidence_ref(memory_path)],
            gate="local store/load roundtrip must pass and remain separated from host DMA-visible memory",
            blockers=[] if local_ready else ["local scratchpad roundtrip evidence missing or failing"],
            next_actions=["bind local allocation limits to compiler/runtime metadata"],
        ),
        surface_row(
            surface="constant",
            readiness="ready_proxy" if constant_ready else "readiness_gap",
            completion="complete_for_proxy_gate" if constant_ready else "incomplete",
            unified_model="read-only constant memory with kernel load events and cache-proxy evidence",
            current_evidence=[evidence_ref(memory_path), evidence_ref(memory_trace_path)],
            gate="constant reads must be repeatable, cacheable in proxy, and reject stores",
            blockers=[] if constant_ready else ["constant read-only/cache evidence missing or failing"],
            next_actions=["add compiler ABI rows for constant argument placement"],
        ),
        surface_row(
            surface="private",
            readiness="readiness_gap",
            completion="listed_gap_not_complete",
            unified_model="per-work-item private memory/spills must be modeled as non-shared access records",
            current_evidence=[evidence_ref(opencl_gap_path)] if opencl_gap_pass else [],
            gate="private address-space accesses, spills, lifetime, and isolation need explicit clean-room traces",
            blockers=["no dedicated private-memory/spill evidence in current memory model"],
            next_actions=["add private memory fixture with per-lane isolation and spill/load/store negative tests"],
        ),
        surface_row(
            surface="image",
            readiness="partial_proxy",
            completion="listed_gap_not_complete",
            unified_model="image object access must use typed coordinates, format, bounds, and sampler linkage records",
            current_evidence=[evidence_ref(opencl_gap_path), evidence_ref(artifact_root / "demo/outputs/image_filter.json")],
            gate="image reads/writes need explicit image-object semantics beyond buffer-backed image_filter proxy",
            blockers=["current image_filter evidence is buffer/kernel proxy, not full image object conformance"],
            next_actions=["add image object fixture for formats, bounds, coordinates, and row pitch"],
        ),
        surface_row(
            surface="sampler",
            readiness="readiness_gap",
            completion="listed_gap_not_complete",
            unified_model="sampler state must be attached to image access records for addressing/filtering modes",
            current_evidence=[evidence_ref(opencl_gap_path)] if opencl_gap_pass else [],
            gate="sampler addressing/filter/normalized-coordinate modes require explicit positive and negative tests",
            blockers=["no sampler-state evidence in current memory model"],
            next_actions=["add sampler fixture covering clamp/repeat/filter mode declarations and unsupported-mode rejection"],
        ),
        surface_row(
            surface="atomics",
            readiness="readiness_gap",
            completion="listed_gap_not_complete",
            unified_model="atomic read-modify-write events must record ordering scope, old value, new value, and conflict group",
            current_evidence=[evidence_ref(opencl_gap_path)] if opencl_gap_pass else [],
            gate="atomic add/cmpxchg/min/max and conflict serialization need deterministic proxy traces",
            blockers=["no atomic memory operation evidence in current memory model"],
            next_actions=["add global/local atomic fixtures, race-group ordering, and unsupported-width negative cases"],
        ),
        surface_row(
            surface="coalescing",
            readiness="ready_proxy" if coalescing_ready else "readiness_gap",
            completion="complete_for_proxy_gate" if coalescing_ready else "incomplete",
            unified_model="lane accesses are grouped by address-space segment into coalesced proxy transactions",
            current_evidence=[evidence_ref(memory_path), evidence_ref(coalescing_path), evidence_ref(phase6_path)],
            gate="coalesced transaction count must be lower than naive lane transaction count for aligned groups",
            blockers=[] if coalescing_ready else ["coalescing score/evidence missing or failing"],
            next_actions=["link coalescing groups to RTL memory issue events before performance claims"],
        ),
        surface_row(
            surface="cache",
            readiness="ready_proxy" if cache_ready else "readiness_gap",
            completion="complete_for_proxy_gate" if cache_ready else "incomplete",
            unified_model="functional line-presence cache proxy records hits/misses without microarchitecture claims",
            current_evidence=[evidence_ref(memory_path), evidence_ref(memory_trace_path)],
            gate="cache proxy must record line size, hit/miss state, and claim boundary",
            blockers=[] if cache_ready else ["cache proxy evidence missing or failing"],
            next_actions=["separate L1/L2/TLB RTL cache evidence before cache microarchitecture claims"],
        ),
        surface_row(
            surface="scratchpad",
            readiness="ready_proxy" if scratchpad_ready else "readiness_gap",
            completion="complete_for_proxy_gate" if scratchpad_ready else "incomplete",
            unified_model="scratchpad is the concrete local-memory backing model for per-workgroup access",
            current_evidence=[evidence_ref(memory_path)],
            gate="scratchpad lane roundtrip and group isolation assumptions must be explicit",
            blockers=[] if scratchpad_ready else ["scratchpad evidence missing or failing"],
            next_actions=["add multi-workgroup isolation and capacity sweep evidence"],
        ),
        surface_row(
            surface="DMA",
            readiness="ready_proxy" if dma_ready else "readiness_gap",
            completion="complete_for_proxy_gate" if dma_ready else "incomplete",
            unified_model="DMA copy/fill uses the same event schema as kernel memory access records",
            current_evidence=[evidence_ref(memory_path), evidence_ref(memory_trace_path), evidence_ref(streaming_path)],
            gate="H2D, D2H, copy/fill, bounds, and alignment behavior must be represented in ordered events",
            blockers=[] if dma_ready else ["DMA event evidence missing or failing"],
            next_actions=["attach DMA descriptors to driver submission and RTL AXI monitor evidence"],
        ),
    ]

    completed = [row for row in rows if row["completion"] == "complete_for_proxy_gate"]
    gaps = [row for row in rows if row["completion"] != "complete_for_proxy_gate"]
    checks = [
        {"name": "memory_phase1_evidence_pass", "pass": memory_pass},
        {"name": "phase6_memory_trace_link_pass", "pass": phase6_pass},
        {"name": "phase7_streaming_or_coalescing_evidence_present", "pass": streaming_pass or coalescing_pass},
        {"name": "all_required_surfaces_listed", "pass": {row["surface"] for row in rows} == {"global", "local", "constant", "private", "image", "sampler", "atomics", "coalescing", "cache", "scratchpad", "DMA"}},
        {"name": "gap_rows_do_not_claim_conformance", "pass": all(row["readiness"] != "ready_proxy" for row in gaps)},
        {"name": "unified_access_model_declared", "pass": bool(UNIFIED_ACCESS_MODEL)},
    ]
    status = "pass" if all(check["pass"] for check in checks) else "fail"
    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "status": status,
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "unified_access_model": UNIFIED_ACCESS_MODEL,
        "source_evidence": {
            "memory_phase1": evidence_ref(memory_path),
            "memory_trace": evidence_ref(memory_trace_path),
            "phase6_memory_trace_integration": evidence_ref(phase6_path),
            "phase7_memory_streaming": evidence_ref(streaming_path),
            "phase7_coalescing_score": evidence_ref(coalescing_path),
            "opencl_conformance_gap_map": evidence_ref(opencl_gap_path),
        },
        "completion_summary": {
            "surface_count": len(rows),
            "complete_for_proxy_gate": len(completed),
            "gap_or_partial": len(gaps),
            "ready_proxy_surfaces": [row["surface"] for row in completed],
            "gap_or_partial_surfaces": [row["surface"] for row in gaps],
            "official_conformance_claim": False,
        },
        "surfaces": rows,
        "checks": checks,
        "claim_boundary": "This gate completes readiness listing and proxy gates only; it does not complete official memory conformance.",
    }


def completion_columns(report: Mapping[str, Any]) -> dict[str, Any]:
    columns = [
        "surface",
        "readiness",
        "completion",
        "unified_access_model",
        "current_evidence",
        "productization_gate",
        "blockers",
        "next_actions",
    ]
    return {
        "schema": COMPLETION_SCHEMA,
        "generated_at": report["generated_at"],
        "status": report["status"],
        "columns": columns,
        "rows": report["surfaces"],
        "summary": report["completion_summary"],
    }


def render_doc(report: Mapping[str, Any], report_path: Path, completion_path: Path) -> str:
    summary = report["completion_summary"]
    lines = [
        "# Phase 9 Memory Conformance Gates",
        "",
        "Status: memory conformance-readiness gate list completed for clean-room proxy evidence.",
        "",
        "This page is generated by:",
        "",
        "```sh",
        "bash scripts/verify_celviz_gpgpu_phase9_memory_conformance.sh",
        "```",
        "",
        "Generated evidence:",
        "",
        f"- `{report_path.as_posix()}`",
        f"- `{completion_path.as_posix()}`",
        "",
        "## Boundary",
        "",
        CLEAN_ROOM_SCOPE + ".",
        "",
        "The gate completes the productization readiness list. It does not claim official OpenCL conformance, Khronos CTS pass, proprietary Vivante compatibility, production driver readiness, cache/LSU microarchitecture signoff, timing/PPA signoff, or silicon signoff.",
        "",
        "## Unified Access Model",
        "",
    ]
    for key, value in report["unified_access_model"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Completion Summary",
            "",
            f"- Surfaces listed: `{summary['surface_count']}`",
            f"- Complete for proxy gate: `{summary['complete_for_proxy_gate']}`",
            f"- Gap or partial: `{summary['gap_or_partial']}`",
            f"- Official conformance claim: `{str(summary['official_conformance_claim']).lower()}`",
            "",
            "## Completion Columns",
            "",
            "| Surface | Readiness | Completion | Productization Gate | Blockers |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in report["surfaces"]:
        blockers = "<br>".join(row["blockers"]) if row["blockers"] else "none"
        lines.append(
            f"| `{row['surface']}` | `{row['readiness']}` | `{row['completion']}` | {row['productization_gate']} | {blockers} |"
        )
    lines.extend(
        [
            "",
            "## Complete For Proxy Gate",
            "",
        ]
    )
    for surface in summary["ready_proxy_surfaces"]:
        lines.append(f"- `{surface}`")
    lines.extend(
        [
            "",
            "## Gap Or Partial Surfaces",
            "",
        ]
    )
    for surface in summary["gap_or_partial_surfaces"]:
        lines.append(f"- `{surface}`")
    lines.append("")
    return "\n".join(lines)


def write_log(path: Path, report: Mapping[str, Any]) -> None:
    summary = report["completion_summary"]
    lines = [
        "Celviz GPGPU IP Phase9 memory conformance-readiness gate",
        f"schema={report['schema']}",
        f"status={report['status']}",
        f"surface_count={summary['surface_count']}",
        f"complete_for_proxy_gate={summary['complete_for_proxy_gate']}",
        f"gap_or_partial={summary['gap_or_partial']}",
        "ready_proxy_surfaces=" + ",".join(summary["ready_proxy_surfaces"]),
        "gap_or_partial_surfaces=" + ",".join(summary["gap_or_partial_surfaces"]),
        "official_conformance_claim=false",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--completion", type=Path, default=DEFAULT_COMPLETION)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--print-summary", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(args.artifact_root)
    completion = completion_columns(report)
    write_json(args.report, report)
    write_json(args.completion, completion)
    args.doc.parent.mkdir(parents=True, exist_ok=True)
    args.doc.write_text(render_doc(report, args.report, args.completion), encoding="utf-8")
    write_log(args.log, report)
    if args.print_summary:
        print(json.dumps(report["completion_summary"], indent=2, sort_keys=True))
    else:
        summary = report["completion_summary"]
        print(
            "celviz_gpgpu_phase9_memory_conformance_gate: "
            f"{report['status']} surfaces={summary['surface_count']} "
            f"complete={summary['complete_for_proxy_gate']} gaps={summary['gap_or_partial']}"
        )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
