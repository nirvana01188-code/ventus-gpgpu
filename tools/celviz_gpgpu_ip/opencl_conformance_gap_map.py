#!/usr/bin/env python3
"""Generate an OpenCL conformance gap map from Celviz GPGPU evidence.

The generated diagram is intentionally a gap map. It records the current
OpenCL-like subset evidence and the remaining work needed before any official
OpenCL conformance discussion. It is not a conformance-pass report.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "celviz.gpgpu.opencl_conformance_gap_map.v1"
DEFAULT_ARTIFACT_ROOT = Path("artifacts/rank_01_vivante_3d_gpgpu_ip")
DEFAULT_OUTPUT_DIR = DEFAULT_ARTIFACT_ROOT / "verification"
CLEAN_ROOM_SCOPE = (
    "OpenCL-like subset gap map for the Ventus-based Celviz GPGPU IP proxy; "
    "not an official OpenCL conformance claim, not Khronos CTS evidence, and "
    "not a proprietary Vivante driver/compiler/firmware compatibility claim"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"missing required evidence file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON in evidence file: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"evidence file is not a JSON object: {path}")
    return payload


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def require_status(path: Path, payload: Mapping[str, Any]) -> None:
    status = payload.get("status")
    if status != "pass":
        raise SystemExit(f"required evidence is not passing: {path} status={status!r}")


def text_lines(items: list[str], x: int, y: int, size: int = 16, fill: str = "#243041", gap: int = 26) -> str:
    out: list[str] = []
    for index, item in enumerate(items):
        out.append(
            f'<text x="{x}" y="{y + index * gap}" font-size="{size}" '
            f'fill="{fill}">{html.escape(item)}</text>'
        )
    return "\n".join(out)


def box(x: int, y: int, w: int, h: int, fill: str, stroke: str, title: str, body: list[str]) -> str:
    title_xml = (
        f'<text x="{x + 24}" y="{y + 42}" font-size="22" font-weight="700" '
        f'fill="#172033">{html.escape(title)}</text>'
    )
    body_xml = text_lines(body, x + 24, y + 82, size=15, fill="#2b3648", gap=24)
    return "\n".join(
        [
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="2"/>',
            title_xml,
            body_xml,
        ]
    )


def pill(x: int, y: int, text: str, fill: str, stroke: str, color: str = "#172033") -> str:
    width = max(150, 9 * len(text) + 28)
    return "\n".join(
        [
            f'<rect x="{x}" y="{y}" width="{width}" height="34" rx="17" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="1.5"/>',
            f'<text x="{x + 14}" y="{y + 23}" font-size="14" font-weight="700" '
            f'fill="{color}">{html.escape(text)}</text>',
        ]
    )


def arrow(x1: int, y1: int, x2: int, y2: int, color: str = "#5a6578") -> str:
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" '
        'stroke-width="3" marker-end="url(#arrow)"/>'
    )


def generate_svg(report: Mapping[str, Any]) -> str:
    metrics = report["current_evidence"]["metrics"]
    kernels = ", ".join(report["current_evidence"]["kernels"])
    current_body = [
        f"{metrics['kernel_count']} subset kernels: {kernels}",
        f"Compiler IR: {metrics['virtual_registers']} vregs, {metrics['predicate_registers']} pregs",
        f"Lowering/execution: {metrics['total_uops']} uops",
        f"Memory events observed: {metrics['memory_events']}",
        "Runtime queue/fence/event proxy: pass",
        f"Functional acceptance bins: {metrics['hit_bins']}/{metrics['total_bins']}",
    ]
    expansion_body = [
        "Grow OpenCL C subset by workload class",
        "Add builtins, atomics, math, images, samplers",
        "Tighten compiler/runtime ABI contracts",
        "Expand negative/error conformance-style tests",
        "Model global/local/constant memory details",
        "Raise structural RTL coverage separately",
    ]
    official_body = [
        "Khronos CTS or licensed official test suite",
        "Official ICD/runtime semantics",
        "Production compiler path such as LLVM/SPIR-V",
        "Device/profile/device-info precision semantics",
        "Production OS driver integration",
        "Certification/legal submission package",
    ]

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1560" height="940" viewBox="0 0 1560 940">
  <defs>
    <marker id="arrow" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto" markerUnits="strokeWidth">
      <path d="M2,2 L10,6 L2,10 Z" fill="#5a6578"/>
    </marker>
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="130%">
      <feDropShadow dx="0" dy="8" stdDeviation="8" flood-color="#142033" flood-opacity="0.14"/>
    </filter>
  </defs>
  <rect width="1560" height="940" fill="#f6f8fb"/>
  <rect x="0" y="0" width="1560" height="130" fill="#172033"/>
  <text x="54" y="58" font-size="34" font-weight="800" fill="#ffffff">Celviz GPGPU IP: OpenCL Conformance Gap Map</text>
  <text x="54" y="96" font-size="18" fill="#c9d4e6">Current status: OpenCL-like subset evidence only. This is not an official OpenCL conformance pass.</text>

  <g filter="url(#shadow)">
    {box(54, 178, 430, 344, "#e8f7ef", "#2f9f64", "Implemented Evidence", current_body)}
    {box(565, 178, 430, 344, "#fff5dc", "#d59624", "Conformance Expansion", expansion_body)}
    {box(1076, 178, 430, 344, "#fde8e8", "#d14b4b", "Official Gap", official_body)}
  </g>

  {arrow(494, 350, 555, 350)}
  {arrow(1005, 350, 1066, 350)}

  <text x="54" y="592" font-size="24" font-weight="800" fill="#172033">Evidence Chain</text>
  <rect x="54" y="625" width="1452" height="115" rx="8" fill="#ffffff" stroke="#c8d1de" stroke-width="2"/>
  {pill(82, 666, "OpenCL-like C subset", "#e8f7ef", "#2f9f64")}
  {arrow(292, 683, 352, 683)}
  {pill(372, 666, "Kernel ABI JSON", "#e8f7ef", "#2f9f64")}
  {arrow(550, 683, 610, 683)}
  {pill(630, 666, "Compiler IR", "#e8f7ef", "#2f9f64")}
  {arrow(792, 683, 852, 683)}
  {pill(872, 666, "Micro-op execution", "#e8f7ef", "#2f9f64")}
  {arrow(1087, 683, 1147, 683)}
  {pill(1167, 666, "Runtime/driver proxy", "#e8f7ef", "#2f9f64")}

  <text x="54" y="802" font-size="24" font-weight="800" fill="#172033">Claim Boundary</text>
  <rect x="54" y="828" width="1452" height="62" rx="8" fill="#172033" stroke="#172033" stroke-width="2"/>
  <text x="82" y="867" font-size="18" font-weight="700" fill="#ffffff">Allowed claim:</text>
  <text x="214" y="867" font-size="18" fill="#e6eefb">clean-room OpenCL-like subset evidence with 348/348 functional acceptance bins.</text>
  <text x="852" y="867" font-size="18" font-weight="700" fill="#ffffff">Not claimed:</text>
  <text x="970" y="867" font-size="18" fill="#e6eefb">Khronos/OpenCL conformance, Vivante compatibility, production driver readiness.</text>

  <text x="54" y="918" font-size="13" fill="#6b7687">Generated {html.escape(str(report['generated_at']))} from repository evidence. Schema: {html.escape(str(report['schema']))}</text>
</svg>
"""


