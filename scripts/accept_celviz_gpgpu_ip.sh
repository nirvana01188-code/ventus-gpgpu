#!/usr/bin/env bash
set -u -o pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root" || exit 2

artifact_root="artifacts/rank_01_vivante_3d_gpgpu_ip"
matrix_path="$artifact_root/verification/acceptance_matrix.json"
control_demo="$artifact_root/rtl/control_plane_demo.json"
e5_demo="$artifact_root/rtl/e5_verification_demo.json"
e5_negative_fixture="$artifact_root/rtl/e5_negative_boundary_fixture.json"
e5_negative_evidence="$artifact_root/rtl/e5_outputs/negative_boundary_evidence.json"
e5_negative_log="$artifact_root/rtl/e5_outputs/negative_boundary_check.log"
kernel_demo="$artifact_root/demo/kernel_demo.json"
tmp_root="${TMPDIR:-/tmp}/celviz-gpgpu-acceptance.$$"
e4_kernel_demo="$tmp_root/e4_kernel_demo.json"
native_runtime_build_manifest="$tmp_root/e3_native_runtime_build_manifest.json"
native_runtime_build_log="$tmp_root/e3_native_runtime_build.log.jsonl"
pass_count=0
fail_count=0
skip_count=0

cleanup() {
  rm -rf "$tmp_root"
}
trap cleanup EXIT
mkdir -p "$tmp_root"

log() {
  printf '%s\n' "$*"
}

configure_java() {
  if command -v java >/dev/null 2>&1 && java -version >/dev/null 2>&1; then
    return 0
  fi

  local candidate
  for candidate in \
    /opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home \
    /opt/homebrew/opt/openjdk/libexec/openjdk.jdk/Contents/Home \
    /usr/local/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home \
    /usr/local/opt/openjdk/libexec/openjdk.jdk/Contents/Home; do
    if [[ -x "$candidate/bin/java" ]]; then
      export JAVA_HOME="$candidate"
      export PATH="$JAVA_HOME/bin:$PATH"
      return 0
    fi
  done
}

print_file_head() {
  local file="$1"
  local lines="${2:-80}"
  if [[ -s "$file" ]]; then
    sed -n "1,${lines}p" "$file"
  fi
}

run_gate() {
  local name="$1"
  shift
  local outfile="$tmp_root/${name}.log"

  log "==> ${name}"
  log "    $*"

  set +e
  "$@" >"$outfile" 2>&1
  local status=$?
  set -e

  if [[ "$status" -eq 0 ]]; then
    log "[PASS] ${name}"
    pass_count=$((pass_count + 1))
  else
    log "[FAIL] ${name} (exit=${status})"
    print_file_head "$outfile" 120
    fail_count=$((fail_count + 1))
  fi
  log ""
  return 0
}

run_gate_shell() {
  local name="$1"
  local command="$2"
  local outfile="$tmp_root/${name}.log"

  log "==> ${name}"
  log "    ${command}"

  set +e
  bash -lc "$command" >"$outfile" 2>&1
  local status=$?
  set -e

  if [[ "$status" -eq 0 ]]; then
    log "[PASS] ${name}"
    pass_count=$((pass_count + 1))
  else
    log "[FAIL] ${name} (exit=${status})"
    print_file_head "$outfile" 120
    fail_count=$((fail_count + 1))
  fi
  log ""
  return 0
}

skip_gate() {
  local name="$1"
  local reason="$2"
  log "==> ${name}"
  log "[SKIP] ${name}: ${reason}"
  log ""
  skip_count=$((skip_count + 1))
}

find_native_runtime() {
  find /tmp/ventus-gpgpu-celviz-build -path '*/libVentusRTL.so' -type f -print 2>/dev/null | sort | head -n 1
}

log "Celviz GPGPU IP acceptance"
log "repo=${root}"
log "matrix=${matrix_path}"
log "tmp=${tmp_root}"
log ""

configure_java || true

run_gate "acceptance_matrix_json" \
  python3 -m json.tool "$matrix_path"

run_gate "rank1_boundary_check" \
  python3 tools/celviz_gpgpu_ip/boundary_check.py \
    --repo-root .

run_gate "source_check" \
  bash scripts/check_celviz_gpgpu_sources.sh

run_gate "chisel_make_compile" \
  make compile

run_gate "python_py_compile" \
  python3 -m py_compile \
    tools/celviz_gpgpu_ip/compute_model.py \
    tools/celviz_gpgpu_ip/control_plane.py \
    tools/celviz_gpgpu_ip/perf_model.py \
    tools/celviz_gpgpu_ip/integration_evidence.py \
    tools/celviz_gpgpu_ip/boundary_check.py \
    tools/celviz_gpgpu_ip/runtime_cli.py \
    tools/celviz_gpgpu_ip/runtime_proxy.py \
    tools/celviz_gpgpu_ip/verilator_coverage_report.py \
    tools/celviz_gpgpu_ip/verification_coverage_100.py \
    tools/celviz_gpgpu_ip/phase2_integration.py \
    tools/celviz_gpgpu_ip/phase3_cross_layer.py \
    tools/celviz_gpgpu_ip/phase4_lowering_integration.py \
    tools/celviz_gpgpu_ip/phase5_microop_integration.py \
    tools/celviz_gpgpu_ip/kernel_lowering.py \
    tools/celviz_gpgpu_ip/microop_interpreter.py \
    tools/celviz_gpgpu_ip/ppa_proxy.py \
    tools/celviz_gpgpu_ip/simt_execution_model.py \
    tools/celviz_gpgpu_ip/opencl_subset.py \
    tools/celviz_gpgpu_ip/memory_model.py \
    tools/celviz_gpgpu_ip/linux_runtime_proxy.py \
    tools/celviz_gpgpu_ip/verify_linux_runtime_proxy.py \
    scripts/tools/artifacts/celviz_gpgpu_verilator_supplemental_phase1.py

run_gate "runtime_dry_run" \
  python3 tools/celviz_gpgpu_ip/runtime_cli.py \
    --commands "$control_demo" \
    --dry-run \
    --output-dir "$tmp_root/runtime_dry_run" \
    --run-log "$tmp_root/runtime_dry_run.log" \
    --print-status

run_gate "e1_runtime_dry_run_output_check" \
  python3 - "$tmp_root/runtime_dry_run/runtime_metrics.json" "$tmp_root/runtime_dry_run/runtime_status.json" "$control_demo" <<'PY'
import json
import sys
from pathlib import Path

metrics_path = Path(sys.argv[1])
status_path = Path(sys.argv[2])
commands_path = Path(sys.argv[3])

metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
status = json.loads(status_path.read_text(encoding="utf-8"))
commands = json.loads(commands_path.read_text(encoding="utf-8"))
errors = []


def require(condition, message):
    if not condition:
        errors.append(message)


def command_opcodes():
    return [str(command.get("opcode")) for command in commands.get("commands", [])]


def counter(name):
    return int(metrics.get("control_plane_metrics", {}).get("counters", {}).get(name, 0))


require(metrics.get("schema") == "celviz.gpgpu.runtime_metrics.v1", "runtime_metrics schema mismatch")
require(status.get("schema") == "celviz.gpgpu.runtime_status.v1", "runtime_status schema mismatch")
require(metrics.get("status") == "pass", "runtime_metrics status is not pass")
require(status.get("status") == "pass", "runtime_status status is not pass")
require(metrics.get("runtime_bridge", {}).get("mode") == "dry_run_forced", "runtime bridge is not forced dry-run")
require(isinstance(metrics.get("native_proxy_snapshot"), dict), "native_proxy_snapshot is missing from runtime_metrics")
require(metrics.get("native_proxy_snapshot") == {}, "dry-run native_proxy_snapshot should be empty")
require("native_runtime_acceptance" not in metrics, "dry-run unexpectedly reports native_runtime_acceptance")
require("native_runtime_acceptance" not in status, "dry-run status unexpectedly reports native_runtime_acceptance")
require(status.get("metrics_path", "").endswith("runtime_metrics.json"), "runtime_status does not point at runtime_metrics.json")

