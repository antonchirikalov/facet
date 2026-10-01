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


# --- sequential ids ---------------------------------------------------------------------


def test_sequential_ids_name_the_gap() -> None:
    """Клиентская редакция перенумерована: пропущенный номер читается как вычеркнутое требование."""
    text = (
        "| ID | Requirement |\n| --- | --- |\n"
        "| FR-001 | a |\n| FR-002 | b |\n| FR-004 | c |\n| NFR-001 | d |\n"
        "\nSee FR-003 in prose: a reference, not a declaration.\n"
    )
    assert gate.id_gaps(text, r"\b(?:FR|NFR)-\d{3}\b") == ["FR-004 after FR-002"]


def test_sequential_ids_first_must_be_one() -> None:
    text = "| ID | x |\n| --- | --- |\n| D-02 | a |\n"
    assert gate.id_gaps(text, r"\bD-\d{2}\b") == ["D-02 first"]


def test_sequential_ids_via_cli(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc = write(tmp_path, "| ID | x |\n| --- | --- |\n| FR-001 | a |\n| FR-003 | b |\n")
    report, _ = run(capsys, monkeypatch, "--file", str(doc), "--sequential-ids", r"\bFR-\d{3}\b")
    assert report["measures"]["id_gaps"] == ["FR-003 after FR-001"]
    assert any("out of sequence" in p for p in report["problems"])


# --- numbered figure captions -----------------------------------------------------------


def test_figures_numbered_in_order_pass() -> None:
    text = (
        "Text.\n\n![A](figures/a.png)\n\n*Figure 1. What A shows.*\n\n"
        "More.\n\n![B](figures/b.png)\n*Figure 2. What B shows.*\n"
    )
    assert gate.figure_caption_problems(text) == []


def test_figure_without_caption_is_named_by_path() -> None:
    """Картинка без подписи: клиент не может на неё сослаться, и гейт называет её по пути."""
    text = "![A](figures/a.png)\n\nPlain paragraph.\n"
    assert gate.figure_caption_problems(text) == ["figures/a.png: no numbered caption"]


def test_figure_numbered_out_of_order() -> None:
    text = "![A](figures/a.png)\n*Figure 1. A.*\n\n![B](figures/b.png)\n*Figure 3. B.*\n"
    assert gate.figure_caption_problems(text) == ["figures/b.png: numbered 3, expected 2"]


def test_figure_caption_in_russian() -> None:
    text = "![А](figures/a.png)\n\n*Рисунок 1. Что показано.*\n"
    assert gate.figure_caption_problems(text) == []


def test_image_inside_code_is_not_a_figure() -> None:
    text = "```\n![x](figures/x.png)\n```\n\n![A](figures/a.png)\n*Figure 1. A.*\n"
    assert gate.figure_caption_problems(text) == []


def test_figures_numbered_via_cli(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc = write(tmp_path, "![A](figures/a.png)\n\nNo caption here.\n")
    report, _ = run(capsys, monkeypatch, "--file", str(doc), "--figures-numbered")
    assert report["measures"]["figure_captions"] == ["figures/a.png: no numbered caption"]
    assert any("numbered caption" in p for p in report["problems"])


# --- proposal style rules ----------------------------------------------------------------


def test_outside_quotes_keeps_the_clients_words() -> None:
    """Клиент в цитате говорит «you»; обращение к читателю ищется только вне цитат."""
    text = (
        '\u201cis it just an app you download\u201d. Acme Clinics decides. We said "your call".\n'
    )
    assert "you" not in gate.outside_quotes(text).lower().replace("\u201cq\u201d", "")


def test_forbid_outside_quotes_via_cli(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc = write(tmp_path, "\u201cyou said\u201d is fine. You are not.\n")
    report, _ = run(capsys, monkeypatch, "--file", str(doc), "--forbid-outside-quotes", r"\byou\b")
    assert report["measures"]["outside_quotes"] == {r"\byou\b": 1}
    assert any("outside quotes" in p for p in report["problems"])


def test_empty_cells_are_named_and_allowed_columns_skipped() -> None:
    """Пустая ячейка читается как забытая; колонку цены для ПМ разрешено оставить пустой."""
    text = (
        "### Backend\n\n| Service | Part | What |\n| --- | --- | --- |\n"
        "| API | Users | a |\n| | Keys | b |\n\n"
        "### Costs\n\n| Phase | Cost, $ |\n| --- | --- |\n| Discovery | |\n"
    )
    assert gate.empty_cells(text, r"cost") == ["Backend: row 2, Service"]
    assert len(gate.empty_cells(text)) == 2


def test_section_refs_resolve_against_numbered_headings() -> None:
    """После перегруппировки разделов «see section 7» указывал не туда."""
    text = "## 1. One\n\nSee section 2 and sections 1 and 3.\n\n## 2. Two\n"
    assert gate.unresolved_section_refs(text) == ["section 3"]


def test_section_refs_via_cli(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc = write(tmp_path, "## 1. One\n\nSee section 9.\n")
    report, _ = run(capsys, monkeypatch, "--file", str(doc), "--section-refs")
    assert report["measures"]["unresolved_section_refs"] == ["section 9"]
