#!/usr/bin/env python3
"""Phase-1 supplemental Verilator verification fixtures for Celviz GPGPU.

This lane intentionally stays outside the shared acceptance matrix and full
Verilator wrapper.  It builds directed, random, fault-injection, and stress
command streams for the existing clean-room control-plane simulator, executes a
fast gate, and writes JSON evidence that can later be replayed under the full
coverage-enabled Verilator runtime.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, MutableMapping, Sequence


SCHEMA = "celviz.gpgpu.verilator_supplemental_phase1.v1"
CLEAN_ROOM_SCOPE = (
    "supplemental clean-room Verilator structural-coverage uplift fixtures; "
    "fast gate uses the control-plane simulator and does not claim RTL line, "
    "toggle, branch, silicon signoff, timing closure, proprietary Vivante "
    "command-stream compatibility, driver ABI compatibility, or conformance"
)
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts/rank_01_vivante_3d_gpgpu_ip/verification/verilator_supplemental_phase1"
CONTROL_PLANE = REPO_ROOT / "tools/celviz_gpgpu_ip/control_plane.py"
CONTROL_PLANE_SCHEMA = "celviz.gpgpu.control_plane_demo.v1"

STRUCTURAL_TARGETS = (
    "queue_arbitration",
    "doorbell_apb_status_poll",
    "completion_interrupt_clear",
    "error_interrupt_clear",
    "dma_fill_write_path",
    "dma_copy_read_write_path",
    "host_to_device_path",
    "device_to_host_path",
    "fence_signal_wait_success",
    "fence_wait_timeout",
    "scheduler_config_write",
    "shader_mode_fp16_fp32",
    "kernel_dispatch_fp16",
    "kernel_dispatch_fp32",
    "kernel_arg_mmu_fault",
    "dma_mmu_fault",
    "dma_alignment_reject",
    "bad_queue_reject",
    "unsupported_opcode_reject",
    "scheduler_fault_reject",
    "reset_recovery",
    "counter_snapshot",
    "multi_queue_tail_wrap_proxy",
    "long_run_idle_retire",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_json(value: Any) -> str:
    raw = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def parse_int(value: Any, default: int = 0) -> int:
    try:
        if isinstance(value, str):
            return int(value, 0)
        if isinstance(value, bool):
            return int(value)
        return int(value)
    except (TypeError, ValueError):
        return default


def base_demo(commands: Sequence[Mapping[str, Any]], *, label: str) -> dict[str, Any]:
    return {
        "schema": CONTROL_PLANE_SCHEMA,
        "ip_name": "Celviz GPGPU IP",
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "phase1_fixture": label,
        "tier": "gpgpu_nano_ultra31",
        "queues": [
            {"queue_id": 0, "base": "0x10000000", "size_bytes": 4096, "priority": 3},
            {"queue_id": 1, "base": "0x10001000", "size_bytes": 4096, "priority": 2},
            {"queue_id": 2, "base": "0x10002000", "size_bytes": 4096, "priority": 1},
            {"queue_id": 3, "base": "0x10003000", "size_bytes": 4096, "priority": 0},
        ],
        "memory_regions": [
            {"name": "global_a", "base": "0x80000000", "size": 262144, "readable": True, "writable": True},
            {"name": "global_ro", "base": "0x81000000", "size": 65536, "readable": True, "writable": False},
            {"name": "completion_records", "base": "0x90000000", "size": 65536, "readable": True, "writable": True},
        ],
        "commands": list(commands),
    }


def flags(*items: str) -> list[str]:
    return list(items)


def directed_fixture() -> dict[str, Any]:
    commands: list[dict[str, Any]] = [
        {
            "opcode": "reset",
            "sequence": 1,
            "queue_id": 0,
            "submit_tag": "directed-reset",
            "flags": flags("INT_ON_COMPLETE"),
        },
        {
            "opcode": "set_scheduler_config",
            "sequence": 2,
            "queue_id": 0,
            "submit_tag": "directed-scheduler-config",
            "issue_policy": 1,
            "watchdog_cycles": 2048,
            "max_workgroups_per_shader_unit": 6,
            "max_warps_per_shader_unit": 12,
            "flags": flags("INT_ON_COMPLETE", "CAPTURE_COUNTERS"),
            "completion_addr": "0x90000000",
        },
        {
            "opcode": "set_shader_mode",
            "sequence": 3,
            "queue_id": 0,
            "submit_tag": "directed-fp16-mode",
            "fp_mode": "fp16",
            "flags": flags("INT_ON_COMPLETE"),
            "completion_addr": "0x90000020",
        },
        {
            "opcode": "dma_fill",
            "sequence": 4,
            "queue_id": 1,
            "submit_tag": "directed-fill-a",
            "dst_addr": "0x80000000",
            "byte_count": 512,
            "pattern_u32": "0x3c003f80",
            "flags": flags("INT_ON_COMPLETE", "CAPTURE_COUNTERS"),
            "completion_addr": "0x90000040",
        },
        {
            "opcode": "host_to_device",
            "sequence": 5,
            "queue_id": 1,
            "submit_tag": "directed-h2d",
            "dst_addr": "0x80002000",
            "byte_count": 384,
            "flags": flags("INT_ON_COMPLETE", "CAPTURE_COUNTERS"),
            "completion_addr": "0x90000060",
        },
        {
            "opcode": "dma_copy",
            "sequence": 6,
            "queue_id": 1,
            "submit_tag": "directed-copy",
            "src_addr": "0x80000000",
            "dst_addr": "0x80004000",
            "byte_count": 512,
            "flags": flags("INT_ON_COMPLETE", "FENCE_AFTER", "CAPTURE_COUNTERS"),
            "completion_addr": "0x90000080",
        },
        {
            "opcode": "fence_signal",
            "sequence": 7,
            "queue_id": 1,
            "submit_tag": "directed-signal",
            "fence": "copy_done",
            "value": 1,
            "flags": flags("INT_ON_COMPLETE"),
        },
        {
            "opcode": "fence_wait",
            "sequence": 8,
            "queue_id": 2,
            "submit_tag": "directed-wait",
            "fence": "copy_done",
            "value": 1,
            "timeout_cycles": 1024,
            "flags": flags("FENCE_BEFORE", "INT_ON_COMPLETE"),
            "completion_addr": "0x900000a0",
        },
        {
            "opcode": "kernel_dispatch",
            "sequence": 9,
            "queue_id": 2,
            "submit_tag": "directed-kernel-fp16",
            "kernel": "image_filter",
            "kernel_entry": "0x80008000",
            "arg_buffer": "0x80002000",
            "arg_bytes": 128,
            "grid": [8, 8, 1],
            "local": [8, 8, 1],
            "required_fp_mode": "fp16",
            "shared_bytes": 2048,
            "private_bytes_per_thread": 12,
            "sgpr_count": 12,
            "vgpr_count": 24,
            "flags": flags("INT_ON_COMPLETE", "KERNEL_USES_FP16", "CAPTURE_COUNTERS"),
            "completion_addr": "0x900000c0",
        },
        {
            "opcode": "set_shader_mode",
            "sequence": 10,
            "queue_id": 2,
            "submit_tag": "directed-fp32-mode",
            "fp_mode": "fp32",
            "flags": flags("INT_ON_COMPLETE"),
            "completion_addr": "0x900000e0",
        },
        {
            "opcode": "kernel_dispatch",
            "sequence": 11,
            "queue_id": 3,
            "submit_tag": "directed-kernel-fp32",
            "kernel": "vector_add",
            "kernel_entry": "0x80008400",
            "arg_buffer": "0x80002200",
            "arg_bytes": 96,
            "grid": [4, 1, 1],
            "local": [64, 1, 1],
            "required_fp_mode": "fp32",
            "shared_bytes": 1024,
            "private_bytes_per_thread": 16,
            "sgpr_count": 16,
            "vgpr_count": 32,
            "flags": flags("INT_ON_COMPLETE", "KERNEL_USES_FP32", "CAPTURE_COUNTERS"),
            "completion_addr": "0x90000100",
        },
        {
            "opcode": "device_to_host",
            "sequence": 12,
            "queue_id": 3,
            "submit_tag": "directed-d2h",
            "src_addr": "0x80004000",
            "byte_count": 256,
            "flags": flags("INT_ON_COMPLETE", "CAPTURE_COUNTERS"),
            "completion_addr": "0x90000120",
        },
        {
            "opcode": "counter_snapshot",
            "sequence": 13,
            "queue_id": 3,
            "submit_tag": "directed-counter-snapshot",
            "flags": flags("INT_ON_COMPLETE"),
            "completion_addr": "0x90000140",
        },
    ]
    return base_demo(commands, label="directed")


def random_fixture(seed: int, command_count: int) -> dict[str, Any]:
    rng = random.Random(seed)
    commands: list[dict[str, Any]] = []
    seq = 1
    commands.append({"opcode": "reset", "sequence": seq, "queue_id": 0, "submit_tag": "random-reset", "flags": flags("INT_ON_COMPLETE")})
    seq += 1
    fence_names: list[str] = []
    op_choices = ("nop", "dma_fill", "dma_copy", "host_to_device", "device_to_host", "barrier", "fence_signal", "fence_wait", "kernel_dispatch", "counter_snapshot")
    for _ in range(max(1, command_count - 1)):
        opcode = rng.choice(op_choices)
        queue_id = rng.randrange(0, 4)
        command: dict[str, Any] = {
            "opcode": opcode,
            "sequence": seq,
            "queue_id": queue_id,
            "submit_tag": f"random-{opcode}-{seq}",
            "flags": flags("INT_ON_COMPLETE") if rng.random() < 0.72 else [],
        }
        if opcode == "dma_fill":
            command.update({"dst_addr": hex(0x80000000 + rng.randrange(0, 0x8000, 0x100)), "byte_count": rng.choice([64, 128, 256, 512]), "pattern_u32": hex(rng.getrandbits(32))})
        elif opcode == "dma_copy":
            src = 0x80000000 + rng.randrange(0, 0x7000, 0x100)
            command.update({"src_addr": hex(src), "dst_addr": hex(src + 0x4000), "byte_count": rng.choice([64, 128, 256, 512])})
        elif opcode == "host_to_device":
            command.update({"dst_addr": hex(0x80008000 + rng.randrange(0, 0x4000, 0x80)), "byte_count": rng.choice([32, 64, 128, 256])})
        elif opcode == "device_to_host":
            command.update({"src_addr": hex(0x80008000 + rng.randrange(0, 0x4000, 0x80)), "byte_count": rng.choice([32, 64, 128, 256])})
        elif opcode == "fence_signal":
            name = f"rfence_{seq}"
            fence_names.append(name)
            command.update({"fence": name, "value": 1})
        elif opcode == "fence_wait":
            if fence_names:
                name = rng.choice(fence_names)
                command.update({"fence": name, "value": 1, "timeout_cycles": rng.choice([16, 64, 256])})
            else:
                command.update({"fence": "rfence_bootstrap", "value": 1, "timeout_cycles": 4, "expect_error": "ERR_FENCE_WAIT"})
        elif opcode == "kernel_dispatch":
            fp_mode = rng.choice(["fp16", "fp32"])
            local = rng.choice([[32, 1, 1], [64, 1, 1], [8, 8, 1]])
            grid = rng.choice([[2, 1, 1], [4, 1, 1], [4, 4, 1], [8, 8, 1]])
            command.update(
                {
                    "kernel": rng.choice(["vector_add", "image_filter", "gemm_proxy"]),
                    "kernel_entry": hex(0x80010000 + seq * 0x40),
                    "arg_buffer": hex(0x80002000 + rng.randrange(0, 0x2000, 0x80)),
                    "arg_bytes": rng.choice([64, 96, 128]),
                    "grid": grid,
                    "local": local,
                    "required_fp_mode": fp_mode,
                    "shared_bytes": rng.choice([0, 512, 1024, 2048]),
                    "private_bytes_per_thread": rng.choice([8, 12, 16]),
                }
            )
        if opcode in {"dma_fill", "dma_copy", "host_to_device", "device_to_host", "kernel_dispatch", "counter_snapshot"} and rng.random() < 0.6:
            command["completion_addr"] = hex(0x90001000 + seq * 0x20)
            command["flags"] = sorted(set(command.get("flags", []) + ["CAPTURE_COUNTERS"]))
        commands.append(command)
        seq += 1
    return base_demo(commands, label=f"random_seed_{seed}")


def fault_fixture() -> dict[str, Any]:
    commands: list[dict[str, Any]] = [
        {"opcode": "reset", "sequence": 1, "queue_id": 0, "submit_tag": "fault-reset", "flags": flags("INT_ON_COMPLETE")},
        {
            "opcode": "dma_copy",
            "sequence": 2,
            "queue_id": 0,
            "submit_tag": "fault-dma-align",
            "src_addr": "0x80000002",
            "dst_addr": "0x80001000",
            "byte_count": 64,
            "expect_error": "ERR_BAD_DMA",
            "flags": flags("INT_ON_COMPLETE"),
        },
        {
            "opcode": "dma_copy",
            "sequence": 3,
            "queue_id": 0,
            "submit_tag": "fault-dma-mmu",
            "src_addr": "0xdead0000",
            "dst_addr": "0x80001000",
            "byte_count": 64,
            "expect_error": "ERR_MMU_FAULT",
            "flags": flags("INT_ON_COMPLETE", "INJECT_MMU_FAULT"),
        },
        {
            "opcode": "kernel_dispatch",
            "sequence": 4,
            "queue_id": 1,
            "submit_tag": "fault-scheduler",
            "kernel": "oversized_local",
            "kernel_entry": "0x80020000",
            "arg_buffer": "0x80002000",
            "arg_bytes": 64,
            "grid": [1, 1, 1],
            "local": [1024, 1, 1],
            "required_fp_mode": "fp32",
            "expect_error": "ERR_SCHEDULER_FAULT",
            "flags": flags("INT_ON_COMPLETE"),
        },
        {
            "opcode": "kernel_dispatch",
            "sequence": 5,
            "queue_id": 1,
            "submit_tag": "fault-kernel-arg-mmu",
            "kernel": "bad_arg",
            "kernel_entry": "0x80020040",
            "arg_buffer": "0x81200000",
            "arg_bytes": 128,
            "grid": [1, 1, 1],
            "local": [32, 1, 1],
            "required_fp_mode": "fp32",
            "expect_error": "ERR_MMU_FAULT",
            "flags": flags("INT_ON_COMPLETE"),
        },
        {"opcode": "fence_wait", "sequence": 6, "queue_id": 2, "submit_tag": "fault-fence-timeout", "fence": "never", "value": 1, "timeout_cycles": 2, "expect_error": "ERR_FENCE_WAIT", "flags": flags("INT_ON_COMPLETE")},
        {"opcode": "undefined_opcode", "sequence": 7, "queue_id": 2, "submit_tag": "fault-unsupported", "expect_error": "ERR_UNSUPPORTED_OPCODE", "flags": flags("INT_ON_COMPLETE")},
        {"opcode": "nop", "sequence": 8, "queue_id": 7, "submit_tag": "fault-bad-queue", "expect_error": "ERR_BAD_QUEUE", "flags": flags("INT_ON_COMPLETE")},
        {"opcode": "reset", "sequence": 9, "queue_id": 0, "submit_tag": "fault-recovery-reset", "flags": flags("INT_ON_COMPLETE")},
        {
            "opcode": "dma_fill",
            "sequence": 10,
            "queue_id": 0,
            "submit_tag": "fault-post-reset-smoke",
            "dst_addr": "0x80000000",
            "byte_count": 64,
            "pattern_u32": "0x00000000",
            "flags": flags("INT_ON_COMPLETE", "CAPTURE_COUNTERS"),
            "completion_addr": "0x90002000",
        },
    ]
    return base_demo(commands, label="fault_injection")


def stress_fixture(iterations: int) -> dict[str, Any]:
    commands: list[dict[str, Any]] = [
        {"opcode": "reset", "sequence": 1, "queue_id": 0, "submit_tag": "stress-reset", "flags": flags("INT_ON_COMPLETE")}
    ]
    seq = 2
    for index in range(iterations):
        queue_id = index % 4
        commands.append(
            {
                "opcode": "dma_fill",
                "sequence": seq,
                "queue_id": queue_id,
                "submit_tag": f"stress-fill-{index}",
                "dst_addr": hex(0x80000000 + (index % 128) * 0x100),
                "byte_count": 64 + (index % 4) * 64,
                "pattern_u32": hex((0x13579BDF + index) & 0xFFFFFFFF),
                "flags": flags("INT_ON_COMPLETE") if index % 5 == 0 else [],
            }
        )
        seq += 1
        commands.append(
            {
                "opcode": "dma_copy",
                "sequence": seq,
                "queue_id": queue_id,
                "submit_tag": f"stress-copy-{index}",
                "src_addr": hex(0x80000000 + (index % 128) * 0x100),
                "dst_addr": hex(0x80010000 + (index % 128) * 0x100),
                "byte_count": 64 + (index % 4) * 64,
                "flags": flags("CAPTURE_COUNTERS") if index % 7 == 0 else [],
                "completion_addr": hex(0x90003000 + ((index % 256) * 0x20)) if index % 7 == 0 else None,
            }
        )
        if commands[-1]["completion_addr"] is None:
            del commands[-1]["completion_addr"]
        seq += 1
        if index % 8 == 0:
            fence = f"stress_fence_{index}"
            commands.append({"opcode": "fence_signal", "sequence": seq, "queue_id": queue_id, "submit_tag": f"stress-signal-{index}", "fence": fence, "value": 1, "flags": flags("INT_ON_COMPLETE")})
            seq += 1
            commands.append({"opcode": "fence_wait", "sequence": seq, "queue_id": (queue_id + 1) % 4, "submit_tag": f"stress-wait-{index}", "fence": fence, "value": 1, "timeout_cycles": 128, "flags": []})
            seq += 1
        if index % 16 == 0:
            commands.append(
                {
                    "opcode": "kernel_dispatch",
                    "sequence": seq,
                    "queue_id": (queue_id + 2) % 4,
                    "submit_tag": f"stress-kernel-{index}",
                    "kernel": "vector_add" if index % 32 else "image_filter",
                    "kernel_entry": hex(0x80030000 + index * 0x40),
                    "arg_buffer": hex(0x80002000 + (index % 64) * 0x80),
                    "arg_bytes": 96,
                    "grid": [4, 1, 1],
                    "local": [64, 1, 1],
                    "required_fp_mode": "fp32" if index % 32 else "fp16",
                    "shared_bytes": 1024,
                    "private_bytes_per_thread": 16,
                    "flags": flags("INT_ON_COMPLETE", "CAPTURE_COUNTERS"),
                    "completion_addr": hex(0x90005000 + ((index % 128) * 0x20)),
                }
            )
            seq += 1
    commands.append({"opcode": "counter_snapshot", "sequence": seq, "queue_id": 0, "submit_tag": "stress-final-counters", "flags": flags("INT_ON_COMPLETE"), "completion_addr": "0x90006000"})
    return base_demo(commands, label=f"stress_{iterations}_iterations")


def fixture_builders(seed: int, random_commands: int, stress_iterations: int) -> dict[str, dict[str, Any]]:
    return {
        "directed": directed_fixture(),
        "random": random_fixture(seed, random_commands),
        "fault": fault_fixture(),
        "stress": stress_fixture(stress_iterations),
    }


def run_control_plane(fixture_path: Path, out_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    stem = fixture_path.stem
    log_path = out_dir / f"{stem}.log"
    metrics_path = out_dir / f"{stem}.metrics.json"
    command = [
        sys.executable,
        str(CONTROL_PLANE),
        "--demo",
        str(fixture_path),
        "--log",
        str(log_path),
        "--metrics",
        str(metrics_path),
    ]
    completed = subprocess.run(command, cwd=str(REPO_ROOT), capture_output=True, text=True, check=False)
    run_record = {
        "command": command,
        "returncode": completed.returncode,
        "stdout_sha256": hashlib.sha256(completed.stdout.encode("utf-8")).hexdigest(),
        "stderr_sha256": hashlib.sha256(completed.stderr.encode("utf-8")).hexdigest(),
        "log": str(log_path),
        "metrics": str(metrics_path),
    }
    if completed.returncode != 0:
        run_record["stdout_tail"] = completed.stdout[-1200:]
        run_record["stderr_tail"] = completed.stderr[-1200:]
        return {}, run_record
    return load_json(metrics_path), run_record


def walk(value: Any) -> Iterable[Any]:
    yield value
    if isinstance(value, Mapping):
        for item in value.values():
            yield from walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk(item)


def collect_dicts(value: Any) -> list[Mapping[str, Any]]:
    return [item for item in walk(value) if isinstance(item, Mapping)]


def opcodes(metrics: Mapping[str, Any]) -> set[str]:
    result: set[str] = set()
    for item in collect_dicts(metrics):
        opcode = item.get("opcode")
        if isinstance(opcode, str):
            result.add(opcode)
    return result


def counter(metrics: Mapping[str, Any], name: str) -> int:
    counters = metrics.get("counters", {})
    if isinstance(counters, Mapping):
        return parse_int(counters.get(name), 0)
    return 0


def hit_targets(metrics_by_suite: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    all_metrics = list(metrics_by_suite.values())
    all_opcodes = set().union(*(opcodes(metrics) for metrics in all_metrics)) if all_metrics else set()
    completion_records = [item for metrics in all_metrics for item in metrics.get("completion_records", []) if isinstance(item, Mapping)]
    queues = {
        str(queue_id)
        for metrics in all_metrics
        for queue_id in (metrics.get("queue_state", {}) if isinstance(metrics.get("queue_state"), Mapping) else {}).keys()
    }
    target_hits = {
        "queue_arbitration": len(queues) >= 4 and any(len({str(item.get("queue_id")) for item in metrics.get("completion_records", []) if isinstance(item, Mapping)}) >= 4 for metrics in all_metrics),
        "doorbell_apb_status_poll": sum(counter(metrics, "apb_writes") for metrics in all_metrics) > 0 and sum(counter(metrics, "apb_reads") for metrics in all_metrics) > 0,
        "completion_interrupt_clear": sum(counter(metrics, "completion_interrupts") for metrics in all_metrics) > 0 and sum(counter(metrics, "interrupt_clears") for metrics in all_metrics) > 0,
        "error_interrupt_clear": sum(counter(metrics, "error_interrupts") for metrics in all_metrics) > 0 and sum(counter(metrics, "interrupt_clears") for metrics in all_metrics) > 0,
        "dma_fill_write_path": "dma_fill" in all_opcodes and sum(counter(metrics, "dma_fills") for metrics in all_metrics) > 0,
        "dma_copy_read_write_path": "dma_copy" in all_opcodes and sum(counter(metrics, "dma_copies") for metrics in all_metrics) > 0,
        "host_to_device_path": "host_to_device" in all_opcodes,
        "device_to_host_path": "device_to_host" in all_opcodes,
        "fence_signal_wait_success": any(item.get("opcode") == "fence_wait" and item.get("error") == "OK" for item in completion_records) and "fence_signal" in all_opcodes,
        "fence_wait_timeout": any(item.get("error") == "ERR_FENCE_WAIT" for item in completion_records),
        "scheduler_config_write": "set_scheduler_config" in all_opcodes,
        "shader_mode_fp16_fp32": "set_shader_mode" in all_opcodes and any(item.get("fp_mode") == "fp16" for item in completion_records) and any(item.get("fp_mode") == "fp32" for item in completion_records),
        "kernel_dispatch_fp16": any(item.get("opcode") == "kernel_dispatch" and item.get("fp16_path") is True for item in completion_records),
        "kernel_dispatch_fp32": any(item.get("opcode") == "kernel_dispatch" and item.get("fp32_path") is True for item in completion_records),
        "kernel_arg_mmu_fault": any(item.get("opcode") == "kernel_dispatch" and item.get("error") == "ERR_MMU_FAULT" for item in completion_records),
        "dma_mmu_fault": any(item.get("opcode") in {"dma_copy", "dma_fill"} and item.get("error") == "ERR_MMU_FAULT" for item in completion_records),
        "dma_alignment_reject": sum(counter(metrics, "dma_alignment_errors") for metrics in all_metrics) > 0,
        "bad_queue_reject": any(item.get("error") == "ERR_BAD_QUEUE" for item in completion_records),
        "unsupported_opcode_reject": any(item.get("error") == "ERR_UNSUPPORTED_OPCODE" for item in completion_records),
        "scheduler_fault_reject": any(item.get("error") == "ERR_SCHEDULER_FAULT" for item in completion_records),
        "reset_recovery": sum(counter(metrics, "reset_recoveries") for metrics in all_metrics) > 0,
        "counter_snapshot": "counter_snapshot" in all_opcodes,
        "multi_queue_tail_wrap_proxy": any(max((parse_int(state.get("tail"), 0) for state in metrics.get("queue_state", {}).values()), default=0) < sum(parse_int(state.get("submitted"), 0) for state in metrics.get("queue_state", {}).values()) * 80 for metrics in all_metrics if isinstance(metrics.get("queue_state"), Mapping)),
        "long_run_idle_retire": any(metrics.get("status") == "pass" and metrics.get("command_count", 0) >= 200 and all(parse_int(state.get("submitted"), 0) == parse_int(state.get("retired"), 0) for state in metrics.get("queue_state", {}).values()) for metrics in all_metrics if isinstance(metrics.get("queue_state"), Mapping)),
    }
    return {
        name: {
            "hit": bool(target_hits.get(name)),
            "structural_coverage_intent": structural_intent(name),
        }
        for name in STRUCTURAL_TARGETS
    }


def structural_intent(name: str) -> str:
    intents = {
        "queue_arbitration": "exercise multiple queue IDs and priority-retire bookkeeping",
        "doorbell_apb_status_poll": "toggle APB submit/status paths for command issue",
        "completion_interrupt_clear": "toggle completion interrupt generation and clear path",
        "error_interrupt_clear": "toggle error interrupt generation and clear path",
        "dma_fill_write_path": "cover DMA fill writable-range and AXI write path",
        "dma_copy_read_write_path": "cover DMA read/write beat accounting",
        "host_to_device_path": "cover runtime H2D copy command category",
        "device_to_host_path": "cover runtime D2H copy command category",
        "fence_signal_wait_success": "cover fence signal and successful wait dependency",
        "fence_wait_timeout": "cover timeout/error branch of fence wait",
        "scheduler_config_write": "cover scheduler config register update path",
        "shader_mode_fp16_fp32": "cover FP mode switch control path",
        "kernel_dispatch_fp16": "cover FP16 kernel dispatch metadata branch",
        "kernel_dispatch_fp32": "cover FP32 kernel dispatch metadata branch",
        "kernel_arg_mmu_fault": "cover kernel arg-buffer MMU fault branch",
        "dma_mmu_fault": "cover DMA MMU range fault branch",
        "dma_alignment_reject": "cover unaligned DMA reject branch",
        "bad_queue_reject": "cover bad queue command-submission reject branch",
        "unsupported_opcode_reject": "cover unsupported opcode reject branch",
        "scheduler_fault_reject": "cover scheduler fault reject branch",
        "reset_recovery": "cover reset cleanup and post-reset recovery path",
        "counter_snapshot": "cover counter snapshot readback path",
        "multi_queue_tail_wrap_proxy": "stress queue head/tail modulo movement",
        "long_run_idle_retire": "stress long-run retirement and idle completion",
    }
    return intents[name]


def summarize_suite(metrics: Mapping[str, Any]) -> dict[str, Any]:
    queue_state = metrics.get("queue_state", {}) if isinstance(metrics.get("queue_state"), Mapping) else {}
    counters = metrics.get("counters", {}) if isinstance(metrics.get("counters"), Mapping) else {}
    return {
        "status": metrics.get("status"),
        "command_count": metrics.get("command_count"),
        "expected_command_passes": metrics.get("expected_command_passes"),
        "expected_command_failures": metrics.get("expected_command_failures"),
        "queues": len(queue_state),
        "opcodes": sorted(opcodes(metrics)),
        "commands_submitted": counters.get("commands_submitted"),
        "commands_completed": counters.get("commands_completed"),
        "commands_failed": counters.get("commands_failed"),
        "kernel_dispatches": counters.get("kernel_dispatches"),
        "dma_copies": counters.get("dma_copies"),
        "dma_fills": counters.get("dma_fills"),
        "bytes_read": counters.get("bytes_read"),
        "bytes_written": counters.get("bytes_written"),
        "completion_interrupts": counters.get("completion_interrupts"),
        "error_interrupts": counters.get("error_interrupts"),
        "mmu_faults": counters.get("mmu_faults"),
        "scheduler_faults": counters.get("scheduler_faults"),
        "dma_alignment_errors": counters.get("dma_alignment_errors"),
        "queue_closed": all(parse_int(state.get("submitted"), 0) == parse_int(state.get("retired"), 0) for state in queue_state.values() if isinstance(state, Mapping)),
    }


def build_evidence(
    output_dir: Path,
    fixtures: Mapping[str, Mapping[str, Any]],
    metrics_by_suite: Mapping[str, Mapping[str, Any]],
    run_records: Mapping[str, Mapping[str, Any]],
    *,
    quick_gate: bool,
) -> tuple[dict[str, Any], int]:
    targets = hit_targets(metrics_by_suite)
    hit_count = sum(1 for item in targets.values() if item["hit"])
    total = len(targets)
    suite_summaries = {name: summarize_suite(metrics) for name, metrics in metrics_by_suite.items()}
    fixture_manifest = {
        name: {
            "fixture": str(output_dir / "fixtures" / f"{name}.json"),
            "sha256": sha256_json(fixture),
            "command_count": len(fixture.get("commands", [])),
        }
        for name, fixture in fixtures.items()
    }
    failures = []
    for name, record in run_records.items():
        if record.get("returncode") != 0:
            failures.append(f"{name}_control_plane_returncode_{record.get('returncode')}")
    for name, summary in suite_summaries.items():
        if summary.get("status") != "pass":
            failures.append(f"{name}_status_{summary.get('status')}")
        if not summary.get("queue_closed"):
            failures.append(f"{name}_queue_not_closed")
    if quick_gate and hit_count != total:
        missed = [name for name, item in targets.items() if not item["hit"]]
        failures.append("structural_targets_missed:" + ",".join(missed))

    observed_metrics = {
        "structural_target_hit_count": hit_count,
        "structural_target_total": total,
        "structural_target_percent": round((hit_count / total) * 100.0, 3) if total else 0.0,
        "total_commands": sum(parse_int(summary.get("command_count"), 0) for summary in suite_summaries.values()),
        "total_kernel_dispatches": sum(parse_int(summary.get("kernel_dispatches"), 0) for summary in suite_summaries.values()),
        "total_dma_copies": sum(parse_int(summary.get("dma_copies"), 0) for summary in suite_summaries.values()),
        "total_dma_fills": sum(parse_int(summary.get("dma_fills"), 0) for summary in suite_summaries.values()),
        "total_completion_interrupts": sum(parse_int(summary.get("completion_interrupts"), 0) for summary in suite_summaries.values()),
        "total_error_interrupts": sum(parse_int(summary.get("error_interrupts"), 0) for summary in suite_summaries.values()),
        "total_mmu_faults": sum(parse_int(summary.get("mmu_faults"), 0) for summary in suite_summaries.values()),
        "total_scheduler_faults": sum(parse_int(summary.get("scheduler_faults"), 0) for summary in suite_summaries.values()),
        "total_dma_alignment_errors": sum(parse_int(summary.get("dma_alignment_errors"), 0) for summary in suite_summaries.values()),
    }
    status = "pass" if not failures else "fail"
    evidence = {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "status": status,
        "quick_gate": quick_gate,
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "responsibility_scope": "scripts/tools/artifacts supplemental lane only; shared acceptance matrix and full wrapper intentionally untouched",
        "fixture_manifest": fixture_manifest,
        "suite_summaries": suite_summaries,
        "structural_targets": targets,
        "observed_metrics": observed_metrics,
        "structural_coverage_improvement_plan": [
            "Replay generated directed/random/fault/stress fixtures through coverage-enabled Verilator runtime_cli once mainline wrapper integration is ready.",
            "Merge target-hit matrix with LCOV line/branch/toggle deltas by source module without treating proxy functional hits as RTL signoff.",
            "Promote suites that produce positive branch/toggle deltas into the shared full wrapper after review by the integration worker.",
            "Keep quick gate deterministic and cheap so it can guard fixture drift while slow coverage remains optional.",
        ],
        "integration_notes": {
            "does_not_modify_shared_acceptance_matrix": True,
            "does_not_modify_full_verilator_wrapper": True,
            "fast_gate_backend": str(CONTROL_PLANE),
            "future_full_coverage_inputs": [item["fixture"] for item in fixture_manifest.values()],
        },
        "run_records": dict(run_records),
        "failures": failures,
    }
    return evidence, 0 if status == "pass" else 1


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--seed", type=int, default=20260502)
    parser.add_argument("--random-commands", type=int, default=48)
    parser.add_argument("--stress-iterations", type=int, default=96)
    parser.add_argument("--generate-only", action="store_true", help="write fixtures/evidence skeleton without running the fast gate")
    parser.add_argument("--no-quick-gate", action="store_true", help="do not fail on missed structural target bins")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    output_dir = args.output_dir.resolve()
    fixtures_dir = output_dir / "fixtures"
    runs_dir = output_dir / "runs"
    fixtures = fixture_builders(args.seed, args.random_commands, args.stress_iterations)
    fixture_paths: dict[str, Path] = {}
    for name, fixture in fixtures.items():
        path = fixtures_dir / f"{name}.json"
        fixture_paths[name] = path
        write_json(path, fixture)

    metrics_by_suite: dict[str, Mapping[str, Any]] = {}
    run_records: dict[str, Mapping[str, Any]] = {}
    if not args.generate_only:
        for name, path in fixture_paths.items():
            metrics, record = run_control_plane(path, runs_dir)
            metrics_by_suite[name] = metrics
            run_records[name] = record
    else:
        run_records = {
            name: {"returncode": None, "fixture": str(path), "status": "generate_only"}
            for name, path in fixture_paths.items()
        }

    evidence, status_code = build_evidence(
        output_dir,
        fixtures,
        metrics_by_suite,
        run_records,
        quick_gate=not args.no_quick_gate and not args.generate_only,
    )
    evidence_path = output_dir / "phase1_supplemental_evidence.json"
    write_json(evidence_path, evidence)
    print(f"celviz_gpgpu_verilator_supplemental_phase1: {evidence['status']}")
    print(f"evidence={evidence_path}")
    print(
        "structural_targets={hit}/{total} ({percent:.3f}%)".format(
            hit=evidence["observed_metrics"]["structural_target_hit_count"],
            total=evidence["observed_metrics"]["structural_target_total"],
            percent=evidence["observed_metrics"]["structural_target_percent"],
        )
    )
    if evidence["failures"]:
        print("failures=" + ",".join(evidence["failures"]), file=sys.stderr)
    return status_code


if __name__ == "__main__":
    raise SystemExit(main())