opcodes = set(command_opcodes())
for opcode in ("dma_fill", "dma_copy", "fence_signal", "fence_wait", "kernel_dispatch", "reset"):
    require(opcode in opcodes, f"E1 command stream missing opcode {opcode}")

expected_errors = {
    str(command.get("expect_error"))
    for command in commands.get("commands", [])
    if command.get("expect_error") is not None
}
require({"ERR_MMU_FAULT", "ERR_FENCE_WAIT"}.issubset(expected_errors), "E1 expected error commands missing")
require(
    any("INJECT_MMU_FAULT" in set(command.get("flags", [])) for command in commands.get("commands", [])),
    "E1 MMU fault injection flag missing",
)

control_metrics = metrics.get("control_plane_metrics", {})
completion_records = control_metrics.get("completion_records", [])
status_records = metrics.get("command_status_records", [])
require(len(status_records) == len(completion_records), "status/completion record count mismatch")
require(len(status_records) >= len(commands.get("commands", [])), "not all commands produced status records")
require(
    sum(1 for record in completion_records if record.get("error_expected") is True) >= 2,
    "expected-error completions were not recorded",
)
require(
    {"ERR_MMU_FAULT", "ERR_FENCE_WAIT"}.issubset(
        {str(record.get("expected_error")) for record in completion_records if record.get("error_expected") is True}
    ),
    "expected-error completion records do not cover MMU fault and fence wait",
)

queue_state = control_metrics.get("queue_state", {})
require(len(queue_state) >= 2, "queue lifecycle state for both E1 queues is missing")
for queue_id, queue in queue_state.items():
    for field in ("head", "tail", "submitted", "retired", "errors", "priority"):
        require(field in queue, f"queue {queue_id} missing lifecycle field {field}")
    require(int(queue.get("submitted", 0)) == int(queue.get("retired", -1)), f"queue {queue_id} is not fully retired")
require(int(metrics.get("summary", {}).get("queue_count", -1)) == len(commands.get("queues", [])), "summary queue count mismatch")

minimum_counters = {
    "commands_submitted": len(commands.get("commands", [])),
    "commands_completed": 1,
    "commands_failed": 2,
    "dma_fills": 1,
    "dma_copies": 2,
    "fence_signals": 1,
    "fence_waits": 2,
    "error_interrupts": 2,
    "mmu_faults": 1,
    "queue_errors": 2,
}
for name, minimum in minimum_counters.items():
    require(counter(name) >= minimum, f"counter {name} below E1 minimum {minimum}: {counter(name)}")

summary = metrics.get("summary", {})
for source, label in ((metrics, "metrics"), (status, "status")):
    if "native_runtime_acceptance" in source:
        require("native_proxy_snapshot" in source, f"{label} has native acceptance without native proxy snapshot")
        acceptance = source.get("native_runtime_acceptance", {})
        require(acceptance.get("status") in {"pass", "partial"}, f"{label} native acceptance has bad status")

require(summary.get("commands_submitted") == counter("commands_submitted"), "summary commands_submitted mismatch")
require(summary.get("commands_completed") == counter("commands_completed"), "summary commands_completed mismatch")
require(summary.get("commands_failed") == counter("commands_failed"), "summary commands_failed mismatch")

if errors:
    print("e1_runtime_dry_run_output_check: fail")
    for error in errors:
        print(f"  - {error}")
    raise SystemExit(1)

print("e1_runtime_dry_run_output_check: pass")
print("  - queue lifecycle/status records")
print("  - DMA fill/copy counters")
print("  - named fence signal/wait counters")
print("  - expected MMU/fence errors")
print("  - native snapshot/acceptance consistency")
PY

run_gate "e5_runtime_control_plane_strict_gate" \
  python3 - "$tmp_root/runtime_dry_run/runtime_metrics.json" "$tmp_root/runtime_dry_run/runtime_status.json" "$control_demo" "$artifact_root" <<'PY'
import json
import sys
from pathlib import Path

metrics = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
status = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
commands = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
artifact_root = Path(sys.argv[4])
errors = []


def require(condition, message):
    if not condition:
        errors.append(message)


def as_int(value, default=0):
    try:
        if isinstance(value, str):
            return int(value, 0)
        return int(value)
    except Exception:
        return default


def field(mapping, name, default=0):
    return as_int(mapping.get(name, default), default)


def contains_region(regions, address, byte_count, *, write):
    for region in regions:
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


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def check_tiers(label, tiers, *, strict_shader_units):
    require(isinstance(tiers, list) and len(tiers) >= 3, f"{label} needs at least three tiers")
    rows = sorted(
        (
            field(tier, "shader_units_vec1", field(tier, "shader_units")),
            field(tier, "fp32_ops_per_cycle"),
            field(tier, "fp16_ops_per_cycle"),
            str(tier.get("tier", tier.get("runtime_tier", "unknown"))),
        )
        for tier in tiers
    )
    last_su = last_fp32 = last_fp16 = -1
    for shader_units, fp32_ops, fp16_ops, tier_name in rows:
        if strict_shader_units:
            require(shader_units > last_su, f"{label} shader units not strictly increasing at {tier_name}")
        else:
            require(shader_units >= last_su, f"{label} shader units not sorted at {tier_name}")
        require(fp32_ops >= last_fp32, f"{label} FP32 throughput not monotonic at {tier_name}")
        require(fp16_ops >= last_fp16, f"{label} FP16 throughput not monotonic at {tier_name}")
        last_su, last_fp32, last_fp16 = shader_units, fp32_ops, fp16_ops


require(metrics.get("status") == "pass", "runtime metrics status is not pass")
require(status.get("status") == "pass", "runtime status is not pass")
require(metrics.get("summary") == status.get("summary"), "runtime metrics/status summaries differ")
control = metrics.get("control_plane_metrics", {})
counters = control.get("counters", {})
records = metrics.get("command_status_records", [])
completion_records = control.get("completion_records", [])
interrupts = control.get("interrupt_events", [])
commands_list = commands.get("commands", [])
regions = commands.get("memory_regions", [])
queues = {field(queue, "queue_id", -1): queue for queue in commands.get("queues", [])}
opcodes = {str(command.get("opcode")) for command in commands_list}

for opcode in (
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
):
    require(opcode in opcodes, f"E5 command stream missing opcode {opcode}")

sequences = [field(command, "sequence", -1) for command in commands_list]
require(sequences == sorted(set(sequences)), "E5 command sequence order is not strict")
require(commands_list and commands_list[0].get("opcode") == "reset", "E5 command stream must start with reset")
require(field(counters, "commands_submitted", -1) == len(commands_list), "commands_submitted does not match command stream")
require(field(counters, "commands_completed", -1) == len(commands_list), "commands_completed does not match command stream")
require(len(records) == len(completion_records) == len(commands_list), "status/completion records do not cover every command")
require(field(counters, "resets") >= 1, "reset counter missing")
require(field(counters, "completion_interrupts") > 0, "completion interrupt counter missing")
require(field(counters, "error_interrupts") >= 3, "error interrupt counter does not cover negative paths")
require({str(event.get("kind")) for event in interrupts}.issuperset({"completion", "error"}), "completion/error interrupt events missing")
require(field(counters, "bytes_read") > 0 and field(counters, "bytes_written") > 0, "AXI byte counters are empty")
require(field(counters, "axi_read_transactions") > 0, "AXI read transactions missing")
require(field(counters, "axi_write_transactions") > 0, "AXI write transactions missing")

