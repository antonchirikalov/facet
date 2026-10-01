"""Бриф точного рисунка проверяется по документу до рендера.

На одном живом прогоне ошибка была в самом брифе: пять столбов на заборе 36 футов под баннером
6'-0" и 2'-0" от концов, а нужно семь. Тридцать рендеров чинили картинку, которую с первой строки
просили нарисовать неверно.
"""

from __future__ import annotations

import figure_facts
import pytest

DOC = (
    'A fixed yellow banner reads “PRELIMINARY ESTIMATE: MAX 6’-0" POST SPACING / '
    '2’-0" FROM ENDS” and the disclaimer says the price remains subject to an on-site '
    "survey.\n"
)


def test_texts_and_true_checks_pass() -> None:
    brief = (
        "Draw the screen.\n\nFacts:\n"
        "- text: MAX 6'-0\" POST SPACING\n"
        "- text: remains subject to an on-site survey\n"
        "- check: ceil((29 - 2 * 2) / 6) + 1 == 6\n"
    )
    problems, measures = figure_facts.check(brief, DOC)
    assert problems == []
    assert measures == {"texts": 2, "checks": 1}


def test_a_wrong_count_in_the_brief_is_caught() -> None:
    """Пять столбов на 36 футах при шаге 6 и отступе 2 — ложь, которую считает питон."""
    brief = "Facts:\n- check: ceil((36 - 2 * 2) / 6) + 1 == 5\n"
    problems, _ = figure_facts.check(brief, DOC)
    assert problems == ["check is false: ceil((36 - 2 * 2) / 6) + 1 == 5"]


def test_text_not_in_the_document_is_named() -> None:
    brief = "Facts:\n- text: and subject to a survey\n"
    problems, _ = figure_facts.check(brief, DOC)
    assert problems == ["text not in the document: and subject to a survey"]


@pytest.mark.parametrize("expr", ["__import__('os').system('x')", "open('f')", "a + 1"])
def test_anything_but_arithmetic_is_refused(expr: str) -> None:
    problems, _ = figure_facts.check(f"Facts:\n- check: {expr}\n", DOC)
    assert problems and problems[0].startswith("check refused")


def test_brief_without_facts_is_a_problem() -> None:
    problems, _ = figure_facts.check("Draw a nice screen.\n", DOC)
    assert problems == ["the brief has no Facts block"]
