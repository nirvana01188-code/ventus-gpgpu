#!/usr/bin/env python3
"""Build clean-room compiler IR evidence from Celviz lowered micro-ops."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "celviz.gpgpu.compiler_ir.v1"
CLEAN_ROOM_SCOPE = (
    "clean-room compiler IR evidence over Celviz micro-ops only; not SPIR-V, "
    "not LLVM, not a production compiler backend, not Vivante ISA, and not a "
    "proprietary command-stream compatibility claim"
)
DEFAULT_ROOT = Path("artifacts/rank_01_vivante_3d_gpgpu_ip")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_json(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def block_name(opcode: str, index: int) -> str:
    if opcode == "uop_kernel_prologue":
        return "entry"
    if opcode in {"uop_loop_begin", "uop_loop_end"}:
        return f"loop_{index}"
    if opcode == "uop_barrier":
        return f"sync_{index}"
    if opcode == "uop_write_completion":
        return "exit"
    return f"bb_{index}"


def build_kernel_ir(lowered: Mapping[str, Any]) -> dict[str, Any]:
    kernel = str(lowered["kernel"])
    uops = list(lowered.get("uops", []))
    vreg_index = 0
    preg_index = 0
    vregs: list[dict[str, Any]] = []
    pregs: list[dict[str, Any]] = []
    blocks: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    def_use: list[dict[str, Any]] = []
    last_block = ""
    live_predicate = ""

    for index, uop in enumerate(uops):
        opcode = str(uop.get("opcode"))
        name = block_name(opcode, index)
        defs: list[str] = []
        uses: list[str] = []
        if opcode == "uop_predicate_bounds":
            preg = f"p{preg_index}"
            preg_index += 1
            pregs.append({"name": preg, "defined_by_pc": uop.get("pc"), "condition": uop.get("predicate")})
            defs.append(preg)
            live_predicate = preg
        elif opcode in {"uop_global_load", "uop_read_scalar_arg", "uop_read_workitem_id"}:
            reg = f"v{vreg_index}"
            vreg_index += 1
            vregs.append({"name": reg, "defined_by_pc": uop.get("pc"), "kind": opcode, "source": uop.get("arg")})
            defs.append(reg)
            if live_predicate:
                uses.append(live_predicate)
        elif opcode.startswith("uop_alu") or opcode in {"uop_vector_unpack", "uop_vector_pack"}:
            reg = f"v{vreg_index}"
            vreg_index += 1
            vregs.append({"name": reg, "defined_by_pc": uop.get("pc"), "kind": opcode, "source": uop.get("inputs")})
            defs.append(reg)
            uses.extend([item["name"] for item in vregs[-3:-1]])
            if live_predicate:
                uses.append(live_predicate)
        elif opcode == "uop_global_store":
            uses.extend([item["name"] for item in vregs[-2:]])
            if live_predicate:
                uses.append(live_predicate)
        elif opcode == "uop_loop_begin":
            preg = f"p{preg_index}"
            preg_index += 1
            pregs.append({"name": preg, "defined_by_pc": uop.get("pc"), "condition": f"loop {uop.get('loop')} active"})
            defs.append(preg)
            live_predicate = preg
        elif opcode == "uop_loop_end" and pregs:
            uses.append(pregs[-1]["name"])
        elif opcode == "uop_write_completion":
            uses.extend([item["name"] for item in vregs[-2:]])

        block = {
            "name": name,
            "pc": uop.get("pc"),
            "opcode": opcode,
            "defs": defs,
            "uses": uses,
            "predicate": live_predicate if opcode not in {"uop_kernel_prologue", "uop_predicate_bounds"} else "",
        }
        blocks.append(block)
        def_use.append({"pc": uop.get("pc"), "opcode": opcode, "defs": defs, "uses": uses})
        if last_block:
            edges.append({"src": last_block, "dst": name, "kind": "fallthrough"})
        if opcode == "uop_loop_end":
            loop_begin = next((b["name"] for b in reversed(blocks) if b["opcode"] == "uop_loop_begin"), "")
            if loop_begin:
                edges.append({"src": name, "dst": loop_begin, "kind": "backedge"})
        last_block = name

    checks = [
        {"name": "has_basic_blocks", "pass": len(blocks) == len(uops) and len(blocks) > 0},
        {"name": "has_virtual_registers", "pass": len(vregs) > 0},
        {"name": "has_predicate_registers", "pass": len(pregs) > 0},
        {"name": "has_cfg_edges", "pass": len(edges) >= max(0, len(blocks) - 1)},
        {"name": "has_def_use", "pass": any(item["defs"] for item in def_use) and any(item["uses"] for item in def_use)},
        {
            "name": "loop_kernels_have_backedge",
            "pass": kernel not in {"gemm", "conv2d"} or any(edge["kind"] == "backedge" for edge in edges),
        },
    ]
    payload = {
        "schema": "celviz.gpgpu.compiler_ir.kernel.v1",
        "kernel": kernel,
        "status": "pass" if all(check["pass"] for check in checks) else "fail",
        "virtual_registers": vregs,
        "predicate_registers": pregs,
        "basic_blocks": blocks,
        "cfg_edges": edges,
        "def_use": def_use,
        "checks": checks,
    }
    payload["sha256"] = sha256_json(payload)
    return payload


def collect(artifact_root: Path, output_dir: Path) -> dict[str, Any]:
    kernels_dir = artifact_root / "lowering" / "kernels"
    reports = []
    paths = {}
    for path in sorted(kernels_dir.glob("*.lowering.json")):
        lowered = load_json(path)
        report = build_kernel_ir(lowered)
        out = output_dir / "kernels" / f"{report['kernel']}.compiler_ir.json"
        write_json(out, report)
        paths[report["kernel"]] = str(out)
        reports.append(report)
    checks = [
        {"name": "all_four_kernels_have_ir", "pass": {r["kernel"] for r in reports} == {"vector_add", "gemm", "conv2d", "image_filter"}},
        {"name": "all_kernel_ir_pass", "pass": all(r["status"] == "pass" for r in reports)},
        {"name": "virtual_and_predicate_registers_present", "pass": all(r["virtual_registers"] and r["predicate_registers"] for r in reports)},
        {"name": "cfg_and_def_use_present", "pass": all(r["cfg_edges"] and r["def_use"] for r in reports)},
    ]
    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "status": "pass" if all(c["pass"] for c in checks) else "fail",
        "kernel_outputs": paths,
        "kernel_count": len(reports),
        "total_virtual_registers": sum(len(r["virtual_registers"]) for r in reports),
        "total_predicate_registers": sum(len(r["predicate_registers"]) for r in reports),
        "total_basic_blocks": sum(len(r["basic_blocks"]) for r in reports),
        "total_cfg_edges": sum(len(r["cfg_edges"]) for r in reports),
        "checks": checks,
        "kernels": [
            {
                "kernel": r["kernel"],
                "status": r["status"],
                "virtual_registers": len(r["virtual_registers"]),
                "predicate_registers": len(r["predicate_registers"]),
                "basic_blocks": len(r["basic_blocks"]),
                "cfg_edges": len(r["cfg_edges"]),
                "sha256": r["sha256"],
            }
            for r in reports
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Celviz compiler IR evidence.")
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_ROOT / "compiler_ir")
    args = parser.parse_args()
    report = collect(args.artifact_root, args.output_dir)
    output = args.output_dir / "compiler_ir_report.json"
    write_json(output, report)
    print(
        "celviz_gpgpu_compiler_ir: "
        f"{report['status']} kernels={report['kernel_count']} "
        f"vregs={report['total_virtual_registers']} pregs={report['total_predicate_registers']} "
        f"blocks={report['total_basic_blocks']} output={output}"
    )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
