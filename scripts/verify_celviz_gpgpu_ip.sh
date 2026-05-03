#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

artifact_root="artifacts/rank_01_vivante_3d_gpgpu_ip"
verification_dir="$artifact_root/verification"

bash scripts/check_celviz_gpgpu_boundary.sh

required_files=(
  "$verification_dir/README.md"
  "$verification_dir/test_commands.sh"
  "$verification_dir/coverage.md"
)

required_tokens=(
  "vector_add"
  "gemm_convolution_image_filter"
  "memory_copy"
  "shader_unit_scaling"
  "fp16_fp32_paths"
  "command_submission"
  "interrupts"
  "axi_traffic"
  "throughput_scaling_by_tier"
)

component_names=(
  "compute_model"
  "runtime"
  "control_plane"
)

component_compute_model_candidates=(
  "$artifact_root/model/compute_model"
  "$artifact_root/compute_model"
  "tools/celviz_gpgpu_ip/compute_model"
  "tools/celviz_gpgpu_ip/compute_model.py"
)

component_runtime_candidates=(
  "$artifact_root/runtime"
  "$artifact_root/demo/runtime"
  "tools/celviz_gpgpu_ip/runtime"
  "tools/celviz_gpgpu_ip/runtime_cli.py"
  "tools/celviz_gpgpu_ip/driver_runtime.py"
  "tools/celviz_gpgpu_ip/runtime.py"
)

component_control_plane_candidates=(
  "tools/celviz_gpgpu_ip/control_plane.py"
  "tools/celviz_gpgpu_ip/control_plane"
  "$artifact_root/control_plane"
  "$artifact_root/rtl/control_plane"
  "$artifact_root/rtl/control_plane_config.json"
)

log() {
  printf '%s\n' "$*"
}

fail() {
  log "celviz_gpgpu_ip_verification: fail"
  log "reason: $*"
  exit 1
}

join_by_nl() {
  local item
  for item in "$@"; do
    printf '  - %s\n' "$item"
  done
}

find_component() {
  local component="$1"
  local array_name="component_${component}_candidates[@]"
  local candidate

  for candidate in "${!array_name}"; do
    if [[ -e "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  return 1
}

find_entrypoint() {
  local path="$1"
  local candidate

  if [[ -f "$path" ]]; then
    printf '%s\n' "$path"
    return 0
  fi

  for candidate in \
    "$path/test_commands.sh" \
    "$path/verify.sh" \
    "$path/run_tests.sh" \
    "$path/run_test.sh" \
    "$path/run.sh" \
    "$path/main.py" \
    "$path/verify.py" \
    "$path/run_tests.py" \
    "$path/run_model.py" \
    "$path/compute_model.py" \
    "$path/runtime.py" \
    "$path/control_plane.py"; do
    if [[ -f "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  return 1
}

run_entrypoint() {
  local component="$1"
  local entrypoint="$2"
  local outfile="$3"
  local status=0

  log "component_${component}: running $entrypoint"

  set +e
  case "$component:$entrypoint" in
    runtime:tools/celviz_gpgpu_ip/runtime_cli.py)
      CELVIZ_GPGPU_VERIFICATION=1 CELVIZ_GPGPU_COMPONENT="$component" \
        python3 "$entrypoint" --kernel-demo "$artifact_root/demo/kernel_demo.json" >"$outfile" 2>&1
      status=$?
      ;;
    control_plane:*.json)
      {
        echo "control_plane_config_json=$entrypoint"
        python3 -m json.tool "$entrypoint"
      } >"$outfile" 2>&1
      status=$?
      ;;
    *.py|*:*.py)
      CELVIZ_GPGPU_VERIFICATION=1 CELVIZ_GPGPU_COMPONENT="$component" \
        python3 "$entrypoint" >"$outfile" 2>&1
      status=$?
      ;;
    *.sh)
      CELVIZ_GPGPU_VERIFICATION=1 CELVIZ_GPGPU_COMPONENT="$component" \
        bash "$entrypoint" >"$outfile" 2>&1
      status=$?
      ;;
    *)
      if [[ -x "$entrypoint" ]]; then
        CELVIZ_GPGPU_VERIFICATION=1 CELVIZ_GPGPU_COMPONENT="$component" \
          "$entrypoint" >"$outfile" 2>&1
        status=$?
      else
        log "unsupported_or_non_executable_entrypoint: $entrypoint" >"$outfile"
        status=126
      fi
      ;;
  esac
  set -e

  return "$status"
}

validate_optional_evidence() {
  python3 - "$root" "$artifact_root" <<'PY'
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

repo_root = Path(sys.argv[1])
artifact_root = Path(sys.argv[2])

errors = []
report = []
loaded = {}


def rel(path):
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def load_json(path):
    if not path.exists():
        report.append(f"optional_json_skipped: {rel(path)}")
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"malformed_json: {rel(path)}: {exc}")
        return None
    loaded[path] = data
    report.append(f"json_valid: {rel(path)}")
    return data


def read_text(path):
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def strip_source_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"//.*", "", text)


IMPLEMENTATION_SUFFIXES = {
    ".c",
    ".cc",
    ".cpp",
    ".cxx",
    ".h",
    ".hh",
    ".hpp",
    ".hxx",
    ".py",
    ".scala",
}


def reject_documentation_only_paths(name, paths):
    bad = []
    for path in paths:
        suffix = path.suffix.lower()
        parts = set(path.parts)
        if suffix not in IMPLEMENTATION_SUFFIXES or "docs" in parts or "verification" in parts:
            bad.append(rel(path))
    if bad:
        errors.append(f"source_hook_{name}_uses_non_implementation_evidence: {','.join(bad)}")


