#!/usr/bin/env python3
"""Turn the office documents of an input folder into markdown, next to them, with pandoc.

The agent that extracts an input document reads files with Read, and Read refuses a .docx: it
is a zip archive, "This tool cannot read binary files". On one live run the Word documents
were converted by hand before the launch, which is why it worked; a folder handed over as it
came from the client would have lost its scope document without an error.

Every ``<name>.docx`` (or .pptx, .odt, .rtf, .epub) inside ``--dir`` (with ``--recursive``, in its
subfolders too) becomes
``<name>.docx.md``. A file whose markdown already exists is left alone, so a continued run does
not convert twice. The folder is the only argument: file names travel in the report, never on
the command line, because a Cyrillic name on a Windows command line is a name mangled.

The output envelope matches gate.py's.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import toollog

CONVERTIBLE = {".docx", ".pptx", ".odt", ".rtf", ".epub"}


def convert(
    folder: Path, pandoc: str | None = None, recursive: bool = False
) -> tuple[list[str], list[str], list[str]]:
    """(converted, kept, problems): names converted now, names already converted, failures."""
    if not folder.is_dir():
        return [], [], [f"directory missing: {folder.as_posix()}"]
    walk = folder.rglob("*") if recursive else folder.iterdir()
    sources = sorted(p for p in walk if p.is_file() and p.suffix.lower() in CONVERTIBLE)
    if not sources:
        return [], [], []
    tool = pandoc or shutil.which("pandoc")
    if tool is None:
        return [], [], [f"pandoc not found; {len(sources)} office document(s) left unreadable"]
    converted: list[str] = []
    kept: list[str] = []
    problems: list[str] = []
    for src in sources:
        out = src.with_name(src.name + ".md")
        if out.is_file() and out.stat().st_size > 0:
            kept.append(src.relative_to(folder).as_posix())
            continue
        done = subprocess.run(
            [tool, str(src), "-t", "gfm", "--wrap=none", "-o", str(out)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if done.returncode != 0 or not out.is_file() or out.stat().st_size == 0:
            problems.append(
                f"{src.relative_to(folder).as_posix()}: pandoc failed: {(done.stderr or 'empty output').strip()[:200]}"
            )
            continue
        converted.append(src.relative_to(folder).as_posix())
    return converted, kept, problems


def main() -> int:
    p = argparse.ArgumentParser(description="Convert office documents in a folder to markdown.")
    p.add_argument("--dir", type=Path, required=True, help="input folder")
    p.add_argument("--recursive", action="store_true", help="also convert documents in subfolders")
    toollog.add_argument(p)
    args = p.parse_args()
    converted, kept, problems = convert(args.dir, recursive=args.recursive)
    report = {
        "ok": not problems,
        "problems": problems,
        "measures": {"converted": converted, "already_converted": kept},
    }
    toollog.append(args.log, "to_text", report, args.log_note, release=args.log_release)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
