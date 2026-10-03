"""Tests for the extract-to-requirements trace: no extract row is lost on the way."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location(
        "facet_extract_trace", ROOT / "tools" / "extract_trace.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EXTRACT = (
    "# Extract: call\n\n## Requirements\n| ID | Statement | Type | Source |\n| --- | --- | --- | --- |\n"
    "| R-01 | Book a visit | functional | 00:10 — “book” |\n"
    "| R-02 | Quote a price | functional | 00:20 — “price” |\n\n"
    "## Facts\n| ID | Topic | Fact | Source |\n| --- | --- | --- | --- |\n"
    "| F-01 | Clinics | Four clinics | 00:30 — “four” |\n"
)
HEADING = r"^##\s+10\."


def document(body: str, not_carried: str) -> str:
    return (
        "# Requirements: Acme Clinics\n\n## 3. Functional requirements\n"
        "| ID | Requirement | Priority | Source |\n| --- | --- | --- | --- |\n"
        f"{body}\n\n## 10. Extract rows not carried\n| Row | Why not carried |\n| --- | --- |\n"
        f"{not_carried}\n"
    )


def test_every_row_carried_or_set_aside_passes() -> None:
    trace = load()
    doc = document(
        "| FR-001 | Book a visit | MUST | call#R-01: 00:10 — “book”; call#F-01 |",
        "| call#R-02 | our own proposal, the client did not take it up |",
    )
    problems, measures = trace.check(doc, {"call": EXTRACT}, HEADING)
    assert problems == []
    assert measures["declared"] == 3
    assert measures["carried"] == 2
    assert measures["not_carried"] == 1


def test_a_row_neither_cited_nor_set_aside_is_lost() -> None:
    trace = load()
    doc = document("| FR-001 | Book a visit | MUST | call#R-01 |", "| call#F-01 | small talk |")
    problems, measures = trace.check(doc, {"call": EXTRACT}, HEADING)
    assert measures["lost"] == ["call#R-02"]
    assert any("lost" in p for p in problems)


def test_a_citation_inside_the_not_carried_section_does_not_count_as_carried() -> None:
    trace = load()
    doc = document("| FR-001 | Book a visit | MUST | call#R-01; call#F-01 |", "| call#R-02 |  |")
    problems, _ = trace.check(doc, {"call": EXTRACT}, HEADING)
    assert any("without a reason" in p for p in problems)


def test_a_cited_row_no_extract_declares_is_dangling() -> None:
    trace = load()
    doc = document(
        "| FR-001 | Book a visit | MUST | call#R-01; call#R-02; call#F-01; call#R-07 |", ""
    )
    problems, measures = trace.check(doc, {"call": EXTRACT}, HEADING)
    assert measures["dangling"] == ["call#R-07"]
    assert any("no extract declares" in p for p in problems)


def test_missing_not_carried_section_is_a_problem() -> None:
    trace = load()
    doc = "## 3. Functional requirements\n| FR-001 | x | MUST | call#R-01; call#R-02; call#F-01 |\n"
    problems, _ = trace.check(doc, {"call": EXTRACT}, HEADING)
    assert any("no not-carried section" in p for p in problems)


def test_extracts_without_row_ids_cannot_be_traced() -> None:
    trace = load()
    old = "## Requirements\n| Statement | Source |\n| --- | --- |\n| Book | “book” |\n"
    problems, _ = trace.check(document("", "| x | y |"), {"call": old}, HEADING)
    assert any("declare no row ids" in p for p in problems)
