#!/usr/bin/env python3
"""Our words where the client has their own: the mirror check of a client-facing text.

The client voice sheet (section 3, "Their vocabulary") lists each term the client uses, what they
mean by it, and the words our drafts tend to substitute for it. A substitute in our prose reads
as a text about someone else's business, even when it is correct English. This finds every
substitute outside quotes and code, and names the client's term to use instead.

The table is read from the sheet itself, so the check follows the client, not a fixed list. The
third column may hold several substitutes separated by commas, slashes or semicolons.

The output envelope matches gate.py's.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import toollog

SECTION = re.compile(r"^##\s+3\.")
QUOTED = re.compile(r"“[^”]*”|\"[^\"\n]*\"|`[^`\n]*`|«[^»]*»")
FENCE = re.compile(r"```.*?```", re.DOTALL)


def vocabulary(sheet: str) -> list[tuple[str, list[str]]]:
    """(client term, substitutes) from the vocabulary table of a client voice sheet."""
    pairs: list[tuple[str, list[str]]] = []
    inside = False
    for line in sheet.splitlines():
        if line.startswith("## "):
            inside = bool(SECTION.match(line))
            continue
        if not inside or not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3 or set(cells[0]) <= set("-: "):
            continue
        term, subs = cells[0], cells[2]
        if term.lower() in {"their term", "term", "термин", "их термин", "party", "сторона"}:
            continue
        words = [w.strip(" .“”\"'") for w in re.split(r"[,/;]", subs)]
        words = [w for w in words if w and w.lower() not in {"—", "-", "none", "нет"}]
        if words:
            pairs.append((term.strip("“”\"'"), words))
    return pairs


def substitutes_in(text: str, pairs: list[tuple[str, list[str]]]) -> list[str]:
    prose = QUOTED.sub(" ", FENCE.sub(" ", text))
    found: list[str] = []
    for term, words in pairs:
        for word in words:
            n = len(re.findall(rf"(?<!\w){re.escape(word)}(?!\w)", prose, re.IGNORECASE))
            if n:
                found.append(f"“{word}” {n}x where the client says “{term}”")
    return found


def main() -> int:
    p = argparse.ArgumentParser(description="Our words where the client has their own.")
    p.add_argument("--file", type=Path, required=True, help="client-facing document")
    p.add_argument("--voice", type=Path, required=True, help="the client voice sheet")
    toollog.add_argument(p)
    args = p.parse_args()
    problems: list[str] = []
    measures: dict[str, object] = {}
    missing = [f for f in (args.file, args.voice) if not f.is_file()]
    if missing:
        problems = [f"file missing: {f.as_posix()}" for f in missing]
    else:
        pairs = vocabulary(args.voice.read_text(encoding="utf-8"))
        found = substitutes_in(args.file.read_text(encoding="utf-8"), pairs)
        measures = {"terms": len(pairs), "substitutes": found}
        if not pairs:
            problems.append("the voice sheet has no vocabulary table in section 3")
        problems.extend(f"our word instead of the client's: {f}" for f in found)
    report = {"ok": not problems, "problems": problems, "measures": measures}
    toollog.append(args.log, "vocab", report, args.log_note, release=args.log_release)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
