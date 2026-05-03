#!/usr/bin/env python3
"""Generate executable Phase-8 work-package artifacts.

This tool turns the Phase-8 closure backlog into concrete, checkable outputs.
It still does not claim completion of external certification, proprietary
compatibility, kernel-driver production readiness, structural coverage closure,
or signoff. The value is that each lane now has an artifact that can be reviewed,
rerun, and expanded.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

try:
    from . import opencl_subset
except ImportError:  # pragma: no cover - direct script fallback
    import opencl_subset  # type: ignore


SCHEMA = "celviz.gpgpu.phase8_work_package_artifacts.v1"
DEFAULT_ARTIFACT_ROOT = Path("artifacts/rank_01_vivante_3d_gpgpu_ip")
CLEAN_ROOM_SCOPE = (
    "Phase-8 executable work-package artifacts for the Ventus-based Celviz "
    "GPGPU IP proxy; not proprietary Vivante compatibility, not official OpenCL "
    "conformance, not production Linux kernel/DRM driver readiness, not RTL "
    "structural coverage closure, not synthesis/STA/power/DFT/physical/silicon "
    "signoff, and not silicon performance evidence"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"missing work-package input: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid work-package input JSON {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"work-package input is not a JSON object: {path}")
    return data


def pass_check(name: str, passed: bool, evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "pass": bool(passed),
        "evidence": dict(evidence or {}),
    }


def run_opencl_negative_tests() -> dict[str, Any]:
    cases = [
        {
            "name": "reject_image_object",
            "source": "__kernel void bad(image2d_t img) { }",
            "expect": "unsupported OpenCL feature token",
        },
        {
            "name": "reject_atomic_builtin",
            "source": "__kernel void bad(__global int *p) { atomic_inc(p); }",
            "expect": "unsupported OpenCL feature token",
        },
        {
            "name": "reject_double_precision",
            "source": "__kernel void bad(__global double *p) { p[0] = 1.0; }",
            "expect": "unsupported OpenCL feature token",
        },
        {
            "name": "reject_unsupported_subgroup_builtin",
            "source": "__kernel void bad(__global uint *p) { p[0] = get_sub_group_id(); }",
            "expect": "unsupported OpenCL feature token",
        },
        {
            "name": "reject_private_pointer",
            "source": "__kernel void bad(float *p) { p[0] = 0.0f; }",
            "expect": "must declare an address space",
        },
        {
            "name": "reject_non_divisible_launch",
            "source": "__kernel void bad(__global float *p) { p[get_global_id(0)] = 0.0f; }",
            "expect": "global_size must be divisible by local_size",
            "global_size": (100, 1, 1),
            "local_size": (64, 1, 1),
        },
        {
            "name": "reject_large_workgroup",
            "source": "__kernel void bad(__global float *p) { p[get_global_id(0)] = 0.0f; }",
            "expect": "local workgroup size exceeds",
            "global_size": (512, 1, 1),
            "local_size": (512, 1, 1),
        },
    ]
    results: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        try:
            spec = opencl_subset.KernelSpec(
                name="bad",
                source=str(case["source"]),
                global_size=tuple(case.get("global_size", (64, 1, 1))),
                local_size=tuple(case.get("local_size", (64, 1, 1))),
                buffers=(
                    {
                        "id": "bad_p",
                        "arg": "p",
                        "device_address": "0x85000000",
                        "size_bytes": 4096,
                        "access": "read_write",
                    },
                ),
                scalar_args={},
                precision="fp32",
            )
            opencl_subset.compile_kernel(spec, index)
            results.append(
                {
                    "name": case["name"],
                    "status": "fail",
                    "expected_rejection": case["expect"],
                    "observed_error": None,
                }
            )
        except opencl_subset.SubsetError as exc:
            observed = str(exc)
            results.append(
                {
                    "name": case["name"],
                    "status": "pass" if str(case["expect"]) in observed else "fail",
                    "expected_rejection": case["expect"],
                    "observed_error": observed,
                }
            )
    return {
        "schema": "celviz.gpgpu.phase8.opencl_negative_tests.v1",
        "status": "pass" if all(item["status"] == "pass" for item in results) else "fail",
        "claim_boundary": "negative subset tests only; not Khronos CTS or official OpenCL conformance",
        "tests": results,
        "test_count": len(results),
    }


def drm_uapi_contract(driver_report: Mapping[str, Any], linux_report: Mapping[str, Any]) -> dict[str, Any]:
    objects = [
        {
            "name": "device",
            "proxy_evidence": "linux_runtime_evidence device open/context lifecycle",
            "kernel_missing": ["real /dev/dri node ownership", "ioctl number allocation", "capability query UAPI"],
        },
        {
            "name": "buffer_object",
            "proxy_evidence": "BO create/map/GPU VA semantics in userspace fixture",
            "kernel_missing": ["GEM handle lifetime", "mmap offsets", "dma-buf import/export", "IOMMU integration"],
        },
        {
            "name": "queue",
            "proxy_evidence": "driver_submission queue lifecycle and no-pending closure",
            "kernel_missing": ["scheduler entity", "preemption policy", "hang recovery"],
        },
        {
            "name": "fence_event",
            "proxy_evidence": "fence/event lifecycle and error paths",
            "kernel_missing": ["syncobj/timeline ABI", "poll/select wakeups", "cross-process sharing"],
        },
        {
            "name": "command_submission",
            "proxy_evidence": "kernel dispatch alignment plus error-path proxy",
            "kernel_missing": ["copy_from_user validation", "command parser hardening", "security review"],
        },
    ]
    checks = [
        pass_check("driver_submission_proxy_pass", driver_report.get("status") == "pass", {"status": driver_report.get("status")}),
        pass_check("linux_runtime_proxy_pass", linux_report.get("status") == "pass", {"status": linux_report.get("status")}),
        pass_check("uapi_objects_mapped", len(objects) >= 5, {"object_count": len(objects)}),
    ]
    return {
        "schema": "celviz.gpgpu.phase8.drm_uapi_contract.v1",
        "status": "pass" if all(item["pass"] for item in checks) else "fail",
        "claim_boundary": "DRM-like contract draft only; not a production Linux kernel/DRM driver",
        "uapi_objects": objects,
        "checks": checks,
    }


def structural_coverage_uplift_plan(e8: Mapping[str, Any]) -> dict[str, Any]:
    line = e8.get("line_metrics", {})
    branch = e8.get("lcov_info", {}).get("branch", {})
    toggle = e8.get("toggle_metrics", {})
    targets = [
        "reset CSR transitions",
        "IRQ mask/status/clear flow",
        "AXI/APB read-write counter fire pulses",
        "scoreboard source/writeback hazard stalls",
        "LSU global/shared request and response paths",
        "warp scheduler accept/branch-flush/reconvergence paths",
        "random command stream with injected MMU, scheduler, and fence faults",
    ]
    return {
        "schema": "celviz.gpgpu.phase8.structural_coverage_uplift_plan.v1",
        "status": "pass",
        "claim_boundary": "structural coverage uplift plan; not RTL structural coverage 100%",
        "current_structural_metrics": {
            "line": line,
            "branch": branch,
            "toggle": toggle,
        },
        "directed_test_targets": targets,
        "acceptance": [
            "each directed target must add or preserve line/branch coverage",
            "toggle/source metrics must remain reported separately from functional acceptance coverage",
            "waivers must be explicit before any 100% structural claim",
        ],
    }


def signoff_requirements(synth: Mapping[str, Any], yosys: Mapping[str, Any], ppa: Mapping[str, Any]) -> dict[str, Any]:
    requirements = [
        {"name": "target_library", "required_inputs": ["standard-cell Liberty", "memory macros", "IO libraries"]},
        {"name": "constraints", "required_inputs": ["clock definitions", "IO delays", "false/multicycle paths"]},
        {"name": "sta", "required_inputs": ["corner list", "timing reports", "constraint lint"]},
        {"name": "power", "required_inputs": ["activity SAIF/VCD", "voltage domains", "power intent if used"]},
        {"name": "dft", "required_inputs": ["scan strategy", "test clocks", "coverage reports"]},
        {"name": "physical", "required_inputs": ["floorplan", "P&R logs", "DRC/LVS/antenna reports"]},
        {"name": "silicon", "required_inputs": ["bring-up plan", "validation logs", "measured PPA"]},
    ]
    checks = [
        pass_check("synthesis_readiness_proxy_pass", synth.get("status") == "pass", {"status": synth.get("status")}),
        pass_check("yosys_probe_records_blocker_or_stats", yosys.get("status") == "pass", {"classification": yosys.get("classification")}),
        pass_check("ppa_proxy_pass", ppa.get("status") == "pass", {"status": ppa.get("status")}),
        pass_check("external_requirements_named", len(requirements) >= 7, {"requirement_count": len(requirements)}),
    ]
    return {
        "schema": "celviz.gpgpu.phase8.signoff_requirements.v1",
        "status": "pass" if all(item["pass"] for item in checks) else "fail",
        "claim_boundary": "input requirements only; not completed synthesis/STA/power/DFT/physical/silicon signoff",
        "requirements": requirements,
        "checks": checks,
    }


def phase7_overclaim_scan(root: Path, artifact_root: Path) -> dict[str, Any]:
    paths = [
        artifact_root / "verification" / "phase7_coalescing_score_report.json",
        artifact_root / "verification" / "phase7_control_flow_manager_report.json",
        artifact_root / "verification" / "phase7_memory_streaming_report.json",
        artifact_root / "verification" / "phase7_config_sweep_report.json",
        artifact_root / "verification" / "phase7_register_occupancy_report.json",
        artifact_root / "verification" / "phase7_warp_collectives_report.json",
        root / "docs" / "celviz-gpgpu-ip" / "RISCV_GPU_PERFORMANCE_RESEARCH.md",
    ]
    forbidden = (
        "silicon performance",
        "post-silicon performance",
        "measured silicon",
        "real silicon",
        "tapeout performance",
    )
    allowed_context = ("not", "no ", "proxy", "boundary", "claim")
    findings: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            findings.append({"path": str(path), "line": 0, "text": "missing file", "severity": "error"})
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_no, line in enumerate(text.splitlines(), start=1):
            lower = line.lower()
            if not any(token in lower for token in forbidden):
                continue
            if any(token in lower for token in allowed_context):
                continue
            findings.append({"path": str(path), "line": line_no, "text": line.strip(), "severity": "overclaim"})
    return {
        "schema": "celviz.gpgpu.phase8.phase7_overclaim_scan.v1",
        "status": "pass" if not findings else "fail",
        "claim_boundary": "Phase7 reports are proxy evidence; silicon performance wording is rejected unless explicitly negated",
        "scanned_paths": [str(path) for path in paths],
        "findings": findings,
    }


def vivante_boundary_checklist() -> dict[str, Any]:
    items = [
        {"id": "licensed_collateral", "required_before_claim": True, "present": False},
        {"id": "legal_approval", "required_before_claim": True, "present": False},
        {"id": "separate_evidence_root", "required_before_claim": True, "present": False},
        {"id": "proprietary_abi_mapping", "required_before_claim": True, "present": False},
        {"id": "firmware_driver_sdk_contract", "required_before_claim": True, "present": False},
        {"id": "clean_room_public_proxy_boundary", "required_before_claim": False, "present": True},
    ]
    return {
        "schema": "celviz.gpgpu.phase8.vivante_clean_room_boundary_checklist.v1",
        "status": "pass",
        "claim_boundary": "checklist prevents proprietary compatibility overclaim; it does not satisfy Vivante compatibility",
        "items": items,
        "compatibility_claim_enabled": False,
    }


def write_markdown(path: Path, title: str, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = [
        f"# {title}",
        "",
        f"Status: `{payload.get('status')}`",
        "",
        str(payload.get("claim_boundary", "")),
        "",
        "```json",
        json.dumps(payload, indent=2, sort_keys=True),
        "```",
        "",
    ]
    path.write_text("\n".join(body), encoding="utf-8")


def build(artifact_root: Path, output_dir: Path, docs_dir: Path) -> dict[str, Any]:
    root = repo_root()
    inputs = {
        "driver": load_json(artifact_root / "driver_submission" / "driver_submission_report.json"),
        "linux": load_json(artifact_root / "os_runtime" / "linux_runtime_evidence.json"),
        "e8": load_json(artifact_root / "verification" / "verilator_coverage" / "verilator_coverage_report.json"),
        "synth": load_json(artifact_root / "synthesis" / "synthesis_readiness_report.json"),
        "yosys": load_json(artifact_root / "synthesis" / "yosys_synthesis_probe_report.json"),
        "ppa": load_json(artifact_root / "ppa" / "ppa_proxy_report.json"),
    }
    artifacts = {
        "opencl_negative_tests": run_opencl_negative_tests(),
        "drm_uapi_contract": drm_uapi_contract(inputs["driver"], inputs["linux"]),
        "structural_coverage_uplift_plan": structural_coverage_uplift_plan(inputs["e8"]),
        "signoff_requirements": signoff_requirements(inputs["synth"], inputs["yosys"], inputs["ppa"]),
        "phase7_overclaim_scan": phase7_overclaim_scan(root, artifact_root),
        "vivante_clean_room_boundary_checklist": vivante_boundary_checklist(),
    }
    output_paths: dict[str, str] = {}
    for name, payload in artifacts.items():
        json_path = output_dir / f"{name}.json"
        write_json(json_path, payload)
        output_paths[name] = str(json_path)
    write_markdown(docs_dir / "PHASE8_DRM_UAPI_CONTRACT.md", "Phase 8 DRM-Like UAPI Contract", artifacts["drm_uapi_contract"])
    write_markdown(docs_dir / "PHASE8_SIGNOFF_REQUIREMENTS.md", "Phase 8 Signoff Requirements", artifacts["signoff_requirements"])
    write_markdown(docs_dir / "PHASE8_VIVANTE_BOUNDARY_CHECKLIST.md", "Phase 8 Vivante Boundary Checklist", artifacts["vivante_clean_room_boundary_checklist"])

    checks = [
        pass_check(f"{name}_status_pass", payload.get("status") == "pass", {"path": output_paths[name]})
        for name, payload in artifacts.items()
    ]
    checks.append(pass_check("all_work_package_artifacts_present", len(artifacts) == 6, {"artifact_count": len(artifacts)}))
    status = "pass" if all(item["pass"] for item in checks) else "fail"
    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "status": status,
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "artifact_paths": output_paths,
        "checks": checks,
        "summary": {
            "artifact_count": len(artifacts),
            "artifacts_passed": sum(1 for payload in artifacts.values() if payload.get("status") == "pass"),
            "completion_claim": "not_completed_for_external_or_signoff_items",
            "engineering_progress_claim": "six Phase-8 work packages now have concrete checkable artifacts",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Phase-8 work-package artifacts.")
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_ARTIFACT_ROOT / "verification" / "phase8_work_package_artifacts")
    parser.add_argument("--docs-dir", type=Path, default=Path("docs/celviz-gpgpu-ip"))
    args = parser.parse_args(argv)

    report = build(args.artifact_root, args.output_dir, args.docs_dir)
    output = args.output_dir / "phase8_work_package_artifacts_report.json"
    write_json(output, report)
    print(
        "celviz_gpgpu_phase8_work_package_artifacts: "
        f"{report['status']} artifacts={report['summary']['artifacts_passed']}/{report['summary']['artifact_count']} "
        f"output={output}"
    )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
