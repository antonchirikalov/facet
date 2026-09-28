#!/usr/bin/env python3
"""Inventory an input folder before anything reads it: every file, its duplicates, its kind.

The Vista run started from a look at the top of ``input/`` and missed ``input/call-2026-09-23/``
with the call digest, a cleaner transcript and sixteen screen frames; it was found only when the
user asked. Our own notes sat next to the client's words without a mark, and five frames existed
twice under two names. This walks the whole tree and says, per file:

- ``kind``: ``client`` (the client's own words or documents), ``ours`` (our notes, digests,
  summaries — an interpretation, to be marked as such), ``media`` (images, video, audio), or
  ``unknown`` — a guess from the name and place, meant to be confirmed by a person;
- ``read_with``: how its text is reached (read directly, pandoc, the PDF reader, frames);
- ``duplicate_of``: the first file with the same bytes.

The guess is deliberately conservative: anything not recognisably ours is not called ours.

The output envelope matches gate.py's.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import toollog

# In order of strength: our own notes first, then the client's words, then our name alone. The
# Vista call transcript was named "... - Sciencesoft initial call.docx": a vendor name in a
# recording's title does not make the recording ours.
OURS = re.compile(r"digest|summary|internal|notes?\b|brief|research|call-prep|ours", re.IGNORECASE)
CLIENT = re.compile(
    r"transcript|meeting|recording|\bcall\b|rfp|rfi|scope|requirement|spec|contract|email|client|answers",
    re.IGNORECASE,
)
VENDOR = re.compile(r"sciencesoft|scnsoft", re.IGNORECASE)
TEXT = {".md", ".txt", ".csv", ".json", ".yaml", ".yml", ".html", ".htm"}
MEDIA = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".mov", ".mkv", ".mp3", ".wav", ".m4a"}
READ_WITH = {
    ".docx": "pandoc -t gfm",
    ".doc": "pandoc -t gfm",
    ".pptx": "pandoc -t gfm",
    ".pdf": "pdf-reader MCP",
    ".xlsx": "openpyxl",
    ".mp4": "frames (ffmpeg) + transcript",
    ".mov": "frames (ffmpeg) + transcript",
}


def kind_of(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in MEDIA:
        return "media"
    name = path.as_posix()
    if OURS.search(name):
        return "ours"
    if CLIENT.search(name):
        return "client"
    if VENDOR.search(name):
        return "ours"
    if suffix in {".docx", ".doc", ".pdf", ".pptx", ".xlsx"}:
        return "client"
    return "unknown"


def read_with(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in TEXT:
        return "read"
    if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
        return "read (image)"
    return READ_WITH.get(suffix, "unknown")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def inventory(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    if not root.is_dir():
        return [], [f"directory missing: {root.as_posix()}"]
    seen: dict[str, str] = {}
    files: list[dict[str, Any]] = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        sha = digest(path)
        entry: dict[str, Any] = {
            "path": rel,
            "bytes": path.stat().st_size,
            "kind": kind_of(path.relative_to(root)),
            "read_with": read_with(path),
        }
        if sha in seen:
            entry["duplicate_of"] = seen[sha]
        else:
            seen[sha] = rel
        files.append(entry)
    return files, []


def main() -> int:
    p = argparse.ArgumentParser(description="Inventory an input folder: files, duplicates, kinds.")
    p.add_argument("--dir", type=Path, required=True, help="input folder to walk")
    toollog.add_argument(p)
    args = p.parse_args()
    files, problems = inventory(args.dir)
    counts: dict[str, int] = {}
    for f in files:
        counts[f["kind"]] = counts.get(f["kind"], 0) + 1
    report = {
        "ok": not problems,
        "problems": problems,
        "measures": {
            "files": len(files),
            "duplicates": sum(1 for f in files if "duplicate_of" in f),
            "folders": len({str(Path(f["path"]).parent) for f in files}),
            **{f"kind_{k}": v for k, v in sorted(counts.items())},
        },
        "files": files,
    }
    toollog.append(args.log, "intake", report, args.log_note, release=args.log_release)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