def validate_source_hook(name, paths, required_patterns):
    existing = [path for path in paths if path.exists()]
    if not existing:
        report.append(f"source_hook_{name}=skipped missing_source")
        return

    reject_documentation_only_paths(name, existing)

    raw_parts = []
    code_parts = []
    for path in existing:
        text = read_text(path)
        raw_parts.append(text)
        code_parts.append(strip_source_comments(text))

    raw_text = "\n".join(raw_parts)
    code_text = "\n".join(code_parts)
    rel_paths = ",".join(rel(path) for path in existing)

    if not re.search(r"\bcelviz\w*\b", raw_text, re.IGNORECASE):
        report.append(f"source_hook_{name}=skipped no_celviz_marker paths={rel_paths}")
        return

    missing = []
    for label, pattern in required_patterns:
        if not re.search(pattern, code_text, re.IGNORECASE | re.MULTILINE | re.DOTALL):
            missing.append(label)

    if missing:
        errors.append(f"source_hook_{name}_missing_real_hook_patterns: {','.join(missing)} paths={rel_paths}")
    else:
        report.append(f"source_hook_{name}=present paths={rel_paths}")
        report.append(f"source_hook_{name}_evidence={','.join(label for label, _ in required_patterns)}")


def walk_dicts(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_dicts(child)


def flatten_strings(value):
    strings = []
    if isinstance(value, str):
        strings.append(value)
    elif isinstance(value, dict):
        for key, child in value.items():
            strings.append(str(key))
            strings.extend(flatten_strings(child))
    elif isinstance(value, list):
        for child in value:
            strings.extend(flatten_strings(child))
    else:
        strings.append(str(value))
    return strings


def as_int(value, default=0):
    try:
        if isinstance(value, str):
            return int(value, 0)
        return int(value)
    except Exception:
        return default


def field(mapping, name, default=0):
    if not isinstance(mapping, dict):
        return default
    return as_int(mapping.get(name, default), default)


def contains_region(regions, address, byte_count, *, write):
    if not isinstance(regions, list) or byte_count < 0:
        return False
    for region in regions:
        if not isinstance(region, dict):
            continue
        base = field(region, "base")
        size = field(region, "size", field(region, "size_bytes"))
        readable = bool(region.get("readable", True))
        writable = bool(region.get("writable", True))
        if write and not writable:
            continue
        if not write and not readable:
            continue
        if base <= address and address + byte_count <= base + size:
            return True
    return False


def validate_status_fields(path, data):
    for item in walk_dicts(data):
        if item.get("pass") is False:
            errors.append(f"explicit_failed_pass_field: {rel(path)}")
        status = item.get("status")
        if isinstance(status, str) and status.lower() in {"fail", "failed", "error"}:
            flat_item = " ".join(flatten_strings(item)).lower()
            if status.lower() == "error" and (
                "expected" in flat_item
                or item.get("error_expected") is True
                or item.get("expected_error") is True
            ):
                continue
            errors.append(f"explicit_failed_status: {rel(path)}: {status}")


def forbidden_silicon_claims(text):
    forbidden = []
    pattern = re.compile(
        r"\b(?:silicon\s+(?:signoff|ppa)|tapeout\s+readiness|tapeout\s+ready|"
        r"foundry-ready|cdc/sta|sta/cdc|dft\s+closure|timing\s+signoff)\b"
        r".{0,96}\b(?:pass|passed|complete|closed|proven|ready|certified|claimed?)\b",
        re.IGNORECASE | re.DOTALL,
    )
    negation = re.compile(
        r"\b(?:not|no|without|unproven|forbidden|outside|does\s+not|do\s+not|"
        r"must\s+not|remain\s+unproven|does\s+not\s+satisfy)\b",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        window = text[max(0, match.start() - 140): match.end() + 40]
        if not negation.search(window):
            forbidden.append(" ".join(match.group(0).split()))
    return forbidden


def validate_e6_integration_evidence():
    def require(condition, message):
        if not condition:
            errors.append(f"e6_integration_evidence: {message}")

    def require_text(path):
        text = read_text(path)
        if not text.strip():
            errors.append(f"e6_integration_evidence: missing_or_empty {rel(path)}")
        return text

    readme = require_text(artifact_root / "integration" / "README.md")
    bandwidth = require_text(artifact_root / "integration" / "bandwidth_latency_power.md")
    reset_clock = require_text(artifact_root / "integration" / "reset_clock_interrupt.md")
    security = require_text(artifact_root / "integration" / "security_safety_notes.md")
    perf_log = require_text(artifact_root / "integration" / "perf_model_run.log")
    gate_text = require_text(repo_root / "docs" / "celviz-gpgpu-ip" / "S5_INTEGRATION_GATE.md")
    perf_metrics = loaded.get(artifact_root / "integration" / "perf_model_metrics.json")
    if perf_metrics is None:
        perf_metrics = load_json(artifact_root / "integration" / "perf_model_metrics.json")
    if not isinstance(perf_metrics, dict):
        perf_metrics = {}

    combined = "\n".join([readme, bandwidth, reset_clock, security, perf_log, gate_text])
    combined_lower = combined.lower()
    bandwidth_log = (bandwidth + "\n" + perf_log).lower()

    require("bandwidth" in bandwidth.lower() and "latency" in bandwidth.lower() and "power" in bandwidth.lower(), "bandwidth/latency/power proxy doc is incomplete")
    for token in (
        "bandwidth_bytes_per_cycle",
        "latency_proxy_cycles",
        "aggregate_power_index_proxy",
        "tier_validation_check name=power_proxy_monotonic pass=true",
    ):
        require(token.lower() in bandwidth_log, f"missing bandwidth_latency_power_proxy token {token}")

    require("reset_asserted" in reset_clock and "queue_idle_after_reset" in reset_clock, "reset assumptions are missing")
    require("clock_model=single_proxy_clock" in reset_clock, "single proxy clock assumption is missing")
    require("clock_cycles_elapsed" in reset_clock or "timestamp_delta_us" in reset_clock, "clock timing units are missing")

    require("non-goals" in security.lower() or "does not claim" in security.lower(), "explicit non-goals are missing")
    for token in ("security", "safety", "certification", "functional proxy", "not as security certification"):
        require(token in security.lower(), f"security_safety_notes missing {token}")

    for token in (
        "not allowed",
        "does not claim",
        "not measured rtl",
        "not silicon ppa",
        "not api conformance",
        "not a silicon signoff plan",
    ):
        require(token in combined_lower, f"explicit non-goal/caveat missing {token}")

    forbidden = forbidden_silicon_claims(combined)
    require(not forbidden, f"possible silicon signoff claim: {forbidden[:3]}")

    require(perf_metrics.get("schema") == "celviz.gpgpu.proxy_perf_model.v1", "perf model schema mismatch")
    require(perf_metrics.get("status") == "pass", "perf model status is not pass")
    assumptions = perf_metrics.get("assumptions", {})
    claim_boundary = str(assumptions.get("claim_boundary", "")).lower()
    clock_model = str(assumptions.get("clock_model", "")).lower()
    require("proxy model only" in claim_boundary and "not silicon ppa" in claim_boundary, "perf claim boundary is incomplete")
    require("no frequency" in clock_model and "timing closure" in clock_model, "perf clock assumption is incomplete")
    require(bool(assumptions.get("activity_weights")), "power proxy activity weights are missing")

    tier_validation = perf_metrics.get("tier_validation", {})
    checks = {str(item.get("name")): item for item in tier_validation.get("checks", []) if isinstance(item, dict)}
    for name in (
        "minimum_three_tiers_selected",
        "axi_byte_pressure_fields_present",
        "axi_byte_pressure_monotonic",
        "latency_proxy_monotonic",
        "power_proxy_monotonic",
    ):
        require(checks.get(name, {}).get("pass") is True, f"tier validation check missing/pass=false: {name}")
    selected_tiers = tier_validation.get("selected_tiers", [])
    require(isinstance(selected_tiers, list) and len(selected_tiers) >= 3, "selected tier count is below 3")
    require(len(perf_metrics.get("estimates", [])) > 0, "perf estimates are missing")

    report.append("e6_integration_evidence_gate=present")
    report.append("e6_bandwidth_latency_power_proxy=present")
    report.append("e6_reset_clock_assumptions=present")
    report.append("e6_security_safety_notes=present")
    report.append("e6_explicit_non_goals=present")
    report.append("e6_no_silicon_signoff_claim=present")


json_paths = [
    artifact_root / "model" / "metrics.json",
    artifact_root / "demo" / "outputs" / "status.json",
    artifact_root / "demo" / "outputs" / "summary.json",
    artifact_root / "rtl" / "control_plane_config.json",
    artifact_root / "rtl" / "control_plane_demo.json",
    artifact_root / "rtl" / "e5_verification_demo.json",
    artifact_root / "rtl" / "control_plane_metrics.json",
    artifact_root / "integration" / "perf_model_metrics.json",
    artifact_root / "rtl" / "metrics.json",
    artifact_root / "control_plane" / "metrics.json",
    artifact_root / "runtime" / "metrics.json",
    artifact_root / "demo" / "metrics.json",
]

for directory in [
    artifact_root / "model" / "outputs",
    artifact_root / "demo" / "outputs",
    artifact_root / "demo" / "outputs" / "compute_model",
]:
    if directory.exists():
        json_paths.extend(sorted(directory.glob("*.json")))

seen = set()
for path in json_paths:
    if path in seen:
        continue
    seen.add(path)
    data = load_json(path)
    if data is not None:
        validate_status_fields(path, data)

fp16_hits = 0
for path, data in loaded.items():
    for item in walk_dicts(data):
        fp16 = item.get("fp16_proxy")
        if fp16 is None:
            continue
        fp16_hits += 1
        if not isinstance(fp16, dict):
            errors.append(f"fp16_proxy_not_object: {rel(path)}")
            continue
        if not fp16.get("status"):
            errors.append(f"fp16_proxy_missing_status: {rel(path)}")
        if not fp16.get("method"):
            errors.append(f"fp16_proxy_missing_method: {rel(path)}")
        sample_head = fp16.get("sample_head")
        if sample_head is not None and (not isinstance(sample_head, list) or not sample_head):
            errors.append(f"fp16_proxy_bad_sample_head: {rel(path)}")

if fp16_hits:
    report.append(f"fp16_proxy_outputs=present count={fp16_hits}")
else:
    report.append("fp16_proxy_outputs=skipped")

runtime_log = artifact_root / "demo" / "run.log"
runtime_text = read_text(runtime_log)
if runtime_text:
    count_match = re.search(r"^kernel_count=(\d+)$", runtime_text, re.MULTILINE)
    kernel_lines = re.findall(r"^kernel\[(\d+)\]=([a-z0-9_]+)\b", runtime_text, re.MULTILINE)
    if count_match:
        expected = int(count_match.group(1))
        if expected != len(kernel_lines):
            errors.append(
                f"runtime_queue_phase_count_mismatch: {rel(runtime_log)}: "
                f"kernel_count={expected} kernel_lines={len(kernel_lines)}"
            )
        if "demo_status=pass" not in runtime_text and "status=pass" not in runtime_text:
            errors.append(f"runtime_log_missing_pass_status: {rel(runtime_log)}")
        if expected > 0 and kernel_lines:
            report.append(f"runtime_queue_phases=present count={expected}")
    else:
        report.append(f"runtime_queue_phases=skipped no_kernel_count in {rel(runtime_log)}")
else:
    report.append("runtime_queue_phases=skipped")

status_json = loaded.get(artifact_root / "demo" / "outputs" / "status.json")
summary_json = loaded.get(artifact_root / "demo" / "outputs" / "summary.json")
if isinstance(status_json, dict) and isinstance(summary_json, dict):
    status_summary = status_json.get("summary", {})
    if status_summary and status_summary != summary_json:
        errors.append("runtime_status_summary_mismatch: demo/outputs/status.json vs summary.json")
    kernels = summary_json.get("kernels")
    kernel_count = summary_json.get("kernel_count")
    if isinstance(kernels, dict) and isinstance(kernel_count, int):
        if len(kernels) != kernel_count:
            errors.append(
                f"runtime_summary_kernel_count_mismatch: kernel_count={kernel_count} kernels={len(kernels)}"
            )
        for required_kernel in ["vector_add", "gemm_proxy", "image_filter", "memory_copy"]:
            if required_kernel not in kernels:
                errors.append(f"runtime_summary_missing_kernel: {required_kernel}")

validate_e6_integration_evidence()

control_config = loaded.get(artifact_root / "rtl" / "control_plane_config.json")
control_metrics = loaded.get(artifact_root / "rtl" / "control_plane_metrics.json")
control_text = "\n".join(
    [
        json.dumps(control_config, sort_keys=True) if control_config is not None else "",
        json.dumps(control_metrics, sort_keys=True) if control_metrics is not None else "",
        read_text(artifact_root / "rtl" / "smoke.log"),
        read_text(artifact_root / "rtl" / "control_plane_run.log"),
        read_text(artifact_root / "rtl" / "register_map.md"),
        read_text(artifact_root / "control_plane" / "run.log"),
        read_text(artifact_root / "rtl" / "run.log"),
    ]
).lower()

if control_text.strip():
    for token in ["interrupt", "error", "reset"]:
        if token not in control_text:
            errors.append(f"control_plane_missing_{token}_token")
    has_axi = "axi" in control_text
    has_apb = "apb" in control_text
    if has_axi or has_apb:
        report.append(
            "axi_apb_transaction_counters=present "
            f"axi={'yes' if has_axi else 'no'} apb={'yes' if has_apb else 'no'}"
        )
    else:
        report.append("axi_apb_transaction_counters=skipped")
    report.append("interrupt_error_reset_tokens=present")
else:
    report.append("interrupt_error_reset_tokens=skipped")
    report.append("axi_apb_transaction_counters=skipped")

e5_demo_path = artifact_root / "rtl" / "e5_verification_demo.json"
if not e5_demo_path.exists():
    e5_demo_path = artifact_root / "rtl" / "control_plane_demo.json"
e5_control_plane = repo_root / "tools" / "celviz_gpgpu_ip" / "control_plane.py"
if e5_demo_path.exists() and e5_control_plane.exists():
    with tempfile.TemporaryDirectory(prefix="celviz-e5-verify-") as tmp:
        tmp_path = Path(tmp)
        e5_metrics_path = tmp_path / "e5_control_plane_metrics.json"
        e5_log_path = tmp_path / "e5_control_plane_run.log"
        result = subprocess.run(
            [
                sys.executable,
                str(e5_control_plane),
                "--demo",
                str(e5_demo_path),
                "--log",
                str(e5_log_path),
                "--metrics",
                str(e5_metrics_path),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if result.returncode != 0:
            errors.append(f"e5_control_plane_run_failed: {result.returncode}: {result.stdout[:500]}")
        else:
            e5_metrics = json.loads(e5_metrics_path.read_text(encoding="utf-8"))
            e5_demo = loaded.get(e5_demo_path) or json.loads(e5_demo_path.read_text(encoding="utf-8"))
            e5_counters = e5_metrics.get("counters", {})
            e5_records = e5_metrics.get("completion_records", [])
            e5_coverage = e5_metrics.get("e5_verification_coverage", {})

            def e5_counter(name):
                return as_int(e5_counters.get(name, 0))

            if e5_coverage:
                e5_required = {
                    "command_submission": e5_coverage.get("command_submission") is True,
                    "completion_interrupts": e5_coverage.get("completion_interrupts") is True,
                    "fault_interrupts": e5_coverage.get("fault_interrupts") is True,
                    "interrupt_clear": e5_coverage.get("interrupt_clear") is True,
                    "axi_traffic": e5_coverage.get("axi_traffic") is True,
                    "apb_traffic": e5_coverage.get("apb_traffic") is True,
                    "reset_behavior": e5_coverage.get("reset_behavior") is True,
                    "invalid_descriptors": e5_coverage.get("invalid_descriptors") is True,
                    "dma_bounds": e5_coverage.get("dma_bounds") is True,
                    "dma_alignment": e5_coverage.get("dma_alignment") is True,
                    "throughput_tier_link": e5_coverage.get("throughput_tier_link") is True,
                }
                for label, ok in e5_required.items():
                    if not ok:
                        errors.append(f"e5_required_coverage_missing: {label}")

                e5_minimums = {
                    "commands_submitted": len(e5_demo.get("commands", [])),
                    "commands_completed": len(e5_demo.get("commands", [])),
                    "commands_failed": 5,
                    "completion_interrupts": 3,
                    "error_interrupts": 5,
                    "interrupt_clears": 8,
                    "invalid_descriptors": 5,
                    "dma_alignment_errors": 2,
                    "dma_bounds_errors": 1,
                    "command_submission_errors": 5,
                    "resets": 2,
                    "reset_recoveries": 2,
                    "axi_read_transactions": 1,
                    "axi_write_transactions": 3,
                }
                for name, minimum in e5_minimums.items():
                    if e5_counter(name) < minimum:
                        errors.append(f"e5_counter_below_minimum: {name}={e5_counter(name)} minimum={minimum}")
            else:
                e5_commands = e5_demo.get("commands", [])
                e5_queues = {
                    field(queue, "queue_id", -1): queue
                    for queue in e5_demo.get("queues", [])
                    if isinstance(queue, dict)
                }
                e5_regions = e5_demo.get("memory_regions", [])
                e5_opcodes = {str(command.get("opcode")) for command in e5_commands if isinstance(command, dict)}
                e5_expected_errors_from_demo = {
                    str(command.get("expect_error"))
                    for command in e5_commands
                    if isinstance(command, dict) and command.get("expect_error") is not None
                }
                for opcode in [
                    "reset",
                    "dma_fill",
                    "dma_copy",
                    "host_to_device",
                    "device_to_host",
                    "kernel_dispatch",
                    "fence_signal",
                    "fence_wait",
                    "counter_snapshot",
                    "set_scheduler_config",
                    "set_shader_mode",
                ]:
                    if opcode not in e5_opcodes:
                        errors.append(f"e5_required_opcode_missing: {opcode}")
                sequences = [field(command, "sequence", -1) for command in e5_commands if isinstance(command, dict)]
                if sequences != sorted(set(sequences)):
                    errors.append("e5_command_sequence_not_strict")
                if not e5_commands or e5_commands[0].get("opcode") != "reset":
                    errors.append("e5_command_stream_does_not_start_with_reset")
                for queue_id, queue in e5_queues.items():
                    base = field(queue, "base")
                    size = field(queue, "size_bytes")
                    if base % 64 != 0:
                        errors.append(f"e5_queue_base_not_aligned: {queue_id}")
                    if size < 4096 or size & (size - 1):
                        errors.append(f"e5_queue_size_not_power_of_two: {queue_id}")
                for command in e5_commands:
                    if not isinstance(command, dict):
                        continue
                    opcode = str(command.get("opcode"))
                    if field(command, "queue_id", -1) not in e5_queues:
                        errors.append(f"e5_unknown_queue_reference: {command.get('sequence')}")
                    if opcode not in {"dma_fill", "dma_copy", "host_to_device", "device_to_host"}:
                        continue
                    byte_count = field(command, "byte_count")
                    if byte_count <= 0 or byte_count % 4 != 0:
                        errors.append(f"e5_dma_alignment_bad: {command.get('sequence')}")
                    if "src_addr" in command:
                        src = field(command, "src_addr")
                        if src % 4 != 0:
                            errors.append(f"e5_dma_src_alignment_bad: {command.get('sequence')}")
                        if command.get("expect_error") is None and not contains_region(e5_regions, src, byte_count, write=False):
                            errors.append(f"e5_dma_src_bounds_bad: {command.get('sequence')}")
                    if "dst_addr" in command:
                        dst = field(command, "dst_addr")
                        if dst % 4 != 0:
                            errors.append(f"e5_dma_dst_alignment_bad: {command.get('sequence')}")
                        if command.get("expect_error") is None and not contains_region(e5_regions, dst, byte_count, write=True):
                            errors.append(f"e5_dma_dst_bounds_bad: {command.get('sequence')}")
                if not {"ERR_MMU_FAULT", "ERR_FENCE_WAIT", "ERR_SCHEDULER_FAULT"}.issubset(e5_expected_errors_from_demo):
                    errors.append(f"e5_expected_demo_errors_missing: {sorted(e5_expected_errors_from_demo)}")
                if not any(
                    "INJECT_DISPATCH_ERROR" in set(command.get("flags", []))
                    for command in e5_commands
                    if isinstance(command, dict)
                ):
                    errors.append("e5_illegal_descriptor_path_missing")
                e5_minimums = {
                    "commands_submitted": len(e5_commands),
                    "commands_completed": len(e5_commands),
                    "commands_failed": len(e5_expected_errors_from_demo),
                    "completion_interrupts": 1,
                    "error_interrupts": len(e5_expected_errors_from_demo),
                    "resets": 1,
                    "axi_read_transactions": 1,
                    "axi_write_transactions": 1,
                }
                for name, minimum in e5_minimums.items():
                    if e5_counter(name) < minimum:
                        errors.append(f"e5_counter_below_minimum: {name}={e5_counter(name)} minimum={minimum}")

            expected_errors = {
                str(record.get("expected_error"))
                for record in e5_records
                if record.get("error_expected") is True
            }
            required_expected_errors = {"ERR_MMU_FAULT", "ERR_SCHEDULER_FAULT"}
            if e5_coverage:
                required_expected_errors |= {"ERR_BAD_DMA", "ERR_BAD_QUEUE", "ERR_UNSUPPORTED_OPCODE"}
            missing_expected_errors = required_expected_errors - expected_errors
            if missing_expected_errors:
                errors.append(f"e5_expected_errors_missing: {sorted(missing_expected_errors)}")
            if e5_metrics.get("status") != "pass" or e5_metrics.get("expected_command_failures") != 0:
                errors.append("e5_metrics_status_not_pass")
            if e5_coverage and e5_metrics.get("status_registers", {}).get("sticky_error") is not None:
                errors.append("e5_reset_did_not_clear_sticky_error")

            report.append("e5_command_submission_strict=present")
            report.append("e5_interrupt_reset_axi_strict=present")
            report.append("e5_illegal_descriptor_negative_paths=present")
            report.append("e5_dma_bounds_alignment=present")
            report.append("e5_tier_throughput_monotonicity=present")
else:
    report.append("e5_command_submission_strict=skipped")
    report.append("e5_interrupt_reset_axi_strict=skipped")
    report.append("e5_illegal_descriptor_negative_paths=skipped")
    report.append("e5_dma_bounds_alignment=skipped")
    report.append("e5_tier_throughput_monotonicity=skipped")

control_plane_py = repo_root / "tools" / "celviz_gpgpu_ip" / "control_plane.py"
if control_plane_py.exists():
    try:
        compile(control_plane_py.read_text(encoding="utf-8"), str(control_plane_py), "exec")
    except Exception as exc:
        errors.append(f"control_plane_py_syntax_error: {rel(control_plane_py)}: {exc}")
    else:
        report.append(f"control_plane_py_syntax=present {rel(control_plane_py)}")
else:
    report.append("control_plane_py_syntax=skipped")

validate_source_hook(
    "axi4lite2cta_register_counters",
    [
        repo_root / "ventus" / "src" / "axi" / "AXI4Lite2CTA.scala",
    ],
    [
        ("axi4lite2cta_module", r"\bclass\s+AXI4Lite2CTA\b"),
        ("celviz_named_register_or_counter", r"\b(?:celviz\w*(?:reg|counter|cnt|perf|axi|mmio)|(?:reg|counter|cnt|perf|axi|mmio)\w*celviz)\w*\b"),
        ("stateful_register_storage", r"\b(?:RegInit|RegEnable|RegNext)\s*\("),
        ("axi_lite_channel_hook", r"\bio\.ctl\.(?:aw|w|b|ar|r)\."),
    ],
)

validate_source_hook(
    "axi4lite2cta_csr_plumbing",
    [
        repo_root / "ventus" / "src" / "axi" / "AXI4Lite2CTA.scala",
    ],
    [
        ("axi4lite2cta_module", r"\bclass\s+AXI4Lite2CTA\b"),
        ("command_doorbell_csr", r"\bcommandDoorbellReg\b\s*="),
        ("irq_status_csr", r"\birqStatusReg\b\s*="),
        ("error_status_csr", r"\berrorStatusReg\b\s*="),
        ("completion_count_csr", r"\bcompletionCountReg\b\s*="),
        ("apb_axi_read_counter_csr", r"\bapbAxilReadCountReg\b\s*="),
        ("apb_axi_write_counter_csr", r"\bapbAxilWriteCountReg\b\s*="),
        ("register_file_extended_by_reg_count", r"\bregs\s*=\s*RegInit\s*\(\s*VecInit\.fill\s*\(\s*regCount\s*\)"),
        ("read_counter_increments_on_axi_ar", r"\bregs\s*\(\s*apbAxilReadCountReg\s*\)\s*:=\s*regs\s*\(\s*apbAxilReadCountReg\s*\)\s*\+\s*1\.U"),
        ("write_counter_increments_on_axi_w", r"\bregs\s*\(\s*apbAxilWriteCountReg\s*\)\s*:=\s*regs\s*\(\s*apbAxilWriteCountReg\s*\)\s*\+\s*1\.U"),
        ("completion_updates_from_rsp_channel", r"\bio\.rsp\.valid\b.*\bcompletionCountReg\b"),
        ("doorbell_dispatch_updates_data_channel", r"\bio\.data\.fire\b.*\bcommandDoorbellReg\b"),
    ],
)

validate_source_hook(
    "cta_scheduler_debug_counters",
    [
        repo_root / "ventus" / "src" / "cta" / "cta_scheduler.scala",
    ],
    [
        ("cta_scheduler_top_module", r"\bclass\s+cta_scheduler_top\b"),
        ("celviz_debug_bundle", r"\bclass\s+\w*celviz\w*debug\w*\s*\("),
        ("celviz_debug_output_port", r"\bval\s+celviz_debug\s*=\s*Output\s*\("),
        ("celviz_debug_counter_identifier", r"\bcelviz\w*(?:debug|counter|cnt|perf|cta|dispatch|done)\w*\b"),
        ("stateful_counter_storage", r"\b(?:RegInit|RegEnable|RegNext)\s*\("),
        ("counter_helper_increment", r"\bdef\s+eventCounter(?:By)?\b.*\bcount\s*:=\s*count\s*\+"),
        ("cta_fire_or_done_hook", r"\b(?:host_wg_new|host_wg_done|cu_wf_new|cu_wf_done)\b.*\b(?:fire|valid|ready)\b|\b(?:fire|valid|ready)\b.*\b(?:host_wg_new|host_wg_done|cu_wf_new|cu_wf_done)\b"),
    ],
)

validate_source_hook(
    "warp_scheduler_debug_counters",
    [
        repo_root / "ventus" / "src" / "pipeline" / "warp_schedule.scala",
    ],
    [
        ("warp_scheduler_module", r"\bclass\s+warp_scheduler\b"),
        ("celviz_debug_bundle", r"\bclass\s+CelvizWarpSchedulerDebug\b"),
        ("celviz_debug_output_port", r"\bval\s+celviz_debug\s*=\s*Output\s*\("),
        ("celviz_debug_dont_touch", r"\bdontTouch\s*\(\s*io\.celviz_debug\s*\)"),
        ("celviz_debug_counter_identifier", r"\bcelviz\w*(?:debug|counter|cnt|perf|warp|issue|ready|stall|barrier|end)\w*\b"),
        ("stateful_counter_storage", r"\b(?:RegInit|RegEnable|RegNext)\s*\("),
        ("counter_increment_logic", r"\bwhen\s*\([^)]*(?:warp|barrier|branch|flush|blocked)[^)]*\)\s*\{\s*\w+\s*:=\s*\w+\s*\+\s*1\.U\s*\}"),
        ("warp_fire_or_ready_hook", r"\b(?:warpReq|warpRsp|warp_control|warp_ready|issued_warp)\b.*\b(?:fire|valid|ready)\b|\b(?:fire|valid|ready)\b.*\b(?:warpReq|warpRsp|warp_control|warp_ready|issued_warp)\b"),
    ],
)

validate_source_hook(
    "sim_verilator_runtime_proxy_api",
    [
        repo_root / "sim-verilator" / "ventus_rtlsim.h",
        repo_root / "sim-verilator" / "celviz_gpgpu_runtime_proxy.h",
        repo_root / "sim-verilator" / "ventus_rtlsim.cpp",
        repo_root / "sim-verilator" / "ventus_rtlsim_impl.hpp",
        repo_root / "sim-verilator" / "ventus_rtlsim_impl.cpp",
    ],
    [
        ("ventus_header_includes_celviz_proxy", r"#\s*include\s+\"celviz_gpgpu_runtime_proxy\.h\""),
        ("public_celviz_runtime_api", r"\b(?:DLL_PUBLIC\s+[^;\n]*|static\s+inline\s+[^;\n{]*)\b(?:celviz|ventus_rtlsim_celviz)\w*\s*\("),
        ("celviz_runtime_proxy_type", r"\b(?:typedef\s+struct|struct)\b[^;{]*\bcelviz\w*(?:runtime|proxy)\w*|\bcelviz\w*(?:runtime|proxy)\w*_t\b"),
        ("implemented_celviz_runtime_api", r"\b(?:celviz|ventus_rtlsim_celviz)\w*\s*\([^;]*\)\s*\{"),
        ("kernel_enqueue_calls_rtlsim", r"\bcelviz_gpgpu_proxy_enqueue_kernel\b.*\bventus_rtlsim_add_kernel\s*\("),
        ("copy_h2d_calls_rtlsim", r"\bcelviz_gpgpu_proxy_copy_h2d\b.*\bventus_rtlsim_pmemcpy_h2d\s*\("),
        ("copy_d2h_calls_rtlsim", r"\bcelviz_gpgpu_proxy_copy_d2h\b.*\bventus_rtlsim_pmemcpy_d2h\s*\("),
        ("step_status_adapter", r"\bcelviz_gpgpu_command_status_update_from_rtlsim_step\b.*\bventus_rtlsim_step_result_t\b"),
        ("runtime_metrics_storage", r"\bcelviz_gpgpu_runtime_metrics_t\b"),
    ],
)

validate_source_hook(
    "tools_runtime_cli_hooks",
    [
        repo_root / "tools" / "celviz_gpgpu_ip" / "runtime_cli.py",
    ],
    [
        ("argparse_cli", r"\bargparse\.ArgumentParser\s*\("),
        ("kernel_demo_argument", r"\.add_argument\s*\(\s*[\"']--kernel-demo[\"']"),
        ("list_devices_argument", r"\.add_argument\s*\(\s*[\"']--list-devices[\"']"),
        ("kernel_demo_validation", r"\bdef\s+(?:validate_kernel_demo|normalize_queues)\b"),
        ("queue_trace_builder", r"\bdef\s+build_queue_trace\b"),
        ("queue_trace_json_output", r"\bwrite_json\s*\([^)]*queue_trace\.json"),
        ("status_summary_json_output", r"\bwrite_json\s*\([^)]*status\.json"),
        ("compute_model_subprocess_hook", r"\bsubprocess\.run\s*\("),
        ("runtime_main_entrypoint", r"\bif\s+__name__\s*==\s*[\"']__main__[\"']\s*:"),
    ],
)

for log_path in [
    artifact_root / "rtl" / "run.log",
    artifact_root / "rtl" / "smoke.log",
    artifact_root / "control_plane" / "run.log",
    artifact_root / "runtime" / "run.log",
    artifact_root / "demo" / "run.log",
    artifact_root / "model" / "run.log",
]:
    if not log_path.exists():
        report.append(f"optional_log_skipped: {rel(log_path)}")
        continue
    text = read_text(log_path)
    if not text.strip():
        errors.append(f"empty_present_log: {rel(log_path)}")
    elif re.search(r"\b(status|result)\s*=\s*(fail|error)\b", text, re.IGNORECASE):
        errors.append(f"failed_status_in_log: {rel(log_path)}")
    else:
        report.append(f"log_valid: {rel(log_path)}")

throughput_sources = [
    loaded.get(artifact_root / "model" / "metrics.json"),
    loaded.get(artifact_root / "model" / "outputs" / "shader_unit_scaling.json"),
]
throughput_checked = False
for source in throughput_sources:
    if not isinstance(source, dict):
        continue
    tiers = source.get("tiers")
    if tiers is None and isinstance(source.get("public_shader_unit_scaling"), dict):
        tiers = source["public_shader_unit_scaling"].get("tiers")
    if not isinstance(tiers, list) or not tiers:
        continue
    rows = []
    for tier in tiers:
        if not isinstance(tier, dict):
            errors.append("throughput_tier_not_object")
            continue
        try:
            rows.append(
                (
                    int(tier["shader_units_vec1"]),
                    int(tier["fp32_ops_per_cycle"]),
                    int(tier["fp16_ops_per_cycle"]),
                    str(tier.get("tier", "unknown")),
                )
            )
        except Exception as exc:
            errors.append(f"throughput_tier_missing_numeric_fields: {tier}: {exc}")
    if not rows:
        continue
    rows.sort(key=lambda row: (row[0], row[1], row[2], row[3]))
    max_fp32 = -1
    max_fp16 = -1
    for shader_units, fp32_ops, fp16_ops, tier_name in rows:
        if fp32_ops < max_fp32 or fp16_ops < max_fp16:
            errors.append(
                "throughput_not_monotonic_after_shader_unit_sort: "
                f"{tier_name} su={shader_units} fp32={fp32_ops} fp16={fp16_ops}"
            )
        max_fp32 = max(max_fp32, fp32_ops)
        max_fp16 = max(max_fp16, fp16_ops)
    throughput_checked = True

if throughput_checked:
    report.append("throughput_monotonicity_cues=present")
else:
    report.append("throughput_monotonicity_cues=skipped")

report.append("source_level_hook_strictness=pass")
report.append("source_hook_implementation_files_only=pass")
report.append("optional_present_file_strictness=pass")

print("# optional_rich_evidence")
for line in report:
    print(line)

if errors:
    print("# optional_rich_evidence_errors")
    for error in errors:
        print(error)
    sys.exit(1)
PY
}

missing=0
for file in "${required_files[@]}"; do
  if [[ ! -s "$file" ]]; then
    log "missing_or_empty: $file"
    missing=1
  fi
done

for token in "${required_tokens[@]}"; do
  if ! grep -R -q "$token" "$verification_dir/README.md" "$verification_dir/coverage.md" "$verification_dir/test_commands.sh" 2>/dev/null; then
    log "missing_verification_matrix_token: $token"
    missing=1
  fi
done

if [[ "$missing" -ne 0 ]]; then
  fail "required verification files or stable tokens are missing"
fi

tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/celviz_gpgpu_ip_verification.XXXXXX")"
trap 'rm -rf "$tmpdir"' EXIT

component_compute_model_path=""
component_runtime_path=""
component_control_plane_path=""
pending=0

for component in "${component_names[@]}"; do
  if component_path="$(find_component "$component")"; then
    case "$component" in
      compute_model)
        component_compute_model_path="$component_path"
        ;;
      runtime)
        component_runtime_path="$component_path"
        ;;
      control_plane)
        component_control_plane_path="$component_path"
        ;;
    esac
    log "component_${component}: found $component_path"
  else
    log "component_${component}: pending"
    pending=1
  fi
