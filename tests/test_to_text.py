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


def write_xlsx(path: Path) -> None:
    """A minimal workbook: one sheet with a shared-string header, a number and an inline string."""
    import zipfile

    main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(
            "xl/workbook.xml",
            f'<workbook xmlns="{main}" xmlns:r="{rel}"><sheets>'
            '<sheet name="Features" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>',
        )
        z.writestr(
            "xl/sharedStrings.xml",
            f'<sst xmlns="{main}"><si><t>Feature</t></si><si><t>Clinics</t></si>'
            "<si><t>Book a | visit</t></si></sst>",
        )
        z.writestr(
            "xl/worksheets/sheet1.xml",
            f'<worksheet xmlns="{main}"><sheetData>'
            '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="C1" t="s"><v>1</v></c></row>'
            '<row r="2"><c r="A2" t="s"><v>2</v></c><c r="C2"><v>4</v></c></row>'
            '<row r="3"><c r="B3" t="inlineStr"><is><t>note</t></is></c></row>'
            "</sheetData></worksheet>",
        )


def test_xlsx_becomes_a_table_per_sheet_without_pandoc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_xlsx(tmp_path / "features.xlsx")
    monkeypatch.setattr(to_text.shutil, "which", lambda _: None)
    converted, _, problems = to_text.convert(tmp_path)
    assert converted == ["features.xlsx"] and problems == []
    text = (tmp_path / "features.xlsx.md").read_text(encoding="utf-8")
    assert "## Features" in text
    assert "| Feature |  | Clinics |" in text
    assert "| Book a / visit |  | 4 |" in text
    assert "|  | note |  |" in text


def test_broken_xlsx_is_a_problem(tmp_path: Path) -> None:
    (tmp_path / "broken.xlsx").write_bytes(b"not a zip")
    converted, _, problems = to_text.convert(tmp_path)
    assert converted == [] and "not a readable spreadsheet" in problems[0]
