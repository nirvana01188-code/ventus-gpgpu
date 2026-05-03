#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

missing=()
for script in \
  scripts/verify_celviz_gpgpu_compiler_ir.sh \
  scripts/verify_celviz_gpgpu_phase6_memory.sh \
  scripts/verify_celviz_gpgpu_driver_submission.sh \
  scripts/verify_celviz_gpgpu_synthesis_readiness.sh \
  scripts/verify_celviz_gpgpu_yosys_synthesis_probe.sh \
  scripts/verify_celviz_eda_methodology.sh; do
  if [[ ! -f "$script" ]]; then
    missing+=("$script")
  fi
done

if [[ "${#missing[@]}" -gt 0 ]]; then
  printf 'celviz_gpgpu_phase6: fail missing_scripts=%s\n' "${missing[*]}" >&2
  exit 1
fi

bash scripts/verify_celviz_gpgpu_compiler_ir.sh
bash scripts/verify_celviz_gpgpu_phase6_memory.sh
bash scripts/verify_celviz_gpgpu_driver_submission.sh
bash scripts/verify_celviz_gpgpu_synthesis_readiness.sh
bash scripts/verify_celviz_gpgpu_yosys_synthesis_probe.sh
bash scripts/verify_celviz_eda_methodology.sh

python3 - <<'PY'
import json
from pathlib import Path

checks = {
    "compiler_ir": Path("artifacts/rank_01_vivante_3d_gpgpu_ip/compiler_ir/compiler_ir_report.json"),
    "phase6_memory": Path("artifacts/rank_01_vivante_3d_gpgpu_ip/verification/phase6_memory_trace_integration_report.json"),
    "driver_submission": Path("artifacts/rank_01_vivante_3d_gpgpu_ip/driver_submission/driver_submission_report.json"),
    "synthesis_readiness": Path("artifacts/rank_01_vivante_3d_gpgpu_ip/synthesis/synthesis_readiness_report.json"),
    "yosys_synthesis_probe": Path("artifacts/rank_01_vivante_3d_gpgpu_ip/synthesis/yosys_synthesis_probe_report.json"),
    "eda_methodology": Path("artifacts/celviz-methodology/methodology_verification_report.json"),
}

failures = []
for name, path in checks.items():
    if not path.exists() or path.stat().st_size == 0:
        failures.append(f"{name}: missing {path}")
        continue
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("status") != "pass":
        failures.append(f"{name}: status={payload.get('status')}")

if failures:
    print("celviz_gpgpu_phase6: fail")
    for failure in failures:
        print(f"  - {failure}")
    raise SystemExit(1)

print("celviz_gpgpu_phase6: pass checks=6/6")
PY
