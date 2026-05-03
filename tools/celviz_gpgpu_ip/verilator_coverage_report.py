#!/usr/bin/env python3
"""Build a Celviz GPGPU Verilator coverage report.

The tool is dependency-free and intentionally evidence-driven: Verilator
coverage artifacts are reported as artifacts, LCOV-style ``.info`` metrics are
reported only when present, and functional bins are derived from runtime metrics.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCHEMA = "celviz.gpgpu.verilator_coverage_report.v1"
CLEAN_ROOM_SCOPE = (
    "clean-room Verilator/runtime coverage evidence for the Celviz GPGPU IP "
    "proxy only; no proprietary Vivante compatibility, proprietary command "
    "stream/driver/firmware/SDK claim, API conformance claim, silicon signoff, "
    "STA/timing closure, PPA, safety certification, or production-readiness claim"
)

FEATURE_BINS = (
    "queues",
    "dma_fill",
    "dma_copy",
    "dma_copy_h2d",
    "dma_copy_d2h",
    "fence_signal",
    "fence_wait",
    "reset",
    "completion_interrupt",
    "error_interrupt",
    "mmu_fault",
    "scheduler_fault",
    "abi_symbol_coverage",
    "native_command_categories",
    "pending_count_zero",
)

ABI_SYMBOL_TOKENS = (
    "abi",
    "abi_version",
    "command_abi",
    "runtime_abi",
    "celviz_gpgpu_proxy",
)
NATIVE_COMMAND_TOKENS = (
    "native_command",
    "runtime_api",
    "kernel_dispatch",
    "dma_fill",
    "dma_copy",
    "host_to_device",
    "device_to_host",
    "fence_signal",
    "fence_wait",
    "set_scheduler_config",
)


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
        if isinstance(value, str):
            return int(value, 0)
        return int(value)
    except (TypeError, ValueError):
        return default


def percent(hit: int, found: int) -> float | None:
    if found <= 0:
        return None
    return round((float(hit) / float(found)) * 100.0, 3)


def artifact_info(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {
            "path": None,
            "exists": False,
            "size_bytes": None,
            "non_empty": False,
        }
    exists = path.exists()
    size = path.stat().st_size if exists else None
    return {
        "path": str(path),
        "exists": exists,
        "size_bytes": size,
        "non_empty": bool(exists and size and size > 0),
    }


def unavailable(reason: str) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "reason": reason,
        "found": None,
        "hit": None,
        "percent": None,
    }


def metric_from_counts(name: str, found: int | None, hit: int | None) -> dict[str, Any]:
    if found is None or hit is None:
        return unavailable(f"{name} counts were not present in coverage info")
    return {
        "status": "available",
        "found": found,
        "hit": hit,
        "percent": percent(hit, found),
    }


def parse_lcov_info(path: Path | None) -> dict[str, Any]:
    """Parse standard LCOV counters from a Verilator-generated .info file."""

    if path is None:
        return {
            "status": "unavailable",
            "reason": "coverage info path was not provided",
            "files": [],
            "summary": {},
        }
    if not path.exists():
        return {
            "status": "unavailable",
            "reason": "coverage info file does not exist",
            "files": [],
            "summary": {},
        }
    if path.stat().st_size == 0:
        return {
            "status": "unavailable",
            "reason": "coverage info file is empty",
            "files": [],
            "summary": {},
        }

    files: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    summary: dict[str, int] = {
        "line_found": 0,
        "line_hit": 0,
        "function_found": 0,
        "function_hit": 0,
        "branch_found": 0,
        "branch_hit": 0,
        "toggle_found": 0,
        "toggle_hit": 0,
    }
    saw_toggle = False

    def finish_current() -> None:
        nonlocal current
        if current:
            files.append(current)
            current = {}

    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line == "end_of_record":
            finish_current()
            continue
        if line.startswith("SF:"):
            finish_current()
            current = {"source_file": line[3:]}
            continue
        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        parsed = as_int(value.split(",", 1)[0], 0)
        if key == "DA":
            fields = value.split(",")
            count = as_int(fields[1] if len(fields) > 1 else 0)
            current["line_found"] = as_int(current.get("line_found")) + 1
            summary["line_found"] += 1
            if count > 0:
                current["line_hit"] = as_int(current.get("line_hit")) + 1
                summary["line_hit"] += 1
        elif key == "BRDA":
            fields = value.split(",")
            taken_raw = fields[3] if len(fields) > 3 else "0"
            taken = 0 if taken_raw == "-" else as_int(taken_raw)
            current["branch_found"] = as_int(current.get("branch_found")) + 1
            summary["branch_found"] += 1
            if taken > 0:
                current["branch_hit"] = as_int(current.get("branch_hit")) + 1
                summary["branch_hit"] += 1
        elif key == "LF":
            current["line_found"] = parsed
            summary["line_found"] += parsed
        elif key == "LH":
            current["line_hit"] = parsed
            summary["line_hit"] += parsed
        elif key == "FNF":
            current["function_found"] = parsed
            summary["function_found"] += parsed
        elif key == "FNH":
            current["function_hit"] = parsed
            summary["function_hit"] += parsed
        elif key == "BRF":
            current["branch_found"] = parsed
            summary["branch_found"] += parsed
        elif key == "BRH":
            current["branch_hit"] = parsed
            summary["branch_hit"] += parsed
        elif key in {"TGF", "TOF", "TFF"}:
            current["toggle_found"] = parsed
            summary["toggle_found"] += parsed
            saw_toggle = True
        elif key in {"TGH", "TOH", "TFH"}:
            current["toggle_hit"] = parsed
            summary["toggle_hit"] += parsed
            saw_toggle = True

    finish_current()

    return {
        "status": "available",
        "files": files,
        "summary": summary,
        "source": metric_from_counts(
            "source/function", summary["function_found"], summary["function_hit"]
        )
        if summary["function_found"] > 0
        else unavailable("LCOV FNF/FNH function counts were not present"),
        "toggle": metric_from_counts("toggle", summary["toggle_found"], summary["toggle_hit"])
        if saw_toggle and summary["toggle_found"] > 0
        else unavailable("toggle counts were not present in coverage info"),
        "line": metric_from_counts("line", summary["line_found"], summary["line_hit"])
        if summary["line_found"] > 0
        else unavailable("LCOV LF/LH line counts were not present"),
        "branch": metric_from_counts("branch", summary["branch_found"], summary["branch_hit"])
        if summary["branch_found"] > 0
        else unavailable("LCOV BRF/BRH branch counts were not present"),
    }


def walk(value: Any) -> Iterable[Any]:
    yield value
    if isinstance(value, Mapping):
        for item in value.values():
            yield from walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk(item)


def text_blob(value: Any) -> str:
    parts: list[str] = []
    for item in walk(value):
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, (int, float)) and not isinstance(item, bool):
            parts.append(str(item))
    return "\n".join(parts).lower()


def collect_dicts(value: Any) -> list[Mapping[str, Any]]:
    return [item for item in walk(value) if isinstance(item, Mapping)]


def collect_key_values(value: Any, key: str) -> list[Any]:
    values: list[Any] = []
    for item in collect_dicts(value):
        if key in item:
            values.append(item[key])
    return values


def sum_numeric_keys(value: Any, keys: Sequence[str]) -> int:
    total = 0
    for item in collect_dicts(value):
        for key in keys:
            if key in item:
                total += as_int(item[key])
    return total


def any_token(value: Any, tokens: Sequence[str]) -> bool:
    blob = text_blob(value)
    return any(token.lower() in blob for token in tokens)


def opcode_count(runtime_metrics: Any, opcodes: Sequence[str], *, successful_only: bool = False) -> int:
    wanted = {opcode.lower() for opcode in opcodes}
    count = 0
    for item in collect_dicts(runtime_metrics):
        opcode = item.get("opcode")
        if not isinstance(opcode, str) or opcode.lower() not in wanted:
            continue
        if successful_only and item.get("status") not in (None, "complete", "pass", "ok"):
            continue
        count += 1
    return count


def event_count(runtime_metrics: Any, kinds: Sequence[str]) -> int:
    wanted = {kind.lower() for kind in kinds}
    count = 0
    for item in collect_dicts(runtime_metrics):
        kind = item.get("kind")
        if isinstance(kind, str) and kind.lower() in wanted:
            count += 1
    return count


def queue_closed(runtime_metrics: Any) -> bool:
    for item in collect_dicts(runtime_metrics):
        if "submitted" in item and "retired" in item:
            if as_int(item.get("submitted")) != as_int(item.get("retired")):
                return False
    return True


def pending_count_zero(runtime_metrics: Any) -> bool:
    pending_values = collect_key_values(runtime_metrics, "pending_count")
    if pending_values:
        checks: list[bool] = []
        for value in pending_values:
            if isinstance(value, Mapping):
                checks.extend(as_int(item, -1) == 0 for item in value.values())
            else:
                checks.append(as_int(value, -1) == 0)
        return bool(checks) and all(checks)

    queue_states = collect_key_values(runtime_metrics, "queue_state")
    if queue_states:
        return queue_closed(queue_states)

    return queue_closed(runtime_metrics) and (
        sum_numeric_keys(runtime_metrics, ("commands_submitted",))
        == sum_numeric_keys(runtime_metrics, ("commands_completed",))
    )


def feature_bin(name: str, hit: bool, evidence: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "hit": bool(hit),
        "evidence": dict(evidence),
    }


def build_feature_bins(runtime_metrics: Any | None) -> list[dict[str, Any]]:
    if runtime_metrics is None:
        return [
            feature_bin(name, False, {"reason": "runtime metrics were not available"})
            for name in FEATURE_BINS
        ]

    queue_values = collect_key_values(runtime_metrics, "queue_state")
    queue_count = 0
    for value in queue_values:
        if isinstance(value, Mapping):
            queue_count = max(queue_count, len(value))
    queue_count = max(queue_count, len(set(collect_key_values(runtime_metrics, "queue_id"))))
    command_category_text = text_blob(runtime_metrics)

    dma_fill_count = opcode_count(runtime_metrics, ("dma_fill",), successful_only=True)
    dma_copy_count = opcode_count(runtime_metrics, ("dma_copy",), successful_only=True)
    h2d_count = opcode_count(runtime_metrics, ("host_to_device",), successful_only=True)
    d2h_count = opcode_count(runtime_metrics, ("device_to_host",), successful_only=True)
    fence_signal_count = opcode_count(runtime_metrics, ("fence_signal",), successful_only=True)
    fence_wait_count = opcode_count(runtime_metrics, ("fence_wait",), successful_only=True)
    reset_count = opcode_count(runtime_metrics, ("reset",), successful_only=True)

    completion_interrupts = max(
        sum_numeric_keys(runtime_metrics, ("completion_interrupts",)),
        event_count(runtime_metrics, ("completion",)),
    )
    error_interrupts = max(
        sum_numeric_keys(runtime_metrics, ("error_interrupts",)),
        event_count(runtime_metrics, ("error",)),
    )
    mmu_faults = max(
        sum_numeric_keys(runtime_metrics, ("mmu_faults", "dma_bounds_errors")),
        command_category_text.count("err_mmu_fault"),
    )
    scheduler_faults = max(
        sum_numeric_keys(runtime_metrics, ("scheduler_faults",)),
        command_category_text.count("err_scheduler_fault"),
    )
    abi_hit = any_token(runtime_metrics, ABI_SYMBOL_TOKENS)
    native_categories = {
        token for token in NATIVE_COMMAND_TOKENS if token.lower() in command_category_text
    }

    return [
        feature_bin("queues", queue_count > 0, {"queue_count": queue_count}),
        feature_bin("dma_fill", dma_fill_count > 0, {"opcode_count": dma_fill_count}),
        feature_bin("dma_copy", dma_copy_count > 0, {"opcode_count": dma_copy_count}),
        feature_bin("dma_copy_h2d", h2d_count > 0, {"opcode_count": h2d_count}),
        feature_bin("dma_copy_d2h", d2h_count > 0, {"opcode_count": d2h_count}),
        feature_bin("fence_signal", fence_signal_count > 0, {"opcode_count": fence_signal_count}),
        feature_bin("fence_wait", fence_wait_count > 0, {"opcode_count": fence_wait_count}),
        feature_bin("reset", reset_count > 0, {"opcode_count": reset_count}),
        feature_bin(
            "completion_interrupt",
            completion_interrupts > 0,
            {"event_or_counter_count": completion_interrupts},
        ),
        feature_bin(
            "error_interrupt",
            error_interrupts > 0,
            {"event_or_counter_count": error_interrupts},
        ),
        feature_bin("mmu_fault", mmu_faults > 0, {"fault_count": mmu_faults}),
        feature_bin("scheduler_fault", scheduler_faults > 0, {"fault_count": scheduler_faults}),
        feature_bin("abi_symbol_coverage", abi_hit, {"tokens": list(ABI_SYMBOL_TOKENS)}),
        feature_bin(
            "native_command_categories",
            len(native_categories) >= 4,
            {"categories_seen": sorted(native_categories)},
        ),
        feature_bin("pending_count_zero", pending_count_zero(runtime_metrics), {}),
    ]


def functional_percent(feature_bins: Sequence[Mapping[str, Any]]) -> float:
    if not feature_bins:
        return 0.0
    hits = sum(1 for item in feature_bins if item.get("hit") is True)
    return round((hits / len(feature_bins)) * 100.0, 3)


def load_runtime_metrics(path: Path | None) -> tuple[Any | None, dict[str, Any]]:
    info = artifact_info(path)
    if path is None:
        info["load_status"] = "not_provided"
        return None, info
    if not path.exists():
        info["load_status"] = "missing"
        return None, info
    if path.stat().st_size == 0:
        info["load_status"] = "empty"
        return None, info
    try:
        data = load_json(path)
    except json.JSONDecodeError as exc:
        info["load_status"] = "invalid_json"
        info["error"] = str(exc)
        return None, info
    info["load_status"] = "loaded"
    return data, info


def build_report(
    coverage_dat: Path,
    coverage_info: Path | None,
    runtime_metrics_path: Path | None,
    require_functional_100: bool,
) -> tuple[dict[str, Any], int]:
    runtime_metrics, runtime_artifact = load_runtime_metrics(runtime_metrics_path)
    lcov = parse_lcov_info(coverage_info)
    bins = build_feature_bins(runtime_metrics)
    functional = functional_percent(bins)

    artifact_failures: list[str] = []
    coverage_dat_artifact = artifact_info(coverage_dat)
    coverage_info_artifact = artifact_info(coverage_info)
    if not coverage_dat_artifact["non_empty"]:
        artifact_failures.append("coverage_dat_missing_or_empty")
    if runtime_metrics_path is not None and runtime_artifact.get("load_status") != "loaded":
        artifact_failures.append("runtime_metrics_unavailable")

    requirement_failures: list[str] = []
    if require_functional_100 and functional != 100.0:
        requirement_failures.append("functional_coverage_below_100")

    status = "pass" if not artifact_failures and not requirement_failures else "fail"
    payload = {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "status": status,
        "functional_coverage_percent": functional,
        "feature_bins": bins,
        "verilator_artifacts": {
            "coverage_dat": coverage_dat_artifact,
            "coverage_info": coverage_info_artifact,
        },
        "runtime_metrics": runtime_artifact,
        "source_metrics": lcov.get("source", unavailable("coverage info unavailable")),
        "toggle_metrics": lcov.get("toggle", unavailable("coverage info unavailable")),
        "line_metrics": lcov.get("line", unavailable("coverage info unavailable")),
        "lcov_info": lcov,
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "requirements": {
            "require_functional_100": require_functional_100,
            "failures": requirement_failures,
        },
        "artifact_failures": artifact_failures,
    }
    return payload, 0 if status == "pass" else 1


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a Celviz GPGPU Verilator coverage JSON report."
    )
    parser.add_argument("--coverage-dat", required=True, type=Path, help="Verilator coverage.dat path")
    parser.add_argument("--coverage-info", type=Path, help="Optional LCOV .info path")
    parser.add_argument("--runtime-metrics", required=True, type=Path, help="runtime_metrics.json path")
    parser.add_argument("--output", required=True, type=Path, help="Output JSON report path")
    parser.add_argument(
        "--require-functional-100",
        action="store_true",
        help="Fail when any required functional coverage bin is not hit",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    report, exit_code = build_report(
        args.coverage_dat,
        args.coverage_info,
        args.runtime_metrics,
        args.require_functional_100,
    )
    write_json(args.output, report)
    print(
        f"celviz_gpgpu_verilator_coverage: {report['status']} "
        f"functional={report['functional_coverage_percent']:.3f}% "
        f"output={args.output}"
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
