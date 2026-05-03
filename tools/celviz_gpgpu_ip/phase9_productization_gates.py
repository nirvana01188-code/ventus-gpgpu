#!/usr/bin/env python3
"""Generate Phase-9 productization gate evidence for Celviz GPGPU IP.

Phase 9 turns the Phase-8 closure backlog into explicit productization gates.
It records what is already backed by local proxy evidence, and keeps synthesis,
STA, power, DFT, physical implementation, and silicon signoff blocked until
real signoff collateral exists.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "celviz.gpgpu.phase9_productization_gates.v1"
DEFAULT_ARTIFACT_ROOT = Path("artifacts/rank_01_vivante_3d_gpgpu_ip")
DEFAULT_DOC = Path("docs/celviz-gpgpu-ip/PHASE9_PRODUCTIZATION_GATES.md")
CLEAN_ROOM_SCOPE = (
    "Phase-9 productization gate checklist for the Ventus-based Celviz GPGPU "
    "IP proxy. It records RTL structural-coverage uplift evidence and "
    "synthesis-readiness probes, but it is not target-library synthesis, not "
    "STA, not power signoff, not DFT, not physical implementation, not silicon "
    "signoff, and not proprietary Vivante compatibility."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def artifact(path: Path) -> dict[str, Any]:
    exists = path.exists()
    size = path.stat().st_size if exists else 0
    return {
        "path": path.as_posix(),
        "exists": exists,
        "size_bytes": size,
        "non_empty": bool(exists and size > 0),
    }


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def status_pass(value: Mapping[str, Any]) -> bool:
    return value.get("status") == "pass"


def pass_check(name: str, passed: bool, evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {"name": name, "pass": bool(passed), "evidence": dict(evidence or {})}


def gate(
    gate_id: str,
    title: str,
    category: str,
    state: str,
    current_evidence: list[str],
    required_for_productization: list[str],
    checks: list[dict[str, Any]],
    claim_boundary: str,
    next_actions: list[str],
) -> dict[str, Any]:
    if state == "pass":
        status = "pass" if all(item.get("pass") is True for item in checks) else "fail"
    elif state == "blocked":
        status = "blocked"
    elif state == "partial":
        status = "partial" if all(item.get("pass") is True for item in checks) else "blocked"
    else:
        status = state
    return {
        "id": gate_id,
        "title": title,
        "category": category,
        "status": status,
        "current_state": state,
        "claim_boundary": claim_boundary,
        "current_evidence": current_evidence,
        "required_for_productization": required_for_productization,
        "checks": checks,
        "next_actions": next_actions,
    }


def build_report(artifact_root: Path) -> dict[str, Any]:
    verification = artifact_root / "verification"
    synthesis_dir = artifact_root / "synthesis"
    ppa_dir = artifact_root / "ppa"
    e8_dir = verification / "verilator_coverage"
    supplemental_dir = verification / "verilator_supplemental_phase1"
    phase8_dir = verification / "phase8_work_package_artifacts"

    e8_report_path = e8_dir / "verilator_coverage_report.json"
    e8 = load_json(e8_report_path)
    supplemental_path = supplemental_dir / "phase1_supplemental_evidence.json"
    supplemental = load_json(supplemental_path)
    synth_path = synthesis_dir / "synthesis_readiness_report.json"
    synth = load_json(synth_path)
    yosys_path = synthesis_dir / "yosys_synthesis_probe_report.json"
    yosys = load_json(yosys_path)
    ppa_path = ppa_dir / "ppa_proxy_report.json"
    ppa = load_json(ppa_path)
    phase8_signoff_path = phase8_dir / "signoff_requirements.json"
    phase8_signoff = load_json(phase8_signoff_path)
    phase8_structural_path = phase8_dir / "structural_coverage_uplift_plan.json"
    phase8_structural = load_json(phase8_structural_path)

    fixture_names = ("directed", "random", "fault", "stress")
    fixture_artifacts = {
        name: artifact(supplemental_dir / "fixtures" / f"{name}.json")
        for name in fixture_names
    }
    run_artifacts = {
        name: artifact(supplemental_dir / "runs" / f"{name}.metrics.json")
        for name in fixture_names
    }
    e8_artifacts = {
        "coverage_dat": artifact(e8_dir / "coverage.dat"),
        "coverage_info": artifact(e8_dir / "coverage.info"),
        "run_log": artifact(e8_dir / "run.log"),
        "report_index": artifact(e8_dir / "report" / "index.html"),
        "annotated_dut": artifact(e8_dir / "report" / "dut.v"),
        "report_json": artifact(e8_report_path),
    }
    synthesis_artifacts = {
        "synthesis_readiness": artifact(synth_path),
        "yosys_probe": artifact(yosys_path),
        "ppa_proxy": artifact(ppa_path),
        "sanitized_dut": artifact(synthesis_dir / "dut.coverage_sanitized.v"),
    }

    e8_lcov = e8.get("lcov_info", {}) if isinstance(e8.get("lcov_info"), dict) else {}
    e8_line = e8.get("line_metrics", {})
    e8_branch = e8_lcov.get("branch", {})
    e8_toggle = e8.get("toggle_metrics", {})
    structural_target_total = supplemental.get("observed_metrics", {}).get("structural_target_total")
    structural_target_hits = supplemental.get("observed_metrics", {}).get("structural_target_hit_count")

    gates = [
        gate(
            "phase9_rtl_supplemental_fixtures",
            "Directed/random/fault/stress supplemental fixtures",
            "rtl_structural_coverage_uplift",
            "pass",
            [supplemental_path.as_posix()]
            + [item["path"] for item in fixture_artifacts.values()]
            + [item["path"] for item in run_artifacts.values()],
            [
                "All four fixture classes exist and are replayable.",
                "Fast gate metrics close queues and record expected negative paths.",
                "Fixture hashes are recorded so slow coverage reruns can prove input stability.",
            ],
            [
                pass_check("supplemental_status_pass", status_pass(supplemental), {"status": supplemental.get("status")}),
                pass_check(
                    "structural_targets_all_hit",
                    structural_target_total is not None and structural_target_hits == structural_target_total,
                    {
                        "hit": structural_target_hits,
                        "total": structural_target_total,
                        "percent": supplemental.get("observed_metrics", {}).get("structural_target_percent"),
                    },
                ),
                pass_check("directed_fixture_present", fixture_artifacts["directed"]["non_empty"], fixture_artifacts["directed"]),
                pass_check("random_fixture_present", fixture_artifacts["random"]["non_empty"], fixture_artifacts["random"]),
                pass_check("fault_fixture_present", fixture_artifacts["fault"]["non_empty"], fixture_artifacts["fault"]),
                pass_check("stress_fixture_present", fixture_artifacts["stress"]["non_empty"], fixture_artifacts["stress"]),
            ],
            "Pass means local clean-room supplemental fixtures are generated and fast-gated; it does not mean RTL structural coverage is closed.",
            [
                "Replay these fixtures through the coverage-enabled Verilator runtime lane.",
                "Track per-fixture LCOV deltas for line, branch, and toggle metrics.",
            ],
        ),
        gate(
            "phase9_verilator_line_branch_toggle_observation",
            "Verilator line/branch/toggle observation",
            "rtl_structural_coverage_uplift",
            "partial",
            [item["path"] for item in e8_artifacts.values()],
            [
                "coverage.dat and coverage.info are non-empty.",
                "LCOV line and branch metrics are available.",
                "Toggle metrics are available or explicitly reported unavailable with reason.",
                "RTL structural metrics remain separate from functional 100% coverage.",
            ],
            [
                pass_check("e8_report_status_pass", status_pass(e8), {"status": e8.get("status")}),
                pass_check("coverage_dat_non_empty", e8_artifacts["coverage_dat"]["non_empty"], e8_artifacts["coverage_dat"]),
                pass_check("coverage_info_non_empty", e8_artifacts["coverage_info"]["non_empty"], e8_artifacts["coverage_info"]),
                pass_check("line_metric_recorded", bool(e8_line), e8_line if isinstance(e8_line, dict) else {}),
                pass_check("branch_metric_recorded", bool(e8_branch), e8_branch if isinstance(e8_branch, dict) else {}),
                pass_check(
                    "toggle_metric_recorded_or_reasoned",
                    isinstance(e8_toggle, dict) and e8_toggle.get("status") in {"available", "unavailable"},
                    e8_toggle if isinstance(e8_toggle, dict) else {},
                ),
            ],
            "Partial means Verilator structural metrics are present as observations; productization still requires closure targets, deltas, and waivers.",
            [
                "Define minimum line/branch/toggle thresholds per source module.",
                "Add waiver file for unreachable generated RTL and black-box paths.",
                "Require a delta report before marking this gate pass for productization.",
            ],
        ),
        gate(
            "phase9_synthesis_probe_readiness",
            "Synthesis readiness and bounded Yosys probe",
            "synthesis",
            "partial",
            [item["path"] for item in synthesis_artifacts.values()],
            [
                "Source scope and synthesis-readiness checks pass.",
                "Yosys probe records either bounded synthesis stats or explicit generated-Verilog blocker.",
                "Target-library synthesis remains blocked until standard-cell and macro libraries exist.",
            ],
            [
                pass_check("synthesis_readiness_status_pass", status_pass(synth), {"status": synth.get("status")}),
                pass_check("yosys_probe_status_pass", status_pass(yosys), {"status": yosys.get("status"), "classification": yosys.get("classification")}),
                pass_check("ppa_proxy_status_pass", status_pass(ppa), {"status": ppa.get("status")}),
                pass_check("no_signoff_overclaim", "not target-library" in str(yosys.get("clean_room_scope", "")) or "not logic synthesis" in str(synth.get("clean_room_scope", ""))),
            ],
            "Partial means source/probe/PPA proxy readiness exists; it is not target-library logic synthesis.",
            [
                "Generate clean synthesis Verilog independent of Verilator coverage annotation.",
                "Add technology-library-independent lint and hierarchy reports.",
                "Add target-library synthesis only after Liberty, RAM macros, and constraints are provided.",
            ],
        ),
        gate(
            "phase9_sta_gate",
            "Static timing analysis gate",
            "signoff",
            "blocked",
            [phase8_signoff_path.as_posix()],
            [
                "SDC clocks, resets, IO delays, false/multicycle paths.",
                "Target PVT/corner list.",
                "STA reports with WNS/TNS, unconstrained path checks, and constraint lint.",
            ],
            [
                pass_check("phase8_names_sta_requirement", any(item.get("name") == "sta" for item in phase8_signoff.get("requirements", []))),
                pass_check("sta_reports_present", False, {"reason": "no STA reports, corner list, or constraints are present"}),
            ],
            "Blocked until real STA inputs and reports exist; proxy timing estimates cannot close this gate.",
            [
                "Create constraints checklist and SDC draft.",
                "Select timing corners after target library is known.",
            ],
        ),
        gate(
            "phase9_power_gate",
            "Power signoff gate",
            "signoff",
            "blocked",
            [phase8_signoff_path.as_posix(), ppa_path.as_posix()],
            [
                "SAIF/VCD activity from representative workloads.",
                "Voltage domains and power intent if used.",
                "Dynamic/leakage/IR inputs and power reports.",
            ],
            [
                pass_check("phase8_names_power_requirement", any(item.get("name") == "power" for item in phase8_signoff.get("requirements", []))),
                pass_check("proxy_ppa_present", status_pass(ppa), {"status": ppa.get("status")}),
                pass_check("power_reports_present", False, {"reason": "proxy PPA is present, but no power signoff reports are present"}),
            ],
            "Blocked until activity, voltage, and real power reports exist; proxy PPA does not close power signoff.",
            [
                "Emit workload VCD/SAIF for representative kernels.",
                "Define voltage/frequency assumptions only after target technology is selected.",
            ],
        ),
        gate(
            "phase9_dft_gate",
            "DFT and test coverage gate",
            "signoff",
            "blocked",
            [phase8_signoff_path.as_posix()],
            [
                "Scan architecture and test clock plan.",
                "ATPG or equivalent test coverage reports.",
                "MBIST/LBIST strategy for memories and logic if required.",
            ],
            [
                pass_check("phase8_names_dft_requirement", any(item.get("name") == "dft" for item in phase8_signoff.get("requirements", []))),
                pass_check("dft_reports_present", False, {"reason": "no scan, ATPG, MBIST, or DFT coverage reports are present"}),
            ],
            "Blocked until DFT insertion strategy and coverage reports exist.",
            [
                "Inventory inferred/register-file/memory structures that need test strategy.",
                "Draft scan clock/reset controllability requirements.",
            ],
        ),
        gate(
            "phase9_physical_implementation_gate",
            "Physical implementation gate",
            "signoff",
            "blocked",
            [phase8_signoff_path.as_posix()],
            [
                "Floorplan, placement, CTS, routing, and extraction reports.",
                "DRC/LVS/antenna reports.",
                "Macro placement and power-grid evidence.",
            ],
            [
                pass_check("phase8_names_physical_requirement", any(item.get("name") == "physical" for item in phase8_signoff.get("requirements", []))),
                pass_check("physical_reports_present", False, {"reason": "no floorplan, P&R, DRC, LVS, antenna, or extraction reports are present"}),
            ],
            "Blocked until real physical implementation evidence exists.",
            [
                "Define top-level physical boundary and macro strategy after synthesizable RTL is selected.",
                "Add physical-report schema before any productization claim.",
            ],
        ),
        gate(
            "phase9_silicon_signoff_gate",
            "Silicon signoff gate",
            "signoff",
            "blocked",
            [phase8_signoff_path.as_posix()],
            [
                "Tapeout checklist, waiver signoff, bring-up plan, validation logs, and measured silicon PPA.",
                "Security/safety/certification evidence if claimed.",
            ],
            [
                pass_check("phase8_names_silicon_requirement", any(item.get("name") == "silicon" for item in phase8_signoff.get("requirements", []))),
                pass_check("silicon_evidence_present", False, {"reason": "no tapeout, bring-up, validation, measured PPA, or certification evidence is present"}),
            ],
            "Blocked until real silicon evidence exists; current project remains a clean-room proxy package.",
            [
                "Keep all silicon-readiness language blocked in active acceptance until measured evidence exists.",
                "Require independent signoff owner approval before changing this gate from blocked.",
            ],
        ),
    ]

    blocked = [item["id"] for item in gates if item["status"] == "blocked"]
    partial = [item["id"] for item in gates if item["status"] == "partial"]
    passed = [item["id"] for item in gates if item["status"] == "pass"]
    report_status = "blocked_for_productization" if blocked else ("partial" if partial else "pass")

    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "status": report_status,
        "productization_ready": False,
        "passed_gates": passed,
        "partial_gates": partial,
        "blocked_gates": blocked,
        "gates": gates,
        "input_artifacts": {
            "e8_verilator": e8_artifacts,
            "supplemental_verilator_phase1": {
                "evidence": artifact(supplemental_path),
                "fixtures": fixture_artifacts,
                "runs": run_artifacts,
            },
            "synthesis": synthesis_artifacts,
            "phase8_signoff_requirements": artifact(phase8_signoff_path),
            "phase8_structural_coverage_uplift_plan": artifact(phase8_structural_path),
        },
        "observed_metrics": {
            "supplemental_structural_targets": supplemental.get("observed_metrics", {}),
            "verilator_line_metrics": e8_line,
            "verilator_branch_metrics": e8_branch,
            "verilator_toggle_metrics": e8_toggle,
            "yosys_classification": yosys.get("classification"),
            "ppa_proxy_status": ppa.get("status"),
        },
        "signoff_boundary": {
            "synthesis_target_library_complete": False,
            "sta_complete": False,
            "power_signoff_complete": False,
            "dft_complete": False,
            "physical_implementation_complete": False,
            "silicon_signoff_complete": False,
        },
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Phase 9 Productization Gates",
        "",
        f"Generated: `{report.get('generated_at')}`",
        "",
        f"Status: `{report.get('status')}`",
        "",
        "This document is generated from local evidence. It separates RTL structural-coverage uplift work from real productization signoff gates. Passing proxy checks here does not claim proprietary Vivante compatibility, target-library synthesis, STA, power signoff, DFT, physical implementation, silicon signoff, or tapeout readiness.",
        "",
        "## Summary",
        "",
        f"- Productization ready: `{str(report.get('productization_ready')).lower()}`",
        f"- Passed gates: `{len(report.get('passed_gates', []))}`",
        f"- Partial gates: `{len(report.get('partial_gates', []))}`",
        f"- Blocked gates: `{len(report.get('blocked_gates', []))}`",
        "",
        "| Gate | Category | Status | Boundary |",
        "| --- | --- | --- | --- |",
    ]
    for gate_item in report.get("gates", []):
        boundary = str(gate_item.get("claim_boundary", "")).replace("|", "/")
        lines.append(
            f"| `{gate_item.get('id')}` | {gate_item.get('category')} | `{gate_item.get('status')}` | {boundary} |"
        )

    lines.extend(["", "## Gate Details", ""])
    for gate_item in report.get("gates", []):
        lines.extend(
            [
                f"### {gate_item.get('title')}",
                "",
                f"- Gate ID: `{gate_item.get('id')}`",
                f"- Category: `{gate_item.get('category')}`",
                f"- Status: `{gate_item.get('status')}`",
                f"- Boundary: {gate_item.get('claim_boundary')}",
                "",
                "Current evidence:",
            ]
        )
        for path in gate_item.get("current_evidence", []):
            lines.append(f"- `{path}`")
        lines.extend(["", "Required for productization:"])
        for requirement in gate_item.get("required_for_productization", []):
            lines.append(f"- {requirement}")
        lines.extend(["", "Checks:"])
        for check in gate_item.get("checks", []):
            state = "pass" if check.get("pass") else "fail"
            lines.append(f"- `{check.get('name')}`: `{state}`")
        lines.extend(["", "Next actions:"])
        for action in gate_item.get("next_actions", []):
            lines.append(f"- {action}")
        lines.append("")

    metrics = report.get("observed_metrics", {})
    lines.extend(
        [
            "## Observed Metrics",
            "",
            "```json",
            json.dumps(metrics, indent=2, sort_keys=True),
            "```",
            "",
            "## Signoff Boundary",
            "",
            "```json",
            json.dumps(report.get("signoff_boundary", {}), indent=2, sort_keys=True),
            "```",
            "",
            "## Completion Rule",
            "",
            "Phase 9 may be called productization-ready only when every gate above is `pass`, every signoff boundary boolean is true, and the evidence paths point to active Rank 1 GPGPU artifacts rather than superseded graphics-only roots. Until then, this file is a gate checklist and blocker ledger, not a signoff claim.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Phase-9 productization gate evidence.")
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_ARTIFACT_ROOT / "verification" / "phase9_productization_gates.json",
    )
    parser.add_argument("--doc-output", type=Path, default=DEFAULT_DOC)
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args()

    report = build_report(args.artifact_root)
    write_json(args.output, report)
    args.doc_output.parent.mkdir(parents=True, exist_ok=True)
    args.doc_output.write_text(render_markdown(report), encoding="utf-8")

    print(
        "celviz_gpgpu_phase9_productization_gates: "
        f"{report['status']} pass={len(report['passed_gates'])} "
        f"partial={len(report['partial_gates'])} blocked={len(report['blocked_gates'])} "
        f"output={args.output} doc={args.doc_output}"
    )
    if args.print_summary:
        print(json.dumps({k: report[k] for k in ("status", "passed_gates", "partial_gates", "blocked_gates")}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
