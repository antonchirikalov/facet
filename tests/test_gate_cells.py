"""Правила гейта по ячейкам таблицы и по языку файла.

Слабые слова и клаузы-лазейки (INCOSE R7–R9) ловятся регуляркой, но только в ячейке требования:
в ячейке источника «по возможности» — законная цитата клиента. И язык извлечения обязан
совпадать с языком документа: извлечение чата по-английски принесло английские описания ролей
в русскую таблицу, и заметил это критик, а не гейт.
"""

from __future__ import annotations

from pathlib import Path

import gate

TABLE = """## 3. Функциональные требования

| ID | Требование | Приоритет | Источник |
| --- | --- | --- | --- |
| FR-001 | Система блокирует учётную запись после 5 неверных попыток входа. | MUST | `05: п.8 — «по возможности»` |
| FR-002 | Система по возможности напоминает клиенту о приёме. | SHOULD | `02: раздел 3` |
| FR-003 | Отчёт формируется быстро и удобно. | MUST | `01: п.5` |

## 5. Бизнес-правила

| ID | Правило | Источник |
| --- | --- | --- |
| BR-001 | Обмен с 1С односторонний, и т.д. | `05: п.3` |
"""


def patterns(tmp_path: Path) -> Path:
    p = tmp_path / "weak.txt"
    p.write_text("# комментарий\nпо возможности\n\\bбыстро\\b\nи т\\.?\\s?д\\.\n", encoding="utf-8")
    return p


def test_weak_words_are_found_in_the_requirement_cell_only(tmp_path: Path) -> None:
    hits, problems = gate.cell_forbidden(TABLE, [patterns(tmp_path)])
    assert problems == []
    assert hits == [
        ("FR-002", "по возможности"),
        ("FR-003", "быстро"),
        ("BR-001", "и т.д."),
    ]


def test_quote_in_source_cell_is_not_a_hit(tmp_path: Path) -> None:
    hits, _ = gate.cell_forbidden(TABLE, [patterns(tmp_path)])
    assert ("FR-001", "по возможности") not in hits


def test_missing_pattern_file_is_a_problem(tmp_path: Path) -> None:
    hits, problems = gate.cell_forbidden(TABLE, [tmp_path / "нет.txt"])
    assert hits == []
    assert "pattern file missing" in problems[0]


def test_table_without_requirement_column_is_ignored(tmp_path: Path) -> None:
    text = "| # | Файл | Тип |\n| --- | --- | --- |\n| 1 | по возможности | быстро |\n"
    hits, _ = gate.cell_forbidden(text, [patterns(tmp_path)])
    assert hits == []


# --- language of the file against its source --------------------------------------------


def test_cyrillic_share_is_measured() -> None:
    assert gate.cyrillic_share("Кот лежит на диване") > 0.9
    assert gate.cyrillic_share("The cat is on the sofa") == 0.0
    assert gate.cyrillic_share("| ID | Требование |") > 0.5


def test_english_extract_of_a_russian_source_is_a_problem(tmp_path: Path) -> None:
    src = tmp_path / "chat.md"
    src.write_text("Громов: журнал у «Севера» надо узнавать по телефону. " * 20, encoding="utf-8")
    problem = gate.language_mismatch(
        "The administrator calls the North clinic to check the journal. " * 20, src
    )
    assert problem is not None and "language" in problem


def test_same_language_is_fine(tmp_path: Path) -> None:
    src = tmp_path / "chat.md"
    src.write_text("Громов: журнал у «Севера» надо узнавать по телефону. " * 20, encoding="utf-8")
    text = (
        "| R-01 | Администратор звонит в «Север», чтобы узнать журнал. | functional | 08.09 |\n"
        * 20
    )
    assert gate.language_mismatch(text, src) is None


def test_missing_reference_file_is_named(tmp_path: Path) -> None:
    problem = gate.language_mismatch("текст", tmp_path / "нет.md")
    assert problem is not None and "reference missing" in problem