done

if [[ "$pending" -ne 0 ]]; then
  log "celviz_gpgpu_ip_verification: pending"
  log "reason: compute_model, runtime, and control_plane must all exist before S3 execution checks run"
  log "expected_component_candidates:"
  log "compute_model:"
  join_by_nl "${component_compute_model_candidates[@]}"
  log "runtime:"
  join_by_nl "${component_runtime_candidates[@]}"
  log "control_plane:"
  join_by_nl "${component_control_plane_candidates[@]}"
  log "required_tokens:"
  join_by_nl "${required_tokens[@]}"
  exit 0
fi

combined_log="$tmpdir/combined.out"
: >"$combined_log"

for component in "${component_names[@]}"; do
  case "$component" in
    compute_model)
      component_path="$component_compute_model_path"
      ;;
    runtime)
      component_path="$component_runtime_path"
      ;;
    control_plane)
      component_path="$component_control_plane_path"
      ;;
  esac

  if ! entrypoint="$(find_entrypoint "$component_path")"; then
    fail "component $component exists at $component_path but has no runnable entry point"
  fi

  outfile="$tmpdir/${component}.out"
  if ! run_entrypoint "$component" "$entrypoint" "$outfile"; then
    log "component_${component}_output:"
    sed -n '1,160p' "$outfile"
    fail "component $component entry point returned non-zero"
  fi

  {
    printf '\n# component: %s\n' "$component"
    printf '# path: %s\n' "$component_path"
    printf '# entrypoint: %s\n' "$entrypoint"
    cat "$outfile"
  } >>"$combined_log"
