#!/usr/bin/env bash
set -euo pipefail

# Celviz reusable clean-room boundary gate template.
# Replace __IP_SLUG__ and __ARTIFACT_ROOT__ when instantiating a new IP flow.

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

artifact_root="${CELVIZ_ARTIFACT_ROOT:-__ARTIFACT_ROOT__}"
acceptance_matrix="$artifact_root/verification/acceptance_matrix.json"
criteria="$artifact_root/criteria_to_evidence.csv"

fail() {
  printf 'celviz_boundary_check: fail reason=%s\n' "$*" >&2
  exit 1
}

[[ -s "$acceptance_matrix" ]] || fail "missing acceptance matrix: $acceptance_matrix"
[[ -s "$criteria" ]] || fail "missing criteria-to-evidence map: $criteria"

python3 - "$acceptance_matrix" "$criteria" <<'PY'
import csv
import json
import sys
from pathlib import Path

matrix_path = Path(sys.argv[1])
criteria_path = Path(sys.argv[2])
matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
errors = []

if not str(matrix.get("schema", "")).startswith("celviz."):
    errors.append("acceptance matrix schema must be explicit")
if "clean_room_scope" not in matrix:
    errors.append("acceptance matrix must carry clean_room_scope")
if not matrix.get("gates"):
    errors.append("acceptance matrix must declare gates")

with criteria_path.open(newline="", encoding="utf-8") as stream:
    rows = list(csv.DictReader(stream))
if not rows:
    errors.append("criteria_to_evidence.csv must contain at least one evidence row")

if errors:
    for error in errors:
        print(f"  - {error}", file=sys.stderr)
    raise SystemExit(1)
print("celviz_boundary_check: pass")
PY
