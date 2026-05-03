#!/usr/bin/env python3
"""CTS-oriented OpenCL smoke manifest runner.

This runner does not execute the Khronos OpenCL CTS.  It creates a focused
manifest that maps CTS-shaped smoke areas to existing Celviz evidence gates and
records pass/fail per item.  The manifest is intentionally conservative:
official CTS pass is always false.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from . import opencl_subset
except ImportError:  # pragma: no cover - direct script fallback
    import opencl_subset  # type: ignore


SCHEMA = "celviz.gpgpu.opencl_cts_smoke_runner.v1"
DEFAULT_ARTIFACT_ROOT = Path("artifacts/rank_01_vivante_3d_gpgpu_ip")
DEFAULT_OUTPUT = DEFAULT_ARTIFACT_ROOT / "verification/opencl_cts_smoke_runner.json"
DEFAULT_DOC = Path("docs/celviz-gpgpu-ip/OPENCL_CTS_SMOKE_RUNNER.md")
CLEAN_ROOM_SCOPE = (
    "CTS-oriented smoke manifest only; this runner does not execute Khronos "
    "OpenCL CTS, does not produce official OpenCL conformance evidence, does "
    "not claim a production ICD/runtime, and does not claim Vivante-compatible "
    "compiler, firmware, SDK, or command-stream behavior."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        return {"_json_error": str(exc)}
    if isinstance(data, dict):
        return data
    return {"_json_error": "top-level JSON is not an object"}


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def evidence_record(path: Path, *, expected_schema: str | None = None, status_key: str = "status") -> dict[str, Any]:
    data = load_json(path)
    exists = path.exists()
    schema_ok = expected_schema is None or data.get("schema") == expected_schema
    status = data.get(status_key)
    status_ok = status in {None, "pass", "covered", "ready"}
    return {
        "path": str(path),
        "exists": exists,
        "expected_schema": expected_schema,
        "observed_schema": data.get("schema"),
        "schema_ok": bool(schema_ok),
        "status_key": status_key,
        "observed_status": status,
        "status_ok": bool(status_ok),
        "json_error": data.get("_json_error"),
        "pass": bool(exists and schema_ok and status_ok and not data.get("_json_error")),
    }


def manifest_item(
    *,
    item_id: str,
    category: str,
    cts_orientation: str,
    smoke_check: str,
    evidence: Sequence[dict[str, Any]],
    gate_binding: str,
    requirement: str,
    extra_pass: bool = True,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    passed = bool(extra_pass and evidence and all(row.get("pass") is True for row in evidence))
    return {
        "id": item_id,
        "category": category,
        "cts_orientation": cts_orientation,
        "smoke_check": smoke_check,
        "gate_binding": gate_binding,
        "requirement": requirement,
        "evidence": list(evidence),
        "details": dict(details or {}),
        "pass": passed,
        "fail": not passed,
        "claim_boundary": "CTS-oriented smoke manifest only; official CTS pass remains false",
    }


def compile_kernel_smoke(spec: opencl_subset.KernelSpec, ordinal: int) -> dict[str, Any]:
    try:
        abi = opencl_subset.compile_kernel(spec, ordinal)
    except opencl_subset.SubsetError as exc:
        return {
            "name": spec.name,
            "pass": False,
            "error": str(exc),
            "global_size": list(spec.global_size),
            "local_size": list(spec.local_size),
        }
    args = abi.get("args", [])
    buffers = abi.get("buffers", [])
    dimensions_ok = len(abi.get("global_size", [])) == 3 and len(abi.get("local_size", [])) == 3
    pointer_args = [arg for arg in args if isinstance(arg, dict) and arg.get("pointer") is True]
    return {
        "name": spec.name,
        "description": spec.description,
        "source_sha256": abi.get("source_sha256"),
        "arg_count": len(args),
        "pointer_arg_count": len(pointer_args),
        "buffer_count": len(buffers),
        "global_size": abi.get("global_size"),
        "local_size": abi.get("local_size"),
        "precision": abi.get("precision"),
        "pass": bool(
            abi.get("name") == spec.name
            and dimensions_ok
            and len(args) > 0
            and len(buffers) == len(spec.buffers)
            and abi.get("precision") in {"fp16", "fp32", "mixed_fp16_fp32"}
        ),
    }


def build_report(artifact_root: Path) -> dict[str, Any]:
    verification = artifact_root / "verification"
    device_info = evidence_record(
        artifact_root / "opencl_conformance/opencl_device_info_table.json",
        expected_schema="celviz.gpgpu.opencl_device_info_table.v1",
    )
    build_errors = evidence_record(
        verification / "opencl_build_error_code_matrix.json",
        expected_schema="celviz.gpgpu.opencl_build_error_code_matrix.v1",
    )
    buffer_flags = evidence_record(
        verification / "phase9_memory_object_flags_map_gate.json",
        expected_schema="celviz.gpgpu.phase9_memory_object_flags_gate.v1",
    )
    events = evidence_record(
        verification / "opencl_event_waitlist_profiling_report.json",
        expected_schema="celviz.gpgpu.opencl_event_waitlist_profiling_gate.v1",
    )
    queue = evidence_record(
        verification / "runtime_queue_semantics_gate.json",
        expected_schema="celviz.gpgpu.runtime_queue_semantics_gate.v1",
    )
    subset = evidence_record(
        artifact_root / "demo/opencl_subset/opencl_subset_evidence.json",
        expected_schema="celviz.gpgpu.opencl_subset.evidence.v1",
    )
    microop = evidence_record(
        artifact_root / "microop_execution/microop_execution_report.json",
        expected_schema="celviz.gpgpu.microop_interpreter.v1",
    )

    kernel_smokes = [compile_kernel_smoke(spec, index) for index, spec in enumerate(opencl_subset.builtin_specs(), start=1)]
    required_kernel_names = {"vector_add", "gemm", "conv2d", "image_filter"}
    kernel_names = {row["name"] for row in kernel_smokes}
    kernel_pass = required_kernel_names == kernel_names and all(row.get("pass") is True for row in kernel_smokes)

    items = [
        manifest_item(
            item_id="cts_smoke_device_info",
            category="device_info",
            cts_orientation="clGetDeviceInfo smoke coverage for profile/version/limits/memory/queue capability rows",
            smoke_check="Existing CL_DEVICE_* readiness table is present, schema-valid, and passing.",
            evidence=[device_info],
            gate_binding="verify_celviz_gpgpu_opencl_device_info_table.sh / opencl_device_info_table.py",
            requirement="device info",
        ),
        manifest_item(
            item_id="cts_smoke_build_errors",
            category="build_errors",
            cts_orientation="clCreateProgramWithSource, clBuildProgram, clCreateKernel, clSetKernelArg, and NDRange negative-path smoke",
            smoke_check="Existing build/error-code matrix is present, schema-valid, and passing.",
            evidence=[build_errors],
            gate_binding="verify_celviz_gpgpu_opencl_build_error_code_matrix.sh / opencl_build_error_code_matrix.py",
            requirement="build errors",
        ),
        manifest_item(
            item_id="cts_smoke_buffer_flags",
            category="buffer_flags",
            cts_orientation="CL_MEM_READ_WRITE/READ_ONLY/WRITE_ONLY/COPY_HOST_PTR/USE_HOST_PTR plus map/unmap/sub-buffer smoke",
            smoke_check="Existing memory-object flags/map gate is present, schema-valid, and passing.",
            evidence=[buffer_flags],
            gate_binding="verify_celviz_gpgpu_phase9_memory_object_flags.sh / phase9_memory_object_flags_gate.py",
            requirement="buffer flags",
        ),
        manifest_item(
            item_id="cts_smoke_events",
            category="events",
            cts_orientation="event wait-list validation, dependency failure propagation, and profiling timestamp ordering smoke",
            smoke_check="Existing event wait-list/profiling gate is present, schema-valid, and passing.",
            evidence=[events],
            gate_binding="verify_celviz_gpgpu_opencl_event_waitlist_profiling.sh / opencl_event_waitlist_profiling_gate.py",
            requirement="events",
        ),
        manifest_item(
            item_id="cts_smoke_queue",
            category="queue",
            cts_orientation="in-order queue, unsupported out-of-order queue, and queue gap rows smoke",
            smoke_check="Existing runtime queue semantics gate is present, schema-valid, and passing.",
            evidence=[queue],
            gate_binding="verify_celviz_gpgpu_runtime_queue_semantics.sh / runtime_queue_semantics_gate.py",
            requirement="queue",
        ),
        manifest_item(
            item_id="cts_smoke_four_kernels",
            category="kernels",
            cts_orientation="CTS-shaped kernel manifest smoke for vector add, GEMM, convolution, and buffer-backed image filter",
            smoke_check="All four built-in OpenCL subset kernels compile to ABI metadata and are backed by subset plus micro-op evidence.",
            evidence=[subset, microop],
            gate_binding="verify_celviz_gpgpu_opencl_host_api_shim.sh, verify_celviz_gpgpu_microop_execution.sh, opencl_subset.py",
            requirement="four kernels",
            extra_pass=kernel_pass,
            details={
                "required_kernel_names": sorted(required_kernel_names),
                "observed_kernel_names": sorted(kernel_names),
                "kernels": kernel_smokes,
            },
        ),
    ]

    category_summary: dict[str, dict[str, int]] = {}
    for item in items:
        category = str(item["category"])
        bucket = category_summary.setdefault(category, {"pass": 0, "fail": 0})
        bucket["pass" if item["pass"] else "fail"] += 1

    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "runner_kind": "cts_oriented_smoke_manifest",
        "khronos_cts_executed": False,
        "official_cts_pass": False,
        "official_opencl_conformance_claimed": False,
        "status": "pass" if all(item["pass"] for item in items) else "fail",
        "summary": {
            "item_count": len(items),
            "pass_count": sum(1 for item in items if item["pass"]),
            "fail_count": sum(1 for item in items if item["fail"]),
            "required_categories": ["device_info", "build_errors", "buffer_flags", "events", "queue", "kernels"],
            "kernel_count": len(kernel_smokes),
            "official_cts_pass": False,
        },
        "category_summary": category_summary,
        "items": items,
    }


def write_doc(path: Path, report: Mapping[str, Any]) -> None:
    lines = [
        "# OpenCL CTS Smoke Runner",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
        f"Status: `{report['status']}`",
        "",
        "This is a CTS-oriented smoke manifest. It does not run Khronos OpenCL CTS and does not claim official OpenCL conformance.",
        "",
        f"- `khronos_cts_executed`: `{report['khronos_cts_executed']}`",
        f"- `official_cts_pass`: `{report['official_cts_pass']}`",
        f"- `official_opencl_conformance_claimed`: `{report['official_opencl_conformance_claimed']}`",
        "",
        "## Scope",
        "",
        str(report["clean_room_scope"]),
        "",
        "## Smoke Items",
        "",
        "| ID | Category | Pass | Gate Binding | Evidence |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in report.get("items", []):
        if not isinstance(item, Mapping):
            continue
        evidence_paths = []
        for evidence in item.get("evidence", []):
            if isinstance(evidence, Mapping):
                marker = "pass" if evidence.get("pass") else "fail"
                evidence_paths.append(f"`{evidence.get('path')}` ({marker})")
        lines.append(
            f"| `{item.get('id')}` | `{item.get('category')}` | `{item.get('pass')}` | "
            f"{item.get('gate_binding')} | {'<br>'.join(evidence_paths)} |"
        )
    lines.extend(["", "## Kernel Smoke", ""])
    kernel_item = next((item for item in report.get("items", []) if isinstance(item, Mapping) and item.get("category") == "kernels"), {})
    details = kernel_item.get("details", {}) if isinstance(kernel_item, Mapping) else {}
    kernels = details.get("kernels", []) if isinstance(details, Mapping) else []
    lines.append("| Kernel | Pass | Global Size | Local Size | Precision |")
    lines.append("| --- | --- | --- | --- | --- |")
    for kernel in kernels:
        if isinstance(kernel, Mapping):
            lines.append(
                f"| `{kernel.get('name')}` | `{kernel.get('pass')}` | "
                f"`{kernel.get('global_size')}` | `{kernel.get('local_size')}` | `{kernel.get('precision')}` |"
            )
    lines.extend(
        [
            "",
            "## Command",
            "",
            "```sh",
            "bash scripts/verify_celviz_gpgpu_opencl_cts_smoke.sh",
            "```",
            "",
            "Generated JSON:",
            "",
            "`artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_cts_smoke_runner.json`",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    args = parser.parse_args(argv)

    report = build_report(args.artifact_root)
    write_json(args.output, report)
    write_doc(args.doc, report)
    print(
        "celviz_gpgpu_opencl_cts_smoke_runner: "
        f"status={report['status']} items={report['summary']['item_count']} "
        f"official_cts_pass={report['official_cts_pass']}"
    )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