expected_errors = {str(command.get("expect_error")) for command in commands_list if command.get("expect_error") is not None}
require({"ERR_MMU_FAULT", "ERR_FENCE_WAIT", "ERR_SCHEDULER_FAULT"}.issubset(expected_errors), "negative command errors missing")
require(
    any("INJECT_DISPATCH_ERROR" in set(command.get("flags", [])) for command in commands_list),
    "illegal descriptor/scheduler-fault command missing",
)
for expected_error in expected_errors:
    require(
        any(record.get("error") == expected_error and record.get("error_expected") is True for record in completion_records),
        f"completion records missing expected error {expected_error}",
    )

for queue_id, queue in queues.items():
    base = field(queue, "base")
    size = field(queue, "size_bytes")
    require(base % 64 == 0, f"queue {queue_id} base is not 64-byte aligned")
    require(size >= 4096 and size & (size - 1) == 0, f"queue {queue_id} ring size is not power-of-two >=4096")
for queue_id, queue in control.get("queue_state", {}).items():
    require(field(queue, "submitted", -1) == field(queue, "retired", -2), f"queue {queue_id} is not fully retired")

for command in commands_list:
    opcode = str(command.get("opcode"))
    require(field(command, "queue_id", -1) in queues, f"command {command.get('sequence')} uses unknown queue")
    if opcode not in {"dma_fill", "dma_copy", "host_to_device", "device_to_host"}:
        continue
    byte_count = field(command, "byte_count")
    require(byte_count > 0, f"{opcode} command {command.get('sequence')} byte_count is not positive")
    require(byte_count % 4 == 0, f"{opcode} command {command.get('sequence')} byte_count is not 4-byte aligned")
    if "src_addr" in command:
        src = field(command, "src_addr")
        require(src % 4 == 0, f"{opcode} command {command.get('sequence')} src_addr is not 4-byte aligned")
        if command.get("expect_error") is None:
            require(contains_region(regions, src, byte_count, write=False), f"{opcode} source failed bounds check")
    if "dst_addr" in command:
        dst = field(command, "dst_addr")
        require(dst % 4 == 0, f"{opcode} command {command.get('sequence')} dst_addr is not 4-byte aligned")
        if command.get("expect_error") is None:
            require(contains_region(regions, dst, byte_count, write=True), f"{opcode} destination failed bounds check")

device_tiers = load_json(artifact_root / "demo/outputs/device_tiers.json")
model_tiers = load_json(artifact_root / "model/outputs/shader_unit_scaling.json")
check_tiers("runtime device_tiers", device_tiers.get("devices", []), strict_shader_units=True)
check_tiers("model shader_unit_scaling", model_tiers.get("tiers", []), strict_shader_units=False)

if errors:
    print("e5_runtime_control_plane_strict_gate: fail")
    for error in errors:
        print(f"  - {error}")
    raise SystemExit(1)

print("e5_runtime_control_plane_strict_gate: pass")
print("  - command_submission_strict")
print("  - interrupt_reset_axi_strict")
print("  - illegal_descriptor_negative_paths")
print("  - dma_bounds_alignment")
print("  - tier_throughput_monotonicity")
PY

run_gate "e5_runtime_negative_contracts" \
  python3 - "$control_demo" "$tmp_root" <<'PY'
import json
import subprocess
import sys
from pathlib import Path

control_demo = Path(sys.argv[1])
tmp_root = Path(sys.argv[2])
base = json.loads(control_demo.read_text(encoding="utf-8"))
errors = []


def require(condition, message):
    if not condition:
        errors.append(message)


def run(command):
    return subprocess.run(command, cwd=Path.cwd(), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)


misaligned = json.loads(json.dumps(base))
misaligned["queues"][0]["base"] = "0x10000001"
misaligned_path = tmp_root / "e5_misaligned_queue.json"
misaligned_path.write_text(json.dumps(misaligned, indent=2, sort_keys=True) + "\n", encoding="utf-8")
result = run([
    "python3",
    "tools/celviz_gpgpu_ip/control_plane.py",
    "--demo",
    str(misaligned_path),
    "--log",
    str(tmp_root / "e5_misaligned_queue.log"),
    "--metrics",
    str(tmp_root / "e5_misaligned_queue_metrics.json"),
])
require(result.returncode != 0, "misaligned_queue descriptor unexpectedly passed")
require("64-byte aligned" in result.stdout, "misaligned_queue rejection did not mention 64-byte alignment")

bad_dma = json.loads(json.dumps(base))
bad_dma["commands"] = [
    bad_dma["commands"][0],
    {
        "opcode": "dma_fill",
        "sequence": 2,
        "queue_id": 0,
        "submit_tag": "expected-bad-dma-alignment",
        "dst_addr": "0x80000000",
        "byte_count": 3,
        "pattern_u32": "0x00000000",
        "expect_error": "ERR_BAD_DMA",
        "flags": ["INT_ON_COMPLETE", "CAPTURE_COUNTERS"],
    },
]
bad_dma_path = tmp_root / "e5_bad_dma_alignment.json"
bad_dma_metrics = tmp_root / "e5_bad_dma_alignment_metrics.json"
bad_dma_path.write_text(json.dumps(bad_dma, indent=2, sort_keys=True) + "\n", encoding="utf-8")
result = run([
    "python3",
    "tools/celviz_gpgpu_ip/control_plane.py",
    "--demo",
    str(bad_dma_path),
    "--log",
    str(tmp_root / "e5_bad_dma_alignment.log"),
    "--metrics",
    str(bad_dma_metrics),
])
require(result.returncode == 0, "bad DMA alignment expected-error fixture did not pass")
if bad_dma_metrics.exists():
    metrics = json.loads(bad_dma_metrics.read_text(encoding="utf-8"))
    records = metrics.get("completion_records", [])
    require(metrics.get("status") == "pass", "bad DMA expected-error metrics did not pass")
    require(any(record.get("error") == "ERR_BAD_DMA" for record in records), "bad DMA fixture did not record ERR_BAD_DMA")
else:
    require(False, "bad DMA metrics were not written")

unsupported = json.loads(json.dumps(base))
unsupported["schema"] = "celviz.gpgpu.runtime_commands.v1"
unsupported["commands"] = [
    {
        "opcode": "unsupported_opcode",
        "sequence": 1,
        "queue_id": 0,
        "submit_tag": "illegal-unsupported-opcode",
    }
]
unsupported_path = tmp_root / "e5_unsupported_opcode.json"
unsupported_path.write_text(json.dumps(unsupported, indent=2, sort_keys=True) + "\n", encoding="utf-8")
result = run([
    "python3",
    "tools/celviz_gpgpu_ip/runtime_cli.py",
    "--commands",
    str(unsupported_path),
    "--dry-run",
    "--output-dir",
    str(tmp_root / "e5_unsupported_opcode"),
])
require(result.returncode != 0, "unsupported_opcode descriptor unexpectedly passed")
require(not (tmp_root / "e5_unsupported_opcode" / "runtime_metrics.json").exists(), "unsupported_opcode unexpectedly wrote runtime metrics")

if errors:
    print("e5_runtime_negative_contracts: fail")
    for error in errors:
        print(f"  - {error}")
    raise SystemExit(1)

print("e5_runtime_negative_contracts: pass")
print("  - misaligned_queue rejected")
print("  - ERR_BAD_DMA alignment fixture recorded")
print("  - unsupported_opcode rejected")
PY

run_gate "e4_kernel_demo_fixture" \
  python3 - "$kernel_demo" "$e4_kernel_demo" <<'PY'