def collect_report(artifact_root: Path, svg_path: Path) -> dict[str, Any]:
    paths = {
        "opencl_subset": artifact_root / "demo" / "opencl_subset" / "opencl_subset_evidence.json",
        "kernel_lowering": artifact_root / "lowering" / "kernel_lowering_report.json",
        "microop_execution": artifact_root / "microop_execution" / "microop_execution_report.json",
        "compiler_ir": artifact_root / "compiler_ir" / "compiler_ir_report.json",
        "driver_submission": artifact_root / "driver_submission" / "driver_submission_report.json",
        "coverage": artifact_root / "verification" / "verification_coverage_100.json",
    }
    evidence = {name: load_json(path) for name, path in paths.items()}
    for name, payload in evidence.items():
        require_status(paths[name], payload)

    kernels = [item.get("name") for item in evidence["opencl_subset"].get("kernels", [])]
    kernels = [str(name) for name in kernels if name]
    if len(kernels) < 4:
        raise SystemExit(f"expected at least four OpenCL-like subset kernels, found {len(kernels)}")

    lowering = evidence["kernel_lowering"]
    microop = evidence["microop_execution"]
    compiler_ir = evidence["compiler_ir"]
    coverage = evidence["coverage"]

    metrics = {
        "kernel_count": int(evidence["opencl_subset"].get("kernel_count", len(kernels))),
        "total_uops": int(lowering.get("total_uops", microop.get("total_uops_executed", 0))),
        "memory_events": int(microop.get("total_memory_events", 0)),
        "virtual_registers": int(compiler_ir.get("total_virtual_registers", 0)),
        "predicate_registers": int(compiler_ir.get("total_predicate_registers", 0)),
        "hit_bins": int(coverage.get("hit_bins", 0)),
        "total_bins": int(coverage.get("total_bins", 0)),
        "coverage_percent": float(coverage.get("coverage_percent", 0.0)),
    }
    if metrics["coverage_percent"] < 100.0:
        raise SystemExit(f"functional/acceptance coverage is below 100%: {metrics['coverage_percent']}")

    return {
        "schema": SCHEMA,
        "status": "pass",
        "generated_at": utc_now(),
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "diagram": str(svg_path),
        "current_evidence": {
            "claim": "OpenCL-like subset evidence only; non-conformant",
            "kernels": kernels,
            "metrics": metrics,
            "source_reports": {name: str(path) for name, path in paths.items()},
        },
        "conformance_expansion_work": [
            "expand OpenCL C subset coverage beyond four representative kernels",
            "add builtins, math, atomics, images, samplers, local memory, and event semantics",
            "connect compiler/runtime ABI to production-grade binary/codegen path",
            "increase directed, random, negative, and long-run conformance-style workloads",
            "keep RTL structural coverage separate from functional acceptance coverage",
        ],
        "official_conformance_gap": [
            "Khronos CTS or licensed official conformance suite is not present",
            "official OpenCL ICD/runtime stack is not present",
            "full OpenCL C/profile/device-info/precision semantics are not present",
            "production OS kernel driver and certification package are not present",
        ],
        "claim_boundary": {
            "allowed": "clean-room OpenCL-like subset evidence with functional/acceptance coverage",
            "not_claimed": [
                "official OpenCL conformance",
                "Khronos CTS pass",
                "proprietary Vivante compatibility",
                "production driver or silicon signoff",
            ],
        },
    }


