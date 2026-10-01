"""Тесты карты покрытия: каждая просьба клиента либо имеет место в документе, либо явно вне объёма.

На одном живом прогоне распространение через магазины, обучение регистратуры и готовые типы
приёмов читатель находил по одному, уже после «готового» черновика. Карта делает пропуск видимым до чтения, а этот
инструмент не даёт карте соврать: цитата дословная, раздел существует, «вне объёма» с причиной.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import coverage
import pytest

SOURCES = (
    "Jane Roe 38:35: is it just an app they download or do they need a login from us?\n"
    "Jane Roe 22:28: the front desk staff would definitely need some training on it\n"
    "Jane Roe 31:19: having a few standard visit types I think is good too\n"
)
DOC = (
    "## 1. Overview\n\nText.\n\n## 3. A day with the app\n\n"
    "### How the app reaches the clinics\n\nStores.\n\n## 7. Decisions\n\n| a | b |\n"
)
HEADER = "| ID | Who | When | Words | Answered in |\n| --- | --- | --- | --- | --- |\n"


def check(rows: str) -> tuple[list[str], dict[str, object]]:
    return coverage.check(HEADER + rows, DOC, SOURCES)


def test_placed_rows_pass() -> None:
    rows = (
        "| CV-01 | Owner | 38:35 | “is it just an app they download” | "
        "section 3, How the app reaches the clinics |\n"
        "| CV-02 | Owner | 31:19 | “having a few standard visit types” | section 7 |\n"
    )
    problems, measures = check(rows)
    assert problems == []
    assert measures == {"rows": 2, "placed": 2, "out_of_scope": 0}


def test_unanswered_ask_is_named() -> None:
    """Обучение регистратуры, которое на прогоне забыли: пустая ячейка — пропуск, а не мелочь."""
    rows = "| CV-03 | Owner | 22:28 | “need some training on it” | |\n"
    problems, _ = check(rows)
    assert problems == ["CV-03: not answered (“empty”)"]


def test_missing_section_and_heading_are_named() -> None:
    rows = (
        "| CV-01 | Owner | 38:35 | “a login from us” | section 5 |\n"
        "| CV-02 | Owner | 38:35 | “a login from us” | section 3, Licensing |\n"
    )
    problems, _ = check(rows)
    assert problems == [
        "CV-01: section 5 does not exist",
        "CV-02: section 3 has no heading “Licensing”",
    ]


def test_out_of_scope_needs_a_reason() -> None:
    rows = (
        "| CV-01 | Owner | 31:19 | “standard visit types” | out of scope |\n"
        "| CV-02 | Owner | 31:19 | “standard visit types” | out of scope: later phase |\n"
    )
    problems, measures = check(rows)
    assert problems == ["CV-01: out of scope without a reason"]
    assert measures["out_of_scope"] == 1


def test_words_must_be_verbatim_and_ids_unique() -> None:
    rows = (
        "| CV-01 | Owner | 38:35 | “we want an app store” | section 3 |\n"
        "| CV-01 | Owner | 38:35 | the owner asked about stores | section 3 |\n"
    )
    problems, _ = check(rows)
    assert problems == [
        "CV-01: not in the sources: “we want an app store”",
        "CV-01: duplicate id",
        "CV-01: words are not a curly-quoted verbatim quote",
    ]


def test_map_without_the_columns_is_a_problem() -> None:
    problems, _ = coverage.check("| A | B |\n| --- | --- |\n| x | y |\n", DOC, SOURCES)
    assert problems == ["no table with ID, Words and Answered in columns"]


def test_cli_reports_json(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "map.md").write_text(
        HEADER + "| CV-01 | Owner | 38:35 | “a login from us” | section 3 |\n",
        encoding="utf-8",
    )
    (tmp_path / "doc.md").write_text(DOC, encoding="utf-8")
    (tmp_path / "t.md").write_text(SOURCES, encoding="utf-8")
    argv = ["coverage.py", "--map", str(tmp_path / "map.md"), "--file", str(tmp_path / "doc.md")]
    monkeypatch.setattr(sys, "argv", [*argv, "--source", str(tmp_path / "t.md")])
    coverage.main()
    report: dict[str, Any] = json.loads(capsys.readouterr().out)
    assert report["ok"] is True
    assert report["measures"]["placed"] == 1
