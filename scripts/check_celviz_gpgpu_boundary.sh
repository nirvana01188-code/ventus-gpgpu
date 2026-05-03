#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

python3 - "$root" <<'PY'
import csv
import json
import re
import sys
from pathlib import Path

repo_root = Path(sys.argv[1]).resolve()
artifact_root = Path("artifacts/rank_01_vivante_3d_gpgpu_ip")

FORBIDDEN_PREFIXES = (
    "docs/celviz-gpu-ip",
    "artifacts/rank_12_vivante_3d_gpu_ip",
)

ALLOWED_EVIDENCE_PREFIXES = (
    "artifacts/rank_01_vivante_3d_gpgpu_ip",
    "artifacts/celviz-methodology",
    "docs/celviz-gpgpu-ip",
    "docs/celviz-methodology",
    "tools/celviz_gpgpu_ip",
    "tools/celviz_eda_methodology",
    "sim-verilator",
    "ventus/src",
    "scripts/accept_celviz_gpgpu_ip.sh",
    "scripts/build_celviz_gpgpu_runtime.sh",
    "scripts/check_celviz_gpgpu_boundary.sh",
    "scripts/check_celviz_gpgpu_sources.sh",
    "scripts/run_celviz_gpgpu_verilator_coverage.sh",
    "scripts/tools/artifacts/celviz_gpgpu_verilator_supplemental_phase1.py",
    "scripts/tools/artifacts/run_celviz_gpgpu_verilator_supplemental_phase1.sh",
    "scripts/verify_celviz_gpgpu_verilator_coverage.sh",
    "scripts/verify_celviz_gpgpu_phase2.sh",
    "scripts/verify_celviz_gpgpu_phase3.sh",
    "scripts/verify_celviz_gpgpu_phase4.sh",
    "scripts/verify_celviz_gpgpu_phase5.sh",
    "scripts/verify_celviz_gpgpu_phase6.sh",
    "scripts/verify_celviz_gpgpu_kernel_lowering.sh",
    "scripts/verify_celviz_gpgpu_microop_execution.sh",
    "scripts/verify_celviz_gpgpu_compiler_ir.sh",
    "scripts/verify_celviz_gpgpu_phase6_memory.sh",
    "scripts/verify_celviz_gpgpu_driver_submission.sh",
    "scripts/verify_celviz_gpgpu_synthesis_readiness.sh",
    "scripts/verify_celviz_gpgpu_yosys_synthesis_probe.sh",
    "scripts/verify_celviz_gpgpu_phase7_coalescing.sh",
    "scripts/verify_celviz_gpgpu_phase7_config_sweep.sh",
    "scripts/verify_celviz_gpgpu_phase7_control_flow_manager.sh",
    "scripts/verify_celviz_gpgpu_phase7_memory_streaming.sh",
    "scripts/verify_celviz_gpgpu_phase7_register_occupancy.sh",
    "scripts/verify_celviz_gpgpu_phase7_warp_collectives.sh",
    "scripts/verify_celviz_gpgpu_opencl_conformance_gap_map.sh",
    "scripts/verify_celviz_gpgpu_phase8_claim_closure.sh",
    "scripts/verify_celviz_gpgpu_phase8_work_packages.sh",
    "scripts/verify_celviz_gpgpu_opencl_host_api_shim.sh",
    "scripts/verify_celviz_gpgpu_phase9_opencl_conformance_readiness.sh",
    "scripts/verify_celviz_gpgpu_phase9_memory_conformance.sh",
    "scripts/verify_celviz_gpgpu_phase9_driver_os.sh",
    "scripts/verify_celviz_gpgpu_phase9_productization.sh",
    "scripts/verify_celviz_eda_methodology.sh",
    "scripts/verify_celviz_gpgpu_coverage_100.sh",
    "scripts/accept_celviz_gpgpu_ip_full.sh",
    "scripts/verify_celviz_gpgpu_ip.sh",
)

TEXT_EXTENSIONS = {
    ".csv",
    ".json",
    ".log",
    ".md",
    ".sh",
    ".txt",
}

NEGATIVE_CONTEXT = (
    "not active evidence",
    "not active",
    "not completion evidence",
    "not rank 1",
    "do not reuse",
    "do not control",
    "does not control",
    "cannot satisfy",
    "forbidden",
    "historical",
    "superseded",
    "excluded",
    "quarantine",
)

errors = []
checked_paths = []


def rel(path):
    path = Path(path)
    try:
        return str(path.resolve().relative_to(repo_root))
    except (OSError, ValueError):
        return str(path)