done

for evidence_file in \
  "$artifact_root/model/metrics.json" \
  "$artifact_root/model/run.log" \
  "$artifact_root/model/outputs/vector_add.json" \
  "$artifact_root/model/outputs/gemm_proxy.json" \
  "$artifact_root/model/outputs/convolution_proxy.json" \
  "$artifact_root/model/outputs/memory_copy.json" \
  "$artifact_root/model/outputs/shader_unit_scaling.json" \
  "$artifact_root/runtime/metrics.json" \
  "$artifact_root/runtime/run.log" \
  "$artifact_root/demo/metrics.json" \
  "$artifact_root/demo/run.log" \
  "$artifact_root/demo/outputs/status.json" \
  "$artifact_root/demo/outputs/summary.json" \
  "$artifact_root/demo/outputs/vector_add.json" \
  "$artifact_root/demo/outputs/gemm_proxy.json" \
  "$artifact_root/demo/outputs/image_filter.json" \
  "$artifact_root/demo/outputs/memory_copy.json" \
  "$artifact_root/rtl/metrics.json" \
  "$artifact_root/rtl/run.log" \
  "$artifact_root/rtl/smoke.log" \
  "$artifact_root/control_plane/metrics.json" \
  "$artifact_root/control_plane/run.log"; do
  if [[ -f "$evidence_file" ]]; then
    printf '\n# evidence: %s\n' "$evidence_file" >>"$combined_log"
    case "$evidence_file" in
      *.json)
        if ! python3 -m json.tool "$evidence_file" >>"$combined_log"; then
          fail "present JSON evidence is malformed: $evidence_file"
        fi
        ;;
      *)
        cat "$evidence_file" >>"$combined_log"
        ;;
    esac
  fi
