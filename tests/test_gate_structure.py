"""Структурные правила гейта под профиль требований.

Три правила, каждое механическое: заголовки с нужными номерами присутствуют, в таблицах с
колонкой источника нет пустых ячеек, идентификаторы не повторяются. Всё, что решает регулярка,
не должно стоить круга критика — и не должно зависеть от языка документа, поэтому заголовки
ищутся по номерам, а колонка источника — по любому из двух названий.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import gate
import pytest


def run(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, *argv: str
) -> tuple[dict[str, Any], int]:
    monkeypatch.setattr(sys, "argv", ["gate.py", *argv])
    code = gate.main()
    report: dict[str, Any] = json.loads(capsys.readouterr().out)
    return report, code


def write(tmp_path: Path, text: str) -> Path:
    target = tmp_path / "doc.md"
    target.write_text(text, encoding="utf-8")
    return target


DOC = """# Requirements: Демо — v1

## Индекс документов

| # | Файл | Тип |
| --- | --- | --- |
| 1 | `01-brief` | brief |

## 1. Роли

| Роль | Описание | Источник |
| --- | --- | --- |
| Админ | ведёт запись | `01-brief: §2` |

## 3. Функциональные требования

### 3.1 Запись

| ID | Требование | Приоритет | Источник |
| --- | --- | --- | --- |
| FR-001 | одно | MUST | `01-brief: §1 — «…»` |
| FR-002 | два | MUST | |
| FR-002 | три | SHOULD | `02-chat: 08.09 11:20, Настя` |

## 8. Вопросы

### 8.1 Конфликты

| # | Conflict | Sources in conflict | Resolution |
| --- | --- | --- | --- |
| C-001 | x | a vs b | RESOLVED |
"""


# --- required headings ------------------------------------------------------------------


def test_missing_numbered_headings_are_named() -> None:
    missing = gate.missing_headings(DOC, [r"^##\s+1\.", r"^##\s+2\.", r"^###\s+8\.2"])
    assert missing == [r"^##\s+2\.", r"^###\s+8\.2"]


def test_require_heading_via_cli(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc = write(tmp_path, DOC)
    report, _ = run(
        capsys,
        monkeypatch,
        "--file",
        str(doc),
        "--require-heading",
        r"^##\s+1\.",
        "--require-heading",
        r"^##\s+9\.",
    )
    assert report["ok"] is False
    assert report["measures"]["missing_headings"] == [r"^##\s+9\."]
    assert any("required heading missing" in p for p in report["problems"])


# --- rows have a source -----------------------------------------------------------------


def test_rows_without_source_are_named_by_id() -> None:
    """Пустая ячейка источника называется по первой ячейке строки, чтобы писатель нашёл её."""
    assert gate.rows_without_source(DOC) == ["FR-002"]


def test_table_without_source_column_is_ignored() -> None:
    text = "| # | Файл | Тип |\n| --- | --- | --- |\n| 1 | a | brief |\n"
    assert gate.rows_without_source(text) == []


def test_source_column_recognised_in_both_languages() -> None:
    en = "| ID | Requirement | Source |\n| --- | --- | --- |\n| FR-001 | x | |\n"
    ru = "| ID | Требование | Источник |\n| --- | --- | --- |\n| FR-001 | x | |\n"
    assert gate.rows_without_source(en) == ["FR-001"]
    assert gate.rows_without_source(ru) == ["FR-001"]


def test_rows_have_source_via_cli(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc = write(tmp_path, DOC)
    report, _ = run(capsys, monkeypatch, "--file", str(doc), "--rows-have-source")
    assert report["measures"]["rows_without_source"] == ["FR-002"]
    assert any("rows without a source" in p for p in report["problems"])


# --- unique ids -------------------------------------------------------------------------


def test_duplicate_ids_are_named() -> None:
    assert gate.duplicate_ids(DOC, r"\b(?:FR|NFR|BR|C|G|A)-\d{3}\b") == ["FR-002"]


def test_ids_in_prose_references_do_not_count() -> None:
    """Ссылка на FR-001 из текста или из ячейки Source — не второй FR-001."""
    text = (
        "| ID | Requirement | Source |\n| --- | --- | --- |\n"
        "| FR-001 | x | a |\n| FR-002 | y, see FR-001 | b [C-001] |\n"
        "\nSee FR-001 and FR-002 above.\n"
    )
    assert gate.duplicate_ids(text, r"\b(?:FR|NFR|BR|C|G|A)-\d{3}\b") == []


def test_unique_ids_via_cli(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc = write(tmp_path, DOC)
    report, _ = run(
        capsys, monkeypatch, "--file", str(doc), "--unique-ids", r"\b(?:FR|NFR|BR|C|G|A)-\d{3}\b"
    )
    assert report["measures"]["duplicate_ids"] == ["FR-002"]
    assert any("duplicate ids" in p for p in report["problems"])


def test_clean_document_passes_all_three(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    clean = DOC.replace("| FR-002 | два | MUST | |\n", "").replace(
        "| FR-002 | три", "| FR-003 | три"
    )
    doc = write(tmp_path, clean)
    report, code = run(
        capsys,
        monkeypatch,
        "--file",
        str(doc),
        "--rows-have-source",
        "--unique-ids",
        r"\b(?:FR|NFR|BR|C|G|A)-\d{3}\b",
        "--require-heading",
        r"^##\s+1\.",
        "--require-heading",
        r"^###\s+8\.1",
    )
    assert report["ok"] is True
    assert code == 0
