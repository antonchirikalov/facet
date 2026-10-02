"""Tests for the citation check and the client vocabulary check."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(name: str):  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location(f"facet_{name}", ROOT / "tools" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REQUIREMENTS = (
    "| ID | Requirement |\n| --- | --- |\n| FR-001 | Book a visit |\n| FR-002 | Quote a price |\n"
)
DESIGN = "### D-01 One booking service\n"


def test_cited_ids_must_be_declared() -> None:
    trace = load("trace_ids")
    problems, measures = trace.check(
        "Step 1 (FR-001, D-01). Step 2 (FR-009).", [REQUIREMENTS, DESIGN], trace.DEFAULT_IDS, []
    )
    assert measures["dangling"] == ["FR-009"]
    assert any("not declared" in p for p in problems)


def test_required_ids_must_be_cited() -> None:
    trace = load("trace_ids")
    problems, _ = trace.check("Step 1 (FR-001).", [REQUIREMENTS], trace.DEFAULT_IDS, ["FR-002"])
    assert any("never cited" in p for p in problems)


SHEET = (
    "## 3. Their vocabulary\n\n| Their term | What they mean | Do not replace with |\n| --- | --- | --- |\n"
    "| front desk | the reception team | receptionist, reception staff |\n| visit | a booked slot | appointment |\n\n"
    "## 4. Who wants what\n"
)


def test_vocabulary_is_read_from_the_sheet() -> None:
    vocab = load("vocab")
    assert vocab.vocabulary(SHEET) == [
        ("front desk", ["receptionist", "reception staff"]),
        ("visit", ["appointment"]),
    ]


def test_substitutes_outside_quotes_are_found() -> None:
    vocab = load("vocab")
    text = "The receptionist books the appointment. The owner said \u201cthe receptionist is slow\u201d."
    found = vocab.substitutes_in(text, vocab.vocabulary(SHEET))
    assert any("receptionist" in f and "1x" in f for f in found)
    assert any("appointment" in f for f in found)
