"""Тесты линейки правок.

Круг правки — это два-семь десятков мелких изменений в документе на 90 КБ. По одному вызову
Edit за ход каждый вызов перечитывает весь контекст: живой круг сделал 72 правки и прочитал
10 миллионов кэшированных токенов — дороже, чем переписать документ. Одним Write модель
перепечатывает 90 КБ ради трёх, и никто не проверяет, что ещё поехало. Поэтому писатель
пишет правки один раз, списком, а применяет их питон.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import apply_edits
import pytest

DOC = "| FR-001 | одно | MUST |\n| FR-002 | два | MUST |\n| FR-003 | три | SHOULD |\nконец\n"


def run(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, *argv: str
) -> tuple[dict[str, Any], int]:
    monkeypatch.setattr(sys, "argv", ["apply_edits.py", *argv])
    code = apply_edits.main()
    report: dict[str, Any] = json.loads(capsys.readouterr().out)
    return report, code


def test_edits_apply_in_order_against_the_running_text() -> None:
    edits = [
        {"old": "| два |", "new": "| два с половиной |"},
        {"old": "половиной", "new": "хвостиком"},
    ]
    text, applied, problems = apply_edits.apply(DOC, edits)
    assert applied == [1, 2] and problems == []
    assert "| два с хвостиком |" in text


def test_unmatched_and_ambiguous_are_named_by_index_and_skipped() -> None:
    edits = [
        {"old": "нет такого", "new": "x"},
        {"old": "| MUST |", "new": "| COULD |"},
        {"old": "три", "new": "3"},
    ]
    text, applied, problems = apply_edits.apply(DOC, edits)
    assert applied == [3]
    assert problems[0].startswith("edit 1 not found")
    assert "edit 2 ambiguous (2 matches)" in problems[1]
    assert "| 3 |" in text and "| MUST |" in text


def test_file_is_left_alone_when_nothing_applied(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc = tmp_path / "d.md"
    doc.write_text(DOC, encoding="utf-8")
    edits = tmp_path / "e.json"
    edits.write_text(json.dumps([{"old": "нет", "new": "да"}]), encoding="utf-8")
    report, code = run(capsys, monkeypatch, "--file", str(doc), "--edits", str(edits))
    assert report["ok"] is False and report["measures"]["applied"] == 0
    assert doc.read_text(encoding="utf-8") == DOC
    assert code == 0


def test_cli_applies_and_reports_measures(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc = tmp_path / "d.md"
    doc.write_text(DOC, encoding="utf-8")
    edits = tmp_path / "e.json"
    edits.write_text(
        json.dumps(
            [{"old": "| одно |", "new": "| раз |"}, {"old": "конец", "new": "финал"}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    log = tmp_path / "tools.jsonl"
    report, code = run(
        capsys, monkeypatch, "--file", str(doc), "--edits", str(edits), "--log", str(log)
    )
    assert report["ok"] is True and code == 0
    assert report["measures"] == {
        "edits": 2,
        "chars_before": len(DOC),
        "chars": len(DOC) - 3,
        "applied": 2,
        "unmatched": 0,
    }
    assert "| раз |" in doc.read_text(encoding="utf-8") and "финал" in doc.read_text(
        encoding="utf-8"
    )
    assert json.loads(log.read_text(encoding="utf-8").splitlines()[-1])["tool"] == "apply_edits"


def test_malformed_edits_file_is_a_problem(tmp_path: Path) -> None:
    bad = tmp_path / "e.json"
    bad.write_text("{not json", encoding="utf-8")
    edits, problems = apply_edits.load_edits(bad)
    assert edits == [] and "not JSON" in problems[0]
    missing, problems = apply_edits.load_edits(tmp_path / "нет.json")
    assert missing == [] and "missing" in problems[0]


def test_empty_old_is_rejected(tmp_path: Path) -> None:
    e = tmp_path / "e.json"
    e.write_text(json.dumps([{"old": "", "new": "x"}, {"old": "a", "new": "b"}]), encoding="utf-8")
    edits, problems = apply_edits.load_edits(e)
    assert len(edits) == 1 and "empty old" in problems[0]