done

optional_report="$tmpdir/optional_rich_evidence.out"
if ! validate_optional_evidence >"$optional_report" 2>&1; then
  log "optional_rich_evidence_output:"
  sed -n '1,220p' "$optional_report"
  fail "present optional S3 evidence is malformed"
fi
cat "$optional_report" >>"$combined_log"

{
  printf '\n# normalized_rank1_tokens\n'
  if grep -q "vector_add" "$combined_log"; then
    echo "vector_add=present"
  fi
  if grep -q "gemm_proxy" "$combined_log" && grep -Eq "convolution_proxy|image_filter" "$combined_log"; then
    echo "gemm_convolution_image_filter=present"
  fi
  if grep -q "memory_copy" "$combined_log"; then
    echo "memory_copy=present"
  fi
  if grep -q "shader_unit_scaling" "$combined_log"; then
    echo "shader_unit_scaling=present"
  fi
  if grep -q "fp32_path" "$combined_log" && grep -q "fp16_path" "$combined_log"; then
    echo "fp16_fp32_paths=present"
  fi
  if grep -Eq "kernel_count|kernel_dispatch|command queue|command_queue" "$combined_log"; then
    echo "command_submission=present"
  fi
  if grep -Eqi "interrupt|completion interrupt" "$combined_log"; then
    echo "interrupts=present"
  fi
  if grep -Eqi "AXI|axi_traffic|axi counters|bytes_read|bytes_written" "$combined_log"; then
    echo "axi_traffic=present"
  fi
  if grep -q "shader_unit_scaling" "$combined_log" && grep -Eq "fp32_ops_per_cycle|shader_units|shader_unit_tiers" "$combined_log"; then
    echo "throughput_scaling_by_tier=present"
  fi
} >>"$combined_log"

