"""Тесты конвертера markdown → Confluence storage format.

Проверяется именно конвертер, а не REST: сеть в тестах не трогается, а весь класс дефектов,
из-за которого этот скрипт вообще существует, живёт в конвертере. Исходный дефект MCP-пути —
подряд идущие буллеты без пустой строки перед ними склеивались в один <p>, и список исчезал
(живой замер: 79 <li> превратились в 29). Поэтому первый же тест — про список сразу после
абзаца, а остальные про то, что ломалось при переносе логики.
"""

from __future__ import annotations

import re
from pathlib import Path

import confluence_publish as cp
import pytest


def _count(pattern: str, text: str) -> int:
    return len(re.findall(pattern, text))


def test_список_сразу_после_абзаца_остаётся_списком() -> None:
    """Тот самый дефект: перед буллетами нет пустой строки."""
    md = "Текст, и сразу список:\n- один\n- два\n- три\n"
    out = cp.md_to_confluence(md)
    assert _count(r"<li>", out) == 3
    assert "<ul>" in out
    assert "<p>Текст, и сразу список:</p>" in out


def test_вложенность_по_отступу_сохраняется() -> None:
    md = "- один\n- два\n  - вложенный\n    - глубже\n- три\n"
    out = cp.md_to_confluence(md)
    # три уровня <ul>, пять пунктов, и вложенный список стоит ВНУТРИ <li>
    assert _count(r"<ul>", out) == 3
    assert _count(r"<li>", out) == 5
    assert "<li>два<ul>" in out


def test_нумерованный_список_после_буллетов_не_прилипает() -> None:
    """Через пустую строку список продолжается только маркером того же вида.

    Без проверки вида маркера нумерованный список поглощался предыдущим <ul> плоскими
    пунктами — поймано тестовым документом, а не рассуждением.
    """
    md = "- один\n- два\n\n1. первый\n2. второй\n"
    out = cp.md_to_confluence(md)
    assert out.count("<ul>") == 1
    assert out.count("<ol>") == 1
    assert _count(r"<li>", out) == 4


def test_пустая_строка_внутри_списка_не_рвёт_его() -> None:
    """Пункты, разделённые пустой строкой, — один список (loose list в markdown)."""
    md = "- один\n\n- два\n\n- три\n"
    out = cp.md_to_confluence(md)
    assert out.count("<ul>") == 1
    assert _count(r"<li>", out) == 3


def test_перенос_строки_продолжает_пункт_а_не_рождает_абзац() -> None:
    md = "- пункт, который\n  продолжается ниже\n- второй\n"
    out = cp.md_to_confluence(md)
    assert "<li>пункт, который продолжается ниже</li>" in out
    assert "<p>" not in out


def test_две_таблицы_подряд_не_сливаются() -> None:
    md = "| A | B |\n|---|---|\n| 1 | 2 |\n\nМежду ними абзац.\n\n| C | D |\n|---|---|\n| 3 | 4 |\n"
    out = cp.md_to_confluence(md)
    assert out.count("<table") == 2
    assert out.count("<th>") == 4


def test_код_не_интерпретируется_как_markdown() -> None:
    md = "```python\nx = 1 if a < b else 2\n# - не список\n```\n"
    out = cp.md_to_confluence(md)
    assert 'ac:name="code"' in out
    assert 'ac:language="python"' in out
    assert "<li>" not in out
    assert "a < b" in out  # внутри CDATA экранирование не нужно и не делается


def test_ссылки_жирный_и_код_в_строке() -> None:
    md = "Смотри **важное** и `код`, и [ссылку](https://example.com).\n"
    out = cp.md_to_confluence(md)
    assert "<strong>важное</strong>" in out
    assert "<code>код</code>" in out
    assert '<a href="https://example.com">ссылку</a>' in out


def test_подчёркивание_в_идентификаторе_не_становится_курсивом() -> None:
    md = "Поле *важное* — курсив, а `snake_case_name` и 2*3*4 — нет.\n"
    out = cp.md_to_confluence(md)
    assert "<em>важное</em>" in out
    assert "<code>snake_case_name</code>" in out


def test_картинка_превращается_в_ссылку_на_вложение() -> None:
    md = "![Схема потоков](figures/flow.png)\n"
    out = cp.md_to_confluence(md)
    assert '<ri:attachment ri:filename="flow.png" />' in out
    assert 'ac:alt="Схема потоков"' in out


def test_алерт_становится_макросом_с_вложенным_списком() -> None:
    md = "> [!WARNING]\n> Осторожно\n> - и список внутри\n"
    out = cp.md_to_confluence(md)
    assert 'ac:name="warning"' in out
    assert "<li>и список внутри</li>" in out


def test_чекбоксы_видны_в_тексте_пункта() -> None:
    md = "- [ ] не сделано\n- [x] сделано\n"
    out = cp.md_to_confluence(md)
    assert "☐ не сделано" in out
    assert "☑ сделано" in out


def test_html_экранируется_а_не_протекает_в_разметку() -> None:
    md = "Сравнение a < b и тег <script> в тексте.\n"
    out = cp.md_to_confluence(md)
    assert "&lt;script&gt;" in out
    assert "<script>" not in out


# ---------------------------------------------------------------------------
# Вложения: агент публикует документ, а не содержимое папки
# ---------------------------------------------------------------------------


def test_прикрепляются_только_упомянутые_картинки(tmp_path: Path) -> None:
    """Папка сгенерированных фигур несёт и резервные копии; их на странице быть не должно."""
    figures = tmp_path / "figures"
    figures.mkdir()
    for name in ("flow.png", "flow_v1_orig.png", "unused.png"):
        (figures / name).write_bytes(b"\x89PNG")

    md = "![Схема](figures/flow.png)\n"
    files, skipped = cp.resolve_attachments(md, figures, [])

    assert [p.name for p in files] == ["flow.png"]
    assert set(skipped) == {"flow_v1_orig.png", "unused.png"}


def test_без_упоминаний_берутся_все_png(tmp_path: Path) -> None:
    figures = tmp_path / "figures"
    figures.mkdir()
    (figures / "a.png").write_bytes(b"\x89PNG")
    (figures / "notes.txt").write_text("x", encoding="utf-8")

    files, skipped = cp.resolve_attachments("Без картинок.\n", figures, [])

    assert [p.name for p in files] == ["a.png"]
    assert skipped == []


def test_отсутствующее_вложение_падает_с_именем_стадии(tmp_path: Path) -> None:
    with pytest.raises(cp.Failure) as exc:
        cp.resolve_attachments("", None, [str(tmp_path / "нет.pdf")])
    assert exc.value.stage == "config"


def test_заголовок_берётся_из_первого_h1() -> None:
    assert cp.first_h1("# Название\n\nтекст\n", "запас") == "Название"
    assert cp.first_h1("текст без заголовка\n", "запас") == "запас"
