#!/usr/bin/env python3
"""Lower OpenCL-like subset kernels to clean-room Celviz micro-ops.

This is a deterministic evidence generator for the prototype stack. It is not a
real compiler backend, ISA definition, LLVM/SPIR-V path, or Vivante command
stream. The output connects existing OpenCL subset ABI metadata to a small
micro-op vocabulary that can be cross-checked against SIMT, memory, runtime, and
verification evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "celviz.gpgpu.kernel_lowering.v1"
CLEAN_ROOM_SCOPE = (
    "clean-room OpenCL-like subset to Celviz micro-op lowering evidence only; "
    "not an OpenCL compiler, not SPIR-V/LLVM, not a Vivante ISA or proprietary "
    "command stream, and not a performance/timing signoff"
)
KERNEL_ALIASES = {
    "vector_add": "vector_add",
    "gemm": "gemm_proxy",
    "conv2d": "convolution_proxy",
    "image_filter": "image_filter",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_json(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def as_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def product(values: list[int]) -> int:
    result = 1
    for value in values:
        result *= max(1, as_int(value, 1))
    return result


def pointer_args(abi: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(arg) for arg in abi.get("args", []) if arg.get("pointer") is True]


def scalar_args(abi: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(arg) for arg in abi.get("args", []) if arg.get("pointer") is not True]


def add_uop(uops: list[dict[str, Any]], opcode: str, **fields: Any) -> None:
    uops.append({"pc": len(uops), "opcode": opcode, **fields})


def lower_kernel(abi: Mapping[str, Any], runtime_command: Mapping[str, Any]) -> dict[str, Any]:
    name = str(abi.get("name"))
    simt_workload = KERNEL_ALIASES.get(name, name)
    metadata = dict(abi.get("metadata", {}))
    ptrs = pointer_args(abi)
    scalars = scalar_args(abi)
    global_size = [as_int(item, 1) for item in abi.get("global_size", [1, 1, 1])]
    local_size = [as_int(item, 1) for item in abi.get("local_size", [1, 1, 1])]
    work_items = as_int(abi.get("work_items"), product(global_size))
    wf_size = as_int(metadata.get("wf_size"), 32)
    uops: list[dict[str, Any]] = []

    add_uop(uops, "uop_kernel_prologue", kernel=name, simt_workload=simt_workload, wf_size=wf_size)
    add_uop(uops, "uop_read_workitem_id", dims=len(global_size), global_size=global_size, local_size=local_size)
    add_uop(uops, "uop_predicate_bounds", work_items=work_items, predicate="global_id < kernel_size")
    for arg in scalars:
        add_uop(uops, "uop_read_scalar_arg", arg=arg["name"], arg_type=arg.get("type"), abi_offset=arg.get("abi_offset"))
    for index, arg in enumerate(ptrs):
        add_uop(
            uops,
            "uop_address_calc",
            arg=arg["name"],
            address_space=arg.get("address_space"),
            access=arg.get("access"),
            buffer_index=index,
            coalescing_hint="lane_contiguous" if index == 0 else "lane_strided_or_reused",
        )
        if arg.get("access") in {"read_only", "read_write"}:
            add_uop(
                uops,
                "uop_global_load",
                arg=arg["name"],
                element_type=arg.get("type"),
                vector_width=arg.get("vector_width"),
                memory_semantic="global",
            )

    if name == "vector_add":
        add_uop(uops, "uop_alu_add", inputs=["a", "b"], output="c", fp_mode=abi.get("required_fp_mode"))
    elif name == "gemm":
        add_uop(uops, "uop_loop_begin", loop="k", trip_count_arg="k")
        add_uop(uops, "uop_alu_mad", inputs=["a", "b", "acc"], output="acc", fp_mode=abi.get("required_fp_mode"))
        add_uop(uops, "uop_loop_end", loop="k")
    elif name == "conv2d":
        add_uop(uops, "uop_loop_begin", loop="filter_yx", trip_count=9)
        add_uop(uops, "uop_alu_mad", inputs=["input", "filter", "acc"], output="acc", fp_mode=abi.get("required_fp_mode"))
        add_uop(uops, "uop_loop_end", loop="filter_yx")
    elif name == "image_filter":
        add_uop(uops, "uop_vector_unpack", input="src", vector_type="uchar4")
        add_uop(uops, "uop_alu_mul_clamp", inputs=["src", "gain"], output="dst", fp_mode=abi.get("required_fp_mode"))
        add_uop(uops, "uop_vector_pack", output="dst", vector_type="uchar4")
    else:
        add_uop(uops, "uop_alu_custom", kernel=name)

    if name in {"gemm", "conv2d"}:
        add_uop(uops, "uop_barrier", scope="workgroup", reason="tile_or_filter_accumulation_boundary")
    for arg in ptrs:
        if arg.get("access") in {"write_only", "read_write"}:
            add_uop(
                uops,
                "uop_global_store",
                arg=arg["name"],
                element_type=arg.get("type"),
                vector_width=arg.get("vector_width"),
                memory_semantic="global",
            )
    add_uop(uops, "uop_write_completion", completion_addr=runtime_command.get("completion_addr"))

    categories = sorted({uop["opcode"] for uop in uops})
    return {
        "schema": "celviz.gpgpu.kernel_lowering.kernel.v1",
        "kernel": name,
        "simt_workload": simt_workload,
        "runtime_sequence": runtime_command.get("sequence"),
        "kernel_entry": runtime_command.get("kernel_entry"),
        "work_items": work_items,
        "wavefront_size": wf_size,
        "uop_count": len(uops),
        "uop_categories": categories,
        "uops": uops,
        "source_abi_schema": abi.get("schema"),
        "runtime_command_schema": "celviz.gpgpu.runtime_commands.v1",
        "metadata_link": {
            "kernel_id": metadata.get("kernel_id"),
            "startaddr": metadata.get("startaddr"),
            "sgprUsage": metadata.get("sgprUsage"),
            "vgprUsage": metadata.get("vgprUsage"),
            "num_buffer": metadata.get("num_buffer"),
        },
    }


def collect(opencl_dir: Path, output_dir: Path) -> dict[str, Any]:
    evidence = load_json(opencl_dir / "opencl_subset_evidence.json")
    runtime_commands = load_json(opencl_dir / "runtime_commands.json")
    commands = {
        str(command.get("kernel")): command
        for command in runtime_commands.get("commands", [])
        if command.get("opcode") == "kernel_dispatch"
    }
    lowered: list[dict[str, Any]] = []
    kernel_paths: dict[str, str] = {}
    for kernel in evidence.get("kernels", []):
        abi_path = Path(kernel["abi"])
        abi = load_json(abi_path)
        lowered_kernel = lower_kernel(abi, commands[str(kernel["name"])])
        lowered_kernel["sha256"] = sha256_json(lowered_kernel)
        lowered.append(lowered_kernel)
        kernel_output = output_dir / "kernels" / f"{lowered_kernel['kernel']}.lowering.json"
        write_json(kernel_output, lowered_kernel)
        kernel_paths[lowered_kernel["kernel"]] = str(kernel_output)

    required_uops = {
        "uop_kernel_prologue",
        "uop_read_workitem_id",
        "uop_predicate_bounds",
        "uop_address_calc",
        "uop_global_load",
        "uop_global_store",
        "uop_write_completion",
    }
    checks = [
        {
            "name": "all_opencl_kernels_lowered",
            "pass": len(lowered) == evidence.get("kernel_count") == 4,
            "observed": [item["kernel"] for item in lowered],
        },
        {
            "name": "required_micro_ops_present",
            "pass": all(required_uops.issubset(set(item["uop_categories"])) for item in lowered),
        },
        {
            "name": "loop_kernels_have_loop_ops",
            "pass": all(
                {"uop_loop_begin", "uop_loop_end"}.issubset(set(item["uop_categories"]))
                for item in lowered
                if item["kernel"] in {"gemm", "conv2d"}
            ),
        },
        {
            "name": "image_filter_has_vector_ops",
            "pass": any(
                item["kernel"] == "image_filter"
                and {"uop_vector_unpack", "uop_vector_pack"}.issubset(set(item["uop_categories"]))
                for item in lowered
            ),
        },
        {
            "name": "runtime_sequences_unique",
            "pass": len({item["runtime_sequence"] for item in lowered}) == len(lowered),
        },
        {
            "name": "metadata_links_present",
            "pass": all(item["metadata_link"].get("kernel_id") and item["metadata_link"].get("startaddr") for item in lowered),
        },
    ]
    status = "pass" if all(item["pass"] for item in checks) else "fail"
    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "status": status,
        "opencl_evidence": str(opencl_dir / "opencl_subset_evidence.json"),
        "runtime_commands": str(opencl_dir / "runtime_commands.json"),
        "kernel_outputs": kernel_paths,
        "kernel_count": len(lowered),
        "total_uops": sum(as_int(item.get("uop_count")) for item in lowered),
        "uop_categories": sorted({category for item in lowered for category in item["uop_categories"]}),
        "checks": checks,
        "kernels": [
            {
                "kernel": item["kernel"],
                "simt_workload": item["simt_workload"],
                "runtime_sequence": item["runtime_sequence"],
                "uop_count": item["uop_count"],
                "uop_categories": item["uop_categories"],
                "sha256": item["sha256"],
            }
            for item in lowered
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Lower Celviz OpenCL-like subset kernels to micro-op evidence.")
    parser.add_argument(
        "--opencl-dir",
        type=Path,
        default=Path("artifacts/rank_01_vivante_3d_gpgpu_ip/demo/opencl_subset"),
        help="OpenCL subset evidence directory",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/rank_01_vivante_3d_gpgpu_ip/lowering"),
        help="Output directory",
    )
    args = parser.parse_args()
    report = collect(args.opencl_dir, args.output_dir)
    output = args.output_dir / "kernel_lowering_report.json"
    write_json(output, report)
    print(
        "celviz_gpgpu_kernel_lowering: "
        f"{report['status']} kernels={report['kernel_count']} "
        f"uops={report['total_uops']} output={output}"
    )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
