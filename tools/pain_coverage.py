#!/usr/bin/env python3
"""Every pain and worry of the pain map reaches the proposal in the client's own words.

The pain map numbers the client's pains (P-01 …) and worries (WR-01 …), each with the client's
words in curly quotes. The proposal drops internal ids, so a pain is traced by those words: it
is answered when one of its quotes occurs in the proposal, or when a quote the proposal uses (of
at least ``MIN_QUOTE`` characters) is a part of one of its quotes, since a proposal shortens a
long quote to what reads at a glance.

Problems:
- a pain or worry whose words appear nowhere in the proposal;
- one of the ``--top`` highest-ranked pains first answered at or after ``--early-before``
  (the heading of the first section that is too late, "## 5." by default): the client's main
  problem belongs in the opening sections, not after the architecture.

Matching is the same forgiving matching tools/check_quotes.py uses (apostrophes, case,
whitespace, emphasis; "…" splits a quote into fragments).

The output envelope matches gate.py's.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import toollog
from check_quotes import QUOTE, SPLIT, normalise

ROW_ID = re.compile(r"^(P|WR)-\d{2}\b")
MIN_QUOTE = 15
SHOWN = 15


def pain_rows(pains: str) -> list[tuple[str, list[str]]]:
    """(id, quotes) for every table row that opens with a pain or worry id, in document order."""
    rows: list[tuple[str, list[str]]] = []
    seen: set[str] = set()
    for line in pains.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        m = ROW_ID.match(cells[0])
        if not m or m.group(0) in seen:
            continue
        seen.add(m.group(0))
        rows.append((m.group(0), QUOTE.findall(line)))
    return rows


def fragments(quote: str) -> list[str]:
    return [normalise(f) for f in SPLIT.split(quote) if normalise(f)]


def first_position(quotes: list[str], document: str, doc_quotes: list[str]) -> int:
    """Where the pain is first answered in the normalised document, or -1."""
    haystack = normalise(document)
    best = -1
    for q in quotes:
        parts = fragments(q)
        if parts and all(p in haystack for p in parts):
            pos = haystack.find(parts[0])
            best = pos if best < 0 else min(best, pos)
        whole = normalise(q)
        for dq in doc_quotes:
            short = normalise(dq)
            if len(short) >= MIN_QUOTE and short in whole:
                pos = haystack.find(short)
                if pos >= 0:
                    best = pos if best < 0 else min(best, pos)
    return best


def check(
    pains: str, document: str, top: int, early_before: str
) -> tuple[list[str], dict[str, object]]:
    rows = pain_rows(pains)
    doc_quotes = QUOTE.findall(document)
    cut_line = next((ln for ln in document.splitlines() if re.match(early_before, ln)), None)
    cut = normalise(document).find(normalise(cut_line)) if cut_line else -1
    missing: list[str] = []
    late: list[str] = []
    unquoted: list[str] = []
    answered = 0
    pain_ids = [pid for pid, _ in rows if pid.startswith("P-")]
    for pid, quotes in rows:
        if not quotes:
            unquoted.append(pid)
            continue
        pos = first_position(quotes, document, doc_quotes)
        if pos < 0:
            missing.append(pid)
            continue
        answered += 1
        if pid in pain_ids[:top] and cut >= 0 and pos >= cut:
            late.append(pid)
    problems: list[str] = []
    if not rows:
        problems.append("the pain map declares no P- or WR- rows")
    if missing:
        problems.append(
            f"pains or worries whose words appear nowhere in the proposal ({len(missing)}): "
            + ", ".join(missing[:SHOWN])
        )
    if late:
        problems.append(
            f"top pains first answered only after {early_before!r} ({len(late)}): "
            + ", ".join(late)
        )
    if unquoted:
        problems.append(
            f"pain map rows with no quote to trace ({len(unquoted)}): " + ", ".join(unquoted)
        )
    measures: dict[str, object] = {
        "pains": len(pain_ids),
        "worries": len(rows) - len(pain_ids),
        "answered": answered,
        "missing": missing,
        "late": late,
    }
    return problems, measures


def main() -> int:
    p = argparse.ArgumentParser(description="Every pain of the pain map reaches the proposal.")
    p.add_argument("--pains", type=Path, required=True, help="the pain map")
    p.add_argument("--file", type=Path, required=True, help="the proposal")
    p.add_argument("--top", type=int, default=3, help="how many top pains must come early")
    p.add_argument(
        "--early-before",
        default=r"^##\s+5\.",
        metavar="REGEX",
        help="heading of the first section where a top pain is already too late",
    )
    toollog.add_argument(p)
    args = p.parse_args()
    problems: list[str]
    measures: dict[str, object]
    absent = [x for x in (args.pains, args.file) if not x.is_file()]
    if absent:
        problems = [f"file missing: {x.as_posix()}" for x in absent]
        measures = {}
    else:
        problems, measures = check(
            args.pains.read_text(encoding="utf-8"),
            args.file.read_text(encoding="utf-8"),
            args.top,
            args.early_before,
        )
    report = {"ok": not problems, "problems": problems, "measures": measures}
    toollog.append(args.log, "pain_coverage", report, args.log_note, release=args.log_release)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
