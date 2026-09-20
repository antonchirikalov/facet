#!/usr/bin/env python3
"""Deterministic content gates for generated documents.

Why a separate script instead of asking a model: every rule here is arithmetic or a
regex, and a workflow script cannot read the filesystem itself. So a cheap agent runs
this command and returns its JSON, and the orchestrating script branches on the numbers
without ever opening the file. The output format is the one the old engine wrote into
`gate_report.json`, so reports stay comparable across the two implementations.

Prose is measured separately from the file, and that distinction was learned the hard
way: a brief asking for "8 to 12 thousand characters" means readable text, while the
file also carries markdown, tables, fenced formulas and figure captions. A live article
measured 13 662 characters as a file and 11 111 without whitespace; its critic spent a
remark on length in all three of its rounds and the piece still shipped over budget.

Exit code is 0 even when the gate fails: the verdict travels in the JSON, and a non-zero
exit would read to the calling agent as "the command broke". Pass --strict when you want
the process to fail too, which is what a hook wants.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import toollog

FENCED_BLOCK = re.compile(r"^```.*?^```\s*", re.DOTALL | re.MULTILINE)
INLINE_CODE = re.compile(r"`[^`\n]*`")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
TABLE_ROW = re.compile(r"^[ \t]*\|.*\|[ \t]*$\n?", re.MULTILINE)
IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
HEADING_MARK = re.compile(r"^#{1,6}[ \t]+", re.MULTILINE)
LIST_MARK = re.compile(r"^[ \t]*([-*+]|\d+\.)[ \t]+", re.MULTILINE)
BACKTICK = re.compile(r"`+")
EMPHASIS = re.compile(r"(\*\*|__|\*|_)")
BLANKS = re.compile(r"[ \t]*\n[ \t]*")
MSYS_DRIVE = re.compile(r"^/([A-Za-z])(?=/|$)")

# Forbidden patterns come from FILES, not from this module and not from argv.
#
# They used to live here, as a dict of Russian phrases inside a Python tool. That was wrong in
# the ordinary way: a dead-phrase list is editorial policy for one language, the same kind of
# thing as the author's voice profile next to it — data a person edits, not code. Wanting to
# add a phrase should not mean opening a parser.
#
# Not argv either, and that part was right the first time: Cyrillic through a command line on
# Windows depends on the codepage and on which shell the carrying agent picked. A file sidesteps
# it completely — the path is ASCII, the contents are UTF-8 read by Python.
#
# One regex per line. `#` starts a comment, blank lines are ignored. Matched OUTSIDE code:
# fenced blocks and inline code are removed first, because `d_k ** 0.5` is a power and
# `**важно**` is bold, and only the caller knows which was meant.
COMMENT = re.compile(r"^\s*#")
HEADING = re.compile(r"^(#{1,6})[ \t]+(.*\S)")

# A table's source column, by header, in either of the two languages the pipeline writes. The
# requirements profile puts a Source cell on every row; a row with that cell empty is a
# conclusion dressed as a requirement, and a regex finds it before a critic spends a round.
SOURCE_HEADER = re.compile(r"^\s*(source|источник)\b", re.IGNORECASE)
# The column weak-word patterns are applied to: the statement itself, never the Source cell,
# where "where possible" may be a client's own words and is exactly what a citation is for.
STATEMENT_HEADER = re.compile(
    r"^\s*(requirement|требование|rule|правило|statement|утверждение|constraint|ограничение)\b",
    re.IGNORECASE,
)
CYRILLIC = re.compile(r"[а-яА-ЯёЁ]")
LETTER = re.compile(r"[^\W\d_]", re.UNICODE)
TABLE_LINE = re.compile(r"^\s*\|.*\|\s*$")
TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{3,}")


@dataclass
class Section:
    """One heading while it is still open: what it is, and whether anything filled it."""

    level: int
    title: str
    line: int
    filled: bool = False
    has_children: bool = False


def patterns_of(path: Path) -> tuple[list[str], list[str]]:
    """Read one pattern file. A missing file is a problem, not an empty rule set.

    Silently checking nothing is the failure this returns instead of: a gate that found no
    violations because it had no patterns reads exactly like a gate that passed.
    """
    if not path.is_file():
        return [], [f"pattern file missing: {path.as_posix()}"]
    lines = path.read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not COMMENT.match(ln)], []


def outside_code(text: str) -> str:
    """The document with fenced blocks and inline code removed, markup otherwise intact.

    Not `prose_of`: that one also strips emphasis markers, so a bold-hunting pattern would
    find nothing there. Headings, lists and tables stay — a cliché in a table heading is
    still a cliché.
    """
    return INLINE_CODE.sub("", FENCED_BLOCK.sub("", text))


def resolve_path(path: Path) -> Path:
    """Accept the msys spelling of a Windows path.

    The gate stage does not control which shell the agent picks, and the probe run showed
    all three forms for one and the same command the script emitted: Bash with the path
    rewritten to ``/c/Users/…``, PowerShell with a ``cd`` prefix, Bash with the path
    quoted. Git Bash rewrites a drive path on the way to the process, so ``/c/Users/…``
    is what argv actually carries — real for the shell, absent for Python.

    Fallback only, never a rewrite: a path that exists as given is returned untouched, and
    a candidate that does not exist either leaves the original in place so the "output
    missing" message still names the path the caller passed.
    """
    if path.exists():
        return path
    posix = path.as_posix()
    match = MSYS_DRIVE.match(posix)
    if match is None:
        return path
    candidate = Path(f"{match.group(1).upper()}:{posix[match.end() :] or '/'}")
    return candidate if candidate.exists() else path


def prose_of(text: str) -> str:
    """Strip what a reader does not read as sentences.

    Fenced blocks, tables, images and HTML comments go entirely; link syntax collapses
    to its visible text; heading, list, emphasis and code markers are dropped. What
    remains is close to what a person would count as the article's prose.
    """
    t = FENCED_BLOCK.sub("", text)
    t = HTML_COMMENT.sub("", t)
    t = TABLE_ROW.sub("", t)
    t = IMAGE.sub("", t)
    t = LINK.sub(r"\1", t)
    t = HEADING_MARK.sub("", t)
    t = LIST_MARK.sub("", t)
    t = BACKTICK.sub("", t)
    t = EMPHASIS.sub("", t)
    return BLANKS.sub("\n", t).strip()


def empty_sections(text: str, floor: int) -> list[str]:
    """Headings with nothing under them, by title, in order.

    A length floor catches "the agent wrote nothing" and misses the failure that actually
    happens: the agent writes the SHAPE of the artifact — every heading the contract asks for,
    in the right order — and leaves the work out. Measured live: an analysis built from 25
    source files came back as 1 748 bytes of headings alone, which is comfortably past any
    floor a document that size would be given.

    A section counts as filled by any non-blank line that is not itself a heading, and content
    fills every heading open above it — a filled child fills its parent, which is what a reader
    would say looking at it. Only leaves are reported: naming a parent whose subsections are
    empty says the same thing twice and buries the one title worth acting on.
    """
    open_heads: list[Section] = []
    empty: list[Section] = []

    def close() -> None:
        section = open_heads.pop()
        if not section.filled and not section.has_children:
            empty.append(section)

    for number, line in enumerate(text.splitlines()):
        head = HEADING.match(line)
        if head:
            level = len(head.group(1))
            while open_heads and open_heads[-1].level >= level:
                close()
            if open_heads:
                open_heads[-1].has_children = True
            open_heads.append(Section(level, head.group(2), number))
            continue
        if len(line.strip()) < floor:
            continue
        for section in open_heads:
            section.filled = True

    while open_heads:
        close()

    return [section.title for section in sorted(empty, key=lambda s: s.line)]


def split_row(line: str) -> list[str]:
    """Cells of one markdown table row, outer pipes removed, each cell stripped."""
    inner = line.strip()
    inner = inner.removeprefix("|")
    inner = inner.removesuffix("|")
    return [c.strip() for c in inner.split("|")]


def missing_headings(text: str, patterns: list[str]) -> list[str]:
    """Required heading patterns that match no line of the document, in the order given.

    By number, not by name: the profile fixes `## 1.` … `## 9.` and `### 8.1` … `### 8.3`,
    and the names translate with the document's language while the numbers do not.
    """
    lines = text.splitlines()
    return [pattern for pattern in patterns if not any(re.search(pattern, line) for line in lines)]


def rows_without_source(text: str) -> list[str]:
    """First cell of every body row whose source cell is empty, in tables that have one.

    Tables without a Source/Источник header are not judged: the document index has no source
    of its own. A body row is named by its first cell — the ID — so the writer can find it.
    """
    empty: list[str] = []
    source_index: int | None = None
    in_table = False
    for line in text.splitlines():
        if not TABLE_LINE.match(line):
            in_table = False
            source_index = None
            continue
        cells = split_row(line)
        if not in_table:
            in_table = True
            source_index = next(
                (i for i, cell in enumerate(cells) if SOURCE_HEADER.match(cell)), None
            )
            continue
        if TABLE_RULE.match(line) and all(TABLE_RULE.match(c) or not c for c in cells):
            continue
        if source_index is None:
            continue
        if source_index >= len(cells) or not cells[source_index]:
            empty.append(cells[0] if cells and cells[0] else "(row without an id)")
    return empty


def cell_forbidden(text: str, pattern_files: list[Path]) -> tuple[list[tuple[str, str]], list[str]]:
    """(row id, matched phrase) for every weak-word hit inside a statement cell.

    INCOSE R7–R9: vague terms and escape clauses — "where possible", "as appropriate", "fast",
    "etc." — make a requirement unverifiable, and a regex finds them with near-total recall. Only
    the statement column is searched: the same words in a Source cell are the client's quoted
    words, which is what the citation exists to preserve.
    """
    patterns: list[str] = []
    problems: list[str] = []
    for pf in pattern_files:
        found, missing = patterns_of(pf)
        patterns.extend(found)
        problems.extend(missing)
    hits: list[tuple[str, str]] = []
    column: int | None = None
    in_table = False
    for line in text.splitlines():
        if not TABLE_LINE.match(line):
            in_table = False
            column = None
            continue
        cells = split_row(line)
        if not in_table:
            in_table = True
            column = next((i for i, c in enumerate(cells) if STATEMENT_HEADER.match(c)), None)
            continue
        if TABLE_RULE.match(line) and all(TABLE_RULE.match(c) or not c for c in cells):
            continue
        if column is None or column >= len(cells):
            continue
        for pattern in patterns:
            for m in re.finditer(pattern, cells[column], flags=re.IGNORECASE):
                hits.append((cells[0] or "(row without an id)", m.group(0)))
    return hits, problems


def cyrillic_share(text: str) -> float:
    """Share of letters that are Cyrillic, 0.0 when the text has no letters."""
    letters = LETTER.findall(text)
    if not letters:
        return 0.0
    return len(CYRILLIC.findall(text)) / len(letters)


def language_mismatch(text: str, reference: Path, gap: float = 0.5) -> str | None:
    """A problem string when the file and its reference are written in different scripts.

    Cheap and blunt on purpose: it tells Cyrillic from Latin, which is the mismatch that has
    actually happened — a Russian chat extracted in English. A gap of 0.5 between the two
    shares means one is mostly Cyrillic and the other is mostly not.
    """
    ref = resolve_path(reference)
    if not ref.is_file():
        return f"language reference missing: {reference.as_posix()}"
    mine = cyrillic_share(text)
    theirs = cyrillic_share(ref.read_text(encoding="utf-8", errors="replace"))
    if abs(mine - theirs) >= gap:
        return (
            f"language differs from {ref.name}: cyrillic share {mine:.2f} here vs "
            f"{theirs:.2f} in the reference"
        )
    return None


def duplicate_ids(text: str, pattern: str) -> list[str]:
    """Ids that open more than one table row, in first-seen order.

    Only the first cell of a row counts as a declaration; the same id quoted in a Source cell
    or in prose is a reference, and references are what the ids exist for.
    """
    rx = re.compile(pattern)
    seen: set[str] = set()
    dupes: list[str] = []
    for line in text.splitlines():
        if not TABLE_LINE.match(line):
            continue
        cells = split_row(line)
        if not cells:
            continue
        match = rx.search(cells[0])
        if match is None or match.start() != 0:
            continue
        found = match.group(0)
        if found in seen and found not in dupes:
            dupes.append(found)
        seen.add(found)
    return dupes


def main() -> int:
    p = argparse.ArgumentParser(description="Deterministic content gates.")
    p.add_argument("--file", type=Path, help="document to check")
    p.add_argument("--dir", type=Path, help="directory to check for entry count")
    p.add_argument("--max-length", type=int, help="ceiling on file characters, with spaces")
    p.add_argument("--min-length", type=int, help="floor on file characters, with spaces")
    p.add_argument("--max-prose", type=int, help="ceiling on prose characters")
    p.add_argument("--min-prose", type=int, help="floor on prose characters")
    p.add_argument(
        "--forbid",
        action="append",
        default=[],
        metavar="REGEX",
        help="pattern that must not appear (case-insensitive); repeatable",
    )
    p.add_argument(
        "--forbid-file",
        action="append",
        default=[],
        type=Path,
        metavar="PATH",
        help="file of patterns matched outside code, one per line; repeatable",
    )
    p.add_argument(
        "--no-empty-sections",
        nargs="?",
        type=int,
        const=1,
        default=None,
        metavar="MIN_LINE",
        help="every heading must have content under it; optional floor on a line that counts",
    )
    p.add_argument(
        "--require-heading",
        action="append",
        default=[],
        metavar="REGEX",
        help="a heading line matching this pattern must exist; repeatable",
    )
    p.add_argument(
        "--rows-have-source",
        action="store_true",
        help="in every table with a Source/Источник column, every body row fills it",
    )
    p.add_argument(
        "--unique-ids",
        metavar="REGEX",
        help="ids matching this pattern at the start of a table row must be unique",
    )
    p.add_argument(
        "--cell-forbid-file",
        action="append",
        default=[],
        type=Path,
        metavar="PATH",
        help="patterns forbidden inside the Requirement/Rule/Statement column; repeatable",
    )
    p.add_argument(
        "--language-of",
        type=Path,
        metavar="PATH",
        help="the file must be in the same script (Cyrillic/Latin) as this reference file",
    )
    p.add_argument("--min-entries", type=int, help="floor on entries directly inside --dir")
    p.add_argument("--strict", action="store_true", help="also exit 1 when the gate fails")
    toollog.add_argument(p)
    args = p.parse_args()

    problems: list[str] = []
    measures: dict[str, object] = {}

    if args.file is not None:
        target = resolve_path(args.file)
        if not target.exists():
            problems.append(f"output missing: {target.as_posix()}")
        else:
            text = target.read_text(encoding="utf-8")
            chars = len(text)
            prose = len(prose_of(text))
            measures["chars"] = chars
            measures["prose_chars"] = prose

            if args.max_length is not None and chars > args.max_length:
                problems.append(f"max_length {args.max_length} exceeded (got {chars})")
            if args.min_length is not None and chars < args.min_length:
                problems.append(f"min_length {args.min_length} not met (got {chars})")
            if args.max_prose is not None and prose > args.max_prose:
                problems.append(f"max_prose {args.max_prose} exceeded (got {prose})")
            if args.min_prose is not None and prose < args.min_prose:
                problems.append(f"min_prose {args.min_prose} not met (got {prose})")

            if args.no_empty_sections is not None:
                empty = empty_sections(text, args.no_empty_sections)
                measures["empty_sections"] = empty
                if empty:
                    # By name, not by count. The number says something is missing; the name
                    # says what, and only the name tells the caller whether it matters.
                    problems.append(
                        f"headings with nothing under them ({len(empty)}): " + "; ".join(empty[:8])
                    )

            if args.require_heading:
                missing = missing_headings(text, args.require_heading)
                measures["missing_headings"] = missing
                if missing:
                    problems.append(
                        f"required heading missing ({len(missing)}): " + "; ".join(missing)
                    )

            if args.rows_have_source:
                unsourced = rows_without_source(text)
                measures["rows_without_source"] = unsourced
                if unsourced:
                    problems.append(
                        f"rows without a source ({len(unsourced)}): " + ", ".join(unsourced[:12])
                    )

            if args.unique_ids:
                dupes = duplicate_ids(text, args.unique_ids)
                measures["duplicate_ids"] = dupes
                if dupes:
                    problems.append(f"duplicate ids ({len(dupes)}): " + ", ".join(dupes[:12]))

            if args.cell_forbid_file:
                weak, missing = cell_forbidden(text, args.cell_forbid_file)
                problems.extend(missing)
                measures["weak_words"] = [f"{rid}: {phrase}" for rid, phrase in weak]
                if weak:
                    sample = "; ".join(f"{rid} «{phrase}»" for rid, phrase in weak[:10])
                    problems.append(f"weak words in requirement cells ({len(weak)}): {sample}")

            if args.language_of is not None:
                mismatch = language_mismatch(text, args.language_of)
                measures["cyrillic_share"] = round(cyrillic_share(text), 2)
                if mismatch:
                    problems.append(mismatch)

            hits: dict[str, int] = {}
            for pattern in args.forbid:
                found = re.findall(pattern, text, flags=re.IGNORECASE)
                hits[pattern] = len(found)
                if found:
                    sample = ", ".join(sorted({str(f) for f in found})[:3])
                    problems.append(
                        f"forbidden pattern matched {len(found)}x: {pattern} ({sample})"
                    )
            if hits:
                measures["regex"] = hits

            file_hits: dict[str, int] = {}
            prose_markup = outside_code(text)
            for pattern_file in args.forbid_file:
                patterns, missing = patterns_of(pattern_file)
                problems.extend(missing)
                for pattern in patterns:
                    found = re.findall(pattern, prose_markup, flags=re.IGNORECASE)
                    file_hits[pattern] = len(found)
                    if found:
                        # The sample is what makes the problem actionable: the writer gets
                        # the phrase it must remove, not the regex that caught it.
                        sample = ", ".join(sorted({str(f) for f in found})[:3])
                        problems.append(
                            f"{pattern_file.name} matched {len(found)}x: {pattern} ({sample})"
                        )
            if file_hits:
                measures["forbidden"] = file_hits

    if args.dir is not None:
        target_dir = resolve_path(args.dir)
        if not target_dir.is_dir():
            problems.append(f"output directory missing: {target_dir.as_posix()}")
        else:
            entries = sorted(x.name for x in target_dir.iterdir())
            measures["entries"] = len(entries)
            if not entries:
                problems.append("output directory has no content")
            if args.min_entries is not None and len(entries) < args.min_entries:
                problems.append(f"min_entries {args.min_entries} not met (got {len(entries)})")

    report = {"ok": not problems, "problems": problems, "measures": measures}
    toollog.append(args.log, "gate", report, args.log_note, release=args.log_release)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if (problems and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
