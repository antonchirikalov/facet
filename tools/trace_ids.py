#!/usr/bin/env python3
"""Every id a document cites exists in the documents it cites from.

A story step that says "(FR-031)" or a pain row that says "answered by D-04" is a promise that a
reader can follow the reference. A reference to an id the requirements never declared is a
claim nobody can check, and it is the commonest way a client-facing text drifts from the
documents it was built on.

An id counts as declared when it opens a table row or a heading line in one of the ``--against``
files (the same rule as gate.py's unique ids). ``--require`` names ids that must be cited at
least once, for example every MUST requirement of the area a story is about.

The output envelope matches gate.py's.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import toollog

DEFAULT_IDS = r"\b(?:FR|NFR|BR|C|D)-\d{2,3}\b"


def declared(text: str, pattern: re.Pattern[str]) -> set[str]:
    ids: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            first = stripped.strip("|").split("|", 1)[0].strip()
            m = pattern.match(first)
            if m:
                ids.add(m.group(0))
        elif stripped.startswith("#"):
            m = pattern.search(stripped)
            if m:
                ids.add(m.group(0))
    return ids


def cited(text: str, pattern: re.Pattern[str]) -> list[str]:
    return list(dict.fromkeys(m.group(0) for m in pattern.finditer(text)))


def check(
    document: str, references: list[str], pattern: str, required: list[str]
) -> tuple[list[str], dict[str, object]]:
    rx = re.compile(pattern)
    known: set[str] = set()
    for ref in references:
        known |= declared(ref, rx)
    refs = cited(document, rx)
    dangling = [i for i in refs if i not in known]
    missing = [i for i in required if i not in refs]
    problems: list[str] = []
    if dangling:
        problems.append(
            f"ids cited but not declared ({len(dangling)}): " + ", ".join(dangling[:15])
        )
    if missing:
        problems.append(f"required ids never cited ({len(missing)}): " + ", ".join(missing[:15]))
    if not refs:
        problems.append("the document cites no id at all")
    measures: dict[str, object] = {
        "cited": len(refs),
        "declared": len(known),
        "dangling": dangling,
        "missing": missing,
    }
    return problems, measures


def main() -> int:
    p = argparse.ArgumentParser(description="Every cited id exists in the referenced documents.")
    p.add_argument("--file", type=Path, required=True, help="document whose citations are checked")
    p.add_argument(
        "--against",
        type=Path,
        action="append",
        required=True,
        help="document that declares ids; repeatable",
    )
    p.add_argument("--ids", default=DEFAULT_IDS, help="regex of an id")
    p.add_argument(
        "--require", action="append", default=[], help="an id that must be cited; repeatable"
    )
    toollog.add_argument(p)
    args = p.parse_args()
    missing_files = [f for f in [args.file, *args.against] if not f.is_file()]
    if missing_files:
        problems = [f"file missing: {f.as_posix()}" for f in missing_files]
        measures: dict[str, object] = {}
    else:
        problems, measures = check(
            args.file.read_text(encoding="utf-8"),
            [a.read_text(encoding="utf-8") for a in args.against],
            args.ids,
            args.require,
        )
    report = {"ok": not problems, "problems": problems, "measures": measures}
    toollog.append(args.log, "trace_ids", report, args.log_note, release=args.log_release)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
