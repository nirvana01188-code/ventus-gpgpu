#!/usr/bin/env python3
"""Build E6 clean-room integration evidence for the Celviz GPGPU IP package."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA = "celviz.gpgpu.e6_integration_evidence.v1"
CLEAN_ROOM_SCOPE = (
    "clean-room proxy integration evidence only; no proprietary Vivante "
    "collateral, driver ABI, firmware, SDK, compiler, API conformance, RTL "
    "timing closure, PPA, safety certification, or silicon signoff claim"
)
FORBIDDEN_CLAIMS = (
    "licensed vendor collateral",
    "proprietary Vivante RTL",
    "proprietary Vivante firmware",
    "proprietary Vivante driver",
    "official OpenCL conformance",
    "official OpenCV conformance",
    "silicon signoff",
    "tapeout readiness",
    "production PPA",
    "STA closure",
    "CDC/RDC closure",
    "DFT/scan signoff",
    "safety certification",
    "product security certification",
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def artifact_root(root: Path) -> Path:
    return root / "artifacts/rank_01_vivante_3d_gpgpu_ip"


def integration_root(root: Path) -> Path:
    return artifact_root(root) / "integration"


def default_output(root: Path) -> Path:
    return integration_root(root) / "e6_integration_evidence.json"


def default_log(root: Path) -> Path:
    return integration_root(root) / "e6_integration_check.log"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def as_int(value: Any, default: int = 0) -> int:
    try:
        if isinstance(value, str):
            return int(value, 0)
        return int(value)
    except Exception:
        return default


def all_checks_pass(checks: Sequence[Mapping[str, Any]]) -> bool:
    return bool(checks) and all(check.get("pass") is True or check.get("result") == "pass" for check in checks)


def contains_any(text: str, needles: Sequence[str]) -> bool:
    lowered = text.lower()
    return any(needle.lower() in lowered for needle in needles)


def build_payload(root: Path) -> tuple[dict[str, Any], list[str]]:
    art = artifact_root(root)
    integ = integration_root(root)
    perf_path = integ / "perf_model_metrics.json"
    perf_log_path = integ / "perf_model_run.log"
    control_path = art / "rtl/control_plane_metrics.json"
    neg_path = art / "rtl/e5_outputs/negative_boundary_evidence.json"
    verify_log_path = art / "verification/test_results.log"
    bandwidth_doc = integ / "bandwidth_latency_power.md"
    reset_doc = integ / "reset_clock_interrupt.md"
    security_doc = integ / "security_safety_notes.md"
    readme_doc = integ / "README.md"

    perf = load_json(perf_path)
    control = load_json(control_path)
    negative = load_json(neg_path)
    perf_log = read_text(perf_log_path)
    verification_log = read_text(verify_log_path)
    bandwidth_text = read_text(bandwidth_doc)
    reset_text = read_text(reset_doc)
    security_text = read_text(security_doc)
    readme_text = read_text(readme_doc)
    combined_docs = "\n".join([bandwidth_text, reset_text, security_text, readme_text])

    counters = control.get("counters", {})
    tier_validation = perf.get("tier_validation", {})
    tier_summary = perf.get("tier_summary", [])
    selected_tiers = tier_validation.get("selected_tiers", [])
    selected_tier_rows = tier_validation.get("selected_tier_rows", [])
    tier_checks = tier_validation.get("checks", [])
    negative_summary = negative.get("summary", {})

    bandwidth = {
        "status": "pass_proxy",
        "evidence": [
            str(control_path.relative_to(root)),
            str(perf_path.relative_to(root)),
            str(bandwidth_doc.relative_to(root)),
        ],
        "axi_read_transactions": as_int(counters.get("axi_read_transactions")),
        "axi_write_transactions": as_int(counters.get("axi_write_transactions")),
        "axi_read_beats": as_int(counters.get("axi_read_beats")),
        "axi_write_beats": as_int(counters.get("axi_write_beats")),
        "bytes_read": as_int(counters.get("bytes_read")),
        "bytes_written": as_int(counters.get("bytes_written")),
        "bytes_moved": as_int(counters.get("bytes_moved")),
        "proxy_bandwidth_fields_present": contains_any(bandwidth_text, ("bandwidth_bytes_per_cycle", "AXI Bandwidth Framework")),
    }

    latency = {
        "status": "pass_proxy",
        "evidence": [
            str(perf_path.relative_to(root)),
            str(perf_log_path.relative_to(root)),
            str(reset_doc.relative_to(root)),
        ],
        "selected_tiers": selected_tiers,
        "latency_proxy_cycles": [
            as_int(row.get("latency_proxy_cycles"))
            for row in selected_tier_rows
        ],
        "tier_validation_status": tier_validation.get("status"),
        "latency_check_present": any(check.get("name") == "latency_proxy_monotonic" for check in tier_checks),
    }

    proxy_power = {
        "status": "pass_proxy",
        "evidence": [
            str(perf_path.relative_to(root)),
            str(bandwidth_doc.relative_to(root)),
        ],
        "activity_weights_present": bool(perf.get("assumptions", {}).get("activity_weights")),
        "power_check_present": any(check.get("name") == "power_proxy_monotonic" for check in tier_checks),
        "aggregate_power_index_proxy": [
            row.get("aggregate_power_index_proxy")
            for row in selected_tier_rows
        ],
    }

    reset_clock = {
        "status": "pass_proxy",
        "evidence": [
            str(control_path.relative_to(root)),
            str(neg_path.relative_to(root)),
            str(reset_doc.relative_to(root)),
        ],
        "resets": as_int(counters.get("resets")),
        "reset_recoveries": as_int(counters.get("reset_recoveries")),
        "interrupt_clears": as_int(counters.get("interrupt_clears")),
        "completion_interrupts": as_int(counters.get("completion_interrupts")),
        "error_interrupts": as_int(counters.get("error_interrupts")),
        "reset_pending_active_scenarios": as_int(negative_summary.get("reset_pending_active_scenarios")),
        "clock_model": "single_proxy_clock",
        "clock_claim_scope": "proxy_cycle_model_only",
        "reset_doc_has_clock_model": "clock_model=single_proxy_clock" in reset_text,
    }

    security_safety = {
        "status": "pass_proxy",
        "evidence": [
            str(security_doc.relative_to(root)),
            str(neg_path.relative_to(root)),
            str(verify_log_path.relative_to(root)),
        ],
        "invalid_descriptor_scenarios": as_int(negative_summary.get("invalid_descriptor_scenarios")),
        "dma_bounds_alignment_scenarios": as_int(negative_summary.get("dma_bounds_alignment_scenarios")),
        "expected_error_records": as_int(negative_summary.get("expected_error_records")),
        "claim_scope": "functional_proxy_only",
        "non_goal_tokens_present": contains_any(security_text, ("Safety certification", "Production MMU security", "Product security claim")),
    }

    non_goals = {
        "status": "pass",
        "forbidden_claims": list(FORBIDDEN_CLAIMS),
        "claim_boundary_present": all(
            token.lower() in combined_docs.lower()
            for token in (
                "silicon signoff",
                "tapeout readiness",
                "api conformance",
                "proprietary vivante",
            )
        ),
        "licensed_vendor_collateral_excluded": (
            "licensed vendor collateral" in combined_docs.lower()
            or "proprietary vivante" in combined_docs.lower()
        ),
    }

    checks = [
        {
            "name": "bandwidth_axi_proxy_counters",
            "pass": bandwidth["axi_read_transactions"] > 0
            and bandwidth["axi_write_transactions"] > 0
            and bandwidth["bytes_read"] > 0
            and bandwidth["bytes_written"] > 0
            and bandwidth["proxy_bandwidth_fields_present"] is True,
        },
        {
            "name": "latency_proxy_tier_validation",
            "pass": perf.get("status") == "pass"
            and tier_validation.get("status") == "pass"
            and latency["latency_check_present"] is True
            and len(latency["latency_proxy_cycles"]) >= 3,
        },
        {
            "name": "proxy_power_activity_index",
            "pass": proxy_power["activity_weights_present"] is True
            and proxy_power["power_check_present"] is True
            and len(proxy_power["aggregate_power_index_proxy"]) >= 3,
        },
        {
            "name": "reset_clock_interrupt_assumptions",
            "pass": reset_clock["resets"] >= 1
            and reset_clock["reset_recoveries"] >= 1
            and reset_clock["interrupt_clears"] > 0
            and reset_clock["reset_pending_active_scenarios"] >= 2
            and reset_clock["reset_doc_has_clock_model"] is True,
        },
        {
            "name": "security_safety_functional_proxy_notes",
            "pass": security_safety["invalid_descriptor_scenarios"] >= 5
            and security_safety["dma_bounds_alignment_scenarios"] >= 5
            and security_safety["expected_error_records"] >= 10
            and security_safety["non_goal_tokens_present"] is True,
        },
        {
            "name": "explicit_non_goals_and_no_signoff_claim",
            "pass": non_goals["claim_boundary_present"] is True
            and non_goals["licensed_vendor_collateral_excluded"] is True
            and (
                "celviz_gpgpu_ip_verification: pass" in verification_log
                or "e5_verification_coverage: pass" in verification_log
            ),
        },
    ]

    status = "pass" if all_checks_pass(checks) else "fail"
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "ip_name": "Celviz GPGPU IP",
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "status": status,
        "e6_status": "pass_proxy" if status == "pass" else "fail",
        "evidence": {
            "bandwidth": bandwidth,
            "latency": latency,
            "proxy_power": proxy_power,
            "reset_clock": reset_clock,
            "security_safety": security_safety,
            "non_goals": non_goals,
        },
        "checks": checks,
        "source_paths": {
            "perf_model_metrics": str(perf_path.relative_to(root)),
            "perf_model_run_log": str(perf_log_path.relative_to(root)),
            "control_plane_metrics": str(control_path.relative_to(root)),
            "negative_boundary_evidence": str(neg_path.relative_to(root)),
            "verification_results": str(verify_log_path.relative_to(root)),
            "bandwidth_latency_power": str(bandwidth_doc.relative_to(root)),
            "reset_clock_interrupt": str(reset_doc.relative_to(root)),
            "security_safety_notes": str(security_doc.relative_to(root)),
        },
        "limitations": [
            "Proxy bandwidth, latency, and power evidence are not RTL timing or silicon PPA.",
            "Reset/clock evidence is a clean-room control-plane and cycle-model assumption, not CDC/RDC signoff.",
            "Security/safety notes are functional robustness boundaries, not certification or product security proof.",
            "No licensed vendor collateral, proprietary Vivante implementation, official conformance, or silicon signoff is claimed.",
        ],
    }
    log_lines = [
        f"celviz_gpgpu_e6_integration: {status}",
        f"schema={SCHEMA}",
        f"scope={CLEAN_ROOM_SCOPE}",
    ]
    for check in checks:
        log_lines.append(f"check {check['name']} pass={str(check['pass']).lower()}")
    log_lines.extend(
        [
            f"bandwidth_bytes_read={bandwidth['bytes_read']} bandwidth_bytes_written={bandwidth['bytes_written']}",
            f"latency_selected_tiers={','.join(str(item) for item in selected_tiers)}",
            f"clock_model={reset_clock['clock_model']}",
            f"security_claim_scope={security_safety['claim_scope']}",
            "non_goals=no_licensed_vendor_collateral,no_silicon_signoff,no_official_conformance",
        ]
    )
    return payload, log_lines


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    root = repo_root()
    parser = argparse.ArgumentParser(description="Generate E6 integration evidence")
    parser.add_argument("--repo-root", type=Path, default=root)
    parser.add_argument("--output", type=Path, default=default_output(root))
    parser.add_argument("--log", type=Path, default=default_log(root))
    parser.add_argument("--print-summary", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.repo_root.resolve()
    payload, log_lines = build_payload(root)
    write_json(args.output, payload)
    args.log.parent.mkdir(parents=True, exist_ok=True)
    args.log.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    if args.print_summary:
        print("\n".join(log_lines))
    return 0 if payload.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
