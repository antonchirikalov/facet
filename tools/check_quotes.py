#!/usr/bin/env python3
"""Check that every attributed quote in a document occurs verbatim in the sources.

A client-facing document puts the client's own words next to each requirement. That is its
strength and its risk: a quote the client never said, or said differently, is the fastest way to
lose the reader who was in the room. On the Vista run every quote of the client edition was
checked this way by a throwaway script; the same check caught three wrong speaker attributions in
our own call digest. It belongs in the gate, not in a scratchpad.

Which quotes are checked. Not every string in quotation marks is the client's: a document also
quotes its own interface ("Generate estimate") and banner texts, and flagging those trains people
to ignore the report. A quote is checked when it is attributed:

- it sits in a table column whose header names quotes or the client's words ("In the client's
  words", "Quote", "Source", "Цитата"), or
- it is followed by a parenthesised attribution, `“…” (owner)`.

`--all` checks every curly-quoted string instead.

Matching is forgiving only where transcripts are noisy: curly and straight apostrophes, case,
runs of whitespace and markdown emphasis are normalised; `…` and `...` split a quote into
fragments that must each occur; a `[bracketed]` insertion (an editor's `[pier]` for a transcript's
"peer") is skipped. Everything else must match character for character.

The output envelope matches gate.py's.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import toollog

QUOTE = re.compile(r"“([^”]+)”")
ATTRIBUTED = re.compile(r"“([^”]+)”\s*\(([^)]{1,60})\)")
QUOTE_HEADER = re.compile(r"words|quote|source|цитат|слова", re.IGNORECASE)
SPLIT = re.compile(r"\[[^\]]*\]|…|\.\.\.")


def normalise(text: str) -> str:
    text = text.replace("’", "'").replace("‘", "'").replace("\\", "")
    text = re.sub(r"[*_]+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.lower().strip(" .,;:")


def table_quotes(document: str) -> list[str]:
    """Quotes that sit in a quote column of a markdown table."""
    found: list[str] = []
    columns: set[int] = set()
    lines = document.splitlines()
    for i, line in enumerate(lines):
        if not line.lstrip().startswith("|"):
            columns = set()
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if re.fullmatch(r"\|?\s*:?-{3,}.*", nxt):
            columns = {j for j, c in enumerate(cells) if QUOTE_HEADER.search(c)}
            continue
        if re.fullmatch(r"\|?\s*:?-{3,}.*", line.strip()):
            continue
        for j in columns:
            if j < len(cells):
                found.extend(QUOTE.findall(cells[j]))
    return found


def quotes_to_check(document: str, check_all: bool) -> list[str]:
    if check_all:
        return QUOTE.findall(document)
    seen: list[str] = []
    for q in table_quotes(document) + [m.group(1) for m in ATTRIBUTED.finditer(document)]:
        if q not in seen:
            seen.append(q)
    return seen


def check(document: str, sources: str, check_all: bool = False) -> tuple[list[str], int]:
    """Problems (one per quote not found) and the number of quotes checked."""
    haystack = normalise(sources)
    quotes = quotes_to_check(document, check_all)
    problems = []
    for q in quotes:
        fragments = [f for f in SPLIT.split(q) if normalise(f)]
        missing = [f.strip() for f in fragments if normalise(f) not in haystack]
        if missing:
            problems.append(f"not in the sources: “{q}” (missing: {' | '.join(missing)})")
    return problems, len(quotes)


def expand(paths: list[Path]) -> list[Path]:
    """A folder stands for its .md and .txt files: a script cannot list a folder to name them."""
    out: list[Path] = []
    for path in paths:
        if path.is_dir():
            out.extend(sorted(f for f in path.rglob("*") if f.suffix in {".md", ".txt"}))
        elif path.is_file():
            out.append(path)
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Every attributed quote must occur in the sources.")
    p.add_argument("--file", type=Path, required=True, help="document to check")
    p.add_argument(
        "--source",
        type=Path,
        action="append",
        required=True,
        metavar="FILE",
        help="file, or folder of .md/.txt files, the quotes must come from; repeatable",
    )
    p.add_argument("--all", action="store_true", help="check every curly-quoted string")
    toollog.add_argument(p)
    args = p.parse_args()

    problems: list[str] = []
    files = expand(args.source)
    missing = [s for s in [args.file, *args.source] if not s.exists()]
    if missing or not files:
        problems = [f"file missing: {m.as_posix()}" for m in missing] or ["no source files"]
        checked = 0
    else:
        document = args.file.read_text(encoding="utf-8")
        sources = "\n".join(s.read_text(encoding="utf-8") for s in files)
        problems, checked = check(document, sources, args.all)
    report = {
        "ok": not problems,
        "problems": problems,
        "measures": {"quotes": checked, "not_found": len(problems)},
    }
    toollog.append(args.log, "check_quotes", report, args.log_note, release=args.log_release)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
