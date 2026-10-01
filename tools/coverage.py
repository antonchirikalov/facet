#!/usr/bin/env python3
"""Check a coverage map against the document it covers and the sources it quotes.

The map is written by the coverage mapper before the proposal is judged: one row per ask,
worry or question the client raised, with their verbatim words and the place in the document
that answers it. On one live proposal the reader found those one by one after the draft was
"done" — how the app is distributed, that front-desk staff would need training, that standard
visit types would be good — and each cost a revision. A map makes the omission visible before
anyone reads the draft; this tool makes the map itself honest.

A row passes when:

- its id is unique;
- its words are in curly quotes and occur in the sources (the quote checker's normalisation);
- "Answered in" names "section N" with a "## N." heading in the document, optionally followed
  by a subheading that exists under it, or begins with "out of scope" and gives a reason.

The map is a markdown table whose header has the columns ID, Words and Answered in (any order,
other columns allowed). Exit code is 0 either way; the verdict travels in the JSON.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import toollog
from check_quotes import SPLIT, expand, normalise

QUOTE = re.compile(r"“([^”]+)”")
TABLE_LINE = re.compile(r"^\s*\|.*\|\s*$")
TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{3,}")
SECTION = re.compile(r"^section\s+(\d+)\b\s*[,:;—-]?\s*(.*)$", re.IGNORECASE)
OUT_OF_SCOPE = re.compile(r"^out of scope\b\s*[,:;—-]?\s*(.*)$", re.IGNORECASE)
H2 = re.compile(r"^##[ \t]+(\d+)\.")
H3 = re.compile(r"^#{3,6}[ \t]+(.*\S)")


def cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def rows_of(map_text: str) -> tuple[list[dict[str, str]], list[str]]:
    """Rows of the first table that has ID, Words and Answered in columns."""
    lines = map_text.splitlines()
    for i, line in enumerate(lines):
        if not (TABLE_LINE.match(line) and i + 1 < len(lines) and TABLE_RULE.match(lines[i + 1])):
            continue
        header = [h.lower() for h in cells(line)]
        need = {"id": None, "words": None, "answered in": None}
        for j, h in enumerate(header):
            for key in need:
                if h.startswith(key):
                    need[key] = j
        if None in need.values():
            continue
        rows = []
        for body in lines[i + 2 :]:
            if not TABLE_LINE.match(body):
                break
            c = cells(body)
            rows.append(
                {k: (c[j] if j is not None and j < len(c) else "") for k, j in need.items()}
            )
        return rows, []
    return [], ["no table with ID, Words and Answered in columns"]


def subheadings(document: str) -> dict[int, list[str]]:
    """The headings under each "## N." section, lower-cased."""
    out: dict[int, list[str]] = {}
    current: int | None = None
    for line in document.splitlines():
        h2 = H2.match(line)
        if h2:
            current = int(h2.group(1))
            out[current] = []
            continue
        if line.startswith("## "):
            current = None
            continue
        h3 = H3.match(line)
        if h3 and current is not None:
            out[current].append(h3.group(1).strip().lower())
    return out


def check(map_text: str, document: str, sources: str) -> tuple[list[str], dict[str, object]]:
    rows, problems = rows_of(map_text)
    sections = subheadings(document)
    haystack = normalise(sources)
    seen: set[str] = set()
    placed = out_of_scope = 0
    for row in rows:
        rid = row["id"] or "(no id)"
        if rid in seen:
            problems.append(f"{rid}: duplicate id")
        seen.add(rid)
        quotes = QUOTE.findall(row["words"])
        if not quotes:
            problems.append(f"{rid}: words are not a curly-quoted verbatim quote")
        for q in quotes:
            fragments = [f for f in SPLIT.split(q) if normalise(f)]
            if any(normalise(f) not in haystack for f in fragments):
                problems.append(f"{rid}: not in the sources: “{q}”")
        where = row["answered in"].strip()
        section = SECTION.match(where)
        scope = OUT_OF_SCOPE.match(where)
        if section:
            n, sub = int(section.group(1)), section.group(2).strip().strip(".").lower()
            if n not in sections:
                problems.append(f"{rid}: section {n} does not exist")
            elif sub and not any(sub in h for h in sections[n]):
                problems.append(f"{rid}: section {n} has no heading “{section.group(2)}”")
            else:
                placed += 1
        elif scope:
            if not scope.group(1).strip():
                problems.append(f"{rid}: out of scope without a reason")
            else:
                out_of_scope += 1
        else:
            problems.append(f"{rid}: not answered (“{where or 'empty'}”)")
    measures = {"rows": len(rows), "placed": placed, "out_of_scope": out_of_scope}
    return problems, measures


def main() -> int:
    p = argparse.ArgumentParser(description="Every client ask in the coverage map has its place.")
    p.add_argument("--map", type=Path, required=True, help="the coverage map (markdown table)")
    p.add_argument("--file", type=Path, required=True, help="the document the map covers")
    p.add_argument(
        "--source",
        type=Path,
        action="append",
        required=True,
        metavar="FILE",
        help="file, or folder of .md/.txt files, the words must come from; repeatable",
    )
    toollog.add_argument(p)
    args = p.parse_args()

    missing = [s for s in [args.map, args.file, *args.source] if not s.exists()]
    files = expand(args.source)
    if missing or not files:
        problems = [f"file missing: {m.as_posix()}" for m in missing] or ["no source files"]
        measures: dict[str, object] = {}
    else:
        problems, measures = check(
            args.map.read_text(encoding="utf-8"),
            args.file.read_text(encoding="utf-8"),
            "\n".join(s.read_text(encoding="utf-8") for s in files),
        )
    report = {"ok": not problems, "problems": problems, "measures": measures}
    toollog.append(args.log, "coverage", report, args.log_note, release=args.log_release)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
