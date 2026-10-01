"""Тесты перевода офисных документов во входной папке в markdown.

Read не читает .docx; без этого шага документ клиента в Word пропадал бы из разбора молча.
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
    assert to_text.convert(tmp_path / "нет")[2]


@pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc не установлен")
def test_real_docx_becomes_markdown(tmp_path: Path) -> None:
    import subprocess

    src = tmp_path / "src.md"
    src.write_text("# Объём работ\n\nКлиент хочет «быстро».\n", encoding="utf-8")
    subprocess.run(["pandoc", str(src), "-o", str(tmp_path / "Скоуп.docx")], check=True)
    src.unlink()
    converted, _kept, problems = to_text.convert(tmp_path)
    assert problems == [] and converted == ["Скоуп.docx"]
    assert "Объём работ" in (tmp_path / "Скоуп.docx.md").read_text(encoding="utf-8")