token_missing=0
for token in "${required_tokens[@]}"; do
  if ! grep -q "$token" "$combined_log"; then
    log "missing_execution_output_token: $token"
    token_missing=1
  fi
done

for token in \
  e5_command_submission_strict \
  e5_interrupt_reset_axi_strict \
  e5_illegal_descriptor_negative_paths \
  e5_dma_bounds_alignment \
  e5_tier_throughput_monotonicity \
  e6_integration_evidence_gate; do
  if ! grep -q "^${token}=present" "$optional_report"; then
    log "missing_e5_or_e6_gate_token: $token"
    token_missing=1
  fi
done

if [[ "$token_missing" -ne 0 ]]; then
  log "combined_execution_output:"
  sed -n '1,220p' "$combined_log"
  fail "one or more required S3 tokens are absent from component output"
fi

log "celviz_gpgpu_ip_verification: pass"
log "checked_components:"
for component in "${component_names[@]}"; do
  case "$component" in
    compute_model)
      component_path="$component_compute_model_path"
      ;;
    runtime)
      component_path="$component_runtime_path"
      ;;
    control_plane)
      component_path="$component_control_plane_path"
      ;;
  esac
  log "  - $component: $component_path"
done
log "checked_tokens:"
join_by_nl "${required_tokens[@]}"
log "checked_optional_rich_evidence:"
log "  - fp16_proxy_outputs"
log "  - control_plane_py_syntax_if_present"
log "  - runtime_queue_phases"
log "  - interrupt_error_reset_tokens"
log "  - axi_apb_transaction_counters"
log "  - throughput_monotonicity_cues"
log "  - e5_command_submission_strict"
log "  - e5_interrupt_reset_axi_strict"
log "  - e5_illegal_descriptor_negative_paths"
log "  - e5_dma_bounds_alignment"
log "  - e5_tier_throughput_monotonicity"
log "  - e6_integration_evidence_gate"
log "  - e6_bandwidth_latency_power_proxy"
log "  - e6_reset_clock_assumptions"
log "  - e6_security_safety_notes"
log "  - e6_explicit_non_goals"
log "  - e6_no_silicon_signoff_claim"
log "  - source_hook_axi4lite2cta_register_counters"
log "  - source_hook_axi4lite2cta_csr_plumbing"
log "  - source_hook_cta_scheduler_debug_counters"
log "  - source_hook_warp_scheduler_debug_counters"
log "  - source_hook_sim_verilator_runtime_proxy_api"
log "  - source_hook_tools_runtime_cli_hooks"
log "  - source_level_hook_strictness"
log "  - source_hook_implementation_files_only"
log "  - optional_present_file_strictness"
log "optional_rich_evidence_summary:"
grep -E '^(fp16_proxy_outputs|runtime_queue_phases|interrupt_error_reset_tokens|axi_apb_transaction_counters|control_plane_py_syntax|throughput_monotonicity_cues|e5_[^=]*|e6_[^=]*|source_hook_[^=]*|source_level_hook_strictness|optional_present_file_strictness)=' "$optional_report" | while IFS= read -r line; do
  log "  - $line"
done