import json
import sys
from pathlib import Path

source = Path(sys.argv[1])
destination = Path(sys.argv[2])
demo = json.loads(source.read_text(encoding="utf-8"))
buffers = {buffer.get("id"): buffer for buffer in demo.get("buffers", [])}
for buffer in (
    {"id": "buf_conv_input", "size_bytes": 196, "access": "read", "host_visible": True, "binding": "global"},
    {"id": "buf_conv_kernel", "size_bytes": 36, "access": "read", "host_visible": True, "binding": "global"},
    {"id": "buf_conv_out", "size_bytes": 100, "access": "write", "host_visible": True, "binding": "global"},
):
    if buffer["id"] not in buffers:
        demo.setdefault("buffers", []).append(buffer)

kernel_names = {kernel.get("name") for kernel in demo.get("kernels", [])}
if "convolution_proxy" not in kernel_names:
    demo.setdefault("kernels", []).append(
        {
            "name": "convolution_proxy",
            "dispatch_name": "conv",
            "language": "opencl-c-subset",
            "tier": "micro",
            "queue_id": "queue0",
            "global_size": [5, 5],
            "local_size": [5, 5],
            "precision_modes": ["fp32", "fp16_proxy"],
            "args": [
                {
                    "name": "src",
                    "type": "float*",
                    "address_space": "global",
                    "buffer_id": "buf_conv_input",
                    "access": "read",
                },
                {
                    "name": "filter",
                    "type": "float*",
                    "address_space": "global",
                    "buffer_id": "buf_conv_kernel",
                    "access": "read",
                },
                {
                    "name": "dst",
                    "type": "float*",
                    "address_space": "global",
                    "buffer_id": "buf_conv_out",
                    "access": "write",
                },
            ],
        }
    )

destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(json.dumps(demo, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print("e4_kernel_demo_fixture: pass")
print(f"  - source={source}")
print(f"  - output={destination}")
print("  - convolution_proxy present")
PY

run_gate "runtime_kernel_demo" \
  python3 tools/celviz_gpgpu_ip/runtime_cli.py \
    --kernel-demo "$e4_kernel_demo" \
    --output-dir "$tmp_root/kernel_demo_outputs" \
    --run-log "$tmp_root/kernel_demo_run.log"

run_gate "e4_demo_model_output_check" \
  python3 - "$tmp_root/kernel_demo_outputs" "$artifact_root/model" "$e4_kernel_demo" <<'PY'
import json
import sys
from pathlib import Path

demo_output_dir = Path(sys.argv[1])
model_dir = Path(sys.argv[2])
kernel_demo_path = Path(sys.argv[3])
errors = []


def require(condition, message):
    if not condition:
        errors.append(message)


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_optional_json(path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def sha(value):
    return isinstance(value, str) and len(value) >= 32


def as_int(mapping, field, default=0):
    try:
        return int(mapping.get(field, default))
    except Exception:
        return default


def result_digest(output):
    return output.get("result_sha256") or output.get("hashes", {}).get("result_sha256")


core_kernels = {"vector_add", "gemm_proxy", "image_filter", "memory_copy"}
kernel_demo = load_json(kernel_demo_path)
summary = load_json(demo_output_dir / "summary.json")
queue_trace = load_json(demo_output_dir / "queue_trace.json")
buffer_binds = load_json(demo_output_dir / "buffer_binds.json")
device_tiers = load_json(demo_output_dir / "device_tiers.json")
kernel_metrics = load_json(demo_output_dir / "kernel_metrics.json")
demo_outputs = {
    "vector_add": load_json(demo_output_dir / "vector_add.json"),
    "gemm_proxy": load_json(demo_output_dir / "gemm_proxy.json"),
    "image_filter": load_json(demo_output_dir / "image_filter.json"),
    "memory_copy": load_json(demo_output_dir / "memory_copy.json"),
}
optional_convolution_demo = load_optional_json(demo_output_dir / "convolution_proxy.json")
if optional_convolution_demo is not None:
    demo_outputs["convolution_proxy"] = optional_convolution_demo
model_metrics = load_json(model_dir / "metrics.json")
model_outputs = {
    "vector_add": load_json(model_dir / "outputs/vector_add.json"),
    "gemm_proxy": load_json(model_dir / "outputs/gemm_proxy.json"),
    "convolution_proxy": load_json(model_dir / "outputs/convolution_proxy.json"),
    "memory_copy": load_json(model_dir / "outputs/memory_copy.json"),
    "shader_unit_scaling": load_json(model_dir / "outputs/shader_unit_scaling.json"),
}

kernel_entries = {str(kernel.get("name")): kernel for kernel in kernel_demo.get("kernels", [])}
summary_kernel_names = set(summary.get("kernels", {}))
require(core_kernels.issubset(set(kernel_entries)), f"kernel demo missing kernels: {sorted(core_kernels - set(kernel_entries))}")
require(summary.get("status") == "pass", "demo summary status is not pass")
require(summary.get("completion_status") == "complete", "demo completion_status is not complete")
require(core_kernels.issubset(summary_kernel_names), f"demo summary missing kernels: {sorted(core_kernels - summary_kernel_names)}")
require(summary_kernel_names.issubset(set(kernel_entries)), "demo summary includes kernels absent from kernel_demo")

declared_buffers = {buffer.get("id"): buffer for buffer in kernel_demo.get("buffers", [])}
binding_map = buffer_binds.get("kernel_bindings", {})
require(summary_kernel_names.issubset(set(binding_map)), "buffer_binds missing summary kernels")
for kernel_name, kernel in kernel_entries.items():
    args = kernel.get("args", [])
    global_args = [arg for arg in args if arg.get("address_space") == "global"]
    require(global_args, f"{kernel_name} missing global buffer bindings")
    require({"read", "write"}.issubset({arg.get("access") for arg in global_args}), f"{kernel_name} missing read/write buffer bindings")
    for arg in global_args:
        require(arg.get("buffer_id") in declared_buffers, f"{kernel_name} uses undeclared buffer {arg.get('buffer_id')}")
    global_binds = [bind for bind in binding_map.get(kernel_name, []) if bind.get("address_space") == "global"]
    require(global_binds, f"{kernel_name} missing runtime buffer binds")
    require({"read", "write"}.issubset({bind.get("access") for bind in global_binds}), f"{kernel_name} runtime binds missing read/write")

events = queue_trace.get("events", [])
require(queue_trace.get("status") in {"pass", "complete"}, "queue_trace status is not pass/complete")
require(as_int(queue_trace, "event_count", -1) == len(events), "queue_trace event_count mismatch")
for kernel_name in summary_kernel_names:
    kernel_events = [event for event in events if event.get("kernel") == kernel_name]
    phases = {event.get("phase") for event in kernel_events}
    require({"submit", "wait", "readback"}.issubset(phases), f"{kernel_name} missing dispatch/wait/readback phases")
    for event in kernel_events:
        require(event.get("status") == "complete", f"{kernel_name} event not complete")
        require(event.get("completion_status") == "success", f"{kernel_name} event completion is not success")
    submit = next((event for event in kernel_events if event.get("phase") == "submit"), {})
    readback = next((event for event in kernel_events if event.get("phase") == "readback"), {})
    require(submit.get("buffer_binds"), f"{kernel_name} submit missing buffer_binds")
    require(sha(readback.get("readback_sha256")), f"{kernel_name} missing readback_sha256")
    require(readback.get("readback_sha256") == summary.get("kernels", {}).get(kernel_name), f"{kernel_name} readback/golden hash mismatch")

for kernel_name, output in demo_outputs.items():
    require(output.get("pass") is True, f"{kernel_name} demo output did not pass")
    if kernel_name in summary_kernel_names:
        require(result_digest(output) == summary.get("kernels", {}).get(kernel_name), f"{kernel_name} result/golden hash mismatch")
    elif kernel_name == "convolution_proxy":
        require(result_digest(output) == model_outputs["convolution_proxy"].get("result_sha256"), "convolution result/model golden hash mismatch")
    else:
        require(False, f"{kernel_name} has output but no summary golden")
require(demo_outputs["vector_add"].get("result") == demo_outputs["vector_add"].get("expected"), "vector_add golden compare failed")
require(demo_outputs["memory_copy"].get("source_sha256") == demo_outputs["memory_copy"].get("result_sha256"), "memory_copy golden compare failed")
require(demo_outputs["gemm_proxy"].get("shape", {}).get("m") and demo_outputs["gemm_proxy"].get("shape", {}).get("n"), "gemm shape missing")
require(demo_outputs["image_filter"].get("filter") and demo_outputs["image_filter"].get("width"), "image_filter metadata missing")
if "convolution_proxy" in demo_outputs:
    require(demo_outputs["convolution_proxy"].get("golden_comparison", {}).get("status") == "pass", "convolution golden compare failed")
    require(demo_outputs["convolution_proxy"].get("input_shape") and demo_outputs["convolution_proxy"].get("output_shape"), "convolution shape metadata missing")

require(summary_kernel_names.issubset(set(kernel_metrics.get("kernels", {}))), "kernel_metrics missing summary kernels")
for kernel_name, metric in kernel_metrics.get("kernels", {}).items():
    require(metric.get("model_data_available") is True, f"{kernel_name} metric missing model data")
    require(as_int(metric, "work_items", 0) > 0, f"{kernel_name} metric missing work_items")

devices = sorted(device_tiers.get("devices", []), key=lambda device: as_int(device, "shader_units_vec1", 0))
require(len(devices) >= 4, "tier scaling needs at least four runtime tiers")
last_shader_units = last_fp16 = last_fp32 = -1
for device in devices:
    shader_units = as_int(device, "shader_units_vec1", 0)
    fp16_ops = as_int(device, "fp16_ops_per_cycle", 0)
    fp32_ops = as_int(device, "fp32_ops_per_cycle", 0)
    require(shader_units > last_shader_units, "runtime tier shader units are not strictly increasing")
    require(fp16_ops >= last_fp16, "runtime tier FP16 ops are not monotonic")
    require(fp32_ops >= last_fp32, "runtime tier FP32 ops are not monotonic")
    last_shader_units, last_fp16, last_fp32 = shader_units, fp16_ops, fp32_ops

require(model_metrics.get("status") == "pass", "model metrics status is not pass")
require(as_int(model_metrics.get("totals", {}), "fp16_proxy_ops", 0) > 0, "model FP16 ops missing")
require(as_int(model_metrics.get("totals", {}), "fp32_ops", 0) > 0, "model FP32 ops missing")
for workload in ("vector_add", "gemm_proxy"):
    output = model_outputs[workload]
    require(output.get("precision_path") == "FP32", f"{workload} FP32 model path missing")
    require(as_int(output, "fp32_ops", 0) > 0, f"{workload} FP32 ops missing")
    fp16 = output.get("fp16_proxy", {})
    require(fp16.get("status") == "executed_proxy", f"{workload} FP16 proxy not executed")
    require(fp16.get("method"), f"{workload} FP16 method missing")
    require(sha(fp16.get("result_sha256")), f"{workload} FP16 result hash missing")
    require(fp16.get("error_vs_fp32", {}).get("max_abs") is not None, f"{workload} FP16 tolerance missing")

convolution = model_outputs["convolution_proxy"]
require(convolution.get("alias") == "image_filter", "convolution/image_filter alias missing")
require(convolution.get("precision_path") == "FP32", "convolution FP32 path missing")
require(as_int(convolution, "fp32_ops", 0) > 0, "convolution FP32 ops missing")
require(convolution.get("fp16_proxy", {}).get("status") in {"metadata_only", "executed_proxy"}, "convolution FP16 metadata missing")
require(convolution.get("fp16_proxy", {}).get("method") or convolution.get("fp16_proxy", {}).get("sample_head"), "convolution FP16 method/sample missing")
require(sha(convolution.get("result_sha256")), "convolution result hash missing")
memory_copy = model_outputs["memory_copy"]
require(memory_copy.get("pass") is True, "model memory_copy did not pass")
require(memory_copy.get("source_sha256") == memory_copy.get("destination_sha256"), "model memory_copy source/destination mismatch")

model_tiers = sorted(model_outputs["shader_unit_scaling"].get("tiers", []), key=lambda tier: as_int(tier, "shader_units_vec1", 0))
require(len(model_tiers) >= len(devices), "model tier scaling is thinner than runtime tier scaling")
last_shader_units = last_fp16 = last_fp32 = -1
for tier in model_tiers:
    shader_units = as_int(tier, "shader_units_vec1", 0)
    fp16_ops = as_int(tier, "fp16_ops_per_cycle", 0)
    fp32_ops = as_int(tier, "fp32_ops_per_cycle", 0)
    require(shader_units >= last_shader_units, "model shader tiers are not sorted")
    require(fp16_ops >= last_fp16, "model FP16 tier ops are not monotonic")
    require(fp32_ops >= last_fp32, "model FP32 tier ops are not monotonic")
    last_shader_units, last_fp16, last_fp32 = shader_units, fp16_ops, fp32_ops

if errors:
    print("e4_demo_model_output_check: fail")
    for error in errors:
        print(f"  - {error}")
    raise SystemExit(1)

print("e4_demo_model_output_check: pass")
print("  - vector_add/gemm/convolution/image_filter/memory_copy golden evidence")
print("  - FP16/FP32 model paths and tolerance metadata")
print("  - tier scaling metadata")
print("  - buffer bindings")
print("  - dispatch/readback/golden compare")
PY

run_gate "control_plane_demo" \
  python3 tools/celviz_gpgpu_ip/control_plane.py \
    --demo "$control_demo" \
    --log "$tmp_root/control_plane_run.log" \
    --metrics "$tmp_root/control_plane_metrics.json" \
    --print-metrics

run_gate "e5_verification_coverage" \
  python3 tools/celviz_gpgpu_ip/control_plane.py \
    --demo "$e5_demo" \
    --log "$tmp_root/e5_control_plane_run.log" \
    --metrics "$tmp_root/e5_control_plane_metrics.json" \
    --print-metrics

run_gate "e5_verification_output_check" \
  python3 - "$tmp_root/e5_control_plane_metrics.json" "$e5_demo" "$tmp_root/e5_control_plane_run.log" <<'PY'
import json
import sys
from pathlib import Path

metrics = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
demo = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
run_log = Path(sys.argv[3]).read_text(encoding="utf-8")
errors = []


def require(condition, message):
    if not condition:
        errors.append(message)


def counter(name):
    return int(metrics.get("counters", {}).get(name, 0))


require(metrics.get("schema") == "celviz.gpgpu.control_plane_metrics.v1", "metrics schema mismatch")
require(metrics.get("status") == "pass", "E5 control-plane metrics status is not pass")
require(demo.get("e5_verification_expectations"), "E5 fixture expectations are missing")
require(metrics.get("command_count") == len(demo.get("commands", [])), "E5 command count mismatch")
require(metrics.get("expected_command_failures") == 0, "E5 expected command failures are nonzero")

coverage = metrics.get("e5_verification_coverage", {})
for field in (
    "command_submission",
    "completion_interrupts",
    "fault_interrupts",
    "interrupt_clear",
    "axi_traffic",
    "apb_traffic",
    "reset_behavior",
    "invalid_descriptors",
    "dma_bounds",
    "dma_alignment",
    "throughput_tier_link",
):
    require(coverage.get(field) is True, f"E5 coverage field is not true: {field}")

minimums = {
    "commands_submitted": len(demo.get("commands", [])),
    "commands_completed": len(demo.get("commands", [])),
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
    "apb_reads": 1,
    "apb_writes": 1,
}
for name, minimum in minimums.items():
    require(counter(name) >= minimum, f"counter {name} below {minimum}: {counter(name)}")

records = metrics.get("completion_records", [])
expected_errors = {str(record.get("expected_error")) for record in records if record.get("error_expected") is True}
require(
    {"ERR_BAD_DMA", "ERR_BAD_QUEUE", "ERR_UNSUPPORTED_OPCODE", "ERR_MMU_FAULT", "ERR_SCHEDULER_FAULT"}.issubset(expected_errors),
    f"E5 expected errors incomplete: {sorted(expected_errors)}",
)
for sequence in (4, 5, 6, 7, 8, 9):
    record = next((item for item in records if int(item.get("sequence", -1)) == sequence), {})
    require(record.get("error_expected") is True, f"sequence {sequence} is not marked error_expected")
    require(record.get("status") == "error", f"sequence {sequence} did not produce error status")

reset_records = [record for record in records if record.get("opcode") == "reset"]
require(len(reset_records) >= 2, "E5 reset records missing")
require(
    any(record.get("reset_recovery", {}).get("queue_idle_after_reset") is True for record in reset_records),
    "E5 reset recovery does not report idle queue",
)
require(metrics.get("status_registers", {}).get("sticky_error") is None, "sticky_error was not cleared by reset recovery")
require(any(event.get("kind") == "clear" for event in metrics.get("interrupt_events", [])), "interrupt clear event missing")
require("summary commands=" in run_log and "error_interrupts=" in run_log, "E5 run log summary missing")

if errors:
    print("e5_verification_output_check: fail")
    for error in errors:
        print(f"  - {error}")
    raise SystemExit(1)

print("e5_verification_output_check: pass")
print("  - command submission/error records")
print("  - completion/fault interrupt and clear events")
print("  - AXI/APB traffic counters")
print("  - reset recovery and post-reset smoke")
print("  - invalid descriptor plus DMA bounds/alignment negative paths")
print("  - throughput tier linkage")
PY

run_gate "e5_negative_boundary_fixture_check" \
  python3 - "$e5_negative_fixture" "$e5_negative_evidence" "$e5_negative_log" <<'PY'
import json
import sys
from pathlib import Path

fixture_path = Path(sys.argv[1])
evidence_path = Path(sys.argv[2])
log_path = Path(sys.argv[3])
fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
log_text = log_path.read_text(encoding="utf-8")
errors = []


def require(condition, message):
    if not condition:
        errors.append(message)


summary = evidence.get("summary", {})
coverage = evidence.get("coverage", {})
checks = evidence.get("acceptance_checks", {})
scenarios = fixture.get("scenarios", [])
fields = set(fixture.get("expected_error_record_fields", []))
required_fields = {
    "sequence",
    "submit_tag",
    "queue_id",
    "opcode",
    "descriptor_offset",
    "error",
    "error_code",
    "detail",
    "sticky_error",
    "interrupt_bits",
    "queue_error_count_after",
    "axi_issued",
    "apb_submission_writes",
}

require(fixture.get("schema") == "celviz.gpgpu.e5_negative_boundary_fixture.v1", "fixture schema mismatch")
require(evidence.get("schema") == "celviz.gpgpu.e5_negative_boundary_evidence.v1", "evidence schema mismatch")
require(evidence.get("status") == "pass", "negative boundary evidence status is not pass")
require(summary.get("scenario_count") == len(scenarios) >= 12, "scenario count mismatch or too small")
require(summary.get("invalid_descriptor_scenarios", 0) >= 5, "invalid descriptor coverage is too thin")
require(summary.get("dma_bounds_alignment_scenarios", 0) >= 5, "DMA bounds/alignment coverage is too thin")
require(summary.get("reset_pending_active_scenarios", 0) >= 2, "reset pending/active coverage is missing")
require(summary.get("expected_error_records", 0) >= 10, "expected error records are too few")
require(summary.get("expected_reset_records", 0) >= 2, "expected reset records are too few")
require(summary.get("axi_suppressed_for_rejected_or_flushed_work") is True, "rejected/flushed work should suppress AXI")
require(summary.get("reset_clears_sticky_error_and_pending_state") is True, "reset recovery summary is not true")
require(required_fields.issubset(fields), f"missing command submission record fields: {sorted(required_fields - fields)}")

scenario_categories = {str(item.get("category")) for item in scenarios}
require({"invalid_descriptors", "dma_bounds_alignment", "reset_pending_active"}.issubset(scenario_categories), "scenario categories incomplete")
require(any(item.get("expect_axi_issued") is False for item in scenarios), "no rejected AXI-suppression scenario")
for key in ("invalid_descriptors", "dma_bounds_alignment", "reset_pending_active", "command_submission_error_records"):
    require(coverage.get(key), f"coverage.{key} missing")
if isinstance(checks, dict):
    for name, value in checks.items():
        require(value is True, f"acceptance check failed: {name}")
elif isinstance(checks, list):
    for check in checks:
        name = str(check.get("name", "unnamed_check"))
        require(check.get("result") == "pass", f"acceptance check failed: {name}")
else:
    require(False, "acceptance_checks must be an object or list")
require("celviz_gpgpu_e5_negative_boundary: pass" in log_text, "negative boundary check log missing pass marker")

if errors:
    print("e5_negative_boundary_fixture_check: fail")
    for error in errors:
        print(f"  - {error}")
    raise SystemExit(1)

print("e5_negative_boundary_fixture_check: pass")
print(f"  - scenarios={summary.get('scenario_count')}")
print(f"  - invalid_descriptors={summary.get('invalid_descriptor_scenarios')}")
print(f"  - dma_bounds_alignment={summary.get('dma_bounds_alignment_scenarios')}")
print(f"  - reset_pending_active={summary.get('reset_pending_active_scenarios')}")
print("  - command submission error record fields")
PY

run_gate "e6_integration_evidence" \
  python3 tools/celviz_gpgpu_ip/integration_evidence.py \
    --output "$artifact_root/integration/e6_integration_evidence.json" \
    --log "$artifact_root/integration/e6_integration_check.log" \
    --print-summary

run_gate "e6_integration_output_check" \
  python3 - \
    "$artifact_root/integration/e6_integration_evidence.json" \
    "$artifact_root/integration/e6_integration_check.log" \
    "$artifact_root/integration" \
    "docs/celviz-gpgpu-ip/S5_INTEGRATION_GATE.md" <<'PY'
import json
import re
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
log_text = Path(sys.argv[2]).read_text(encoding="utf-8")
integration_dir = Path(sys.argv[3])
gate_path = Path(sys.argv[4])
errors = []


def require(condition, message):
    if not condition:
        errors.append(message)


def read_text(path):
    if not path.exists():
        errors.append(f"missing file: {path}")
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        errors.append(f"empty file: {path}")
    return text


def load_json(path):
    if not path.exists():
        errors.append(f"missing JSON: {path}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"malformed JSON: {path}: {exc}")
        return {}


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


readme = read_text(integration_dir / "README.md")
bandwidth_doc = read_text(integration_dir / "bandwidth_latency_power.md")
reset_clock_doc = read_text(integration_dir / "reset_clock_interrupt.md")
security_doc = read_text(integration_dir / "security_safety_notes.md")
perf_log = read_text(integration_dir / "perf_model_run.log")
gate_doc = read_text(gate_path)
perf_metrics = load_json(integration_dir / "perf_model_metrics.json")
combined_docs = "\n".join([readme, bandwidth_doc, reset_clock_doc, security_doc, perf_log, gate_doc])
combined_lower = combined_docs.lower()

require(payload.get("schema") == "celviz.gpgpu.e6_integration_evidence.v1", "E6 schema mismatch")
require(payload.get("status") == "pass", "E6 status is not pass")
require(payload.get("e6_status") == "pass_proxy", "E6 proxy status is not pass_proxy")
evidence = payload.get("evidence", {})
for section in ("bandwidth", "latency", "proxy_power", "reset_clock", "security_safety", "non_goals"):
    require(section in evidence, f"E6 evidence section missing: {section}")

for check in payload.get("checks", []):
    require(check.get("pass") is True, f"E6 check failed: {check.get('name')}")

bandwidth = evidence.get("bandwidth", {})
require(int(bandwidth.get("bytes_read", 0)) > 0, "E6 bandwidth bytes_read missing")
require(int(bandwidth.get("bytes_written", 0)) > 0, "E6 bandwidth bytes_written missing")
require(int(bandwidth.get("axi_read_transactions", 0)) > 0, "E6 AXI read transactions missing")
require(int(bandwidth.get("axi_write_transactions", 0)) > 0, "E6 AXI write transactions missing")

latency = evidence.get("latency", {})
require(latency.get("tier_validation_status") == "pass", "E6 latency tier validation is not pass")
require(len(latency.get("latency_proxy_cycles", [])) >= 3, "E6 latency proxy needs at least three tiers")

power = evidence.get("proxy_power", {})
require(power.get("activity_weights_present") is True, "E6 proxy power weights missing")
require(power.get("power_check_present") is True, "E6 proxy power check missing")

reset_clock = evidence.get("reset_clock", {})
require(reset_clock.get("clock_model") == "single_proxy_clock", "E6 clock model mismatch")
require(int(reset_clock.get("resets", 0)) >= 1, "E6 reset evidence missing")
require(int(reset_clock.get("reset_recoveries", 0)) >= 1, "E6 reset recovery missing")
require(int(reset_clock.get("interrupt_clears", 0)) > 0, "E6 interrupt clear evidence missing")

security = evidence.get("security_safety", {})
require(security.get("claim_scope") == "functional_proxy_only", "E6 security/safety claim scope mismatch")
require(int(security.get("invalid_descriptor_scenarios", 0)) >= 5, "E6 invalid descriptor scenarios missing")
require(int(security.get("dma_bounds_alignment_scenarios", 0)) >= 5, "E6 DMA bounds/alignment scenarios missing")

non_goals = evidence.get("non_goals", {})
require(non_goals.get("claim_boundary_present") is True, "E6 claim boundary missing")
require(non_goals.get("licensed_vendor_collateral_excluded") is True, "E6 licensed vendor exclusion missing")
for forbidden in ("silicon signoff", "official OpenCL conformance", "licensed vendor collateral"):
    require(any(forbidden.lower() == str(item).lower() for item in non_goals.get("forbidden_claims", [])), f"E6 forbidden claim missing: {forbidden}")

for token in (
    "bandwidth_bytes_per_cycle",
    "latency_proxy_cycles",
    "aggregate_power_index_proxy",
    "tier_validation_check name=power_proxy_monotonic pass=true",
):
    require(token.lower() in (bandwidth_doc + "\n" + perf_log).lower(), f"E6 doc/log missing proxy token: {token}")

require("clock_model=single_proxy_clock" in reset_clock_doc, "E6 reset/clock doc missing single proxy clock assumption")
require("reset_asserted" in reset_clock_doc and "queue_idle_after_reset" in reset_clock_doc, "E6 reset/clock doc missing reset assumptions")
require("non-goals" in security_doc.lower() or "does not claim" in security_doc.lower(), "E6 security/safety doc missing explicit non-goals")
for token in (
    "not allowed",
    "does not claim",
    "not measured rtl",
    "not silicon ppa",
    "not api conformance",
    "not a silicon signoff plan",
):
    require(token in combined_lower, f"E6 explicit non-goal/caveat missing: {token}")
require(not forbidden_silicon_claims(combined_docs), f"E6 possible silicon signoff claim: {forbidden_silicon_claims(combined_docs)[:3]}")

require(perf_metrics.get("schema") == "celviz.gpgpu.proxy_perf_model.v1", "E6 perf model schema mismatch")
require(perf_metrics.get("status") == "pass", "E6 perf model status is not pass")
tier_validation = perf_metrics.get("tier_validation", {})
tier_checks = {str(item.get("name")): item for item in tier_validation.get("checks", []) if isinstance(item, dict)}
for name in (
    "minimum_three_tiers_selected",
    "axi_byte_pressure_fields_present",
    "axi_byte_pressure_monotonic",
    "latency_proxy_monotonic",
    "power_proxy_monotonic",
):
    require(tier_checks.get(name, {}).get("pass") is True, f"E6 tier validation check missing/pass=false: {name}")

require("celviz_gpgpu_e6_integration: pass" in log_text, "E6 log missing pass marker")
require("no_silicon_signoff" in log_text, "E6 log missing non-goal marker")

if errors:
    print("e6_integration_output_check: fail")
    for error in errors:
        print(f"  - {error}")
    raise SystemExit(1)

print("e6_integration_output_check: pass")
print("  - bandwidth/latency/power proxy")
print("  - reset/clock/interrupt assumptions")
print("  - security/safety functional proxy boundary")
print("  - explicit non-goals and no silicon signoff")
PY

run_gate "artifact_verification" \
  bash scripts/verify_celviz_gpgpu_ip.sh

run_gate "native_runtime_build" \
  env \
    CELVIZ_GPGPU_BUILD_MANIFEST="$native_runtime_build_manifest" \
    CELVIZ_GPGPU_BUILD_LOG="$native_runtime_build_log" \
    bash scripts/build_celviz_gpgpu_runtime.sh --auto

run_gate "e3_native_runtime_build_manifest_log" \
  python3 - "$native_runtime_build_manifest" "$native_runtime_build_log" <<'PY'
import json
import subprocess
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
build_log_path = Path(sys.argv[2])
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
log_entries = [json.loads(line) for line in build_log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
errors = []


def require(condition, message):
    if not condition:
        errors.append(message)


def exported_symbols(lib_path):
    output = ""
    result = subprocess.run(["nm", "-D", "--defined-only", "-g", lib_path], text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
    if result.returncode == 0:
        output = result.stdout
    else:
        for command in (["nm", "-gU", lib_path], ["nm", "-g", lib_path]):
            result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
            if result.returncode == 0:
                output = result.stdout
                break
    symbols = set()
    for line in output.splitlines():
        fields = line.split()
        if not fields:
            continue
        if len(fields) >= 3 and fields[-2] == "U":
            continue
        symbol = fields[-1].rsplit("@", 1)[0]
        if symbol.startswith("_"):
            symbol = symbol[1:]
        symbols.add(symbol)
    return symbols


require(manifest.get("schema") == "celviz.gpgpu.runtime_build_manifest.v1", "manifest schema mismatch")
require(manifest.get("status") == "pass", "manifest status is not pass")
require(manifest.get("build_root"), "manifest missing build_root")
require(manifest.get("requested_mode") == "auto", "manifest mode is not auto")
require(manifest.get("actual_build") in {"fast-relink", "full"}, "manifest actual build is not fast-relink/full")
require(bool(manifest.get("fast_relink_used")) != bool(manifest.get("full_build_used")), "manifest build mode booleans are inconsistent")
require(manifest.get("timestamp_utc"), "manifest missing timestamp")

lib_path = str(manifest.get("native_runtime_lib") or "")
require(lib_path.endswith("libVentusRTL.so"), "manifest native runtime lib is not libVentusRTL.so")
require(Path(lib_path).is_file(), "manifest native runtime lib does not exist")
require(any(entry.get("event") == "manifest_written" for entry in log_entries), "native runtime build log missing manifest_written event")

symbol_check = manifest.get("symbol_check", {})
missing_exported_symbols = list(symbol_check.get("missing_symbols", []))
require(symbol_check.get("complete") is True, "manifest symbol check is incomplete")
require(int(symbol_check.get("missing_count", -1)) == 0, "manifest reports missing exported symbols")
require(not missing_exported_symbols, f"missing exported symbols: {missing_exported_symbols}")
require(int(symbol_check.get("optional_missing_count", -1)) == 0, "manifest reports missing optional exported symbols")

observed_exports = exported_symbols(lib_path)
for symbol in symbol_check.get("present_symbols", []):
    require(symbol in observed_exports, f"manifest symbol missing from nm exports: {symbol}")
for symbol in symbol_check.get("optional_present_symbols", []):
    require(symbol in observed_exports, f"manifest optional symbol missing from nm exports: {symbol}")

if errors:
    print("e3_native_runtime_build_manifest_log: fail")
    for error in errors:
        print(f"  - {error}")
    raise SystemExit(1)

print("e3_native_runtime_build_manifest_log: pass")
print(f"  - manifest={manifest_path}")
print(f"  - log={build_log_path}")
print(f"  - mode={manifest.get('actual_build')}")
print(f"  - CELVIZ_GPGPU_RUNTIME_LIB={lib_path}")
print(f"  - exported_symbols={symbol_check.get('present_count')}")
print(f"  - missing_exported_symbols={symbol_check.get('missing_count')}")
PY

native_runtime="$(find_native_runtime)"
if [[ -n "$native_runtime" ]]; then
  run_gate "native_runtime_require_runtime" \
    python3 tools/celviz_gpgpu_ip/runtime_cli.py \
      --commands "$control_demo" \
      --runtime-lib "$native_runtime" \
      --require-runtime \
      --output-dir "$tmp_root/native_runtime" \
      --run-log "$tmp_root/native_runtime.log" \
      --print-status

  run_gate "e3_native_runtime_output_check" \
    python3 - "$tmp_root/native_runtime/runtime_metrics.json" "$tmp_root/native_runtime/runtime_status.json" <<'PY'
import json
import sys
from pathlib import Path

metrics = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
status = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
errors = []


def require(condition, message):
    if not condition:
        errors.append(message)


require(metrics.get("status") == "pass", "native runtime metrics status is not pass")
require(status.get("status") == "pass", "native runtime status is not pass")
require(metrics.get("runtime_bridge", {}).get("mode") == "ctypes_bound", "native runtime was not ctypes-bound")
require("native_runtime_acceptance" in metrics, "native_runtime_acceptance missing from native metrics")
require("native_proxy_snapshot" in metrics, "native_proxy_snapshot missing from native metrics")
require("native_runtime_acceptance" in status, "native_runtime_acceptance missing from native status")
require("native_proxy_snapshot" in status, "native_proxy_snapshot missing from native status")
require(metrics.get("native_runtime_acceptance") == status.get("native_runtime_acceptance"), "native acceptance differs between metrics and status")
require(metrics.get("native_proxy_snapshot") == status.get("native_proxy_snapshot"), "native snapshot differs between metrics and status")

acceptance = metrics.get("native_runtime_acceptance", {})
require(acceptance.get("status") == "pass", f"native acceptance status is {acceptance.get('status')!r}")
require(not acceptance.get("missing_categories"), "native acceptance has missing categories")
require(not acceptance.get("failed_categories"), "native acceptance has failed categories")
for category in ("dma_fill", "dma_copy", "fence"):
    data = acceptance.get("categories", {}).get(category, {})
    require(int(data.get("observed", 0)) > 0, f"native category {category} not observed")
    require(int(data.get("failed", 0)) == 0, f"native category {category} failed")

snapshot = metrics.get("native_proxy_snapshot", {})
coverage = snapshot.get("abi_symbol_coverage", {})
require(coverage.get("complete") is True, "native ABI symbol coverage is incomplete")
require(int(coverage.get("missing_count", -1)) == 0, "native ABI has missing symbols")
require(coverage.get("optional_present_symbols"), "native ABI optional_present_symbols is empty")
for symbol in (
    "celviz_gpgpu_runtime_proxy_get_queue_by_id",
    "celviz_gpgpu_runtime_proxy_get_queue_pending_count",
    "celviz_gpgpu_runtime_proxy_get_command_status",
    "celviz_gpgpu_runtime_proxy_get_last_event",
    "celviz_gpgpu_runtime_proxy_inject_next_error",
):
    require(symbol in coverage.get("optional_present_symbols", []), f"native ABI optional symbol missing: {symbol}")
queue_totals = snapshot.get("queue_totals", {})
queues = snapshot.get("queues", [])
require(int(queue_totals.get("queue_count", -1)) == len(queues), "native queue total count mismatch")
require(int(queue_totals.get("pending_count", -1)) == int(snapshot.get("pending_count", -2)), "native pending count mismatch")
require(int(queue_totals.get("pending_count", -1)) == 0, "pending count is not zero")
for queue in queues:
    queue_id = queue.get("queue_id")
    for field in ("head", "tail", "doorbell", "submitted", "retired", "errors", "pending_count", "lifecycle"):
        require(field in queue, f"native queue {queue_id} missing {field}")
    require(int(queue.get("pending_count", -1)) == 0, f"native queue {queue_id} pending count is not zero")
    if "queue_pending_count" in queue:
        require(int(queue.get("queue_pending_count", -1)) == 0, f"native queue {queue_id} optional pending count is not zero")
require(snapshot.get("metrics_ok") is True, "native metrics snapshot was not accepted")
require(snapshot.get("device_ok") is True, "native device snapshot was not accepted")
native_metrics = snapshot.get("metrics", {})
for field in ("commands_submitted", "dma_copies", "dma_fills", "fence_waits", "fence_signals"):
    require(field in native_metrics, f"native metrics missing {field}")

summary = snapshot.get("native_pass_fail_summary", {})
require(summary.get("status") == "pass", "native pass/fail summary is not pass")
require(int(summary.get("failed", -1)) == 0, "native pass/fail summary has failures")
require(int(summary.get("passed", 0)) > 0, "native pass/fail summary has no passes")
native_command_results = metrics.get("native_command_results", [])
require(isinstance(native_command_results, list) and native_command_results, "native_command_results missing or empty")

if errors:
    print("e3_native_runtime_output_check: fail")
    for error in errors:
        print(f"  - {error}")
    raise SystemExit(1)

print("e3_native_runtime_output_check: pass")
print("  - native_proxy_snapshot mirrors runtime_status")
print("  - native_runtime_acceptance covers DMA and fence categories")
print("  - native queue totals, metrics, and ABI symbol coverage are consistent")
PY
else
  skip_gate "native_runtime_require_runtime" \
    "no /tmp/ventus-gpgpu-celviz-build/.../libVentusRTL.so found"
  skip_gate "e3_native_runtime_output_check" \
    "no /tmp/ventus-gpgpu-celviz-build/.../libVentusRTL.so found"
fi

run_gate_shell "git_diff_check" "git diff --check"

log "Celviz GPGPU IP acceptance summary"
log "PASS=${pass_count} FAIL=${fail_count} SKIP=${skip_count}"

if [[ "$fail_count" -eq 0 ]]; then
  log "OVERALL: PASS"
  exit 0
fi

log "OVERALL: FAIL"
exit 1
