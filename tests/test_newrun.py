"""Tests for naming a run directory.

A workflow script has no clock (`Date.now()` is unavailable there), so the directory name comes
from outside. Seven launches of one article went into the same directory, and reuse from disk
faithfully picked up the other run: there was nothing left to compare.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import newrun
import pytest

WHEN = datetime(2026, 8, 16, 14, 25, 30, tzinfo=UTC)


def test_name_carries_label_and_moment() -> None:
    assert newrun.run_dir("docs-runs", "attention", WHEN) == "docs-runs/attention-20260816-142530"


def test_cyrillic_label_is_transliterated_not_dropped() -> None:
    """Cyrillic in a path broke PowerShell, but the label must not be thrown away.

    Without transliteration every run was called `run-<time>`, a name that tells nothing apart.
    """
    got = newrun.run_dir("docs-runs", "Внимание в трансформерах", WHEN)
    assert got == "docs-runs/vnimanie-v-transformerah-20260816-142530"
    assert got.isascii()


def test_punctuation_collapses_to_single_dashes() -> None:
    assert newrun.slugify("Solution   Design: v2!!") == "solution-design-v2"


def test_empty_label_still_yields_a_name() -> None:
    assert newrun.slugify("---") == "run"


def test_path_is_posix_even_on_windows() -> None:
    """A backslash once already sent four finders to work for nothing."""
    assert "\\" not in newrun.run_dir("a/b", "c", WHEN)


def test_two_runs_in_the_same_second_collide_and_that_is_visible(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--check` exists precisely so that a collision is a refusal, not a silent inheritance."""
    target = newrun.run_dir(str(tmp_path), "x", datetime.now(tz=UTC))
    Path(target).mkdir(parents=True)
    monkeypatch.setattr(
        sys, "argv", ["newrun.py", "--base", str(tmp_path), "--label", "x", "--check"]
    )
    monkeypatch.setattr(newrun, "run_dir", lambda *a, **k: target)
    assert newrun.main() == 1
    assert "already exists" in capsys.readouterr().err
