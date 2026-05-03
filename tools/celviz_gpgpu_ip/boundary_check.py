#!/usr/bin/env python3
"""Boundary checker for active Celviz GPGPU IP acceptance surfaces.

The check is intentionally small and dependency-free. It only scans Rank 1
acceptance surfaces and fails when those active surfaces cite superseded
graphics-IP evidence roots as active references.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


DEFAULT_ACCEPTANCE_ROOTS = (
    "artifacts/rank_01_vivante_3d_gpgpu_ip",
    "docs/celviz-gpgpu-ip",
)
DEFAULT_FORBIDDEN_ROOTS = (
    "artifacts/rank_12_vivante_3d_gpu_ip",
    "docs/celviz-gpu-ip",
)
SKIP_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "node_modules",
    }
)
TEXT_BYTES_SAMPLE = 8192
HISTORICAL_CONTEXT_MARKERS = (
    "audit context",
    "boundary",
    "cannot satisfy",
    "do not use",
    "excluded",
    "graphics-only",
    "historical",
    "history/style",
    "not active",
    "not be counted",
    "not completion evidence",
    "preserv",
    "quarantine",
    "reference-only",
    "superseded",
    "supersession",
)


@dataclass(frozen=True)
class Finding:
    """One forbidden path reference inside an active acceptance surface."""

    file: str
    line: int
    column: int
    forbidden_root: str
    excerpt: str


@dataclass(frozen=True)
class ScanResult:
    """Serializable summary of a boundary scan."""

    repo_root: Path
    acceptance_roots: tuple[str, ...]
    forbidden_roots: tuple[str, ...]
    scanned_files: int
    skipped_binary_files: int
    missing_roots: tuple[str, ...]
    findings: tuple[Finding, ...]

    @property
    def ok(self) -> bool:
        return not self.findings


def _repo_relative(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _is_probably_text(path: Path) -> bool:
    try:
        sample = path.read_bytes()[:TEXT_BYTES_SAMPLE]
    except OSError:
        return False
    if b"\x00" in sample:
        return False
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _iter_files(root: Path) -> Iterable[Path]:
    if root.is_file():
        yield root
        return
    if not root.is_dir():
        return

    stack = [root]
    while stack:
        current = stack.pop()
        try:
            children = sorted(current.iterdir(), key=lambda item: item.name)
        except OSError:
            continue
        for child in children:
            if child.is_dir():
                if child.name not in SKIP_DIRS:
                    stack.append(child)
            elif child.is_file():
                yield child


def _normalize_for_search(text: str) -> str:
    return text.replace("\\", "/")


def _line_excerpt(line: str, column: int, width: int = 160) -> str:
    clean = line.strip()
    if len(clean) <= width:
        return clean
    zero_based = max(column - 1, 0)
    start = max(zero_based - width // 3, 0)
    end = min(start + width, len(line))
    start = max(end - width, 0)
    prefix = "..." if start else ""
    suffix = "..." if end < len(line) else ""
    return prefix + line[start:end].strip() + suffix


def _line_has_historical_context(lines: Sequence[str], line_index: int) -> bool:
    start = max(line_index - 6, 0)
    end = min(line_index + 7, len(lines))
    context = " ".join(lines[start:end]).lower()
    return any(marker in context for marker in HISTORICAL_CONTEXT_MARKERS)


def _scan_text_file(path: Path, repo_root: Path, forbidden_roots: Sequence[str]) -> list[Finding]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []

    findings: list[Finding] = []
    rel_file = _repo_relative(path, repo_root)
    normalized_forbidden = tuple(_normalize_for_search(root) for root in forbidden_roots)
    lines = text.splitlines()
    for line_index, line in enumerate(lines):
        line_no = line_index + 1
        normalized_line = _normalize_for_search(line)
        for original_root, normalized_root in zip(forbidden_roots, normalized_forbidden):
            search_from = 0
            while True:
                index = normalized_line.find(normalized_root, search_from)
                if index == -1:
                    break
                if _line_has_historical_context(lines, line_index):
                    search_from = index + len(normalized_root)
                    continue
                findings.append(
                    Finding(
                        file=rel_file,
                        line=line_no,
                        column=index + 1,
                        forbidden_root=original_root,
                        excerpt=_line_excerpt(line, index + 1),
                    )
                )
                search_from = index + len(normalized_root)
    return findings


def scan_boundaries(
    repo_root: Path,
    acceptance_roots: Sequence[str] = DEFAULT_ACCEPTANCE_ROOTS,
    forbidden_roots: Sequence[str] = DEFAULT_FORBIDDEN_ROOTS,
) -> ScanResult:
    """Scan active acceptance roots for references to forbidden evidence roots."""

    root = repo_root.resolve()
    missing_roots: list[str] = []
    findings: list[Finding] = []
    scanned_files = 0
    skipped_binary_files = 0

    for acceptance_root in acceptance_roots:
        absolute_root = root / acceptance_root
        if not absolute_root.exists():
            missing_roots.append(acceptance_root)
            continue
        for path in _iter_files(absolute_root):
            if not _is_probably_text(path):
                skipped_binary_files += 1
                continue
            scanned_files += 1
            findings.extend(_scan_text_file(path, root, forbidden_roots))

    return ScanResult(
        repo_root=root,
        acceptance_roots=tuple(acceptance_roots),
        forbidden_roots=tuple(forbidden_roots),
        scanned_files=scanned_files,
        skipped_binary_files=skipped_binary_files,
        missing_roots=tuple(missing_roots),
        findings=tuple(findings),
    )


def result_to_dict(result: ScanResult) -> dict[str, object]:
    return {
        "ok": result.ok,
        "repo_root": result.repo_root.as_posix(),
        "acceptance_roots": list(result.acceptance_roots),
        "forbidden_roots": list(result.forbidden_roots),
        "scanned_files": result.scanned_files,
        "skipped_binary_files": result.skipped_binary_files,
        "missing_roots": list(result.missing_roots),
        "finding_count": len(result.findings),
        "findings": [
            {
                "file": finding.file,
                "line": finding.line,
                "column": finding.column,
                "forbidden_root": finding.forbidden_root,
                "excerpt": finding.excerpt,
            }
            for finding in result.findings
        ],
    }


def print_readable(result: ScanResult) -> None:
    status = "PASS" if result.ok else "FAIL"
    print(f"Celviz GPGPU boundary check: {status}")
    print(f"repo_root: {result.repo_root.as_posix()}")
    print(f"scanned_files: {result.scanned_files}")
    print(f"skipped_binary_files: {result.skipped_binary_files}")
    if result.missing_roots:
        print("missing_acceptance_roots:")
        for root in result.missing_roots:
            print(f"  - {root}")
    print("acceptance_roots:")
    for root in result.acceptance_roots:
        print(f"  - {root}")
    print("forbidden_roots:")
    for root in result.forbidden_roots:
        print(f"  - {root}")
    if result.ok:
        print(
            "No forbidden active-evidence references were found in Rank 1 "
            "surfaces; historical/superseded references are allowed only when "
            "they are explicitly non-acceptance context."
        )
        return

    print(f"findings: {len(result.findings)}")
    for finding in result.findings:
        print(
            f"  - {finding.file}:{finding.line}:{finding.column}: "
            f"{finding.forbidden_root}"
        )
        print(f"    {finding.excerpt}")


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Scan active Rank 1 Celviz GPGPU surfaces and fail if they use "
            "superseded graphics-IP roots as active acceptance evidence."
        )
    )
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[2],
        type=Path,
        help="repository root to scan; defaults to the root containing this tool",
    )
    parser.add_argument(
        "--acceptance-root",
        action="append",
        dest="acceptance_roots",
        help=(
            "active acceptance root relative to repo root; may be repeated "
            f"(default: {', '.join(DEFAULT_ACCEPTANCE_ROOTS)})"
        ),
    )
    parser.add_argument(
        "--forbidden-root",
        action="append",
        dest="forbidden_roots",
        help=(
            "forbidden evidence root string; may be repeated "
            f"(default: {', '.join(DEFAULT_FORBIDDEN_ROOTS)})"
        ),
    )
    parser.add_argument(
        "--format",
        choices=("readable", "json"),
        default="readable",
        help="output format for later script integration",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = scan_boundaries(
        repo_root=args.repo_root,
        acceptance_roots=tuple(args.acceptance_roots or DEFAULT_ACCEPTANCE_ROOTS),
        forbidden_roots=tuple(args.forbidden_roots or DEFAULT_FORBIDDEN_ROOTS),
    )
    if args.format == "json":
        print(json.dumps(result_to_dict(result), indent=2, sort_keys=True))
    else:
        print_readable(result)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
