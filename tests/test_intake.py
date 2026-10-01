"""Tests for the inventory of the input folder.

Every case comes from one live run: a skipped subfolder holding the call, our notes next to the
client's words, five frames under two names.
"""

from __future__ import annotations

from pathlib import Path

import intake


def make(root: Path, rel: str, data: bytes = b"x") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def test_nested_folders_are_walked(tmp_path: Path) -> None:
    make(tmp_path, "descr.txt")
    make(tmp_path, "call-2026-01-15/transcript.md", b"t")
    make(tmp_path, "call-2026-01-15/frames/client-01.jpg", b"img")
    files, problems = intake.inventory(tmp_path)
    assert problems == []
    assert {f["path"] for f in files} == {
        "descr.txt",
        "call-2026-01-15/transcript.md",
        "call-2026-01-15/frames/client-01.jpg",
    }


def test_duplicates_by_content_not_name(tmp_path: Path) -> None:
    make(tmp_path, "frames/01-plan.jpg", b"same")
    make(tmp_path, "frames/client-01-plan.jpg", b"same")
    make(tmp_path, "frames/02-other.jpg", b"other")
    files, _ = intake.inventory(tmp_path)
    dup = [f for f in files if "duplicate_of" in f]
    assert len(dup) == 1 and dup[0]["duplicate_of"] == "frames/01-plan.jpg"


def test_kinds_separate_our_notes_from_client_words(tmp_path: Path) -> None:
    make(tmp_path, "call/digest.md", b"a")
    make(tmp_path, "sciencesoft-internal-pre-call-summary.txt", b"b")
    make(tmp_path, "call/transcript.md", b"c")
    make(tmp_path, "Phase 1 Scope.docx", b"d")
    make(tmp_path, "call/frames/x.jpg", b"e")
    make(tmp_path, "misc.txt", b"f")
    make(tmp_path, "Acme Clinics - Sciencesoft initial call.docx", b"g")
    make(tmp_path, "sciencesoft-proposal-draft.md", b"h")
    kinds = {f["path"]: f["kind"] for f in intake.inventory(tmp_path)[0]}
    assert kinds["call/digest.md"] == "ours"
    assert kinds["sciencesoft-internal-pre-call-summary.txt"] == "ours"
    assert kinds["call/transcript.md"] == "client"
    assert kinds["Phase 1 Scope.docx"] == "client"
    assert kinds["call/frames/x.jpg"] == "media"
    assert kinds["misc.txt"] == "unknown"
    assert kinds["Acme Clinics - Sciencesoft initial call.docx"] == "client"
    assert kinds["sciencesoft-proposal-draft.md"] == "ours"


def test_read_with(tmp_path: Path) -> None:
    for rel in ("a.docx", "b.pdf", "c.md", "d.mp4", "e.png"):
        make(tmp_path, rel, rel.encode())
    how = {f["path"]: f["read_with"] for f in intake.inventory(tmp_path)[0]}
    assert how["a.docx"].startswith("pandoc")
    assert how["b.pdf"].startswith("pdf-reader")
    assert how["c.md"] == "read"
    assert how["d.mp4"].startswith("frames")
    assert how["e.png"] == "read (image)"


def test_missing_directory(tmp_path: Path) -> None:
    files, problems = intake.inventory(tmp_path / "missing")
    assert files == [] and problems
