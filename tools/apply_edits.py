#!/usr/bin/env python3
"""Apply a list of exact-match edits to a document, and say which ones did not land.

Why this exists: a revision round is twenty to seventy small changes to a 90 KB document.
Made one Edit tool call at a time, each call is a model turn that re-reads the whole context —
a live round made 72 edits and read 10 million cached tokens doing it, more than rewriting the
document from scratch would have cost. Made as one Write of the whole file, the model re-types
90 KB to change 3, and nothing checks what else moved. So the writer writes its edits ONCE, as
a JSON list of {old, new} pairs copied verbatim from the draft, and this ruler applies them:
deterministic, one process, no re-reading.

Rules, all mechanical:
- `old` must occur exactly once in the current text; zero matches or several are reported by
  index and the edit is skipped. Ambiguity is the writer's to resolve by quoting more context.
- edits apply in order, each against the text as the previous ones left it;
- the file is rewritten only if at least one edit applied; an all-unmatched list leaves it alone.

    python tools/apply_edits.py --file draft.md --edits rounds/edits-2.json [--log tools.jsonl]

The edits file: `[{"old": "...", "new": "..."}, ...]`. An `old` that is empty is rejected.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import toollog

MAX_HEAD = 60


def head(text: str) -> str:
    """The first line of an edit, shortened, for a problem message a person can act on."""
    first = text.strip().splitlines()[0] if text.strip() else ""
    return first if len(first) <= MAX_HEAD else first[: MAX_HEAD - 1] + "…"


def load_edits(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    """Read the edits file; a malformed file is a problem, not an empty list."""
    if not path.is_file():
        return [], [f"edits file missing: {path.as_posix()}"]
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [], [f"edits file is not JSON: {exc}"]
    if not isinstance(raw, list):
        return [], ["edits file must be a JSON array of {old, new}"]
    edits: list[dict[str, str]] = []
    problems: list[str] = []
    for i, item in enumerate(raw, 1):
        if not isinstance(item, dict) or "old" not in item or "new" not in item:
            problems.append(f"edit {i}: not an object with old and new")
            continue
        old, new = str(item["old"]), str(item["new"])
        if not old:
            problems.append(f"edit {i}: empty old text")
            continue
        edits.append({"old": old, "new": new})
    return edits, problems


def apply(text: str, edits: list[dict[str, str]]) -> tuple[str, list[int], list[str]]:
    """Apply edits in order. Returns the new text, the indices applied, and the problems."""
    applied: list[int] = []
    problems: list[str] = []
    for i, edit in enumerate(edits, 1):
        count = text.count(edit["old"])
        if count == 0:
            problems.append(f"edit {i} not found: «{head(edit['old'])}»")
            continue
        if count > 1:
            problems.append(f"edit {i} ambiguous ({count} matches): «{head(edit['old'])}»")
            continue
        text = text.replace(edit["old"], edit["new"], 1)
        applied.append(i)
    return text, applied, problems


def main() -> int:
    p = argparse.ArgumentParser(description="Apply exact-match edits to a document.")
    p.add_argument("--file", dest="target", type=Path, required=True, help="the document")
    p.add_argument("--edits", type=Path, required=True, help="JSON array of {old, new}")
    p.add_argument("--strict", action="store_true", help="also exit 1 when any edit did not land")
    toollog.add_argument(p)
    args = p.parse_args()

    measures: dict[str, Any] = {}
    edits, problems = load_edits(args.edits)
    measures["edits"] = len(edits)
    if not args.target.is_file():
        problems.append(f"document missing: {args.target.as_posix()}")
        applied: list[int] = []
    else:
        text = args.target.read_text(encoding="utf-8")
        new_text, applied, apply_problems = apply(text, edits)
        problems.extend(apply_problems)
        if applied:
            args.target.write_text(new_text, encoding="utf-8")
        measures["chars_before"] = len(text)
        measures["chars"] = len(new_text) if applied else len(text)
    measures["applied"] = len(applied)
    measures["unmatched"] = len(edits) - len(applied)

    report = {"ok": not problems, "problems": problems, "measures": measures}
    toollog.append(args.log, "apply_edits", report, args.log_note, release=args.log_release)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if (problems and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
