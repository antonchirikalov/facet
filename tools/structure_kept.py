#!/usr/bin/env python3
"""A wording pass changes words, not the document's structure.

A text stage (a slop critic and a writer answering it) is there to change how things are said.
On one live run it also took out two of the three notes the profile requires, because the critic
read them as repetition, and nothing measured it: every other gate checks the document as it is,
not what it lost. This ruler compares the document before the wording pass with the document
now, and names what went missing:

- a heading that is gone (matched by its text);
- fewer blockquote lines (notes, callouts, quoted client words set apart);
- fewer table rows;
- fewer figure placeholders.

More of any of them is fine; a rename of a heading counts as a loss, because headings are what
other sections and the reader refer to. It knows nothing about any document type.

The output envelope matches gate.py's.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import toollog

HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
FIGURE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
SEPARATOR = re.compile(r"^\s*\|?\s*:?-{3,}")


def shape(text: str) -> dict[str, object]:
    headings: list[str] = []
    quotes = rows = figures = 0
    for line in text.splitlines():
        m = HEADING.match(line)
        if m:
            headings.append(f"{m.group(1)} {m.group(2)}")
        if line.lstrip().startswith(">"):
            quotes += 1
        if line.lstrip().startswith("|") and not SEPARATOR.match(line):
            rows += 1
        figures += len(FIGURE.findall(line))
    return {
        "headings": headings,
        "blockquote_lines": quotes,
        "table_rows": rows,
        "figures": figures,
    }


def check(before: str, after: str) -> tuple[list[str], dict[str, object]]:
    b, a = shape(before), shape(after)
    problems: list[str] = []
    gone = [h for h in b["headings"] if h not in a["headings"]]  # type: ignore[operator]
    if gone:
        problems.append(f"headings gone ({len(gone)}): " + "; ".join(gone[:10]))
    for key, what in (
        ("blockquote_lines", "blockquote lines"),
        ("table_rows", "table rows"),
        ("figures", "figure placeholders"),
    ):
        was, now = int(str(b[key])), int(str(a[key]))
        if now < was:
            problems.append(f"fewer {what}: {was} before, {now} now")
    measures: dict[str, object] = {
        "before": {k: v for k, v in b.items() if k != "headings"},
        "after": {k: v for k, v in a.items() if k != "headings"},
        "headings_gone": gone,
    }
    return problems, measures


def main() -> int:
    p = argparse.ArgumentParser(description="A wording pass keeps the document's structure.")
    p.add_argument("--before", type=Path, required=True, help="the document before the pass")
    p.add_argument("--file", type=Path, required=True, help="the document now")
    toollog.add_argument(p)
    args = p.parse_args()
    absent = [x for x in (args.before, args.file) if not x.is_file()]
    if absent:
        problems = [f"file missing: {x.as_posix()}" for x in absent]
        measures: dict[str, object] = {}
    else:
        problems, measures = check(
            args.before.read_text(encoding="utf-8"), args.file.read_text(encoding="utf-8")
        )
    report = {"ok": not problems, "problems": problems, "measures": measures}
    toollog.append(args.log, "structure_kept", report, args.log_note, release=args.log_release)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
