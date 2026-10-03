#!/usr/bin/env python3
"""Every row of every extract reaches the requirements, or is set aside with a reason.

The requirements writer consolidates fifty to three hundred extract rows into one document, and
nothing short of counting tells whether one of them fell out on the way. A critic asked to walk
the extracts back reads the first ones closely and skims the rest; this ruler does not skim.

An extract row is declared when its first cell opens with a row id (R-01, DE-03, CO-02, RO-04,
F-11, Q-02); its full name is ``<extract file stem>#<row id>``, e.g. ``call-transcript#R-04``.
The requirements cite a row by that full name, usually at the start of a Source cell. A row the
writer deliberately does not carry is listed in the not-carried section (``--not-carried``, the
heading of that section) as a table row whose first cell is the full name and whose second cell
says why.

Problems:
- lost: a declared row neither cited anywhere outside the not-carried section nor listed in it;
- dangling: a full name cited that no extract declares (a typo reads as a trace and is not one);
- not carried without a reason: a not-carried row with an empty reason cell.

The output envelope matches gate.py's.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import toollog

ROW_ID = r"(?:R|DE|CO|RO|F|Q)-\d{2,3}"
FULL = re.compile(r"([A-Za-z0-9._-]+)#(" + ROW_ID + r")\b")
FIRST_ID = re.compile(r"^" + ROW_ID + r"\b")
SHOWN = 20


def cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def declared_rows(extract: str, stem: str) -> list[str]:
    rows: list[str] = []
    for line in extract.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        first = cells(line)[0]
        m = FIRST_ID.match(first)
        if m:
            name = f"{stem}#{m.group(0)}"
            if name not in rows:
                rows.append(name)
    return rows


def split_sections(document: str, heading: re.Pattern[str]) -> tuple[str, str]:
    """The document without the not-carried section, and that section alone."""
    inside: list[str] = []
    outside: list[str] = []
    level = 0
    for line in document.splitlines():
        hashes = len(line) - len(line.lstrip("#"))
        is_heading = 0 < hashes <= 6 and line[hashes : hashes + 1] == " "
        if is_heading and heading.search(line):
            level = hashes
            continue
        if level and is_heading and hashes <= level:
            level = 0
        (inside if level else outside).append(line)
    return "\n".join(outside), "\n".join(inside)


def not_carried_rows(section: str) -> tuple[list[str], list[str]]:
    """Full names listed as not carried, and those among them with no reason."""
    listed: list[str] = []
    bare: list[str] = []
    for line in section.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        row = cells(line)
        m = FULL.match(row[0])
        if not m:
            continue
        name = m.group(0)
        listed.append(name)
        if len(row) < 2 or not row[1].strip(" -—"):
            bare.append(name)
    return listed, bare


def check(
    document: str, extracts: dict[str, str], heading: str
) -> tuple[list[str], dict[str, object]]:
    declared: list[str] = []
    per_extract: dict[str, int] = {}
    for stem, text in sorted(extracts.items()):
        rows = declared_rows(text, stem)
        per_extract[stem] = len(rows)
        declared.extend(rows)
    body, section = split_sections(document, re.compile(heading))
    cited = list(dict.fromkeys(m.group(0) for m in FULL.finditer(body)))
    listed, bare = not_carried_rows(section)
    known = set(declared)
    lost = [r for r in declared if r not in cited and r not in listed]
    dangling = [r for r in dict.fromkeys(cited + listed) if r not in known]
    problems: list[str] = []
    if not declared:
        problems.append("the extracts declare no row ids: nothing can be traced")
    if not section.strip():
        problems.append(f"no not-carried section matching {heading!r}")
    if lost:
        problems.append(
            f"extract rows lost, neither cited nor set aside ({len(lost)}): "
            + ", ".join(lost[:SHOWN])
            + (" ..." if len(lost) > SHOWN else "")
        )
    if dangling:
        problems.append(
            f"cited rows no extract declares ({len(dangling)}): " + ", ".join(dangling[:SHOWN])
        )
    if bare:
        problems.append(f"not carried without a reason ({len(bare)}): " + ", ".join(bare[:SHOWN]))
    carried = [r for r in declared if r in cited]
    measures: dict[str, object] = {
        "declared": len(declared),
        "carried": len(carried),
        "not_carried": len([r for r in declared if r in listed and r not in cited]),
        "lost": lost,
        "dangling": dangling,
        "per_extract": per_extract,
    }
    return problems, measures


def main() -> int:
    p = argparse.ArgumentParser(description="Every extract row is carried or set aside.")
    p.add_argument("--file", type=Path, required=True, help="the requirements document")
    p.add_argument("--extracts", type=Path, required=True, help="folder of extract .md files")
    p.add_argument(
        "--not-carried",
        default=r"^##\s+10\.",
        metavar="REGEX",
        help="heading of the section that lists rows not carried, with the reason",
    )
    toollog.add_argument(p)
    args = p.parse_args()
    problems: list[str]
    measures: dict[str, object]
    if not args.file.is_file() or not args.extracts.is_dir():
        missing = [x for x in (args.file, args.extracts) if not x.exists()]
        problems = [f"missing: {x.as_posix()}" for x in missing] or ["bad arguments"]
        measures = {}
    else:
        extracts = {
            f.stem: f.read_text(encoding="utf-8") for f in sorted(args.extracts.glob("*.md"))
        }
        problems, measures = check(
            args.file.read_text(encoding="utf-8"), extracts, args.not_carried
        )
    report = {"ok": not problems, "problems": problems, "measures": measures}
    toollog.append(args.log, "extract_trace", report, args.log_note, release=args.log_release)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