def normalize_path(value):
    text = str(value).strip().strip("\"'`")
    if not text:
        return ""
    text = text.replace("\\", "/")
    if text.startswith("./"):
        text = text[2:]
    if text.startswith(str(repo_root).replace("\\", "/") + "/"):
        text = text[len(str(repo_root).replace("\\", "/")) + 1 :]
    return text.rstrip("/")


def has_prefix(path_text, prefixes):
    normalized = normalize_path(path_text)
    return any(normalized == prefix or normalized.startswith(prefix + "/") for prefix in prefixes)


def is_tmp_or_generated_runtime_path(path_text):
    normalized = normalize_path(path_text)
    return (
        normalized.startswith("$TMP/")
        or normalized.startswith("${TMP}/")
        or normalized.startswith("/tmp/ventus-gpgpu-celviz-build/")
        or normalized == "/tmp/ventus-gpgpu-celviz-build"
        or normalized == "working tree diff"
    )


def is_allowed_evidence_path(path_text):
    normalized = normalize_path(path_text)
    if not normalized:
        return True
    if is_tmp_or_generated_runtime_path(normalized):
        return True
    return has_prefix(normalized, ALLOWED_EVIDENCE_PREFIXES)


def check_forbidden_evidence_path(context, path_text):
    normalized = normalize_path(path_text)
    if has_prefix(normalized, FORBIDDEN_PREFIXES):
        errors.append(f"{context}: forbidden_rank12_evidence_path: {normalized}")


def check_allowed_evidence_path(context, path_text):
    normalized = normalize_path(path_text)
    if not normalized:
        return
    check_forbidden_evidence_path(context, normalized)
    if not is_allowed_evidence_path(normalized):
        errors.append(f"{context}: non_gpgpu_rank1_evidence_path: {normalized}")


def split_evidence_field(value):
    return [item.strip() for item in re.split(r"[;\n]", value or "") if item.strip()]


def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"{rel(path)}: malformed_json: {exc}")
        return None


def walk_json(value, key_path=()):
    yield key_path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk_json(child, key_path + (str(key),))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_json(child, key_path + (str(index),))


def check_acceptance_matrix(path):
    data = load_json(path)
    if data is None:
        return
    checked_paths.append(rel(path))
    for key_path, value in walk_json(data):
        key_name = key_path[-1] if key_path else ""
        context = f"{rel(path)}:{'.'.join(key_path) or '<root>'}"
        if key_name == "evidence":
            if not isinstance(value, list):
                errors.append(f"{context}: evidence_field_not_list")
                continue
            for item in value:
                check_allowed_evidence_path(context, item)
        elif key_name in {"artifact_root", "script"}:
            check_allowed_evidence_path(context, value)
        elif isinstance(value, str) and has_prefix(value, FORBIDDEN_PREFIXES):
            errors.append(f"{context}: forbidden_rank12_reference: {normalize_path(value)}")


def check_criteria_to_evidence(path):
    if not path.exists():
        errors.append(f"missing_boundary_input: {rel(path)}")
        return
    checked_paths.append(rel(path))
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        for line_number, row in enumerate(reader, start=2):
            evidence = row.get("evidence_path", "")
            for item in split_evidence_field(evidence):
                check_allowed_evidence_path(f"{rel(path)}:{line_number}:evidence_path", item)


def check_forbidden_text_context(path):
    if path.suffix.lower() not in TEXT_EXTENSIONS or path.suffix.lower() == ".json":
        return
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="replace")
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not any(prefix in line for prefix in FORBIDDEN_PREFIXES):
            continue
        lower = line.lower()
        if any(marker in lower for marker in NEGATIVE_CONTEXT):
            continue
        if "rg -n" in lower or "grep" in lower:
            continue
        if "evidence" in lower or "acceptance" in lower or "pass" in lower:
            errors.append(f"{rel(path)}:{line_number}: forbidden_rank12_active_reference: {line.strip()}")


criteria_path = artifact_root / "criteria_to_evidence.csv"
matrix_path = artifact_root / "verification" / "acceptance_matrix.json"

check_criteria_to_evidence(criteria_path)
check_acceptance_matrix(matrix_path)

if artifact_root.exists():
    for path in sorted(artifact_root.rglob("*")):
        if path.is_file():
            check_forbidden_text_context(path)
else:
    errors.append(f"missing_boundary_input: {artifact_root}")

if errors:
    print("celviz_gpgpu_boundary_check: fail")
    for error in errors:
        print(f"  - {error}")
    raise SystemExit(1)

print("celviz_gpgpu_boundary_check: pass")
print("  - forbidden_rank12_evidence_roots: docs/celviz-gpu-ip, artifacts/rank_12_vivante_3d_gpu_ip")
print("  - active_rank1_evidence_paths_only")
for path in checked_paths:
    print(f"  - checked: {path}")
PY