def verify_outputs(svg_path: Path, report_path: Path) -> None:
    if not svg_path.exists() or svg_path.stat().st_size <= 0:
        raise SystemExit(f"SVG was not generated: {svg_path}")
    if not report_path.exists() or report_path.stat().st_size <= 0:
        raise SystemExit(f"JSON report was not generated: {report_path}")
    svg = svg_path.read_text(encoding="utf-8")
    required_svg_terms = (
        "OpenCL Conformance Gap Map",
        "not an official OpenCL conformance pass",
        "Implemented Evidence",
        "Conformance Expansion",
        "Official Gap",
        "348/348",
    )
    for term in required_svg_terms:
        if term not in svg:
            raise SystemExit(f"generated SVG is missing required term: {term}")
    report = load_json(report_path)
    if report.get("schema") != SCHEMA or report.get("status") != "pass":
        raise SystemExit(f"generated report failed schema/status check: {report_path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)

    root = repo_root()
    artifact_root = args.artifact_root
    output_dir = args.output_dir
    if not artifact_root.is_absolute():
        artifact_root = root / artifact_root
    if not output_dir.is_absolute():
        output_dir = root / output_dir

    svg_path = output_dir / "opencl_conformance_gap_map.svg"
    report_path = output_dir / "opencl_conformance_gap_map.json"

    if not args.verify_only:
        report = collect_report(artifact_root, svg_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        svg_path.write_text(generate_svg(report), encoding="utf-8")
        write_json(report_path, report)

    verify_outputs(svg_path, report_path)
    print(f"opencl_conformance_gap_map: pass svg={svg_path} report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
