#!/usr/bin/env python3
"""Verify reusable Celviz EDA methodology documentation and manifest."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "celviz.eda_methodology.verification.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Celviz GPGPU IP EDA methodology assets.")
    parser.add_argument("--doc", type=Path, default=Path("docs/celviz-methodology/GPGPU_IP_EDA_METHOD.md"))
    parser.add_argument("--manifest", type=Path, default=Path("docs/celviz-methodology/methodology_manifest.json"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/celviz-methodology/methodology_verification_report.json"))
    parser.add_argument(
        "--bootstrap-output",
        type=Path,
        default=Path("artifacts/celviz-methodology/bootstrap_acceptance_matrix.json"),
    )
    args = parser.parse_args()

    doc_text = args.doc.read_text(encoding="utf-8")
    manifest = load_json(args.manifest)
    required_sections = list(manifest.get("required_sections", []))
    templates = list(manifest.get("reusable_gate_templates", []))
    boundaries = list(manifest.get("claim_boundaries", []))
    assets = dict(manifest.get("methodology_assets", {}))
    bootstrap_contract = dict(manifest.get("bootstrap_contract", {}))
    acceptance_template_path = Path(str(assets.get("acceptance_template", "")))
    bootstrap_tool_path = Path(str(assets.get("bootstrap_tool", "")))
    acceptance_template = load_json(acceptance_template_path) if acceptance_template_path.exists() else {}
    gate_templates = list(acceptance_template.get("gate_templates", []))
    phase_sequence = list(acceptance_template.get("required_phase_sequence", []))
    bootstrap_result = subprocess.run(
        [
            sys.executable,
            str(bootstrap_tool_path),
            "--ip-slug",
            "celviz_methodology_selftest_gpgpu_ip",
            "--template",
            str(acceptance_template_path),
            "--output",
            str(args.bootstrap_output),
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    bootstrap_payload = load_json(args.bootstrap_output) if args.bootstrap_output.exists() else {}
    bootstrap_gate_ids = {str(gate.get("id", "")) for gate in bootstrap_payload.get("gates", [])}
    template_gate_ids = {str(gate.get("id", "")) for gate in gate_templates}
    checks = [
        {"name": "manifest_schema", "pass": manifest.get("schema") == "celviz.eda_methodology.gpgpu_ip.v1"},
        {"name": "doc_exists_nonempty", "pass": args.doc.exists() and len(doc_text) > 1000},
        {"name": "all_required_sections_present", "pass": all(section in doc_text for section in required_sections)},
        {"name": "gate_templates_present", "pass": len(templates) >= 16 and all(template.endswith("_check") for template in templates)},
        {"name": "manifest_template_gate_alignment", "pass": set(templates).issubset(template_gate_ids)},
        {"name": "claim_boundaries_present", "pass": len(boundaries) >= 4 and all(boundary in json.dumps(manifest) for boundary in boundaries)},
        {"name": "methodology_assets_exist", "pass": all(Path(str(path)).exists() for path in assets.values())},
        {"name": "acceptance_template_schema", "pass": acceptance_template.get("schema") == bootstrap_contract.get("template_schema")},
        {"name": "acceptance_template_phase_depth", "pass": len(phase_sequence) >= int(bootstrap_contract.get("minimum_phase_count", 0))},
        {"name": "acceptance_template_gate_depth", "pass": len(gate_templates) >= int(bootstrap_contract.get("minimum_gate_count", 0))},
        {"name": "bootstrap_tool_exists", "pass": bootstrap_tool_path.exists() and "bootstrap" in bootstrap_tool_path.read_text(encoding="utf-8", errors="replace")},
        {
            "name": "bootstrap_command_pass",
            "pass": bootstrap_result.returncode == 0,
            "stdout": bootstrap_result.stdout.strip(),
            "stderr": bootstrap_result.stderr.strip(),
        },
        {
            "name": "bootstrap_output_schema",
            "pass": bootstrap_payload.get("schema") == bootstrap_contract.get("bootstrap_schema"),
            "schema": bootstrap_payload.get("schema"),
        },
        {
            "name": "bootstrap_output_phase_depth",
            "pass": len(bootstrap_payload.get("required_phase_sequence", [])) >= int(bootstrap_contract.get("minimum_phase_count", 0)),
            "phase_count": len(bootstrap_payload.get("required_phase_sequence", [])),
        },
        {
            "name": "bootstrap_output_gate_alignment",
            "pass": template_gate_ids == bootstrap_gate_ids and len(bootstrap_gate_ids) >= int(bootstrap_contract.get("minimum_gate_count", 0)),
            "template_gate_count": len(template_gate_ids),
            "bootstrap_gate_count": len(bootstrap_gate_ids),
        },
        {
            "name": "bootstrap_claim_boundary_present",
            "pass": bool(bootstrap_payload.get("claim_boundary_template", {}).get("forbidden_without_evidence")),
        },
        {"name": "functional_structural_boundary_written", "pass": "Functional Coverage vs Structural Coverage" in doc_text and "Do not convert structural observations" in doc_text},
        {"name": "microop_execution_method_written", "pass": "Micro-op Execution Lane" in doc_text and "compare result hashes" in doc_text},
        {"name": "worker_decomposition_written", "pass": "Worker Decomposition" in doc_text and "disjoint write scopes" in doc_text},
        {"name": "no_overclaim_wording_written", "pass": "Disallowed wording" in doc_text and "Vivante-compatible IP" in doc_text},
        {"name": "template_library_written", "pass": "Template Library" in doc_text and "coverage_100_template.py" in doc_text},
    ]
    report = {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "status": "pass" if all(check["pass"] for check in checks) else "fail",
        "checks": checks,
        "summary": {
            "required_sections": len(required_sections),
            "reusable_gate_templates": len(templates),
            "claim_boundaries": len(boundaries),
            "methodology_assets": len(assets),
            "template_phase_count": len(phase_sequence),
            "template_gate_count": len(gate_templates),
            "bootstrap_output_path": str(args.bootstrap_output),
            "bootstrap_gate_count": len(bootstrap_gate_ids),
            "doc_path": str(args.doc),
            "manifest_path": str(args.manifest),
        },
    }
    write_json(args.output, report)
    passed = sum(1 for check in checks if check["pass"])
    print(f"celviz_eda_methodology: {report['status']} checks={passed}/{len(checks)} output={args.output}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
