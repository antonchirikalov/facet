"""Tests for listing a profile's checklist rules."""

from __future__ import annotations

from pathlib import Path

import rules

ROOT = Path(__file__).resolve().parent.parent

PROFILE = """# Profile

## Critic checklist

In order of severity. CRITICAL alone forces revise;
MINOR never does.

CRITICAL
1. A row whose source does not support it,
   or a changed quantifier.
2. A silent resolution.
MAJOR
3. A bundled row.

## Gate rules

1. Not a checklist rule.
"""


def test_tiers_and_continuations() -> None:
    got = rules.rules_of(PROFILE)
    assert [(r["id"], r["severity"], r["rank"]) for r in got] == [
        ("1", "CRITICAL", 0),
        ("2", "CRITICAL", 0),
        ("3", "MAJOR", 1),
    ]
    assert got[0]["text"].endswith("or a changed quantifier.")


def test_a_sentence_starting_with_a_severity_word_is_not_a_tier() -> None:
    assert all(r["severity"] != "MINOR" for r in rules.rules_of(PROFILE))


def test_real_profiles_have_top_rules() -> None:
    for name in ("requirements", "solution-design", "proposal"):
        text = (ROOT / ".claude" / "skills" / f"{name}-profile" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        top = [r for r in rules.rules_of(text) if r["rank"] == 0]
        assert len(top) >= 5, name
