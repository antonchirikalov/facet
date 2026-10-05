"""Tests for the check that a wording pass keeps the document's structure."""

from __future__ import annotations

import structure_kept

BEFORE = (
    "## 1. Overview\nText.\n\n> The scope is preliminary.\n\n"
    "## 2. What was said\n| Words | Answer |\n| --- | --- |\n| a | b |\n| c | d |\n\n"
    "![Plan](figures/plan.png)\n"
)


def test_a_reworded_document_with_its_structure_passes() -> None:
    after = BEFORE.replace("Text.", "Shorter text.").replace("| a | b |", "| a | b, said plainly |")
    problems, _ = structure_kept.check(BEFORE, after)
    assert problems == []


def test_a_removed_note_row_figure_and_heading_are_named() -> None:
    after = "## 1. Overview\nText.\n\n## 2. Said\n| Words | Answer |\n| --- | --- |\n| a | b |\n"
    problems, measures = structure_kept.check(BEFORE, after)
    assert measures["headings_gone"] == ["## 2. What was said"]
    joined = " ".join(problems)
    assert "fewer blockquote lines: 1 before, 0 now" in joined
    assert "fewer table rows: 3 before, 2 now" in joined
    assert "fewer figure placeholders: 1 before, 0 now" in joined


def test_more_structure_is_fine() -> None:
    after = BEFORE + "\n> Another note.\n"
    assert structure_kept.check(BEFORE, after)[0] == []
