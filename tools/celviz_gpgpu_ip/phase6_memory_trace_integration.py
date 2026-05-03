#!/usr/bin/env python3
"""Phase-6B micro-op memory trace integration gate.

This tool consumes phase-5 micro-op execution evidence, per-kernel micro-op
execution JSON, and the clean-room memory-system proxy evidence.  It proves the
current phase-6B contract: per-kernel load/store traces are present, the traces
use global-memory semantics, aggregate micro-op memory counts close, and the
coalescing/proxy memory model is linked to the micro-op memory stream.

It is intentionally standard-library only and clean-room scoped.  It is not a
production ISA simulator, cache model, LSU model, DMA engine, command stream,
compiler backend, proprietary Vivante compatibility claim, timing model, PPA
claim, or API conformance claim.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA = "celviz.gpgpu.phase6_memory_trace_integration.v1"
CLEAN_ROOM_SCOPE = (
    "clean-room phase-6B micro-op memory trace integration evidence; uses "
    "phase-5 proxy micro-op traces and the clean-room memory model only; not "
    "a production ISA simulator, proprietary Vivante RTL/firmware/driver/SDK, "
    "cache microarchitecture, command-stream compatibility, timing/PPA signoff, "
    "or official API conformance claim"
)
DEFAULT_ROOT = Path("artifacts/rank_01_vivante_3d_gpgpu_ip")
REQUIRED_KERNELS = ("vector_add", "gemm", "conv2d", "image_filter")
KERNEL_FILE_NAMES = {
    "vector_add": "vector_add.microop_execution.json",
    "gemm": "gemm.microop_execution.json",
    "conv2d": "conv2d.microop_execution.json",
    "image_filter": "image_filter.microop_execution.json",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def as_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def rel(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def event_samples(kernel_report: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    execution = kernel_report.get("execution", {})
    if not isinstance(execution, Mapping):
        return []
    samples: list[Mapping[str, Any]] = []
    for key in ("memory_trace_head", "memory_trace_tail"):
        value = execution.get(key, [])
        if isinstance(value, list):
            samples.extend(item for item in value if isinstance(item, Mapping))
    return samples


def coalescing_groups_from_samples(events: Sequence[Mapping[str, Any]], *, segment_bytes: int) -> dict[str, Any]:
    memory_events = [
        event
        for event in events
        if event.get("kind") in {"load", "store"}
        and event.get("address_space") == "global"
        and as_int(event.get("bytes_per_element")) > 0
    ]
    groups: dict[tuple[str, str, int], list[Mapping[str, Any]]] = {}
    for event in memory_events:
        key = (
            str(event.get("kind")),
            str(event.get("arg")),
            as_int(event.get("byte_offset")) // segment_bytes,
        )
        groups.setdefault(key, []).append(event)

    rows = []
    for (kind, arg, segment), items in sorted(groups.items()):
        offsets = [as_int(item.get("byte_offset")) for item in items]
        sizes = [as_int(item.get("bytes_per_element")) for item in items]
        rows.append(
            {
                "kind": kind,
                "arg": arg,
                "segment_index": segment,
                "segment_base_offset": segment * segment_bytes,
                "sample_event_count": len(items),
                "byte_span": [min(offsets), max(offset + size for offset, size in zip(offsets, sizes))],
                "proxy_transactions": 1,
            }
        )

    return {
        "segment_bytes": segment_bytes,
        "sample_events": len(memory_events),
        "naive_transactions": len(memory_events),
        "coalesced_transactions": len(rows),
        "coalescing_reduction_observed": len(rows) < len(memory_events),
        "groups_head": rows[:16],
    }


def kernel_summary(kernel: str, report: Mapping[str, Any], *, segment_bytes: int) -> dict[str, Any]:
    execution = report.get("execution", {})
    if not isinstance(execution, Mapping):
        execution = {}
    memory_counts = execution.get("memory_counts", {})
    if not isinstance(memory_counts, Mapping):
        memory_counts = {}
    result = report.get("result", {})
    if not isinstance(result, Mapping):
        result = {}

    samples = event_samples(report)
    kinds = {str(event.get("kind")) for event in samples}
    address_spaces = {str(event.get("address_space")) for event in samples}
    expected_event_count = sum(as_int(value) for value in memory_counts.values())
    execution_event_count = as_int(execution.get("memory_event_count"))
    return {
        "kernel": kernel,
        "status": report.get("status"),
        "oracle_workload": report.get("oracle_workload"),
        "result_sha256": result.get("result_sha256"),
        "report_sha256": report.get("sha256"),
        "wavefront_size": as_int(execution.get("wavefront_size")),
        "work_items": as_int(execution.get("work_items")),
        "memory_event_count": execution_event_count,
        "memory_counts": {
            "load": as_int(memory_counts.get("load")),
            "store": as_int(memory_counts.get("store")),
        },
        "memory_count_sum": expected_event_count,
        "memory_count_closes": expected_event_count == execution_event_count,
        "sample_event_count": len(samples),
        "sample_kinds": sorted(kinds),
        "sample_address_spaces": sorted(address_spaces),
        "address_args": execution.get("address_args", []),
        "sample_args": sorted({str(event.get("arg")) for event in samples if event.get("arg") is not None}),
        "sample_bytes_per_element": sorted({as_int(event.get("bytes_per_element")) for event in samples}),
        "global_only_samples": address_spaces == {"global"},
        "has_load_store_samples": {"load", "store"}.issubset(kinds),
        "coalescing_proxy_from_samples": coalescing_groups_from_samples(samples, segment_bytes=segment_bytes),
    }


def collect(artifact_root: Path) -> dict[str, Any]:
    repo_root = artifact_root.parent.parent
    microop_report_path = artifact_root / "microop_execution" / "microop_execution_report.json"
    memory_evidence_path = artifact_root / "memory" / "memory_system_phase1_evidence.json"
    memory_trace_path = artifact_root / "memory" / "memory_event_trace.json"
    memory_summary_path = artifact_root / "memory" / "summary.json"
    kernel_dir = artifact_root / "microop_execution" / "kernels"

    microop_report = load_json(microop_report_path)
    memory_evidence = load_json(memory_evidence_path)
    memory_trace = load_json(memory_trace_path)
    memory_summary = load_json(memory_summary_path)

    memory_parameters = memory_evidence.get("parameters", {})
    if not isinstance(memory_parameters, Mapping):
        memory_parameters = {}
    segment_bytes = as_int(memory_parameters.get("coalescing_segment_bytes"), 32)
    memory_semantics = memory_evidence.get("semantics", {})
    if not isinstance(memory_semantics, Mapping):
        memory_semantics = {}
    memory_ops = memory_evidence.get("summary", {}).get("operations", {})
    if not isinstance(memory_ops, Mapping):
        memory_ops = {}
    memory_checks = memory_evidence.get("checks", [])
    if not isinstance(memory_checks, list):
        memory_checks = []

    per_kernel_reports: dict[str, Mapping[str, Any]] = {}
    per_kernel_paths: dict[str, Path] = {}
    for kernel, filename in KERNEL_FILE_NAMES.items():
        path = kernel_dir / filename
        per_kernel_paths[kernel] = path
        per_kernel_reports[kernel] = load_json(path)

    kernel_rows = [kernel_summary(kernel, per_kernel_reports[kernel], segment_bytes=segment_bytes) for kernel in REQUIRED_KERNELS]
    aggregate_loads = sum(row["memory_counts"]["load"] for row in kernel_rows)
    aggregate_stores = sum(row["memory_counts"]["store"] for row in kernel_rows)
    aggregate_events = sum(row["memory_event_count"] for row in kernel_rows)
    report_kernel_rows = microop_report.get("kernels", [])
    report_kernel_map = {str(row.get("kernel")): row for row in report_kernel_rows if isinstance(row, Mapping)}
    memory_events = memory_trace.get("events", [])
    if not isinstance(memory_events, list):
        memory_events = []
    memory_event_categories = {str(event.get("category")) for event in memory_events if isinstance(event, Mapping)}
    memory_event_ops = {str(event.get("operation")) for event in memory_events if isinstance(event, Mapping)}
    memory_event_schemas = {str(event.get("schema")) for event in memory_events if isinstance(event, Mapping)}
    coalescing_scenario = memory_evidence.get("scenario", {}).get("coalescing_group", {})
    if not isinstance(coalescing_scenario, Mapping):
        coalescing_scenario = {}
    coalescing_sample_kernels = [
        row["kernel"]
        for row in kernel_rows
        if row["coalescing_proxy_from_samples"]["coalescing_reduction_observed"] is True
    ]

    checks = [
        {
            "name": "input_reports_pass_and_clean_room_scoped",
            "pass": microop_report.get("status") == "pass"
            and microop_report.get("schema") == "celviz.gpgpu.microop_interpreter.v1"
            and memory_evidence.get("summary", {}).get("status") == "pass"
            and memory_evidence.get("schema") == "celviz.gpgpu.memory_model.phase1.v1"
            and memory_summary.get("status") == "pass"
            and "clean-room" in str(microop_report.get("clean_room_scope", "")).lower()
            and "clean-room" in str(memory_evidence.get("clean_room_scope", "")).lower(),
            "evidence": {
                "microop_status": microop_report.get("status"),
                "microop_schema": microop_report.get("schema"),
                "memory_status": memory_evidence.get("summary", {}).get("status"),
                "memory_schema": memory_evidence.get("schema"),
                "memory_summary_status": memory_summary.get("status"),
            },
        },
        {
            "name": "required_per_kernel_microop_reports_present",
            "pass": all(per_kernel_reports[kernel].get("status") == "pass" for kernel in REQUIRED_KERNELS)
            and set(report_kernel_map) == set(REQUIRED_KERNELS),
            "evidence": {
                "required": list(REQUIRED_KERNELS),
                "per_kernel_status": {kernel: per_kernel_reports[kernel].get("status") for kernel in REQUIRED_KERNELS},
                "aggregate_report_kernels": sorted(report_kernel_map),
            },
        },
        {
            "name": "per_kernel_load_store_traces_close",
            "pass": all(
                row["memory_event_count"] > 0
                and row["memory_counts"]["load"] > 0
                and row["memory_counts"]["store"] > 0
                and row["memory_count_closes"] is True
                and row["has_load_store_samples"] is True
                for row in kernel_rows
            ),
            "evidence": {
                row["kernel"]: {
                    "memory_event_count": row["memory_event_count"],
                    "memory_counts": row["memory_counts"],
                    "sample_kinds": row["sample_kinds"],
                    "memory_count_closes": row["memory_count_closes"],
                }
                for row in kernel_rows
            },
        },
        {
            "name": "aggregate_microop_memory_counts_match_report",
            "pass": aggregate_events == as_int(microop_report.get("total_memory_events"))
            and aggregate_loads > 0
            and aggregate_stores > 0,
            "evidence": {
                "per_kernel_total_memory_events": aggregate_events,
                "microop_report_total_memory_events": microop_report.get("total_memory_events"),
                "aggregate_loads": aggregate_loads,
                "aggregate_stores": aggregate_stores,
            },
        },
        {
            "name": "global_memory_semantics_close",
            "pass": all(row["global_only_samples"] for row in kernel_rows)
            and "global" in memory_semantics
            and "mutable device memory" in str(memory_semantics.get("global", "")).lower()
            and as_int(memory_parameters.get("global_size_bytes")) > 0
            and as_int(memory_parameters.get("alignment_bytes")) > 0,
            "evidence": {
                "kernel_sample_address_spaces": {row["kernel"]: row["sample_address_spaces"] for row in kernel_rows},
                "memory_global_semantics": memory_semantics.get("global"),
                "global_size_bytes": memory_parameters.get("global_size_bytes"),
                "alignment_bytes": memory_parameters.get("alignment_bytes"),
            },
        },
        {
            "name": "memory_model_load_store_copy_fill_event_schema_closes",
            "pass": {"dma", "kernel", "negative"}.issubset(memory_event_categories)
            and {"copy", "fill", "load", "store"}.issubset(memory_event_ops)
            and memory_event_schemas == {"celviz.gpgpu.memory_event.v1"}
            and as_int(memory_trace.get("event_count")) == len(memory_events)
            and as_int(memory_ops.get("load")) > 0
            and as_int(memory_ops.get("store")) > 0,
            "evidence": {
                "memory_event_categories": sorted(memory_event_categories),
                "memory_event_operations": sorted(memory_event_ops),
                "memory_event_schemas": sorted(memory_event_schemas),
                "memory_trace_event_count": memory_trace.get("event_count"),
                "memory_operations": memory_ops,
            },
        },
        {
            "name": "coalescing_proxy_model_links_to_microop_samples",
            "pass": "coalescing" in memory_semantics
            and as_int(coalescing_scenario.get("coalesced_transactions")) < as_int(coalescing_scenario.get("naive_transactions"))
            and as_int(coalescing_scenario.get("segment_bytes")) == segment_bytes
            and len(coalescing_sample_kernels) >= 2,
            "evidence": {
                "memory_model_coalescing": coalescing_scenario,
                "coalescing_sample_kernels": coalescing_sample_kernels,
                "kernel_sample_coalescing": {
                    row["kernel"]: row["coalescing_proxy_from_samples"] for row in kernel_rows
                },
            },
        },
        {
            "name": "result_and_hash_continuity",
            "pass": all(
                str(report_kernel_map[row["kernel"]].get("sha256")) == str(row["report_sha256"])
                and str(report_kernel_map[row["kernel"]].get("result_sha256")) == str(row["result_sha256"])
                for row in kernel_rows
            ),
            "evidence": {
                row["kernel"]: {
                    "aggregate_report_sha256": report_kernel_map[row["kernel"]].get("sha256"),
                    "per_kernel_report_sha256": row["report_sha256"],
                    "aggregate_result_sha256": report_kernel_map[row["kernel"]].get("result_sha256"),
                    "per_kernel_result_sha256": row["result_sha256"],
                }
                for row in kernel_rows
            },
        },
        {
            "name": "memory_model_checks_all_pass",
            "pass": bool(memory_checks) and all(isinstance(check, Mapping) and check.get("pass") is True for check in memory_checks),
            "evidence": {
                "memory_checks": [
                    {"name": check.get("name"), "pass": check.get("pass")}
                    for check in memory_checks
                    if isinstance(check, Mapping)
                ],
            },
        },
    ]

    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "status": "pass" if all(check["pass"] for check in checks) else "fail",
        "checks": checks,
        "summary": {
            "kernel_count": len(kernel_rows),
            "total_microop_memory_events": aggregate_events,
            "total_microop_loads": aggregate_loads,
            "total_microop_stores": aggregate_stores,
            "memory_model_event_count": memory_trace.get("event_count"),
            "memory_model_operations": memory_ops,
            "coalescing_segment_bytes": segment_bytes,
            "coalescing_sample_kernels": coalescing_sample_kernels,
            "global_memory_semantics": memory_semantics.get("global"),
        },
        "per_kernel": kernel_rows,
        "artifacts": {
            "microop_execution_report": rel(microop_report_path, repo_root),
            "per_kernel_microop_execution": {kernel: rel(path, repo_root) for kernel, path in sorted(per_kernel_paths.items())},
            "memory_model_evidence": rel(memory_evidence_path, repo_root),
            "memory_event_trace": rel(memory_trace_path, repo_root),
            "memory_summary": rel(memory_summary_path, repo_root),
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify phase-6B micro-op memory trace integration.")
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ROOT, help="Rank 1 artifact root")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_ROOT / "verification" / "phase6_memory_trace_integration_report.json",
        help="Output report path",
    )
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args(argv)
    report = collect(args.artifact_root)
    write_json(args.output, report)
    passed = sum(1 for check in report["checks"] if check["pass"])
    total = len(report["checks"])
    if args.print_summary:
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "checks": f"{passed}/{total}",
                    "summary": report["summary"],
                    "output": str(args.output),
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(f"celviz_gpgpu_phase6_memory: {report['status']} checks={passed}/{total} output={args.output}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
