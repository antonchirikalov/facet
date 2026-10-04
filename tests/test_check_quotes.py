"""Tests of checking quotes against their sources.

Every rule here was paid for by a document for a real client: a quote that is not in the
transcript is visible to the client at once, and interface labels in quotation marks reported as
"not found" teach the reader to stop reading the report.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import check_quotes
import pytest

SOURCE = (
    "Jane Roe 20:30\nor maybe you pick a slot and you type in the patient name and pick another slot.\n"
    "John Doe 15:00\nI'd rather it came out of the box and maybe they have a flat fee per misit "
    "plus maybe like a custom add-on.\n"
)


def test_straight_quotes_with_attribution_are_checked() -> None:
    doc = (
        '- "you type in the patient name" (office manager, 20:30)\n'
        '- "a quote nobody said" (owner, 15:00)\n'
        '- a field called "status" is not a quote\n'
    )
    problems, checked = check_quotes.check(doc, SOURCE)
    assert checked == 2 and len(problems) == 1 and "nobody said" in problems[0]


def test_quotes_located_in_an_image_are_not_checked() -> None:
    doc = (
        "| ID | Fact | Source |\n| --- | --- | --- |\n"
        "| F-01 | Sample tax line | demo-08-quote-33m40s.jpg — “Tax 10.1%” |\n"
        "| F-02 | Flat fee | 15:00 John Doe — “a flat fee per misit” |\n"
        "Shown on screen: “Works with no signal” (frame demo-02.jpg)\n"
    )
    problems, checked = check_quotes.check(doc, SOURCE)
    assert checked == 1 and problems == []


def test_attributed_quote_found() -> None:
    doc = "Typed names “you pick a slot and you type in the patient name” (office manager)."
    problems, checked = check_quotes.check(doc, SOURCE)
    assert checked == 1 and problems == []


def test_invented_quote_reported() -> None:
    doc = "“we need this by Friday” (owner)"
    problems, checked = check_quotes.check(doc, SOURCE)
    assert checked == 1 and len(problems) == 1
    assert "we need this by Friday" in problems[0]


def test_bracketed_editor_insertion_and_curly_apostrophe() -> None:
    doc = "“I’d rather it came out of the box” (engineer) and “a flat fee per [visit] plus maybe” (engineer)"
    problems, checked = check_quotes.check(doc, SOURCE)
    assert checked == 2 and problems == []


def test_ellipsis_splits_into_fragments() -> None:
    doc = "“you pick a slot … pick another slot” (office manager)"
    assert check_quotes.check(doc, SOURCE)[0] == []


def test_ui_label_without_attribution_is_not_checked() -> None:
    doc = "The receptionist taps “Generate estimate” and the PDF appears."
    problems, checked = check_quotes.check(doc, SOURCE)
    assert checked == 0 and problems == []


def test_quote_column_of_a_table_is_checked() -> None:
    doc = (
        "| ID | Requirement | In the client's words |\n"
        "| --- | --- | --- |\n"
        "| FR-1 | Typed names | “you type in the patient name” |\n"
        "| FR-2 | Deadline | “ship it by Friday” |\n"
    )
    problems, checked = check_quotes.check(doc, SOURCE)
    assert checked == 2 and len(problems) == 1 and "Friday" in problems[0]


def test_other_columns_are_not_checked() -> None:
    doc = (
        "| ID | Requirement | In the client's words |\n"
        "| --- | --- | --- |\n"
        "| FR-1 | Banner “PRELIMINARY ESTIMATE” shown | “you type in the patient name” |\n"
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
    doc.write_text("“you type in the patient name” (office manager)", encoding="utf-8")
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
    """A directory of extracts as the source: the script cannot list its files itself."""
    doc, folder = tmp_path / "doc.md", tmp_path / "extracts"
    folder.mkdir()
    (folder / "t.md").write_text(SOURCE, encoding="utf-8")
    doc.write_text("“you type in the patient name” (office manager)", encoding="utf-8")
    report = run(capsys, monkeypatch, "--file", str(doc), "--source", str(folder))
    assert report["ok"] is True and report["measures"]["quotes"] == 1
