"""Тесты сверки цитат с источниками.

Каждое правило здесь оплачено документом для клиента Vista: цитата, которой нет в транскрипте,
видна заказчику сразу, а подписи интерфейса в кавычках, помеченные как «не найдено», приучают
не читать отчёт.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import check_quotes
import pytest

SOURCE = (
    "Eric Struben 20:30\nor maybe you draw a line and you type in 48 feet and draw another line.\n"
    "Curtis Fry 15:00\nI'd like it to be built in and maybe they have a standard price per peer "
    "plus maybe like a custom add-on.\n"
)


def test_attributed_quote_found() -> None:
    doc = "Typed lengths “you draw a line and you type in 48 feet” (owner)."
    problems, checked = check_quotes.check(doc, SOURCE)
    assert checked == 1 and problems == []


def test_invented_quote_reported() -> None:
    doc = "“we need this by Friday” (owner)"
    problems, checked = check_quotes.check(doc, SOURCE)
    assert checked == 1 and len(problems) == 1
    assert "we need this by Friday" in problems[0]


def test_bracketed_editor_insertion_and_curly_apostrophe() -> None:
    doc = "“I’d like it to be built in” (engineer) and “a standard price per [pier] plus maybe” (engineer)"
    problems, checked = check_quotes.check(doc, SOURCE)
    assert checked == 2 and problems == []


def test_ellipsis_splits_into_fragments() -> None:
    doc = "“you draw a line … draw another line” (owner)"
    assert check_quotes.check(doc, SOURCE)[0] == []


def test_ui_label_without_attribution_is_not_checked() -> None:
    doc = "The technician taps “Generate estimate” and the PDF appears."
    problems, checked = check_quotes.check(doc, SOURCE)
    assert checked == 0 and problems == []


def test_quote_column_of_a_table_is_checked() -> None:
    doc = (
        "| ID | Requirement | In the client's words |\n"
        "| --- | --- | --- |\n"
        "| FR-1 | Typed lengths | “you type in 48 feet” |\n"
        "| FR-2 | Deadline | “ship it by Friday” |\n"
    )
    problems, checked = check_quotes.check(doc, SOURCE)
    assert checked == 2 and len(problems) == 1 and "Friday" in problems[0]


def test_other_columns_are_not_checked() -> None:
    doc = (
        "| ID | Requirement | In the client's words |\n"
        "| --- | --- | --- |\n"
        "| FR-1 | Banner “PRELIMINARY ESTIMATE” shown | “you type in 48 feet” |\n"
    )
    problems, checked = check_quotes.check(doc, SOURCE)
    assert checked == 1 and problems == []


def test_all_mode_checks_every_quote() -> None:
    problems, checked = check_quotes.check("taps “Generate estimate”", SOURCE, check_all=True)
    assert checked == 1 and len(problems) == 1


def run(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, *argv: str
) -> dict[str, Any]:
    monkeypatch.setattr(sys, "argv", ["check_quotes.py", *argv])
    assert check_quotes.main() == 0
    report: dict[str, Any] = json.loads(capsys.readouterr().out)
    return report


def test_cli_report_shape(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc, src = tmp_path / "doc.md", tmp_path / "t.md"
    doc.write_text("“you type in 48 feet” (owner)", encoding="utf-8")
    src.write_text(SOURCE, encoding="utf-8")
    report = run(capsys, monkeypatch, "--file", str(doc), "--source", str(src))
    assert report["ok"] is True
    assert report["measures"] == {"quotes": 1, "not_found": 0}


def test_cli_missing_file_is_a_problem(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    report = run(
        capsys, monkeypatch, "--file", str(tmp_path / "no.md"), "--source", str(tmp_path / "no2.md")
    )
    assert report["ok"] is False and len(report["problems"]) == 2


def test_cli_source_folder(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Папка извлечений как источник: скрипт не умеет перечислить её файлы сам."""
    doc, folder = tmp_path / "doc.md", tmp_path / "extracts"
    folder.mkdir()
    (folder / "t.md").write_text(SOURCE, encoding="utf-8")
    doc.write_text("“you type in 48 feet” (owner)", encoding="utf-8")
    report = run(capsys, monkeypatch, "--file", str(doc), "--source", str(folder))
    assert report["ok"] is True and report["measures"]["quotes"] == 1
