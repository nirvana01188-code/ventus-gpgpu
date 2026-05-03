#!/usr/bin/env python3
"""Generate clean-room synthesis/PPA proxy evidence for Celviz GPGPU.

The report is an engineering proxy, not a synthesis signoff. It combines local
RTL/source structure counts with the public proxy tier model already tracked in
the Rank 1 artifacts, then emits a deterministic JSON bundle that can be gated.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


SCHEMA = "celviz.gpgpu.ppa_proxy.v1"
CLEAN_ROOM_SCOPE = (
    "clean-room synthesis/PPA proxy evidence for the Ventus-based Celviz GPGPU "
    "IP only; not a physical synthesis report, STA/timing closure, power signoff, "
    "licensed Vivante collateral review, or silicon/tapeout readiness claim"
)
RTL_GLOBS = (
    "ventus/src/**/*.scala",
    "sim-verilator/*.cpp",
    "sim-verilator/*.hpp",
    "sim-verilator/*.h",
)
CORE_RTL_MARKERS = (
    "CelvizGPGPUDebug",
    "celviz_debug",
    "commandDoorbellReg",
    "completionCountReg",
    "irqPendingReg",
    "errorStatusReg",
    "celviz_gpgpu_runtime_proxy",
)
PUBLIC_BASELINE_TIERS = ("CC8000L", "CC8000")


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


def iter_files(root: Path, patterns: Iterable[str]) -> list[Path]:
    files: set[Path] = set()
    for pattern in patterns:
        files.update(path for path in root.glob(pattern) if path.is_file())
    return sorted(files)


def count_text_file(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    nonblank = [line for line in lines if line.strip()]
    marker_hits = {marker: text.count(marker) for marker in CORE_RTL_MARKERS}
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "lines": len(lines),
        "nonblank_lines": len(nonblank),
        "marker_hits": marker_hits,
        "marker_hit_count": sum(marker_hits.values()),
    }


def tool_probe(name: str, version_args: tuple[str, ...]) -> dict[str, Any]:
    path = shutil.which(name)
    result: dict[str, Any] = {"tool": name, "available": bool(path), "path": path}
    if not path:
        return result
    try:
        completed = subprocess.run(
            [path, *version_args],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=10,
        )
        result["exit_code"] = completed.returncode
        result["version_output"] = completed.stdout.splitlines()[:5]
    except Exception as exc:  # pragma: no cover - defensive probe only
        result["probe_error"] = str(exc)
    return result


def public_tier_proxy(shader_scaling: Mapping[str, Any]) -> list[dict[str, Any]]:
    tiers = shader_scaling.get("tiers", [])
    rows: list[dict[str, Any]] = []
    for item in tiers:
        tier = str(item.get("tier"))
        if tier not in PUBLIC_BASELINE_TIERS:
            continue
        shader_units = as_int(item.get("shader_units_vec1"))
        fp32 = as_int(item.get("fp32_ops_per_cycle"))
        fp16 = as_int(item.get("fp16_ops_per_cycle"))
        rows.append(
            {
                "tier": tier,
                "shader_units_vec1": shader_units,
                "fp32_ops_per_cycle_public_proxy": fp32,
                "fp16_ops_per_cycle_public_proxy": fp16,
                "fp32_ops_per_shader_unit": round(fp32 / shader_units, 3) if shader_units else None,
                "fp16_ops_per_shader_unit": round(fp16 / shader_units, 3) if shader_units else None,
                "comparison_scope": "public tier proxy only; not measured local RTL PPA",
            }
        )
    return rows


def estimate_proxy_metrics(source_summary: Mapping[str, Any], tiers: list[dict[str, Any]]) -> dict[str, Any]:
    rtl_nonblank = as_int(source_summary.get("nonblank_lines"))
    marker_hits = as_int(source_summary.get("marker_hit_count"))
    max_shader_units = max((as_int(item.get("shader_units_vec1")) for item in tiers), default=0)

    # These are deliberately dimensionless proxies anchored to auditable source
    # counts. They are used to compare internal build evidence over time, not to
    # claim silicon area, MHz, or watts.
    area_units = rtl_nonblank + marker_hits * 32
    control_complexity = marker_hits + len(tiers) * 8
    frequency_index = round(1_000_000 / max(1, rtl_nonblank + control_complexity), 3)
    activity_index = round((marker_hits + max_shader_units) / max(1, rtl_nonblank), 6)
    power_index = round(activity_index * max(1, len(tiers)), 6)
    return {
        "area_proxy_units": area_units,
        "frequency_proxy_index": frequency_index,
        "activity_proxy_index": activity_index,
        "power_proxy_index": power_index,
        "control_complexity_index": control_complexity,
        "proxy_formula_version": "source-count-v1",
        "claim_boundary": "dimensionless proxy metrics; not synthesized area/frequency/power",
    }


def build_report(repo_root: Path, artifact_root: Path) -> dict[str, Any]:
    shader_scaling_path = artifact_root / "model" / "outputs" / "shader_unit_scaling.json"
    shader_scaling = load_json(shader_scaling_path)
    rtl_files = iter_files(repo_root, RTL_GLOBS)
    file_summaries = [count_text_file(path) for path in rtl_files]
    source_summary = {
        "file_count": len(file_summaries),
        "bytes": sum(as_int(item.get("bytes")) for item in file_summaries),
        "lines": sum(as_int(item.get("lines")) for item in file_summaries),
        "nonblank_lines": sum(as_int(item.get("nonblank_lines")) for item in file_summaries),
        "marker_hit_count": sum(as_int(item.get("marker_hit_count")) for item in file_summaries),
        "marker_hits": {
            marker: sum(as_int(item.get("marker_hits", {}).get(marker)) for item in file_summaries)
            for marker in CORE_RTL_MARKERS
        },
    }
    public_tiers = public_tier_proxy(shader_scaling)
    tools = {
        "yosys": tool_probe("yosys", ("-V",)),
        "verilator": tool_probe("verilator", ("--version",)),
        "sbt": tool_probe("sbt", ("--script-version",)),
    }
    checks = [
        {
            "name": "rtl_sources_present",
            "pass": source_summary["file_count"] > 0 and source_summary["nonblank_lines"] > 0,
        },
        {
            "name": "celviz_markers_present",
            "pass": source_summary["marker_hit_count"] > 0,
        },
        {
            "name": "public_baseline_tiers_present",
            "pass": {item["tier"] for item in public_tiers} == set(PUBLIC_BASELINE_TIERS),
        },
        {
            "name": "proxy_metrics_generated",
            "pass": True,
        },
        {
            "name": "limitations_declared",
            "pass": True,
        },
    ]
    status = "pass" if all(item["pass"] for item in checks) else "fail"
    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "status": status,
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "source_summary": source_summary,
        "source_files": file_summaries,
        "public_baseline_tiers": public_tiers,
        "proxy_metrics": estimate_proxy_metrics(source_summary, public_tiers),
        "tool_availability": tools,
        "checks": checks,
        "limitations": [
            "No claim of completed logic synthesis, physical implementation, STA, CDC, DFT, or power signoff.",
            "Public CC8000L/CC8000 tier rows are used only as clean-room proxy comparison points.",
            "Proxy indices are deterministic engineering evidence, not MHz, mm^2, mW, or TOPS measurements.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Celviz GPGPU synthesis/PPA proxy evidence.")
    parser.add_argument("--repo-root", type=Path, default=Path("."), help="Repository root")
    parser.add_argument(
        "--artifact-root",
        type=Path,
        default=Path("artifacts/rank_01_vivante_3d_gpgpu_ip"),
        help="Rank 1 artifact root",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/rank_01_vivante_3d_gpgpu_ip/ppa/ppa_proxy_report.json"),
        help="Output report path",
    )
    args = parser.parse_args()

    report = build_report(args.repo_root.resolve(), args.artifact_root)
    write_json(args.output, report)
    print(
        "celviz_gpgpu_ppa_proxy: "
        f"{report['status']} files={report['source_summary']['file_count']} "
        f"markers={report['source_summary']['marker_hit_count']} "
        f"output={args.output}"
    )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
