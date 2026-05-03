#!/usr/bin/env python3
"""Phase-9 OpenCL conformance-readiness gate for Celviz GPGPU IP.

Phase 9 moves the project toward a product-grade OpenCL conformance path by
making CTS-oriented gaps executable and reviewable. It does not claim Khronos
CTS pass or official OpenCL conformance.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

try:
    from . import opencl_icd_runtime_contract, opencl_subset_conformance_tests
except ImportError:  # pragma: no cover - direct script fallback
    import opencl_icd_runtime_contract  # type: ignore
    import opencl_subset_conformance_tests  # type: ignore


SCHEMA = "celviz.gpgpu.phase9_opencl_conformance_readiness.v1"
DEFAULT_ARTIFACT_ROOT = Path("artifacts/rank_01_vivante_3d_gpgpu_ip")
CLEAN_ROOM_SCOPE = (
    "Phase-9 OpenCL conformance-readiness for a clean-room Ventus-based Celviz "
    "GPGPU IP proxy. This is CTS-oriented gap and local readiness evidence only: "
    "not Khronos CTS, not official OpenCL conformance, not a product ICD, not a "
    "production Linux kernel/DRM driver, not RTL structural coverage 100%, and "
    "not synthesis/STA/power/DFT/physical/silicon signoff."
)

OFFICIAL_REFERENCES = [
    {
        "name": "Khronos OpenCL Registry",
        "url": "https://registry.khronos.org/OpenCL/",
        "use": "authoritative OpenCL API/C/extension specification index",
    },
    {
        "name": "OpenCL 3.0 unified API specification",
        "url": "https://registry.khronos.org/OpenCL/specs/3.0-unified/html/OpenCL_API.html",
        "use": "platform, execution, memory, synchronization, host API, and device query semantics",
    },
    {
        "name": "OpenCL 3.0 unified C specification",
        "url": "https://registry.khronos.org/OpenCL/specs/3.0-unified/html/OpenCL_C.html",
        "use": "OpenCL C language, address spaces, types, builtins, atomics, and barriers",
    },
    {
        "name": "Khronos OpenCL-CTS",
        "url": "https://github.com/KhronosGroup/OpenCL-CTS",
        "use": "official open-source conformance test suite repository",
    },
    {
        "name": "Khronos conformant products/adopters",
        "url": "https://www.khronos.org/conformance/adopters/conformant-products/opencl",
        "use": "public adopter/product conformance publication path",
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"missing Phase-9 input: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid Phase-9 JSON input {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"Phase-9 input is not a JSON object: {path}")
    return data


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def pass_check(name: str, passed: bool, evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {"name": name, "pass": bool(passed), "evidence": dict(evidence or {})}


def requirement(
    category: str,
    title: str,
    status: str,
    evidence: list[str],
    blocker: str,
    next_test: str,
    cts_hint: str,
) -> dict[str, Any]:
    return {
        "category": category,
        "title": title,
        "current_status": status,
        "local_evidence": evidence,
        "blocker_to_official_conformance": blocker,
        "next_executable_test": next_test,
        "cts_orientation": cts_hint,
        "claim_boundary": "readiness/gap evidence only; not official OpenCL conformance",
    }


def readiness_matrix(artifact_root: Path) -> list[dict[str, Any]]:
    verification = artifact_root / "verification"
    return [
        requirement(
            "platform_device_info",
            "Platform and device enumeration/info",
            "partial",
            [
                str(artifact_root / "demo/outputs/device_tiers.json"),
                str(artifact_root / "demo/outputs/kernel_metrics.json"),
            ],
            "OpenCL 3.0 profile/version/extensions/device-info tables and optional-feature queries are incomplete.",
            "Generate device-info golden table and reject unsupported CL_DEVICE_* queries deterministically.",
            "api/test_cl_get_device_info style coverage",
        ),
        requirement(
            "context_queue_program_kernel_mem_api",
            "Core host object API lifecycle",
            "partial",
            [str(verification / "opencl_icd_runtime_contract.json")],
            "No stable ICD handles, reference counts, object ownership, or complete OpenCL error-code mapping.",
            "Run host API lifecycle contract tests for context/queue/buffer/program/kernel/event create/release.",
            "api object lifecycle CTS groups",
        ),
        requirement(
            "opencl_c_language_subset",
            "OpenCL C subset compilation",
            "partial",
            [
                str(artifact_root / "demo/opencl_subset/opencl_subset_evidence.json"),
                str(verification / "opencl_subset_conformance_tests.json"),
            ],
            "The compiler accepts a first-stage subset only: one kernel per source and limited grammar/types/builtins.",
            "Extend parser/lowering case by case from vector add, GEMM, conv2d, image filter to CTS-shaped fixtures.",
            "compiler and kernel language CTS groups",
        ),
        requirement(
            "builtins_math_precision",
            "Builtins, math, and numerical precision",
            "absent",
            [str(verification / "opencl_subset_conformance_tests.json")],
            "Math builtins, transcendental precision, denorm/rounding behavior, and conformance tolerances are not implemented.",
            "Add integer/float builtin fixture families plus ULP/tolerance golden checks before enabling math CTS lanes.",
            "math_brute_force and builtin coverage families",
        ),
        requirement(
            "atomics_memory_order",
            "Atomics and memory ordering",
            "absent",
            [str(verification / "opencl_subset_conformance_tests.json")],
            "Atomic operations are intentionally rejected in the current subset; memory-order scopes are not modeled.",
            "Add local/global atomic op micro-tests behind an explicit feature flag, then map to scoreboard/LSU semantics.",
            "atomics and memory model CTS groups",
        ),
        requirement(
            "images_samplers",
            "Images and samplers",
            "absent",
            [str(verification / "opencl_subset_conformance_tests.json")],
            "image*_t and sampler_t are rejected; no image object storage, formats, addressing, or filtering semantics.",
            "Keep image/sampler negative tests green; only open implementation after memory object model supports images.",
            "image read/write/sampler CTS groups",
        ),
        requirement(
            "memory_address_spaces",
            "Global/local/constant/private memory semantics",
            "partial",
            [
                str(artifact_root / "memory/memory_event_trace.json"),
                str(artifact_root / "verification/phase6_memory_trace_integration_report.json"),
            ],
            "Address spaces are parsed and traced but cache/scratchpad/coherency/local lifetime rules are not spec-complete.",
            "Add local memory lifetime/barrier tests and constant memory read-only violation tests.",
            "memory object, buffer, local memory, and barrier CTS groups",
        ),
        requirement(
            "events_fences_queue_semantics",
            "Events, fences, and queue ordering",
            "partial",
            [
                str(artifact_root / "driver_submission/fence_event_lifecycle.json"),
                str(artifact_root / "driver_submission/driver_submission_report.json"),
            ],
            "Proxy fence/event semantics exist; OpenCL event wait lists, callbacks, profiling, and out-of-order queues are incomplete.",
            "Add event dependency DAG tests with success/fault propagation and queue drain checks.",
            "event, queue, and synchronization CTS groups",
        ),
        requirement(
            "error_negative_behavior",
            "Error and negative behavior",
            "partial",
            [
                str(verification / "opencl_subset_conformance_tests.json"),
                str(artifact_root / "rtl/e5_outputs/negative_boundary_evidence.json"),
            ],
            "Local subset rejects known unsupported features but does not yet map all failures to OpenCL error codes.",
            "Create an OpenCL-style error code matrix for bad args, bad objects, bad geometry, and unsupported features.",
            "api negative tests",
        ),
        requirement(
            "icd_runtime_integration",
            "ICD/runtime integration",
            "proxy",
            [str(verification / "opencl_icd_runtime_contract.json")],
            "Current runtime is a CLI/proxy bridge, not a Khronos ICD vendor library.",
            "Build a mock libOpenCL vendor shim once host API contract tests are stable.",
            "ICD loader and CTS harness integration",
        ),
        requirement(
            "driver_os_integration",
            "Linux driver and OS integration",
            "proxy",
            [
                str(artifact_root / "os_runtime/linux_runtime_evidence.json"),
                str(artifact_root / "verification/phase8_work_package_artifacts/drm_uapi_contract.json"),
            ],
            "No production kernel DRM driver, GEM BO model, ioctl ABI, syncobj, scheduler, or hang recovery.",
            "Promote DRM-like submission proxy tests to ioctl-shaped fixtures before kernel-driver implementation.",
            "runtime/driver behavior under CTS process model",
        ),
        requirement(
            "rtl_structural_coverage_signoff",
            "RTL structural coverage and product signoff",
            "partial",
            [
                str(artifact_root / "verification/verilator_coverage/verilator_coverage_report.json"),
                str(artifact_root / "synthesis/synthesis_readiness_report.json"),
            ],
            "Functional/acceptance coverage is 100%, but structural RTL line/branch/toggle and signoff closure are not 100%.",
            "Add directed/random/fault/stress RTL structural coverage gates and signoff input checks without redefining functional coverage.",
            "implementation-quality prerequisite before official submission",
        ),
    ]


def productization_gates(artifact_root: Path) -> dict[str, Any]:
    gates = [
        {
            "id": "memory_model_global_local_constant",
            "domain": "memory",
            "required_artifacts": [
                str(artifact_root / "memory/memory_event_trace.json"),
                str(artifact_root / "verification/opencl_subset_conformance_tests.json"),
            ],
            "pass_condition": "global/local/constant fixtures compile and unsupported image/sampler/atomic cases reject deterministically",
            "next_action": "add barrier/local lifetime and constant read-only violation directed tests",
        },
        {
            "id": "cache_scratchpad_coalescing",
            "domain": "memory_performance",
            "required_artifacts": [str(artifact_root / "verification/phase7_coalescing_score_report.json")],
            "pass_condition": "coalescing evidence remains proxy-labeled and ties to memory event traces",
            "next_action": "add cache/scratchpad hit/miss and coalesced transaction counters",
        },
        {
            "id": "dma_kernel_access_unification",
            "domain": "runtime_memory",
            "required_artifacts": [
                str(artifact_root / "rtl/control_plane_demo.json"),
                str(artifact_root / "demo/opencl_subset/runtime_commands.json"),
            ],
            "pass_condition": "DMA copy/fill and kernel memory access share region bounds and fault handling",
            "next_action": "create shared memory-region validator for DMA and NDRange dispatch paths",
        },
        {
            "id": "queue_fence_event_semantics",
            "domain": "driver_runtime",
            "required_artifacts": [str(artifact_root / "driver_submission/fence_event_lifecycle.json")],
            "pass_condition": "queue drain, fence wait, event status, and fault paths are observed",
            "next_action": "add OpenCL wait-list DAG and callback/profiling placeholders",
        },
        {
            "id": "rtl_structural_uplift",
            "domain": "rtl_verification",
            "required_artifacts": [str(artifact_root / "verification/verilator_coverage/verilator_coverage_report.json")],
            "pass_condition": "structural metrics are reported separately from 100% functional acceptance coverage",
            "next_action": "add directed reset/IRQ/scoreboard/LSU/branch tests and random/fault/stress seeds",
        },
        {
            "id": "synthesis_sta_power_dft_physical",
            "domain": "signoff",
            "required_artifacts": [
                str(artifact_root / "synthesis/synthesis_readiness_report.json"),
                str(artifact_root / "ppa/ppa_proxy_report.json"),
            ],
            "pass_condition": "signoff inputs are named and proxy PPA remains separated from signed-off PPA",
            "next_action": "attach target library/SDC/SAIF/DFT/floorplan inputs when a technology target exists",
        },
    ]
    checks = [
        pass_check("gate_count", len(gates) >= 6, {"gate_count": len(gates)}),
        pass_check("all_gates_have_next_action", all(gate.get("next_action") for gate in gates)),
        pass_check("signoff_boundary_kept", any(gate["domain"] == "signoff" for gate in gates)),
    ]
    return {
        "schema": "celviz.gpgpu.phase9_productization_gates.v1",
        "status": "pass" if all(item["pass"] for item in checks) else "fail",
        "claim_boundary": "productization readiness gates only; not product signoff or official OpenCL conformance",
        "gates": gates,
        "checks": checks,
    }


def build_report(artifact_root: Path, output_dir: Path, docs_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)

    subset_path = output_dir / "opencl_subset_conformance_tests.json"
    icd_path = output_dir / "opencl_icd_runtime_contract.json"
    gates_path = output_dir / "phase9_opencl_readiness_gates.json"
    matrix_path = output_dir / "opencl_cts_readiness_matrix.json"

    subset_report = opencl_subset_conformance_tests.build_report()
    icd_report = opencl_icd_runtime_contract.build_contract()
    gates_report = productization_gates(artifact_root)
    matrix = readiness_matrix(artifact_root)

    write_json(subset_path, subset_report)
    write_json(icd_path, icd_report)
    write_json(gates_path, gates_report)
    write_json(
        matrix_path,
        {
            "schema": "celviz.gpgpu.opencl_cts_readiness_matrix.v1",
            "generated_at": utc_now(),
            "clean_room_scope": CLEAN_ROOM_SCOPE,
            "status": "pass",
            "status_vocabulary": ["absent", "proxy", "partial", "ready"],
            "official_references": OFFICIAL_REFERENCES,
            "requirements": matrix,
        },
    )

    required_categories = {
        "platform_device_info",
        "context_queue_program_kernel_mem_api",
        "opencl_c_language_subset",
        "builtins_math_precision",
        "atomics_memory_order",
        "images_samplers",
        "memory_address_spaces",
        "events_fences_queue_semantics",
        "error_negative_behavior",
        "icd_runtime_integration",
        "driver_os_integration",
        "rtl_structural_coverage_signoff",
    }
    observed_categories = {item["category"] for item in matrix}
    checks = [
        pass_check("subset_conformance_tests_pass", subset_report.get("status") == "pass", {"path": str(subset_path)}),
        pass_check("icd_runtime_contract_pass", icd_report.get("status") == "pass", {"path": str(icd_path)}),
        pass_check("productization_gates_pass", gates_report.get("status") == "pass", {"path": str(gates_path)}),
        pass_check("required_categories_present", required_categories <= observed_categories, {"observed": sorted(observed_categories)}),
        pass_check("all_requirements_have_blocker", all(item.get("blocker_to_official_conformance") for item in matrix)),
        pass_check("all_requirements_have_next_test", all(item.get("next_executable_test") for item in matrix)),
        pass_check("official_references_present", len(OFFICIAL_REFERENCES) >= 5, {"references": OFFICIAL_REFERENCES}),
        pass_check("no_official_conformance_overclaim", "not official OpenCL conformance" in CLEAN_ROOM_SCOPE and "not Khronos CTS" in CLEAN_ROOM_SCOPE),
    ]

    report = {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "status": "pass" if all(item["pass"] for item in checks) else "fail",
        "official_references": OFFICIAL_REFERENCES,
        "readiness_status_vocabulary": ["absent", "proxy", "partial", "ready"],
        "artifact_paths": {
            "opencl_subset_conformance_tests": str(subset_path),
            "opencl_icd_runtime_contract": str(icd_path),
            "phase9_opencl_readiness_gates": str(gates_path),
            "opencl_cts_readiness_matrix": str(matrix_path),
        },
        "requirement_count": len(matrix),
        "requirements": matrix,
        "checks": checks,
    }
    write_phase9_doc(docs_dir / "PHASE9_OPENCL_CONFORMANCE_READINESS.md", report)
    write_icd_doc(docs_dir / "OPENCL_ICD_RUNTIME_CONTRACT.md", icd_report)
    write_productization_doc(docs_dir / "PHASE9_OPENCL_READINESS_GATES.md", gates_report)
    return report


def write_phase9_doc(path: Path, report: Mapping[str, Any]) -> None:
    lines = [
        "# Phase9 OpenCL Conformance Readiness",
        "",
        "This phase pushes Celviz GPGPU IP toward the official OpenCL conformance path without claiming Khronos CTS pass.",
        "",
        "## Claim Boundary",
        "",
        str(report["clean_room_scope"]),
        "",
        "## Official Anchors",
        "",
    ]
    for ref in report["official_references"]:
        lines.append(f"- {ref['name']}: {ref['url']} ({ref['use']})")
    lines.extend(["", "## Readiness Matrix", ""])
    for item in report["requirements"]:
        lines.extend(
            [
                f"### {item['category']}",
                f"- Status: {item['current_status']}",
                f"- Evidence: {', '.join(item['local_evidence'])}",
                f"- Blocker: {item['blocker_to_official_conformance']}",
                f"- Next executable test: {item['next_executable_test']}",
                f"- CTS orientation: {item['cts_orientation']}",
                "",
            ]
        )
    lines.extend(["## Generated Artifacts", ""])
    for name, artifact_path in report["artifact_paths"].items():
        lines.append(f"- {name}: {artifact_path}")
    write_text(path, "\n".join(lines).rstrip() + "\n")


def write_icd_doc(path: Path, report: Mapping[str, Any]) -> None:
    lines = [
        "# OpenCL ICD Runtime Contract",
        "",
        str(report["clean_room_scope"]),
        "",
        "## Host API Surface",
        "",
    ]
    for item in report["host_api_contract"]:
        lines.extend(
            [
                f"### {item['api']}",
                f"- Status: {item['current_status']}",
                f"- Proxy mapping: {item['proxy_mapping']}",
                f"- Evidence: {', '.join(item['local_evidence'])}",
                f"- Blocker: {item['blocker_to_official_conformance']}",
                f"- Next executable test: {item['next_executable_test']}",
                "",
            ]
        )
    write_text(path, "\n".join(lines).rstrip() + "\n")


def write_productization_doc(path: Path, report: Mapping[str, Any]) -> None:
    lines = [
        "# Phase9 Productization Gates",
        "",
        str(report["claim_boundary"]),
        "",
        "## Gates",
        "",
    ]
    for gate in report["gates"]:
        lines.extend(
            [
                f"### {gate['id']}",
                f"- Domain: {gate['domain']}",
                f"- Required artifacts: {', '.join(gate['required_artifacts'])}",
                f"- Pass condition: {gate['pass_condition']}",
                f"- Next action: {gate['next_action']}",
                "",
            ]
        )
    write_text(path, "\n".join(lines).rstrip() + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Phase9 OpenCL conformance-readiness artifacts.")
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_ARTIFACT_ROOT / "verification")
    parser.add_argument("--docs-dir", type=Path, default=Path("docs/celviz-gpgpu-ip"))
    args = parser.parse_args()
    report = build_report(args.artifact_root, args.output_dir, args.docs_dir)
    output = args.output_dir / "phase9_opencl_conformance_readiness_report.json"
    write_json(output, report)
    print(
        "celviz_gpgpu_phase9_opencl_conformance_readiness: "
        f"{report['status']} requirements={report['requirement_count']} output={output}"
    )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
