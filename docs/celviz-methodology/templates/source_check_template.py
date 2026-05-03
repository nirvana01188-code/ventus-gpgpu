#!/usr/bin/env python3
"""Celviz reusable source-hook check template.

Instantiate this file into a new IP tool directory, then fill REQUIRED_HOOKS
with project-specific source files and regexes. The template intentionally
fails closed: implementation evidence must live in source, not only artifacts.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


REQUIRED_HOOKS: dict[str, tuple[str, ...]] = {
    "__SOURCE_FILE__": (
        r"__REQUIRED_SOURCE_HOOK__",
    ),
}


def main() -> int:
    repo_root = Path.cwd()
    errors: list[str] = []
    for relative_path, patterns in REQUIRED_HOOKS.items():
        path = repo_root / relative_path
        if not path.exists():
            errors.append(f"missing source file: {relative_path}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in patterns:
            if not re.search(pattern, text):
                errors.append(f"{relative_path}: missing pattern {pattern}")

    if errors:
        print("celviz_source_hook_check: fail", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print("celviz_source_hook_check: pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
