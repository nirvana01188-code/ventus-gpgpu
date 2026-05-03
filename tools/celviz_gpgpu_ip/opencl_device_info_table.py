#!/usr/bin/env python3
"""Generate a clean-room OpenCL CL_DEVICE_* device-info readiness table.

This is a CTS-oriented device-info taxonomy and local proxy table. It is not a
Khronos CTS result, not an official OpenCL conformance claim, and not a product
ICD/device implementation.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "celviz.gpgpu.opencl_device_info_table.v1"
DEFAULT_ARTIFACT_ROOT = Path("artifacts/rank_01_vivante_3d_gpgpu_ip")
CLEAN_ROOM_SCOPE = (
    "OpenCL CL_DEVICE_* device-info readiness table for a clean-room Celviz "
    "GPGPU proxy. Values are explicit support taxonomy entries and local proxy "
    "evidence, not Khronos CTS results, not official OpenCL conformance, not a "
    "product ICD, not a Vivante-compatible OpenCL stack, and not a claim that "
    "the device passes clGetDeviceInfo CTS."
)

OFFICIAL_SOURCES = [
    {
        "name": "Khronos OpenCL 3.0 unified API specification",
        "url": "https://registry.khronos.org/OpenCL/specs/3.0-unified/html/OpenCL_API.html",
        "scope": "CL_DEVICE_* query semantics, device types, profiles, versions, extensions, limits, memory, image, atomic, and SVM fields",
    },
    {
        "name": "Khronos OpenCL CTS",
        "url": "https://github.com/KhronosGroup/OpenCL-CTS",
        "scope": "official open-source CTS repository; this report only prepares a device-info table and does not run CTS",
    },
    {
        "name": "Khronos OpenCL conformant products/adopters",
        "url": "https://www.khronos.org/conformance/adopters/conformant-products/opencl",
        "scope": "public conformance publication path; no Celviz product listing is claimed here",
    },
]

STATUS_VALUES = {
    "supported_proxy": "Local proxy evidence reports a deterministic value, but this is not an OpenCL conformance result.",
    "reported_not_claimed": "A conservative query value is defined to avoid overclaiming optional functionality.",
    "unsupported_optional": "The feature is optional or extension-scoped and is not advertised by the proxy.",
    "unsupported_required_gap": "The query is important for CTS/device-info readiness but lacks enough implementation evidence.",
    "not_applicable": "The query does not apply to the selected clean-room proxy scope.",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if isinstance(data, dict):
        return data
    return {}


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def as_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def best_device(device_tiers: Mapping[str, Any]) -> dict[str, Any]:
    devices = [item for item in device_tiers.get("devices", []) if isinstance(item, dict)]
    if not devices:
        return {}
    return max(devices, key=lambda item: as_int(item.get("shader_units_vec1")) + as_int(item.get("queue_count")) * 16)


def query(
    name: str,
    category: str,
    status: str,
    value: Any,
    value_source: str,
    cts_orientation: str,
    evidence_paths: list[str],
    rationale: str,
    required_for_readiness: bool = True,
) -> dict[str, Any]:
    return {
        "name": name,
        "category": category,
        "support_status": status,
        "reported_value": value,
        "value_source": value_source,
        "required_for_readiness": required_for_readiness,
        "cts_orientation": cts_orientation,
        "evidence_paths": evidence_paths,
        "rationale": rationale,
        "claim_boundary": "device-info readiness only; not official OpenCL conformance or CTS pass",
    }


def build_queries(artifact_root: Path) -> list[dict[str, Any]]:
    tiers_path = artifact_root / "demo/outputs/device_tiers.json"
    host_api_path = artifact_root / "verification/opencl_host_api_shim_report.json"
    icd_path = artifact_root / "verification/opencl_icd_runtime_contract.json"
    memory_path = artifact_root / "memory/summary.json"
    driver_path = artifact_root / "driver_submission/driver_submission_report.json"
    subset_path = artifact_root / "demo/opencl_subset/opencl_subset_evidence.json"
    tiers = load_json(tiers_path)
    device = best_device(tiers)
    shader_units = as_int(device.get("shader_units_vec1"), 0)
    queue_count = as_int(device.get("queue_count"), 0)
    address_bits = as_int(device.get("address_bits"), 32)
    fp32_ops = as_int(device.get("fp32_ops_per_cycle"), 0)
    fp16_ops = as_int(device.get("fp16_ops_per_cycle"), 0)
    max_compute_units = max(1, shader_units // 16) if shader_units else 1
    max_work_group_size = 256 if shader_units >= 128 else 64
    global_mem_size = 256 * 1024 * 1024 if address_bits <= 32 else 1024 * 1024 * 1024
    local_mem_size = 32 * 1024
    evidence_tiers = [str(tiers_path)]
    evidence_host = [str(host_api_path), str(icd_path)]
    evidence_memory = [str(memory_path), str(subset_path)]
    evidence_driver = [str(driver_path)]

    rows = [
        query("CL_DEVICE_TYPE", "profile_version", "supported_proxy", "CL_DEVICE_TYPE_GPU", "proxy device taxonomy", "device_info type query", evidence_tiers, "The target is modeled as a GPGPU proxy."),
        query("CL_DEVICE_VENDOR_ID", "profile_version", "reported_not_claimed", 0, "not assigned", "device_info vendor query", evidence_tiers, "No Khronos/vendor product identity is claimed."),
        query("CL_DEVICE_NAME", "profile_version", "supported_proxy", device.get("device_id", "celviz-gpgpu-proxy"), "device_tiers best proxy", "device_info string query", evidence_tiers, "Uses local clean-room proxy device id."),
        query("CL_DEVICE_VENDOR", "profile_version", "reported_not_claimed", "Celviz clean-room proxy", "claim boundary", "device_info string query", evidence_tiers, "Vendor string must not imply Khronos or proprietary Vivante compatibility."),
        query("CL_DEVICE_PROFILE", "profile_version", "reported_not_claimed", "not_claimed", "conformance boundary", "profile query", evidence_host, "FULL_PROFILE/EMBEDDED_PROFILE is not claimed until CTS and Adopter steps exist."),
        query("CL_DEVICE_VERSION", "profile_version", "reported_not_claimed", "OpenCL readiness taxonomy only", "conformance boundary", "version query", evidence_host, "No official OpenCL implementation version is advertised."),
        query("CL_DRIVER_VERSION", "profile_version", "reported_not_claimed", "celviz-proxy-not-product-driver", "conformance boundary", "driver version query", evidence_driver, "No production OpenCL driver is claimed."),
        query("CL_DEVICE_OPENCL_C_VERSION", "profile_version", "reported_not_claimed", "OpenCL C subset only", "subset evidence", "OpenCL C version query", [str(subset_path)], "The current parser/lowering covers an OpenCL-like subset only."),
        query("CL_DEVICE_EXTENSIONS", "extensions", "reported_not_claimed", "", "extension boundary", "extension string query", evidence_host, "No cl_khr_* extension is advertised by default."),
        query("CL_DEVICE_EXTENSIONS_WITH_VERSION", "extensions", "reported_not_claimed", [], "extension boundary", "extension version query", evidence_host, "No versioned extension list is claimed."),
        query("CL_DEVICE_NUMERIC_VERSION", "profile_version", "reported_not_claimed", 0, "conformance boundary", "numeric version query", evidence_host, "No OpenCL numeric version is advertised."),
        query("CL_DEVICE_MAX_COMPUTE_UNITS", "limits", "supported_proxy", max_compute_units, "device_tiers shader_units_vec1", "compute unit limit query", evidence_tiers, "Derived conservatively from local proxy shader unit tiers."),
        query("CL_DEVICE_MAX_WORK_ITEM_DIMENSIONS", "limits", "supported_proxy", 3, "subset NDRange model", "work item dimension query", [str(subset_path)], "Existing subset artifacts use 3D global/local size arrays."),
        query("CL_DEVICE_MAX_WORK_GROUP_SIZE", "limits", "supported_proxy", max_work_group_size, "proxy tier heuristic", "work group size query", evidence_tiers, "Proxy value chosen from current local-size evidence; not CTS proven."),
        query("CL_DEVICE_MAX_WORK_ITEM_SIZES", "limits", "supported_proxy", [max_work_group_size, max_work_group_size, 1], "proxy tier heuristic", "work item size query", evidence_tiers, "Matches current 2D/1D proxy workload shapes."),
        query("CL_DEVICE_MAX_CLOCK_FREQUENCY", "limits", "reported_not_claimed", 0, "no silicon timing evidence", "clock query", [str(artifact_root / "synthesis/synthesis_readiness_report.json")], "No signed-off frequency exists."),
        query("CL_DEVICE_ADDRESS_BITS", "limits", "supported_proxy", address_bits, "device_tiers address_bits", "address bits query", evidence_tiers, "Taken from local proxy tier metadata."),
        query("CL_DEVICE_MAX_PARAMETER_SIZE", "limits", "supported_proxy", 1024, "ABI proxy convention", "parameter size query", [str(subset_path)], "Sufficient for current kernel ABI fixtures only."),
        query("CL_DEVICE_MEM_BASE_ADDR_ALIGN", "memory", "supported_proxy", 128, "proxy alignment policy", "alignment query", evidence_memory, "Conservative alignment for buffer-style accesses."),
        query("CL_DEVICE_MIN_DATA_TYPE_ALIGN_SIZE", "memory", "supported_proxy", 128, "proxy alignment policy", "data alignment query", evidence_memory, "Conservative minimum data-type alignment policy."),
        query("CL_DEVICE_GLOBAL_MEM_SIZE", "memory", "supported_proxy", global_mem_size, "address_bits proxy size", "global memory size query", evidence_memory, "Proxy memory aperture, not measured product memory."),
        query("CL_DEVICE_MAX_MEM_ALLOC_SIZE", "memory", "supported_proxy", global_mem_size // 4, "global_mem_size policy", "max allocation query", evidence_memory, "Conservative quarter-aperture allocation limit."),
        query("CL_DEVICE_GLOBAL_MEM_CACHE_TYPE", "memory", "unsupported_required_gap", "CL_NONE", "cache model not complete", "cache query", evidence_memory, "Cache behavior is not CTS-ready."),
        query("CL_DEVICE_GLOBAL_MEM_CACHELINE_SIZE", "memory", "reported_not_claimed", 0, "cache model not complete", "cacheline query", evidence_memory, "No product cacheline is claimed."),
        query("CL_DEVICE_GLOBAL_MEM_CACHE_SIZE", "memory", "reported_not_claimed", 0, "cache model not complete", "cache size query", evidence_memory, "No product cache size is claimed."),
        query("CL_DEVICE_LOCAL_MEM_TYPE", "memory", "reported_not_claimed", "CL_LOCAL", "local memory readiness placeholder", "local memory query", evidence_memory, "Local memory needs CTS-shaped lifetime/barrier evidence."),
        query("CL_DEVICE_LOCAL_MEM_SIZE", "memory", "supported_proxy", local_mem_size, "proxy local memory policy", "local memory size query", evidence_memory, "Proxy size, not product signoff."),
        query("CL_DEVICE_ERROR_CORRECTION_SUPPORT", "memory", "reported_not_claimed", False, "no ECC evidence", "ECC query", evidence_memory, "ECC is not implemented or claimed."),
        query("CL_DEVICE_HOST_UNIFIED_MEMORY", "memory", "reported_not_claimed", False, "discrete proxy boundary", "unified memory query", evidence_memory, "Unified host memory is not claimed."),
        query("CL_DEVICE_IMAGE_SUPPORT", "images", "unsupported_optional", False, "image features not implemented", "image support query", [str(artifact_root / "verification/opencl_subset_conformance_tests.json")], "Current subset keeps image/sampler support unclaimed."),
        query("CL_DEVICE_MAX_READ_IMAGE_ARGS", "images", "unsupported_optional", 0, "image support false", "image arg limit query", [], "Image support is false."),
        query("CL_DEVICE_MAX_WRITE_IMAGE_ARGS", "images", "unsupported_optional", 0, "image support false", "image arg limit query", [], "Image support is false."),
        query("CL_DEVICE_IMAGE2D_MAX_WIDTH", "images", "unsupported_optional", 0, "image support false", "image dimension query", [], "Image support is false."),
        query("CL_DEVICE_IMAGE2D_MAX_HEIGHT", "images", "unsupported_optional", 0, "image support false", "image dimension query", [], "Image support is false."),
        query("CL_DEVICE_IMAGE3D_MAX_WIDTH", "images", "unsupported_optional", 0, "image support false", "image dimension query", [], "Image support is false."),
        query("CL_DEVICE_IMAGE3D_MAX_HEIGHT", "images", "unsupported_optional", 0, "image support false", "image dimension query", [], "Image support is false."),
        query("CL_DEVICE_IMAGE3D_MAX_DEPTH", "images", "unsupported_optional", 0, "image support false", "image dimension query", [], "Image support is false."),
        query("CL_DEVICE_MAX_SAMPLERS", "images", "unsupported_optional", 0, "sampler support false", "sampler query", [], "Sampler support is not claimed."),
        query("CL_DEVICE_SINGLE_FP_CONFIG", "fp_numeric", "supported_proxy", ["CL_FP_ROUND_TO_NEAREST"], "fp32 proxy evidence", evidence_tiers, "single fp config query", "Only a minimal FP32 proxy mode is recorded; full numeric conformance is not claimed."),
        query("CL_DEVICE_HALF_FP_CONFIG", "fp_numeric", "unsupported_optional", [], "fp16 is proxy-only", "half fp config query", evidence_tiers, "FP16 proxy throughput exists but OpenCL cl_khr_fp16/half semantics are not claimed."),
        query("CL_DEVICE_DOUBLE_FP_CONFIG", "fp_numeric", "unsupported_optional", [], "no fp64 evidence", "double fp config query", evidence_tiers, "FP64 is not implemented or claimed."),
        query("CL_DEVICE_ENDIAN_LITTLE", "fp_numeric", "supported_proxy", True, "RISC-V/proxy convention", "endianness query", evidence_tiers, "Little-endian proxy assumption."),
        query("CL_DEVICE_AVAILABLE", "execution", "supported_proxy", True, "local proxy available", "availability query", evidence_host, "The proxy is available for local evidence generation."),
        query("CL_DEVICE_COMPILER_AVAILABLE", "execution", "reported_not_claimed", False, "no OpenCL C compiler", "compiler availability query", [str(subset_path)], "The subset lowerer is not a product OpenCL compiler."),
        query("CL_DEVICE_LINKER_AVAILABLE", "execution", "reported_not_claimed", False, "no OpenCL linker", "linker availability query", [str(subset_path)], "No OpenCL linker is implemented."),
        query("CL_DEVICE_EXECUTION_CAPABILITIES", "execution", "supported_proxy", ["CL_EXEC_KERNEL"], "kernel execution proxy", "execution capabilities query", [str(artifact_root / "microop_execution/microop_execution_report.json")], "Kernel execution exists as clean-room micro-op proxy evidence."),
        query("CL_DEVICE_QUEUE_PROPERTIES", "queue", "supported_proxy", ["CL_QUEUE_PROFILING_ENABLE"], "driver submission proxy", "queue properties query", evidence_driver, "In-order/profiling-like proxy evidence only."),
        query("CL_DEVICE_QUEUE_ON_HOST_PROPERTIES", "queue", "supported_proxy", ["CL_QUEUE_PROFILING_ENABLE"], "driver submission proxy", "host queue properties query", evidence_driver, "Host queue properties are proxy-scoped."),
        query("CL_DEVICE_QUEUE_ON_DEVICE_PROPERTIES", "queue", "unsupported_optional", [], "device-side queues unsupported", "device queue properties query", evidence_driver, "OpenCL 2.x device-side enqueue is not claimed."),
        query("CL_DEVICE_MAX_ON_DEVICE_QUEUES", "queue", "unsupported_optional", 0, "device-side queues unsupported", "device queue limit query", evidence_driver, "Device-side queues are not claimed."),
        query("CL_DEVICE_MAX_ON_DEVICE_EVENTS", "queue", "unsupported_optional", 0, "device-side queues unsupported", "device event limit query", evidence_driver, "Device-side events are not claimed."),
        query("CL_DEVICE_ATOMIC_MEMORY_CAPABILITIES", "atomics_svm", "unsupported_optional", [], "atomics not modeled", "atomic capability query", [str(artifact_root / "verification/opencl_subset_conformance_tests.json")], "OpenCL atomics are not supported in the current subset."),
        query("CL_DEVICE_ATOMIC_FENCE_CAPABILITIES", "atomics_svm", "unsupported_optional", [], "atomics not modeled", "atomic fence query", [], "OpenCL atomic fences are not claimed."),
        query("CL_DEVICE_SVM_CAPABILITIES", "atomics_svm", "unsupported_optional", [], "SVM unsupported", "SVM capability query", [], "Shared virtual memory is not claimed."),
        query("CL_DEVICE_PREFERRED_PLATFORM_ATOMIC_ALIGNMENT", "atomics_svm", "reported_not_claimed", 0, "atomics unsupported", "atomic alignment query", [], "Atomics are unsupported."),
        query("CL_DEVICE_PREFERRED_GLOBAL_ATOMIC_ALIGNMENT", "atomics_svm", "reported_not_claimed", 0, "atomics unsupported", "atomic alignment query", [], "Atomics are unsupported."),
        query("CL_DEVICE_PREFERRED_LOCAL_ATOMIC_ALIGNMENT", "atomics_svm", "reported_not_claimed", 0, "atomics unsupported", "atomic alignment query", [], "Atomics are unsupported."),
    ]
    return rows


def summarize(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    by_category: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for row in rows:
        by_category[str(row["category"])] = by_category.get(str(row["category"]), 0) + 1
        by_status[str(row["support_status"])] = by_status.get(str(row["support_status"]), 0) + 1
    return {
        "query_count": len(rows),
        "categories": by_category,
        "support_status": by_status,
        "overclaim_safe": True,
    }


def build_report(artifact_root: Path) -> dict[str, Any]:
    rows = build_queries(artifact_root)
    required_categories = {
        "profile_version",
        "extensions",
        "limits",
        "memory",
        "images",
        "fp_numeric",
        "execution",
        "queue",
        "atomics_svm",
    }
    observed_categories = {str(row["category"]) for row in rows}
    observed_status = {str(row["support_status"]) for row in rows}
    checks = [
        {
            "name": "minimum_device_info_query_count",
            "pass": len(rows) >= 50,
            "evidence": {"query_count": len(rows)},
        },
        {
            "name": "required_categories_present",
            "pass": required_categories <= observed_categories,
            "evidence": {"observed": sorted(observed_categories)},
        },
        {
            "name": "status_vocabulary_valid",
            "pass": observed_status <= set(STATUS_VALUES),
            "evidence": {"observed": sorted(observed_status)},
        },
        {
            "name": "no_conformance_overclaim",
            "pass": "not official OpenCL conformance" in CLEAN_ROOM_SCOPE and "not a claim" in CLEAN_ROOM_SCOPE,
            "evidence": {"clean_room_scope": CLEAN_ROOM_SCOPE},
        },
        {
            "name": "all_rows_have_cts_orientation",
            "pass": all(row.get("cts_orientation") for row in rows),
        },
        {
            "name": "unsupported_optional_not_advertised",
            "pass": all(row.get("reported_value") in (False, 0, [], "") for row in rows if row.get("support_status") == "unsupported_optional"),
        },
    ]
    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "status": "pass" if all(item["pass"] for item in checks) else "fail",
        "official_sources": OFFICIAL_SOURCES,
        "status_vocabulary": STATUS_VALUES,
        "artifact_root": str(artifact_root),
        "summary": summarize(rows),
        "queries": rows,
        "checks": checks,
    }


def write_markdown(path: Path, report: Mapping[str, Any]) -> None:
    lines = [
        "# Phase 9 OpenCL Device Info Table Gate",
        "",
        "Status: clean-room `CL_DEVICE_*` device-info readiness table. This is",
        "close to the CTS device-info direction, but it is not Khronos CTS output,",
        "not official OpenCL conformance, and not a product OpenCL driver claim.",
        "",
        "## Claim Boundary",
        "",
        str(report["clean_room_scope"]),
        "",
        "## Inputs and Outputs",
        "",
        "- Input proxy evidence: `artifacts/rank_01_vivante_3d_gpgpu_ip/demo/outputs/device_tiers.json`",
        "- Input host/runtime evidence: `artifacts/rank_01_vivante_3d_gpgpu_ip/verification/opencl_host_api_shim_report.json`",
        "- Output JSON: `artifacts/rank_01_vivante_3d_gpgpu_ip/opencl_conformance/opencl_device_info_table.json`",
        "",
        "## Status Vocabulary",
        "",
    ]
    for key, value in report["status_vocabulary"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Query Categories",
            "",
            "| Category | Count |",
            "| --- | ---: |",
        ]
    )
    for category, count in sorted(report["summary"]["categories"].items()):
        lines.append(f"| `{category}` | {count} |")
    lines.extend(
        [
            "",
            "## Device Info Rows",
            "",
            "| CL_DEVICE query | Category | Status | Reported value | Boundary |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in report["queries"]:
        value = json.dumps(row["reported_value"], sort_keys=True)
        lines.append(
            f"| `{row['name']}` | `{row['category']}` | `{row['support_status']}` | `{value}` | {row['claim_boundary']} |"
        )
    lines.extend(
        [
            "",
            "## Gate Shape",
            "",
            "```json",
            "{",
            '  "id": "phase9_opencl_device_info_table",',
            '  "stage": "phase-9 opencl device-info readiness",',
            '  "command": "bash scripts/verify_celviz_gpgpu_opencl_device_info_table.sh",',
            '  "required": false,',
            '  "evidence": [',
            '    "tools/celviz_gpgpu_ip/opencl_device_info_table.py",',
            '    "docs/celviz-gpgpu-ip/PHASE9_OPENCL_DEVICE_INFO_TABLE.md",',
            '    "artifacts/rank_01_vivante_3d_gpgpu_ip/opencl_conformance/opencl_device_info_table.json"',
            "  ],",
            '  "pass_condition": "The generated table classifies CL_DEVICE_* profile/version/extensions/limits/memory/image/atomics/SVM fields with support status, evidence, CTS orientation, and no-overclaim boundaries. Passing this gate does not claim official OpenCL conformance or CTS pass."',
            "}",
            "```",
            "",
        ]
    )
    write_text(path, "\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate OpenCL CL_DEVICE_* device-info readiness table.")
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_ARTIFACT_ROOT / "opencl_conformance/opencl_device_info_table.json",
    )
    parser.add_argument(
        "--doc",
        type=Path,
        default=Path("docs/celviz-gpgpu-ip/PHASE9_OPENCL_DEVICE_INFO_TABLE.md"),
    )
    args = parser.parse_args()
    report = build_report(args.artifact_root)
    write_json(args.output, report)
    write_markdown(args.doc, report)
    summary = report["summary"]
    print(
        "celviz_gpgpu_opencl_device_info_table: "
        f"{report['status']} queries={summary['query_count']} "
        f"categories={len(summary['categories'])} output={args.output}"
    )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
