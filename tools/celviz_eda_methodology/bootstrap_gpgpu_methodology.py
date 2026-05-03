#!/usr/bin/env python3
"""Bootstrap reusable Celviz GPGPU/IP methodology skeletons."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "celviz.eda_methodology.bootstrap.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render(value: Any, variables: Mapping[str, str]) -> Any:
    if isinstance(value, str):
        result = value
        for key, replacement in variables.items():
            result = result.replace("${" + key + "}", replacement)
        return result
    if isinstance(value, list):
        return [render(item, variables) for item in value]
    if isinstance(value, dict):
        return {key: render(item, variables) for key, item in value.items()}
    return value


def build(template: Mapping[str, Any], ip_slug: str) -> dict[str, Any]:
    variables = dict(template.get("variables", {}))
    variables["ip_slug"] = ip_slug
    variables["artifact_root"] = f"artifacts/{ip_slug}"
    variables["docs_root"] = f"docs/{ip_slug.replace('_', '-')}"
    variables["tool_root"] = f"tools/{ip_slug}"
    rendered_gates = render(template.get("gate_templates", []), variables)
    return {
        "schema": "celviz.gpgpu.acceptance_matrix.bootstrap.v1",
        "generated_at": utc_now(),
        "ip_slug": ip_slug,
        "artifact_root": variables["artifact_root"],
        "docs_root": variables["docs_root"],
        "tool_root": variables["tool_root"],
        "clean_room_scope": "bootstrap skeleton only; fill project-specific evidence before claiming pass",
        "required_phase_sequence": template.get("required_phase_sequence", []),
        "gates": rendered_gates,
        "required_report_fields": template.get("required_report_fields", []),
        "claim_boundary_template": template.get("claim_boundary_template", {}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap a Celviz GPGPU/IP methodology skeleton.")
    parser.add_argument("--ip-slug", default="example_gpgpu_ip")
    parser.add_argument("--template", type=Path, default=Path("docs/celviz-methodology/templates/gpgpu_acceptance_template.json"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/celviz-methodology/bootstrap_acceptance_matrix.json"))
    args = parser.parse_args()
    template = load_json(args.template)
    payload = build(template, args.ip_slug)
    write_json(args.output, payload)
    print(
        "celviz_eda_methodology_bootstrap: "
        f"pass ip_slug={args.ip_slug} phases={len(payload['required_phase_sequence'])} "
        f"gates={len(payload['gates'])} output={args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
