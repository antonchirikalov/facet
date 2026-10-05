#!/usr/bin/env python3
"""Every binding requirement is answered somewhere in the design.

A design answers its requirements by citing their ids. A requirement the design never cites is a
requirement nobody designed for, and a critic told to "read the requirements id by id" samples
once the list is long. This ruler reads the requirements' tables and names every binding id the
design does not cite.

A row is binding when its table has a Priority column and the row's priority is MUST, or when its
table has no Priority column at all (non-functional requirements and business rules bind by
nature). The id is the row's first cell, matched by --ids.

The output envelope matches gate.py's.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import toollog

DEFAULT_IDS = r"\b(?:FR|NFR|BR)-\d{3}\b"
SEPARATOR = re.compile(r"^\s*\|?\s*:?-{3,}")
SHOWN = 25


def cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def binding_ids(requirements: str, pattern: re.Pattern[str]) -> list[str]:
    ids: list[str] = []
    lines = requirements.splitlines()
    priority_col: int | None = None
    in_table = False
    for i, line in enumerate(lines):
        if not line.lstrip().startswith("|"):
            in_table = False
            continue
        row = cells(line)
        following = lines[i + 1] if i + 1 < len(lines) else ""
        if not in_table and SEPARATOR.match(following):
            in_table = True
            heads = [h.lower() for h in row]
            priority_col = next((k for k, h in enumerate(heads) if "priority" in h), None)
            continue
        if SEPARATOR.match(line):
            continue
        m = pattern.match(row[0]) if row else None
        if not m:
            continue
        binding = priority_col is None or (
            priority_col < len(row) and "MUST" in row[priority_col].upper()
        )
        if binding and m.group(0) not in ids:
            ids.append(m.group(0))
    return ids


def check(requirements: str, design: str, ids: str) -> tuple[list[str], dict[str, object]]:
    rx = re.compile(ids)
    binding = binding_ids(requirements, rx)
    cited = set(rx.findall(design))
    missing = [i for i in binding if i not in cited]
    problems: list[str] = []
    if not binding:
        problems.append("the requirements declare no binding row: nothing to check")
    if missing:
        problems.append(
            f"binding requirements the design never cites ({len(missing)}): "
            + ", ".join(missing[:SHOWN])
            + (" ..." if len(missing) > SHOWN else "")
        )
    measures: dict[str, object] = {
        "binding": len(binding),
        "cited": len(binding) - len(missing),
        "missing": missing,
    }
    return problems, measures


def main() -> int:
    p = argparse.ArgumentParser(description="Every binding requirement is cited by the design.")
    p.add_argument("--requirements", type=Path, required=True, help="the requirements document")
    p.add_argument("--file", type=Path, required=True, help="the design")
    p.add_argument("--ids", default=DEFAULT_IDS, help="regex of a requirement id")
    toollog.add_argument(p)
    args = p.parse_args()
    absent = [x for x in (args.requirements, args.file) if not x.is_file()]
    problems: list[str]
    measures: dict[str, object]
    if absent:
        problems = [f"file missing: {x.as_posix()}" for x in absent]
        measures = {}
    else:
        problems, measures = check(
            args.requirements.read_text(encoding="utf-8"),
            args.file.read_text(encoding="utf-8"),
            args.ids,
        )
    report = {"ok": not problems, "problems": problems, "measures": measures}
    toollog.append(args.log, "must_covered", report, args.log_note, release=args.log_release)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
