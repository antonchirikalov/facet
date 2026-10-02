"""Tests for converting office documents in the input folder to markdown.

Read cannot read .docx; without this step a client document in Word would silently drop out
of the analysis.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import to_text


def test_nothing_to_convert(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("x", encoding="utf-8")
    assert to_text.convert(tmp_path) == ([], [], [])


def test_missing_pandoc_is_a_problem(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "scope.docx").write_bytes(b"PK")
    monkeypatch.setattr(to_text.shutil, "which", lambda _: None)
    converted, kept, problems = to_text.convert(tmp_path)
    assert converted == [] and kept == [] and "pandoc not found" in problems[0]


def test_already_converted_is_kept(tmp_path: Path) -> None:
    (tmp_path / "scope.docx").write_bytes(b"PK")
    (tmp_path / "scope.docx.md").write_text("done", encoding="utf-8")
    assert to_text.convert(tmp_path, pandoc="pandoc-not-called") == ([], ["scope.docx"], [])


def test_missing_directory(tmp_path: Path) -> None:
    assert to_text.convert(tmp_path / "missing")[2]


@pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc is not installed")
def test_real_docx_becomes_markdown(tmp_path: Path) -> None:
    import subprocess

    src = tmp_path / "src.md"
    # A Cyrillic file name and Russian text on purpose: client inputs arrive like this.
    src.write_text("# Объём работ\n\nКлиент хочет «быстро».\n", encoding="utf-8")
    subprocess.run(["pandoc", str(src), "-o", str(tmp_path / "Скоуп.docx")], check=True)
    src.unlink()
    converted, _kept, problems = to_text.convert(tmp_path)
    assert problems == [] and converted == ["Скоуп.docx"]
    assert "Объём работ" in (tmp_path / "Скоуп.docx.md").read_text(encoding="utf-8")


def test_recursive_reaches_subfolders(tmp_path: Path) -> None:
    (tmp_path / "call").mkdir()
    (tmp_path / "call" / "notes.docx").write_bytes(b"PK")
    (tmp_path / "call" / "notes.docx.md").write_text("done", encoding="utf-8")
    assert to_text.convert(tmp_path, pandoc="unused")[1] == []
    assert to_text.convert(tmp_path, pandoc="unused", recursive=True)[1] == ["call/notes.docx"]
