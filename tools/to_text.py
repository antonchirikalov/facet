#!/usr/bin/env python3
"""Turn the office documents of an input folder into markdown, next to them.

The agent that extracts an input document reads files with Read, and Read refuses a .docx: it
is a zip archive, "This tool cannot read binary files". On one live run the Word documents
were converted by hand before the launch, which is why it worked; a folder handed over as it
came from the client would have lost its scope document without an error.

Every ``<name>.docx`` (or .pptx, .odt, .rtf, .epub, through pandoc; .xlsx, through the standard
library) inside ``--dir`` (with ``--recursive``, in its subfolders too) becomes ``<name>.docx.md``. A file whose markdown already exists is left alone, so a continued run does
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
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import toollog

PANDOC = {".docx", ".pptx", ".odt", ".rtf", ".epub"}
# Pandoc does not read spreadsheets, and a client's requirements list is often one. An .xlsx is a
# zip of XML, so the standard library reads it: one section per sheet, one table per section.
SPREADSHEET = {".xlsx"}
CONVERTIBLE = PANDOC | SPREADSHEET
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def column_index(ref: str) -> int:
    letters = "".join(ch for ch in ref if ch.isalpha())
    n = 0
    for ch in letters.upper():
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def cell_text(text: str) -> str:
    return " ".join(text.split()).replace("|", "/")


def xlsx_to_markdown(path: Path) -> str:
    """Every sheet with any content as a markdown table; the first non-empty row is the header."""
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            root = ElementTree.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall("m:si", NS):
                shared.append("".join(x.text or "" for x in si.iter(f"{{{NS['m']}}}t")))
        workbook = ElementTree.fromstring(z.read("xl/workbook.xml"))
        rels = ElementTree.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        target = {r.get("Id"): r.get("Target", "") for r in rels}
        parts: list[str] = []
        for sheet in workbook.findall("m:sheets/m:sheet", NS):
            ref = target.get(sheet.get(REL) or "", "")
            member = ref.lstrip("/") if ref.startswith("/") else f"xl/{ref}"
            if member not in names:
                continue
            rows: list[list[str]] = []
            for row in ElementTree.fromstring(z.read(member)).iter(f"{{{NS['m']}}}row"):
                values: dict[int, str] = {}
                for c in row.findall("m:c", NS):
                    kind = c.get("t")
                    v = c.find("m:v", NS)
                    if kind == "s" and v is not None and v.text:
                        text = shared[int(v.text)]
                    elif kind == "inlineStr":
                        text = "".join(x.text or "" for x in c.iter(f"{{{NS['m']}}}t"))
                    else:
                        text = v.text if v is not None and v.text else ""
                    text = cell_text(text)
                    if text:
                        values[column_index(c.get("r", "A"))] = text
                if values:
                    rows.append([values.get(i, "") for i in range(max(values) + 1)])
            if not rows:
                continue
            width = max(len(r) for r in rows)
            rows = [r + [""] * (width - len(r)) for r in rows]
            lines = [f"## {sheet.get('name', 'Sheet')}", ""]
            lines.append("| " + " | ".join(rows[0]) + " |")
            lines.append("|" + " --- |" * width)
            lines.extend("| " + " | ".join(r) + " |" for r in rows[1:])
            parts.append("\n".join(lines))
    return "\n\n".join(parts) + "\n"


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
    converted: list[str] = []
    kept: list[str] = []
    problems: list[str] = []
    for src in sources:
        out = src.with_name(src.name + ".md")
        name = src.relative_to(folder).as_posix()
        if out.is_file() and out.stat().st_size > 0:
            kept.append(name)
            continue
        if src.suffix.lower() in SPREADSHEET:
            try:
                text = xlsx_to_markdown(src)
            except (
                zipfile.BadZipFile,
                KeyError,
                ElementTree.ParseError,
                ValueError,
                IndexError,
            ) as exc:
                problems.append(f"{name}: not a readable spreadsheet: {exc}")
                continue
            if not text.strip():
                problems.append(f"{name}: the spreadsheet has no cells with content")
                continue
            out.write_text(text, encoding="utf-8")
            converted.append(name)
            continue
        if tool is None:
            problems.append(f"{name}: pandoc not found, left unreadable")
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
                f"{name}: pandoc failed: {(done.stderr or 'empty output').strip()[:200]}"
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
