"""Tests for tracing the pain map into the proposal by the client's words."""

from __future__ import annotations

import pain_coverage

PAINS = (
    "## 1. Pains, most important first\n"
    "| ID | The pain in their words | Who feels it |\n| --- | --- | --- |\n"
    "| P-01 | “we call the salesmen back for every missing number” (engineer) | engineer |\n"
    "| P-02 | “the front desk retypes every visit” (owner) | front desk |\n"
    "| P-03 | “prices are on paper” (owner) | owner |\n"
    "| P-04 | “nobody knows which clinic is free” (owner) | owner |\n"
    "## 2. What they worry about\n"
    "| ID | The worry in their words | Who |\n| --- | --- | --- |\n"
    "| WR-01 | “we still sign the engineering ourselves” (owner) | owner |\n"
)


def proposal(early: str, late: str) -> str:
    return (
        "## 1. Overview\n"
        + early
        + "\n## 2. What was said\n\n## 5. How it is built\n"
        + late
        + "\n"
    )


def test_every_pain_answered_early_passes() -> None:
    doc = proposal(
        "“we call the salesmen back for every missing number” · “the front desk retypes every visit” "
        "· “prices are on paper” · “nobody knows which clinic is free” · "
        "“we still sign the engineering ourselves”",
        "",
    )
    problems, measures = pain_coverage.check(PAINS, doc, 3, r"^##\s+5\.")
    assert problems == []
    assert measures["pains"] == 4 and measures["worries"] == 1 and measures["answered"] == 5


def test_a_shortened_quote_counts_as_answered() -> None:
    doc = proposal("“the front desk retypes” — and “every missing number”", "")
    _, measures = pain_coverage.check(PAINS, doc, 3, r"^##\s+5\.")
    assert "P-01" not in measures["missing"] and "P-02" not in measures["missing"]


def test_missing_and_late_pains_are_named() -> None:
    doc = proposal(
        "“the front desk retypes every visit”",
        "“we call the salesmen back for every missing number”",
    )
    problems, measures = pain_coverage.check(PAINS, doc, 3, r"^##\s+5\.")
    assert measures["late"] == ["P-01"]
    assert set(measures["missing"]) == {"P-03", "P-04", "WR-01"}
    assert any("appear nowhere" in p for p in problems)
    assert any("only after" in p for p in problems)


def test_a_pain_map_without_rows_is_a_problem() -> None:
    problems, _ = pain_coverage.check("## 1. Pains\nnothing\n", "## 1. x\n", 3, r"^##\s+5\.")
    assert any("declares no" in p for p in problems)
