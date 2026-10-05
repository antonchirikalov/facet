"""Tests for the check that every binding requirement is answered in the design."""

from __future__ import annotations

import must_covered

REQUIREMENTS = (
    "## 3. Functional requirements\n"
    "| ID | Requirement | Priority | Source |\n| --- | --- | --- | --- |\n"
    "| FR-001 | Book a visit | MUST | call |\n"
    "| FR-002 | Remind by text | SHOULD | call |\n"
    "| FR-003 | Answer opening hours | MUST | rfp |\n"
    "## 4. Non-functional requirements\n"
    "| ID | Requirement | Category | Source |\n| --- | --- | --- | --- |\n"
    "| NFR-001 | Answer within 3 s at p95 | Performance | rfp |\n"
)


def test_binding_rows_are_must_and_rows_of_tables_without_priority() -> None:
    import re

    ids = must_covered.binding_ids(REQUIREMENTS, re.compile(must_covered.DEFAULT_IDS))
    assert ids == ["FR-001", "FR-003", "NFR-001"]


def test_a_binding_requirement_the_design_never_cites_is_named() -> None:
    design = "## 2. Decision points\n| Booking | code | FR-001 |\n## 11. NFR\n| NFR-001 | cache |\n"
    problems, measures = must_covered.check(REQUIREMENTS, design, must_covered.DEFAULT_IDS)
    assert measures["missing"] == ["FR-003"]
    assert any("never cites" in p for p in problems)


def test_a_design_citing_every_binding_requirement_passes() -> None:
    design = "FR-001, FR-003 and NFR-001 are answered."
    assert must_covered.check(REQUIREMENTS, design, must_covered.DEFAULT_IDS)[0] == []
