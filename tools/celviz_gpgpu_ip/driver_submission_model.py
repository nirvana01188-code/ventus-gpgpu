#!/usr/bin/env python3
"""Build clean-room driver submission lifecycle evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "celviz.gpgpu.driver_submission_model.v1"
CLEAN_ROOM_SCOPE = (
    "clean-room Linux userspace/DRM-like submission model only; not a Linux "
    "kernel driver, not DRM/KMS compatibility, not ioctl ABI compatibility, "
    "and not a proprietary Vivante driver or firmware claim"
)
DEFAULT_ROOT = Path("artifacts/rank_01_vivante_3d_gpgpu_ip")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def collect(artifact_root: Path) -> dict[str, Any]:
    runtime = load_json(artifact_root / "demo" / "opencl_subset" / "runtime_commands.json")
    linux = load_json(artifact_root / "os_runtime" / "linux_runtime_evidence.json")
    dispatches = [cmd for cmd in runtime.get("commands", []) if cmd.get("opcode") == "kernel_dispatch"]
    events = linux.get("events", [])
    counters = linux.get("counters", {})
    queues = linux.get("queues", [])
    lifecycle = []
    for command in dispatches:
        sequence = command.get("sequence")
        lifecycle.append(
            {
                "sequence": sequence,
                "kernel": command.get("kernel"),
                "queue_id": command.get("queue_id"),
                "submit_tag": command.get("submit_tag"),
                "fence_model": "out_fence_then_wait",
                "event_model": "eventfd_poll_style_readable_event",
                "completion_addr": command.get("completion_addr"),
                "status": "modeled",
            }
        )
    checks = [
        {"name": "runtime_dispatches_present", "pass": len(dispatches) == 4},
        {"name": "linux_runtime_proxy_pass", "pass": linux.get("status") == "pass"},
        {"name": "queue_lifecycle_no_pending", "pass": all(as_int(q.get("pending")) == 0 for q in queues) if queues else as_int(counters.get("submits")) == as_int(counters.get("completion_events"))},
        {"name": "completion_and_error_paths_present", "pass": as_int(counters.get("submit_success")) > 0 and as_int(counters.get("submit_errors")) > 0},
        {"name": "events_polled", "pass": as_int(counters.get("events_polled")) == len(events) and len(events) >= 4},
        {"name": "fence_wait_signal_path", "pass": as_int(counters.get("fence_waits")) > 0 and as_int(counters.get("fence_signals")) > 0},
        {"name": "kernel_dispatch_set_modeled", "pass": {item["kernel"] for item in lifecycle} == {"vector_add", "gemm", "conv2d", "image_filter"}},
        {"name": "clean_room_non_driver_boundary", "pass": linux.get("boundary", {}).get("kernel_driver_claim") is False},
    ]
    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "status": "pass" if all(c["pass"] for c in checks) else "fail",
        "checks": checks,
        "summary": {
            "runtime_dispatches": len(dispatches),
            "linux_submits": counters.get("submits"),
            "submit_success": counters.get("submit_success"),
            "submit_errors": counters.get("submit_errors"),
            "events_polled": counters.get("events_polled"),
            "fence_waits": counters.get("fence_waits"),
            "fence_signals": counters.get("fence_signals"),
        },
        "dispatch_lifecycle": lifecycle,
        "linux_runtime_boundary": linux.get("boundary", {}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Celviz driver submission evidence.")
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_ROOT / "driver_submission")
    args = parser.parse_args()
    report = collect(args.artifact_root)
    output = args.output_dir / "driver_submission_report.json"
    write_json(output, report)
    passed = sum(1 for c in report["checks"] if c["pass"])
    print(f"celviz_gpgpu_driver_submission: {report['status']} checks={passed}/{len(report['checks'])} output={output}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
