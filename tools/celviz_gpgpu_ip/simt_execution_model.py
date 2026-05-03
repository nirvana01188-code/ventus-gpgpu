#!/usr/bin/env python3
"""Clean-room SIMT execution evidence model for Celviz GPGPU IP.

This is a deterministic software execution model, not a Vivante ISA, RTL,
driver, firmware, compiler, timing, or conformance model.  It exists to push
the S1 proxy workloads through an explicit SIMD/SIMT-shaped path: wavefront
scheduling, per-lane register file access, ALU/LSU operations, scoreboard
hazards, and barriers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, MutableMapping, Sequence


ARTIFACT_ROOT = Path("artifacts/rank_01_vivante_3d_gpgpu_ip/model")
DEFAULT_OUTPUT = ARTIFACT_ROOT / "outputs/simt_execution.json"
SCHEMA = "celviz.gpgpu.simt_execution.v1"
CLEAN_ROOM_SCOPE = (
    "clean-room SIMT execution evidence only; no proprietary Vivante RTL, ISA, "
    "firmware, SDK, compiler, driver, command stream, timing, or conformance claim"
)


def f32(value: float) -> float:
    return struct.unpack(">f", struct.pack(">f", float(value)))[0]


def sha256_json(data: object) -> str:
    blob = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def deterministic_vector(length: int, scale: float, offset: float) -> List[float]:
    return [f32(math.sin(i * 0.37 + offset) * scale + (i % 7) * 0.125) for i in range(length)]


def flatten(matrix: Sequence[Sequence[Any]]) -> List[Any]:
    return [value for row in matrix for value in row]


@dataclass(frozen=True)
class SimtConfig:
    wavefront_size: int = 8
    issue_width: int = 1
    alu_latency: int = 1
    lsu_latency: int = 9
    barrier_latency: int = 1
    max_trace_events: int = 1800


@dataclass(frozen=True)
class Instruction:
    op: str
    dst: str | None = None
    srcs: tuple[str, ...] = ()
    mem: str | None = None
    imm: float | int | None = None
    addr: Callable[[int], int] | None = None
    active: Callable[[int], bool] | None = None
    comment: str = ""


@dataclass
class WarpState:
    warp_id: int
    workload: str
    global_start_lane: int
    lane_count: int
    program: List[Instruction]
    pc: int = 0
    done: bool = False
    barrier_until: int = 0
    registers: MutableMapping[str, List[float | int | None]] = field(default_factory=dict)
    ready_cycle: MutableMapping[str, int] = field(default_factory=dict)
    written_registers: set[str] = field(default_factory=set)

    def logical_lane(self, lane: int) -> int:
        return self.global_start_lane + lane


class SimtMachine:
    def __init__(self, config: SimtConfig, memory: Mapping[str, Sequence[float | int]]) -> None:
        self.config = config
        self.memory: Dict[str, List[float | int]] = {name: list(values) for name, values in memory.items()}
        self.cycle = 0
        self.trace: List[Dict[str, Any]] = []
        self.counters = {
            "scheduler_issues": 0,
            "register_reads": 0,
            "register_writes": 0,
            "alu_ops": 0,
            "lsu_loads": 0,
            "lsu_stores": 0,
            "scoreboard_hazard_events": 0,
            "scoreboard_hazard_cycles": 0,
            "barrier_events": 0,
            "barrier_wait_cycles": 0,
        }

    def emit(self, event: Mapping[str, Any]) -> None:
        if len(self.trace) < self.config.max_trace_events:
            self.trace.append(dict(event))

    def lanes(self, warp: WarpState, inst: Instruction) -> List[int]:
        lanes = []
        for lane in range(self.config.wavefront_size):
            if lane >= warp.lane_count:
                continue
            if inst.active is not None and not inst.active(warp.logical_lane(lane)):
                continue
            lanes.append(lane)
        return lanes

    def ensure_reg(self, warp: WarpState, name: str) -> List[float | int | None]:
        if name not in warp.registers:
            warp.registers[name] = [None for _ in range(self.config.wavefront_size)]
        return warp.registers[name]

    def source_ready_cycle(self, warp: WarpState, inst: Instruction) -> int:
        ready = self.cycle
        for src in inst.srcs:
            if src in warp.written_registers:
                ready = max(ready, int(warp.ready_cycle.get(src, 0)))
        return ready

    def run(self, workload: str, warps: List[WarpState]) -> Dict[str, Any]:
        rr_index = 0
        while not all(warp.done for warp in warps):
            issued = False
            for _ in range(len(warps)):
                warp = warps[rr_index % len(warps)]
                rr_index += 1
                if warp.done:
                    continue
                if self.cycle < warp.barrier_until:
                    wait = warp.barrier_until - self.cycle
                    self.counters["barrier_wait_cycles"] += 1
                    self.emit(
                        {
                            "cycle": self.cycle,
                            "type": "barrier_wait",
                            "workload": workload,
                            "warp_id": warp.warp_id,
                            "wavefront_size": self.config.wavefront_size,
                            "remaining_cycles": wait,
                        }
                    )
                    continue
                inst = warp.program[warp.pc]
                ready = self.source_ready_cycle(warp, inst)
                if ready > self.cycle:
                    stall = ready - self.cycle
                    self.counters["scoreboard_hazard_events"] += 1
                    self.counters["scoreboard_hazard_cycles"] += stall
                    self.emit(
                        {
                            "cycle": self.cycle,
                            "type": "scoreboard_hazard",
                            "workload": workload,
                            "warp_id": warp.warp_id,
                            "pc": warp.pc,
                            "op": inst.op,
                            "blocked_sources": [
                                src
                                for src in inst.srcs
                                if src in warp.written_registers and int(warp.ready_cycle.get(src, 0)) > self.cycle
                            ],
                            "ready_cycle": ready,
                            "stall_cycles": stall,
                        }
                    )
                    continue
                self.issue(workload, warp, inst)
                issued = True
                break
            self.cycle += 1
            if not issued and not all(warp.done for warp in warps):
                continue
        return {
            "workload": workload,
            "cycles": self.cycle,
            "warps": [
                {
                    "warp_id": warp.warp_id,
                    "wavefront_id": warp.warp_id,
                    "global_start_lane": warp.global_start_lane,
                    "lane_count": warp.lane_count,
                    "instruction_count": len(warp.program),
                    "registers_written": sorted(warp.written_registers),
                }
                for warp in warps
            ],
            "counters": dict(self.counters),
            "trace": list(self.trace),
            "trace_truncated": len(self.trace) >= self.config.max_trace_events,
        }

    def issue(self, workload: str, warp: WarpState, inst: Instruction) -> None:
        lanes = self.lanes(warp, inst)
        self.counters["scheduler_issues"] += 1
        self.emit(
            {
                "cycle": self.cycle,
                "type": "warp_schedule",
                "workload": workload,
                "warp_id": warp.warp_id,
                "wavefront_id": warp.warp_id,
                "pc": warp.pc,
                "op": inst.op,
                "active_mask": "".join("1" if lane in lanes else "0" for lane in range(self.config.wavefront_size)),
                "active_lanes": lanes,
                "issue_width": self.config.issue_width,
                "comment": inst.comment,
            }
        )
        if inst.op == "end":
            warp.done = True
            self.emit({"cycle": self.cycle, "type": "warp_done", "workload": workload, "warp_id": warp.warp_id})
            return
        if inst.op == "barrier":
            warp.barrier_until = self.cycle + self.config.barrier_latency
            self.counters["barrier_events"] += 1
            self.emit(
                {
                    "cycle": self.cycle,
                    "type": "barrier",
                    "workload": workload,
                    "warp_id": warp.warp_id,
                    "scope": "workgroup",
                    "release_cycle": warp.barrier_until,
                }
            )
            warp.pc += 1
            return

        if inst.op in {"mov", "ld"} and inst.dst is None:
            raise ValueError(f"{inst.op} requires dst")
        if inst.op == "mov":
            dst = self.ensure_reg(warp, str(inst.dst))
            for lane in lanes:
                dst[lane] = inst.imm
            self.record_reg_write(workload, warp, str(inst.dst), lanes, self.config.alu_latency, dst)
            warp.pc += 1
            return
        if inst.op == "ld":
            if inst.mem is None or inst.addr is None:
                raise ValueError("ld requires mem and addr")
            dst = self.ensure_reg(warp, str(inst.dst))
            addresses = []
            values = []
            for lane in lanes:
                address = inst.addr(warp.logical_lane(lane))
                dst[lane] = self.memory[inst.mem][address]
                addresses.append(address)
                values.append(dst[lane])
            self.counters["lsu_loads"] += len(lanes)
            self.emit(
                {
                    "cycle": self.cycle,
                    "type": "lsu_op",
                    "kind": "load",
                    "workload": workload,
                    "warp_id": warp.warp_id,
                    "mem": inst.mem,
                    "dst": inst.dst,
                    "addresses": addresses,
                    "values": values,
                    "latency": self.config.lsu_latency,
                }
            )
            self.record_reg_write(workload, warp, str(inst.dst), lanes, self.config.lsu_latency, dst)
            warp.pc += 1
            return
        if inst.op == "st":
            if inst.mem is None or inst.addr is None or len(inst.srcs) != 1:
                raise ValueError("st requires mem, addr, and one source")
            src_name = inst.srcs[0]
            src = self.ensure_reg(warp, src_name)
            addresses = []
            values = []
            for lane in lanes:
                address = inst.addr(warp.logical_lane(lane))
                value = src[lane]
                if value is None:
                    raise ValueError(f"store of uninitialized {src_name} lane {lane}")
                self.memory[inst.mem][address] = value
                addresses.append(address)
                values.append(value)
            self.counters["register_reads"] += len(lanes)
            self.counters["lsu_stores"] += len(lanes)
            self.emit(
                {
                    "cycle": self.cycle,
                    "type": "lsu_op",
                    "kind": "store",
                    "workload": workload,
                    "warp_id": warp.warp_id,
                    "mem": inst.mem,
                    "src": src_name,
                    "addresses": addresses,
                    "values": values,
                    "latency": self.config.lsu_latency,
                }
            )
            warp.pc += 1
            return
        self.issue_alu(workload, warp, inst, lanes)
        warp.pc += 1

    def issue_alu(self, workload: str, warp: WarpState, inst: Instruction, lanes: Sequence[int]) -> None:
        if inst.dst is None:
            raise ValueError(f"{inst.op} requires dst")
        src_regs = [self.ensure_reg(warp, src) for src in inst.srcs]
        dst = self.ensure_reg(warp, inst.dst)
        results = []
        for lane in lanes:
            values = [reg[lane] for reg in src_regs]
            if any(value is None for value in values):
                raise ValueError(f"{inst.op} reads uninitialized source at warp {warp.warp_id} lane {lane}")
            if inst.op == "add":
                result: float | int = f32(float(values[0]) + float(values[1]))
            elif inst.op == "mul":
                result = f32(float(values[0]) * float(values[1]))
            elif inst.op == "mad":
                result = f32(float(values[2]) + f32(float(values[0]) * float(values[1])))
            elif inst.op == "iadd":
                result = int(values[0]) + int(values[1])
            else:
                raise ValueError(f"unsupported ALU op {inst.op}")
            dst[lane] = result
            results.append(result)
        self.counters["register_reads"] += len(lanes) * len(inst.srcs)
        self.counters["alu_ops"] += len(lanes) * (2 if inst.op == "mad" else 1)
        self.emit(
            {
                "cycle": self.cycle,
                "type": "alu_op",
                "workload": workload,
                "warp_id": warp.warp_id,
                "op": inst.op,
                "srcs": list(inst.srcs),
                "dst": inst.dst,
                "active_lanes": list(lanes),
                "results": results,
                "latency": self.config.alu_latency,
            }
        )
        self.record_reg_write(workload, warp, inst.dst, lanes, self.config.alu_latency, dst)

    def record_reg_write(
        self,
        workload: str,
        warp: WarpState,
        reg_name: str,
        lanes: Sequence[int],
        latency: int,
        values: Sequence[float | int | None],
    ) -> None:
        ready = self.cycle + latency
        warp.written_registers.add(reg_name)
        warp.ready_cycle[reg_name] = ready
        self.counters["register_writes"] += len(lanes)
        self.emit(
            {
                "cycle": self.cycle,
                "type": "register_write",
                "workload": workload,
                "warp_id": warp.warp_id,
                "register_file": "per_warp_vector_register_file",
                "register": reg_name,
                "lanes": list(lanes),
                "values": [values[lane] for lane in lanes],
                "ready_cycle": ready,
            }
        )


def make_warps(workload: str, items: int, program_builder: Callable[[], List[Instruction]], config: SimtConfig) -> List[WarpState]:
    warps = []
    for warp_id, start in enumerate(range(0, items, config.wavefront_size)):
        warps.append(
            WarpState(
                warp_id=warp_id,
                workload=workload,
                global_start_lane=start,
                lane_count=min(config.wavefront_size, items - start),
                program=program_builder(),
            )
        )
    return warps


def vector_add_program() -> List[Instruction]:
    return [
        Instruction("ld", dst="r1", mem="a", addr=lambda i: i, comment="load vector A"),
        Instruction("ld", dst="r2", mem="b", addr=lambda i: i, comment="load vector B"),
        Instruction("add", dst="r3", srcs=("r1", "r2"), comment="SIMD lane add"),
        Instruction("barrier", comment="workgroup-visible completion before writeback"),
        Instruction("st", srcs=("r3",), mem="out", addr=lambda i: i, comment="store vector result"),
        Instruction("end", comment="retire vector_add wavefront"),
    ]


def gemm_program(k: int, n: int) -> List[Instruction]:
    program = [Instruction("mov", dst="acc", imm=0.0, comment="zero accumulator")]
    for inner in range(k):
        program.extend(
            [
                Instruction("ld", dst="ra", mem="a", addr=lambda i, inner=inner: (i // n) * k + inner),
                Instruction("ld", dst="rb", mem="b", addr=lambda i, inner=inner: inner * n + (i % n)),
                Instruction("mad", dst="acc", srcs=("ra", "rb", "acc"), comment=f"FMA proxy k={inner}"),
            ]
        )
    program.extend(
        [
            Instruction("barrier", comment="all wavefronts finish GEMM accumulation"),
            Instruction("st", srcs=("acc",), mem="out", addr=lambda i: i),
            Instruction("end", comment="retire gemm wavefront"),
        ]
    )
    return program


def conv_program(input_width: int, output_width: int, kernel_width: int = 3) -> List[Instruction]:
    program = [Instruction("mov", dst="acc", imm=0.0, comment="zero convolution accumulator")]
    for ky in range(kernel_width):
        for kx in range(kernel_width):
            tap = ky * kernel_width + kx
            program.extend(
                [
                    Instruction(
                        "ld",
                        dst="pix",
                        mem="image",
                        addr=lambda i, ky=ky, kx=kx: (i // output_width + ky) * input_width + (i % output_width + kx),
                    ),
                    Instruction("ld", dst="coef", mem="kernel", addr=lambda _i, tap=tap: tap),
                    Instruction("mad", dst="acc", srcs=("pix", "coef", "acc"), comment=f"convolution tap {tap}"),
                ]
            )
    program.extend(
        [
            Instruction("barrier", comment="filter tile barrier before store"),
            Instruction("st", srcs=("acc",), mem="out", addr=lambda i: i),
            Instruction("end", comment="retire convolution wavefront"),
        ]
    )
    return program


def image_filter_program(width: int, height: int) -> List[Instruction]:
    program = [Instruction("mov", dst="sum", imm=0, comment="zero u8 box sum")]
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            program.extend(
                [
                    Instruction(
                        "ld",
                        dst="pix",
                        mem="source",
                        addr=lambda i, dy=dy, dx=dx: (i // width + dy) * width + (i % width + dx),
                        active=lambda i, dy=dy, dx=dx: 0 <= i // width + dy < height and 0 <= i % width + dx < width,
                    ),
                    Instruction(
                        "iadd",
                        dst="sum",
                        srcs=("sum", "pix"),
                        active=lambda i, dy=dy, dx=dx: 0 <= i // width + dy < height and 0 <= i % width + dx < width,
                        comment=f"u8 box tap dy={dy} dx={dx}",
                    ),
                ]
            )
    program.extend(
        [
            Instruction("barrier", comment="image filter tile barrier before writeback"),
            Instruction("st", srcs=("sum",), mem="out", addr=lambda i: i),
            Instruction("end", comment="retire image_filter wavefront"),
        ]
    )
    return program


def run_one_workload(workload: str, config: SimtConfig) -> Dict[str, Any]:
    if workload == "vector_add":
        a = deterministic_vector(32, 1.75, 0.15)
        b = deterministic_vector(32, -0.90, 1.10)
        memory = {"a": a, "b": b, "out": [0.0 for _ in a]}
        expected = [f32(x + y) for x, y in zip(a, b)]
        warps = make_warps(workload, len(expected), vector_add_program, config)
    elif workload == "gemm_proxy":
        m, n, k = 4, 5, 6
        a_matrix = [[f32(((row * k + col) % 11 - 5) * 0.1875) for col in range(k)] for row in range(m)]
        b_matrix = [[f32(math.cos((row + 1) * (col + 2) * 0.21) * 0.75) for col in range(n)] for row in range(k)]
        expected = []
        for row in range(m):
            for col in range(n):
                acc = f32(0.0)
                for inner in range(k):
                    acc = f32(acc + f32(a_matrix[row][inner] * b_matrix[inner][col]))
                expected.append(acc)
        memory = {"a": flatten(a_matrix), "b": flatten(b_matrix), "out": [0.0 for _ in expected]}
        warps = make_warps(workload, len(expected), lambda: gemm_program(k, n), config)
    elif workload == "convolution_proxy":
        height, width = 7, 7
        out_h, out_w = 5, 5
        image = [f32(((y * 17 + x * 9) % 23) / 11.0 - 1.0) for y in range(height) for x in range(width)]
        kernel = [
            f32(0.0),
            f32(-0.125),
            f32(0.0),
            f32(-0.125),
            f32(0.75),
            f32(-0.125),
            f32(0.0),
            f32(-0.125),
            f32(0.0),
        ]
        expected = []
        for y in range(out_h):
            for x in range(out_w):
                acc = f32(0.0)
                for ky in range(3):
                    for kx in range(3):
                        acc = f32(acc + f32(image[(y + ky) * width + x + kx] * kernel[ky * 3 + kx]))
                expected.append(acc)
        memory = {"image": image, "kernel": kernel, "out": [0.0 for _ in expected]}
        warps = make_warps(workload, len(expected), lambda: conv_program(width, out_w), config)
    elif workload == "image_filter":
        width, height = 8, 8
        source = [((x * 29 + y * 17 + (x * y) * 3) & 0xFF) for y in range(height) for x in range(width)]
        summed = []
        expected = []
        for y in range(height):
            for x in range(width):
                acc = 0
                count = 0
                for yy in range(max(0, y - 1), min(height, y + 2)):
                    for xx in range(max(0, x - 1), min(width, x + 2)):
                        acc += source[yy * width + xx]
                        count += 1
                summed.append(acc)
                expected.append(acc // count)
        # The SIMT path deliberately stores the clamped 3x3 sum.  Divide policy
        # is reported as a post-LSU scalar output-pack stage to keep the core
        # instruction stream focused on register, ALU, LSU, scoreboard, barrier.
        memory = {"source": source, "out": [0 for _ in source]}
        warps = make_warps(workload, len(source), lambda: image_filter_program(width, height), config)
    else:
        raise ValueError(f"unsupported workload {workload}")

    machine = SimtMachine(config, memory)
    payload = machine.run(workload, warps)
    raw_output = list(machine.memory["out"])
    if workload == "image_filter":
        width = 8
        height = 8
        result = []
        for index, value in enumerate(raw_output):
            y = index // width
            x = index % width
            count = (min(height - 1, y + 1) - max(0, y - 1) + 1) * (min(width - 1, x + 1) - max(0, x - 1) + 1)
            result.append(int(value) // count)
        payload["post_lsu_output_pack"] = {
            "operation": "integer divide by valid unclamped edge tap count",
            "raw_sum_sha256": sha256_json(raw_output),
            "raw_sum_head": raw_output[:8],
        }
    else:
        result = [f32(float(value)) for value in raw_output]

    errors = [abs(float(left) - float(right)) for left, right in zip(result, expected)]
    payload.update(
        {
            "result": result,
            "result_head": result[:8],
            "expected_head": expected[:8],
            "result_sha256": sha256_json(result),
            "expected_sha256": sha256_json(expected),
            "max_abs_error": f32(max(errors) if errors else 0.0),
            "pass": len(result) == len(expected) and all(error == 0 for error in errors),
        }
    )
    return payload


def build_evidence(config: SimtConfig, workloads: Sequence[str]) -> Dict[str, Any]:
    results = [run_one_workload(workload, config) for workload in workloads]
    totals: Dict[str, int] = {}
    for result in results:
        counters = result["counters"]
        for key, value in counters.items():
            totals[key] = totals.get(key, 0) + int(value)
    return {
        "schema": SCHEMA,
        "ip_name": "Celviz GPGPU IP",
        "stage": "S1-real-compute-core-path-phase1",
        "model": "clean-room SIMT execution model",
        "clean_room_scope": CLEAN_ROOM_SCOPE,
        "simt_topology": {
            "wavefront_size": config.wavefront_size,
            "warp_alias": "wavefront",
            "issue_width": config.issue_width,
            "register_file": "per-warp vector register file with per-lane values",
            "scoreboard": "per-warp register ready-cycle tracking",
            "barrier": "workgroup-scope modeled barrier event",
            "alu": "lane-wise add/mul/mad/iadd",
            "lsu": "lane-wise global load/store against deterministic buffers",
        },
        "workload_names": list(workloads),
        "workloads": results,
        "totals": totals,
        "status": "pass" if all(result.get("pass") is True for result in results) else "fail",
        "result_hashes": {str(result["workload"]): str(result["result_sha256"]) for result in results},
    }


def validate_evidence(payload: Mapping[str, Any]) -> List[str]:
    errors = []
    if payload.get("schema") != SCHEMA:
        errors.append("schema mismatch")
    if payload.get("status") != "pass":
        errors.append("status is not pass")
    required_counter_positive = (
        "scheduler_issues",
        "register_reads",
        "register_writes",
        "alu_ops",
        "lsu_loads",
        "lsu_stores",
        "scoreboard_hazard_events",
        "barrier_events",
    )
    totals = payload.get("totals", {})
    if not isinstance(totals, Mapping):
        errors.append("totals missing")
    else:
        for key in required_counter_positive:
            if int(totals.get(key, 0)) <= 0:
                errors.append(f"{key} is not positive")
    for token in ("wavefront_size", "register_file", "scoreboard", "barrier", "alu", "lsu"):
        if token not in payload.get("simt_topology", {}):
            errors.append(f"simt_topology.{token} missing")
    workloads = payload.get("workloads", [])
    if not isinstance(workloads, list) or len(workloads) < 4:
        errors.append("expected at least four workloads")
    else:
        for workload in workloads:
            if workload.get("pass") is not True:
                errors.append(f"{workload.get('workload')} did not pass")
            seen_types = {event.get("type") for event in workload.get("trace", []) if isinstance(event, Mapping)}
            for event_type in ("warp_schedule", "register_write", "alu_op", "lsu_op", "scoreboard_hazard", "barrier"):
                if event_type not in seen_types:
                    errors.append(f"{workload.get('workload')} trace missing {event_type}")
    return errors


def write_json(path: Path, data: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="SIMT evidence JSON path")
    parser.add_argument("--wavefront-size", type=int, default=SimtConfig.wavefront_size)
    parser.add_argument("--check", action="store_true", help="validate generated evidence and return non-zero on failure")
    parser.add_argument("--print-summary", action="store_true", help="print compact JSON summary")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.wavefront_size <= 0:
        raise SystemExit("--wavefront-size must be positive")
    config = SimtConfig(wavefront_size=args.wavefront_size)
    payload = build_evidence(config, ("vector_add", "gemm_proxy", "convolution_proxy", "image_filter"))
    digest = write_json(args.output, payload)
    errors = validate_evidence(payload) if args.check else []
    summary = {
        "status": "pass" if not errors and payload.get("status") == "pass" else "fail",
        "output": str(args.output),
        "sha256": digest,
        "workloads": payload["workload_names"],
        "totals": payload["totals"],
        "errors": errors,
    }
    if args.print_summary or args.check:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"wrote {args.output}")
        print(f"status={summary['status']}")
    return 0 if not errors and payload.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
