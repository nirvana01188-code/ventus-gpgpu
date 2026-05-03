#!/usr/bin/env python3
"""Generate the OpenCL product gap-closure ledger from current evidence.

The ledger is intentionally conservative: a passing ledger means the gap
classification was generated and checked, not that the product OpenCL stack is
complete. Official OpenCL, Khronos CTS, ICD loader, libOpenCL ABI, production
kernel-driver, images, samplers, SVM, atomics, and out-of-order queues remain
blocked unless repository evidence proves otherwise.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


SCHEMA = "celviz.gpgpu.opencl_product_gap_closure.v1"
DEFAULT_ARTIFACT_ROOT = Path("artifacts/rank_01_vivante_3d_gpgpu_ip")
DEFAULT_OUTPUT = DEFAULT_ARTIFACT_ROOT / "verification" / "opencl_product_gap_closure.json"
DEFAULT_DOC = Path("docs/celviz-gpgpu-ip/OPENCL_PRODUCT_GAP_CLOSURE.md")
CLEAN_ROOM_SCOPE = (
    "executable OpenCL product gap-closure ledger for the clean-room Celviz "
    "GPGPU IP proxy; not an official OpenCL conformance claim, not Khronos CTS "
    "pass evidence, not a Khronos ICD loader integration, not a libOpenCL ABI "
    "implementation, not a production Linux kernel/DRM driver, and not "
    "proprietary Vivante compatibility"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path, required: bool = True) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        if required:
            raise SystemExit(f"missing required evidence file: {path}") from exc
        return {}
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON in evidence file {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"evidence file is not a JSON object: {path}")
    return payload


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def status_is_pass(payload: Mapping[str, Any]) -> bool:
    return payload.get("status") == "pass"


def all_checks_pass(payload: Mapping[str, Any]) -> bool:
    checks = payload.get("checks", [])
    if not isinstance(checks, list):
        return False
    return bool(checks) and all(isinstance(item, dict) and item.get("pass") is True for item in checks)


def names(items: Iterable[Mapping[str, Any]]) -> set[str]:
    return {str(item.get("name", "")) for item in items if item.get("name")}


def evidence_ref(path: Path, payload: Mapping[str, Any], note: str) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": bool(payload),
        "status": payload.get("status"),
        "note": note,
    }


def item(
    gap_id: str,
    title: str,
    classification: str,
    rationale: str,
    evidence: list[dict[str, Any]],
    next_executable_step: str,
    *,
    official_blocker: str = "",
) -> dict[str, Any]:
    if classification not in {"done", "partial", "blocked"}:
        raise ValueError(f"bad classification {classification!r}")
    return {
        "id": gap_id,
        "title": title,
        "classification": classification,
        "rationale": rationale,
        "evidence": evidence,
        "official_blocker": official_blocker,
        "next_executable_step": next_executable_step,
        "claim_boundary": "local executable gap evidence only; not official OpenCL conformance",
    }


def classify(artifact_root: Path) -> dict[str, Any]:
    verification = artifact_root / "verification"
    paths = {
        "subset": verification / "opencl_subset_conformance_tests.json",
        "host_shim": verification / "opencl_host_api_shim_report.json",
        "event_waitlist": verification / "opencl_event_waitlist_profiling_report.json",
        "icd_contract": verification / "opencl_icd_runtime_contract.json",
        "cts_readiness": verification / "phase9_opencl_conformance_readiness_report.json",
        "cts_matrix": verification / "opencl_cts_readiness_matrix.json",
        "rtl_cts_cross_check": verification / "opencl_rtl_cts_cross_check.json",
        "device_info": artifact_root / "opencl_conformance" / "opencl_device_info_table.json",
        "driver_os": verification / "phase9_driver_os_conformance_readiness.json",
        "driver_submission": artifact_root / "driver_submission" / "driver_submission_report.json",
        "runtime_commands": artifact_root / "demo" / "opencl_subset" / "runtime_commands.json",
        "runtime_metrics": artifact_root / "demo" / "opencl_subset" / "runtime_proxy" / "runtime_metrics.json",
        "coverage": verification / "verification_coverage_100.json",
    }
    evidence = {name: load_json(path, required=True) for name, path in paths.items()}

    subset = evidence["subset"]
    negative_names = names(subset.get("negative_tests", []))
    positive_names = names(subset.get("positive_tests", []))
    host_shim = evidence["host_shim"]
    event_waitlist = evidence["event_waitlist"]
    icd_contract = evidence["icd_contract"]
    cts_readiness = evidence["cts_readiness"]
    cts_matrix = evidence["cts_matrix"]
    rtl_cts = evidence["rtl_cts_cross_check"]
    driver_os = evidence["driver_os"]
    device_info = evidence["device_info"]
    runtime_commands = evidence["runtime_commands"]
    runtime_metrics = evidence["runtime_metrics"]
    coverage = evidence["coverage"]

    host_apis = {str(call.get("api", "")) for call in host_shim.get("api_call_trace", []) if isinstance(call, dict)}
    required_core_apis = {
        "clGetPlatformIDs",
        "clGetDeviceIDs",
        "clGetDeviceInfo",
        "clCreateContext",
        "clCreateCommandQueueWithProperties",
        "clCreateBuffer",
        "clCreateProgramWithSource",
        "clBuildProgram",
        "clCreateKernel",
        "clSetKernelArg",
        "clEnqueueNDRangeKernel",
        "clFinish",
    }
    cts_requirements = cts_readiness.get("requirements", [])
    requirement_by_category = {
        str(req.get("category")): req
        for req in cts_requirements
        if isinstance(req, dict) and req.get("category")
    }

    subset_done = (
        status_is_pass(subset)
        and int(subset.get("positive_count", 0)) >= 9
        and int(subset.get("negative_count", 0)) >= 12
        and {"address_spaces_global_local_constant", "builtins_geometry", "launch_geometry_2d"} <= positive_names
        and {"reject_image_object", "reject_sampler_object", "reject_atomic_builtin"} <= negative_names
    )
    host_done = status_is_pass(host_shim) and required_core_apis <= host_apis and int(host_shim.get("api_call_count", 0)) >= 40
    event_partial = status_is_pass(event_waitlist) and all_checks_pass(event_waitlist)
    runtime_done = status_is_pass(runtime_metrics) and status_is_pass(coverage)

    ledger = [
        item(
            "executable_opencl_c_subset",
            "Executable OpenCL C subset",
            "done" if subset_done else "partial",
            "Current evidence compiles and rejects the local subset fixtures; this is only the repository-defined subset.",
            [evidence_ref(paths["subset"], subset, "positive/negative subset conformance-readiness fixtures")],
            "Extend one feature at a time from CTS-shaped fixtures while keeping unsupported features rejected.",
        ),
        item(
            "host_api_runtime_proxy_subset",
            "Host API runtime proxy subset",
            "done" if host_done else "partial",
            "The host API shim exercises a local object lifecycle and NDRange/buffer dispatch path, but it is a proxy surface.",
            [evidence_ref(paths["host_shim"], host_shim, "local host API shim trace")],
            "Keep growing API lifecycle/error-code coverage behind explicit non-ICD boundary text.",
        ),
        item(
            "runtime_kernel_dispatch_and_buffers",
            "Runtime kernel dispatch and buffer path",
            "done" if runtime_done else "partial",
            "Runtime commands, metrics, and functional acceptance coverage exist for the subset execution path.",
            [
                evidence_ref(paths["runtime_commands"], runtime_commands, "OpenCL subset runtime command trace"),
                evidence_ref(paths["runtime_metrics"], runtime_metrics, "runtime proxy metrics"),
                evidence_ref(paths["coverage"], coverage, "functional acceptance coverage, not structural closure"),
            ],
            "Add more dispatch, memory, and fault cases without redefining the main coverage gate.",
        ),
        item(
            "event_waitlist_and_profiling_proxy",
            "Event wait-list and profiling proxy",
            "partial" if event_partial else "blocked",
            "Wait-list DAG validation, profiling timestamps, and failure propagation are present, but callbacks and full queue properties are not complete.",
            [evidence_ref(paths["event_waitlist"], event_waitlist, "event wait-list/profiling proxy report")],
            "Add callback, event status query, multi-queue, and unsupported-property negative tests.",
        ),
        item(
            "icd_loader",
            "Khronos ICD loader integration",
            "blocked",
            "Current evidence explicitly says the stack is not a Khronos ICD loader integration.",
            [evidence_ref(paths["icd_contract"], icd_contract, "host API contract explicitly scoped as non-ICD")],
            "Introduce an executable mock vendor-library/ICD-loader fixture before claiming any ICD integration.",
            official_blocker="No Khronos ICD loader vendor-library integration is implemented.",
        ),
        item(
            "libopencl_abi",
            "libOpenCL ABI and stable host handles",
            "blocked",
            "The repository has a host API contract/proxy, not a stable libOpenCL ABI implementation.",
            [
                evidence_ref(paths["icd_contract"], icd_contract, "contract says not a stable public ABI"),
                evidence_ref(paths["event_waitlist"], event_waitlist, "scope says not libOpenCL"),
            ],
            "Define handle layout, ABI symbols, reference counting, and loader-facing entry points in an executable shim test.",
            official_blocker="No stable libOpenCL ABI, vendor ICD library, or loader-facing symbol surface is present.",
        ),
        item(
            "kernel_driver",
            "Production Linux kernel/DRM driver",
            "blocked",
            "Driver submission and OS runtime artifacts are readiness/proxy evidence, not a production kernel driver.",
            [
                evidence_ref(paths["driver_os"], driver_os, "driver/OS conformance-readiness gate"),
                evidence_ref(paths["driver_submission"], evidence["driver_submission"], "driver submission proxy report"),
            ],
            "Promote DRM-like queue, BO, ioctl, sync, scheduler, and hang-recovery fixtures before kernel implementation.",
            official_blocker="No production kernel DRM driver, GEM/BO model, ioctl ABI, scheduler, or hang recovery.",
        ),
        item(
            "khronos_cts",
            "Khronos CTS execution and official conformance",
            "blocked",
            "CTS-oriented readiness and RTL cross-check evidence exists, but the scope explicitly excludes Khronos CTS pass evidence.",
            [
                evidence_ref(paths["cts_readiness"], cts_readiness, "Phase-9 CTS-oriented readiness report"),
                evidence_ref(paths["cts_matrix"], cts_matrix, "CTS readiness matrix"),
                evidence_ref(paths["rtl_cts_cross_check"], rtl_cts, "host-to-RTL CTS-readiness cross-check"),
            ],
            "Add an actual OpenCL-CTS harness lane only after ICD/libOpenCL/runtime/driver prerequisites exist.",
            official_blocker="No Khronos CTS run, adopter submission, or official conformance package is present.",
        ),
        item(
            "images",
            "Images",
            "blocked",
            "Negative tests currently prove image objects are rejected; device-info/readiness materials do not claim image support.",
            [
                evidence_ref(paths["subset"], subset, "reject_image_object passes"),
                evidence_ref(paths["device_info"], device_info, "device information table"),
            ],
            "Keep image negative tests green until image object storage, formats, addressing, and read/write builtins exist.",
            official_blocker="image*_t storage, formats, addressing, filtering, and CTS image groups are absent.",
        ),
        item(
            "samplers",
            "Samplers",
            "blocked",
            "Negative tests currently prove sampler objects are rejected.",
            [evidence_ref(paths["subset"], subset, "reject_sampler_object passes")],
            "Add sampler_t semantics only after image memory object support exists.",
            official_blocker="sampler_t addressing/filtering semantics are absent.",
        ),
        item(
            "svm",
            "Shared Virtual Memory",
            "blocked",
            "Device-info evidence is allowed to report SVM capability queries, but no SVM allocation, sharing, or coherence path is implemented.",
            [evidence_ref(paths["device_info"], device_info, "CL_DEVICE_SVM_CAPABILITIES evidence boundary")],
            "Add explicit SVM allocation/map/coherence negative tests, then implement only behind a feature flag.",
            official_blocker="SVM allocation, host/device shared pointers, and coherence semantics are absent.",
        ),
        item(
            "atomics",
            "Atomics and OpenCL memory model",
            "blocked",
            "The local compiler intentionally rejects atomic builtins; memory-order/scope semantics are not modeled.",
            [
                evidence_ref(paths["subset"], subset, "reject_atomic_builtin passes"),
                evidence_ref(paths["device_info"], device_info, "atomic capability query boundary"),
            ],
            "Add feature-flagged local/global atomic micro-tests before exposing atomic capability bits.",
            official_blocker="OpenCL atomic operations, memory orders, scopes, and CTS atomics groups are absent.",
        ),
        item(
            "out_of_order_queues",
            "Out-of-order queues",
            "blocked",
            "The event DAG proxy validates wait lists, but the ICD contract/readiness evidence says out-of-order queue properties are absent.",
            [
                evidence_ref(paths["event_waitlist"], event_waitlist, "wait-list DAG proxy"),
                evidence_ref(paths["cts_readiness"], cts_readiness, "events/fences/queue readiness item"),
            ],
            "Add a queue-property negative test that rejects out-of-order queues, then implement scheduling semantics if enabled.",
            official_blocker="CL_QUEUE_OUT_OF_ORDER_EXEC_MODE_ENABLE scheduling and ordering semantics are absent.",
        ),
    ]

    blocked = [entry for entry in ledger if entry["classification"] == "blocked"]
    partial = [entry for entry in ledger if entry["classification"] == "partial"]
    done = [entry for entry in ledger if entry["classification"] == "done"]

    checks = [
        {
            "name": "required_gap_items_present",
            "pass": {
                "icd_loader",
                "libopencl_abi",
                "kernel_driver",
                "khronos_cts",
                "images",
                "samplers",
                "svm",
                "atomics",
                "out_of_order_queues",
            }
            <= {entry["id"] for entry in ledger},
        },
        {"name": "subset_evidence_read", "pass": status_is_pass(subset) and subset_done},
        {"name": "host_api_evidence_read", "pass": host_done},
        {"name": "event_proxy_not_overpromoted", "pass": any(entry["id"] == "event_waitlist_and_profiling_proxy" and entry["classification"] == "partial" for entry in ledger)},
        {"name": "official_surfaces_remain_blocked", "pass": all(entry["classification"] == "blocked" for entry in ledger if entry["id"] in {"icd_loader", "libopencl_abi", "kernel_driver", "khronos_cts"})},
        {"name": "unsupported_features_remain_blocked", "pass": all(entry["classification"] == "blocked" for entry in ledger if entry["id"] in {"images", "samplers", "svm", "atomics", "out_of_order_queues"})},
        {"name": "claim_boundary_declared", "pass": all(token in CLEAN_ROOM_SCOPE for token in ("not an official OpenCL conformance claim", "not Khronos CTS pass evidence", "not a Khronos ICD loader integration", "not a libOpenCL ABI implementation"))},
        {"name": "phase9_categories_read", "pass": {"icd_runtime_integration", "driver_os_integration", "events_fences_queue_semantics"} <= set(requirement_by_category)},
    ]

    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "status": "pass" if all(check["pass"] for check in checks) else "fail",
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "classification_vocabulary": {
            "done": "Executable subset behavior is demonstrated by current local evidence, with explicit non-official boundaries.",
            "partial": "Some executable proxy/readiness evidence exists, but product or official semantics are incomplete.",
            "blocked": "Current evidence is absent or explicitly negative; claiming support would overstate the stack.",
        },
        "summary": {
            "done": len(done),
            "partial": len(partial),
            "blocked": len(blocked),
            "ledger_items": len(ledger),
            "official_opencl_conformance": False,
            "khronos_cts_pass": False,
            "product_icd_loader": False,
            "libopencl_abi": False,
            "production_kernel_driver": False,
        },
        "evidence_inputs": {name: str(path) for name, path in paths.items()},
        "ledger": ledger,
        "checks": checks,
    }


def write_doc(path: Path, report: Mapping[str, Any], json_path: Path) -> None:
    by_status: dict[str, list[Mapping[str, Any]]] = {"done": [], "partial": [], "blocked": []}
    for entry in report["ledger"]:
        by_status[str(entry["classification"])].append(entry)

    lines = [
        "# OpenCL Product Gap Closure Ledger",
        "",
        "This ledger is generated from current repository evidence. It is a gap-closure classification, not a product-complete or official conformance report.",
        "",
        "## Claim Boundary",
        "",
        str(report["clean_room_scope"]),
        "",
        "## Summary",
        "",
        f"- Generated JSON: `{json_path}`",
        f"- Ledger status: `{report['status']}`",
        f"- Done executable subset items: `{report['summary']['done']}`",
        f"- Partial items: `{report['summary']['partial']}`",
        f"- Blocked items: `{report['summary']['blocked']}`",
        "- Official OpenCL conformance: `false`",
        "- Khronos CTS pass: `false`",
        "- Product ICD loader/libOpenCL/kernel driver: `false`",
        "",
        "## Executable Subset Done",
        "",
    ]
    for entry in by_status["done"]:
        lines.extend(format_entry(entry))
    lines.extend(["## Partial", ""])
    for entry in by_status["partial"]:
        lines.extend(format_entry(entry))
    lines.extend(["## Blocked", ""])
    for entry in by_status["blocked"]:
        lines.extend(format_entry(entry))
    lines.extend(["## Evidence Inputs", ""])
    for name, input_path in report["evidence_inputs"].items():
        lines.append(f"- `{name}`: `{input_path}`")
    lines.append("")
    write_text(path, "\n".join(lines).rstrip() + "\n")


def format_entry(entry: Mapping[str, Any]) -> list[str]:
    lines = [
        f"### {entry['title']}",
        f"- ID: `{entry['id']}`",
        f"- Classification: `{entry['classification']}`",
        f"- Rationale: {entry['rationale']}",
    ]
    if entry.get("official_blocker"):
        lines.append(f"- Official blocker: {entry['official_blocker']}")
    lines.append(f"- Next executable step: {entry['next_executable_step']}")
    lines.append("- Evidence:")
    for ref in entry.get("evidence", []):
        lines.append(f"  - `{ref['path']}`: {ref['note']}")
    lines.append("")
    return lines


def verify_report(report: Mapping[str, Any]) -> None:
    errors: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    require(report.get("schema") == SCHEMA, "schema mismatch")
    require(report.get("status") == "pass", "ledger status is not pass")
    ledger = report.get("ledger", [])
    require(isinstance(ledger, list) and len(ledger) >= 13, "ledger depth too shallow")
    by_id = {entry.get("id"): entry for entry in ledger if isinstance(entry, dict)}
    for gap_id in (
        "icd_loader",
        "libopencl_abi",
        "kernel_driver",
        "khronos_cts",
        "images",
        "samplers",
        "svm",
        "atomics",
        "out_of_order_queues",
    ):
        require(gap_id in by_id, f"missing required gap: {gap_id}")
        require(by_id.get(gap_id, {}).get("classification") == "blocked", f"required gap not blocked: {gap_id}")
    require(by_id.get("event_waitlist_and_profiling_proxy", {}).get("classification") == "partial", "event proxy was overpromoted")
    require(report.get("summary", {}).get("official_opencl_conformance") is False, "official conformance overclaimed")
    require(report.get("summary", {}).get("khronos_cts_pass") is False, "CTS pass overclaimed")
    require(report.get("summary", {}).get("product_icd_loader") is False, "ICD loader overclaimed")
    require(report.get("summary", {}).get("libopencl_abi") is False, "libOpenCL ABI overclaimed")
    require(report.get("summary", {}).get("production_kernel_driver") is False, "kernel driver overclaimed")
    scope = str(report.get("clean_room_scope", ""))
    for token in ("not an official OpenCL conformance claim", "not Khronos CTS pass evidence", "not a Khronos ICD loader integration", "not a libOpenCL ABI implementation", "not a production Linux kernel/DRM driver"):
        require(token in scope, f"scope token missing: {token}")
    for entry in ledger:
        if isinstance(entry, dict):
            require(entry.get("evidence"), f"missing evidence refs for {entry.get('id')}")
            require(entry.get("next_executable_step"), f"missing next executable step for {entry.get('id')}")

    if errors:
        for error in errors:
            print(f"[FAIL] {error}")
        raise SystemExit(1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate OpenCL product gap-closure ledger.")
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    if args.verify_only:
        report = load_json(args.output, required=True)
    else:
        report = classify(args.artifact_root)
        write_json(args.output, report)
        write_doc(args.doc, report, args.output)

    verify_report(report)
    print(
        "celviz_gpgpu_opencl_product_gap_closure: "
        f"{report['status']} done={report['summary']['done']} "
        f"partial={report['summary']['partial']} blocked={report['summary']['blocked']} "
        f"output={args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
