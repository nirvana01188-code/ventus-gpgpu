#!/usr/bin/env python3
"""Focused validation entry for Linux userspace runtime proxy evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

try:
    from . import linux_runtime_proxy
except ImportError:  # pragma: no cover - direct script fallback
    import linux_runtime_proxy  # type: ignore


REQUIRED_CHECKS = {
    "device_context_open",
    "bo_alloc_map_gpu_va",
    "drm_like_submit_completion",
    "fence_wait_signal",
    "event_poll_readable",
    "completion_error_path",
    "queue_retired_no_pending",
    "clean_room_non_driver_boundary",
}


def load_json(path: Path) -> Mapping[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_evidence(evidence: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if evidence.get("schema") != linux_runtime_proxy.EVIDENCE_SCHEMA:
        errors.append(f"schema mismatch: {evidence.get('schema')}")
    if evidence.get("status") != "pass":
        errors.append(f"status is not pass: {evidence.get('status')}")
    boundary = evidence.get("boundary", {})
    if not isinstance(boundary, Mapping) or boundary.get("kernel_driver_claim") is not False:
        errors.append("boundary.kernel_driver_claim must be false")
    checks = evidence.get("checks", [])
    if not isinstance(checks, list):
        errors.append("checks must be a list")
        checks = []
    check_map = {str(check.get("name")): check.get("pass") is True for check in checks if isinstance(check, Mapping)}
    missing = sorted(REQUIRED_CHECKS.difference(check_map))
    failed = sorted(name for name, ok in check_map.items() if name in REQUIRED_CHECKS and not ok)
    if missing:
        errors.append("missing checks: " + ",".join(missing))
    if failed:
        errors.append("failed checks: " + ",".join(failed))
    counters = evidence.get("counters", {})
    if not isinstance(counters, Mapping):
        errors.append("counters must be an object")
        counters = {}
    minimums = {
        "device_opens": 1,
        "context_creates": 1,
        "bo_allocs": 2,
        "bo_maps": 2,
        "bo_gpu_maps": 2,
        "submits": 2,
        "submit_success": 1,
        "submit_errors": 1,
        "fence_waits": 2,
        "events_generated": 2,
        "events_polled": 1,
    }
    for key, minimum in minimums.items():
        if int(counters.get(key, 0)) < minimum:
            errors.append(f"counter {key} below minimum {minimum}: {counters.get(key)}")
    queues = evidence.get("queues", [])
    if not isinstance(queues, list) or not queues:
        errors.append("queues must contain at least one queue")
    else:
        pending = sum(int(queue.get("pending", 0)) for queue in queues if isinstance(queue, Mapping))
        if pending != 0:
            errors.append(f"queues have pending work: {pending}")
    events = evidence.get("events", [])
    if not isinstance(events, list) or not any(isinstance(event, Mapping) and event.get("error") is True for event in events):
        errors.append("expected at least one error event")
    if not isinstance(events, list) or not any(isinstance(event, Mapping) and event.get("readable") is True for event in events):
        errors.append("expected at least one readable event")
    return errors


def build_argparser() -> argparse.ArgumentParser:
    root = linux_runtime_proxy.repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=linux_runtime_proxy.default_fixture(root), help="Fixture JSON")
    parser.add_argument("--evidence", type=Path, default=linux_runtime_proxy.default_evidence(root), help="Evidence JSON")
    parser.add_argument("--log", type=Path, default=linux_runtime_proxy.default_log(root), help="Run log")
    parser.add_argument("--reuse-existing", action="store_true", help="Validate existing evidence instead of regenerating it")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_argparser()
    args = parser.parse_args(argv)
    if args.reuse_existing:
        evidence = load_json(args.evidence)
    else:
        evidence = linux_runtime_proxy.run_to_files(fixture_path=args.fixture, evidence_path=args.evidence, log_path=args.log)
    errors = validate_evidence(evidence)
    if errors:
        print("celviz_gpgpu_linux_runtime_proxy_verify: fail")
        for error in errors:
            print("reason: " + error)
        return 1
    print("celviz_gpgpu_linux_runtime_proxy_verify: pass")
    print(f"evidence={args.evidence}")
    print(f"log={args.log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
