"""Tests for reading the revision round records.

An agent writes the records, not code, so the format is parsed leniently: a heading and
numbered items. But everything the script branches on (the round number, the verdicts, the
split of items by the source of the remark) must parse unambiguously, or recovery after a
restart will quietly lie about how many rounds have already passed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
import rounds


def run(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    *argv: str,
) -> tuple[dict[str, Any], int]:
    monkeypatch.setattr(sys, "argv", ["rounds.py", *argv])
    code = rounds.main()
    report: dict[str, Any] = json.loads(capsys.readouterr().out)
    return report, code


def write_round(directory: Path, n: int, head: str, items: list[str]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"{i + 1}. {item}" for i, item in enumerate(items))
    target = directory / f"round-{n}.md"
    target.write_text(f"{head}\n\n{body}\n", encoding="utf-8")
    return target


# --- empty and missing ---------------------------------------------------------------


def test_missing_directory_is_not_a_problem(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A first run has no records; that is normal, not a breakage."""
    report, code = run(capsys, monkeypatch, "--dir", str(tmp_path / "missing"))
    assert report["ok"] is True
    assert report["rounds"] == []
    assert {k: v for k, v in report["measures"].items() if k != "counts"} == {
        "rounds": 0,
        "last_round": 0,
    }
    assert code == 0


def test_directory_without_records_reads_as_empty(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "note.txt").write_text("not a record", encoding="utf-8")
    report, _ = run(capsys, monkeypatch, "--dir", str(tmp_path))
    assert report["ok"] is True
    assert report["measures"]["last_round"] == 0


# --- parsing one record ---------------------------------------------------------------


def test_verdicts_come_from_the_heading(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    write_round(tmp_path, 1, "Round 1 — verdict=revise style=ok", ["the example does not add up"])
    report, _ = run(capsys, monkeypatch, "--dir", str(tmp_path))
    one = report["rounds"][0]
    assert one["round"] == 1
    assert one["verdict"] == "revise"
    assert one["style_verdict"] == "ok"


def test_items_split_by_who_said_them(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Three sources of remarks give three lists, the way the loop feeds them back to the writer."""
    write_round(
        tmp_path,
        1,
        "Round 1 — verdict=revise style=revise",
        [
            "the matrices are swapped",
            'Style: "cases are reviewed" is passive voice -> review the cases',
            "Gate: max_prose 30000 exceeded (got 35668)",
            "the number 64 is given without its consequence",
        ],
    )
    report, _ = run(capsys, monkeypatch, "--dir", str(tmp_path))
    one = report["rounds"][0]
    assert one["remarks"] == [
        "the matrices are swapped",
        "the number 64 is given without its consequence",
    ]
    assert one["style"] == ['"cases are reviewed" is passive voice -> review the cases']
    assert one["gate"] == ["max_prose 30000 exceeded (got 35668)"]


def test_missing_verdict_in_heading_is_named_not_guessed(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    write_round(tmp_path, 1, "Round one", ["remark"])
    report, _ = run(capsys, monkeypatch, "--dir", str(tmp_path))
    assert report["rounds"][0]["verdict"] == "unknown"
    assert report["rounds"][0]["style_verdict"] == "unknown"


def test_items_keep_their_order(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    items = [f"remark {i}" for i in range(1, 8)]
    write_round(tmp_path, 1, "Round 1 — verdict=revise style=revise", items)
    report, _ = run(capsys, monkeypatch, "--dir", str(tmp_path))
    assert report["rounds"][0]["remarks"] == items


def test_multiline_item_keeps_only_its_first_line() -> None:
    """An item is one line: a continuation is already a retelling, and a retelling must not be fed to the loop."""
    text = "Round 1 — verdict=revise style=ok\n\n1. first line\n   continuation\n2. second\n"
    assert ITEMS_OF(text) == ["first line", "second"]


def ITEMS_OF(text: str) -> list[str]:
    return rounds.ITEM.findall(text)


# --- several records ------------------------------------------------------------------


def test_rounds_sorted_by_number_not_by_filename(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`round-10.md` comes after `round-9.md`, not between 1 and 2."""
    for n in (1, 2, 9, 10):
        write_round(tmp_path, n, f"Round {n} — verdict=revise style=revise", ["x"])
    report, _ = run(capsys, monkeypatch, "--dir", str(tmp_path))
    assert [r["round"] for r in report["rounds"]] == [1, 2, 9, 10]


def test_last_round_is_the_highest(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    write_round(tmp_path, 1, "Round 1 — verdict=revise style=revise", ["x"])
    write_round(tmp_path, 2, "Round 2 — verdict=ok style=ok", [])
    report, _ = run(capsys, monkeypatch, "--dir", str(tmp_path))
    assert {k: v for k, v in report["measures"].items() if k != "counts"} == {
        "rounds": 2,
        "last_round": 2,
    }


def test_a_gap_in_the_records_is_reported(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A missing record is a lost round; continuing from the maximum would hide the loss."""
    write_round(tmp_path, 1, "Round 1 — verdict=revise style=revise", ["x"])
    write_round(tmp_path, 3, "Round 3 — verdict=revise style=revise", ["y"])
    report, code = run(capsys, monkeypatch, "--dir", str(tmp_path))
    assert report["ok"] is False
    assert any("not consecutive" in p for p in report["problems"])
    assert code == 0


def test_strict_makes_a_broken_record_fail_the_process(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    write_round(tmp_path, 2, "Round 2 — verdict=ok style=ok", ["x"])
    _, code = run(capsys, monkeypatch, "--dir", str(tmp_path), "--strict")
    assert code == 1


def test_empty_round_record_is_a_real_round_with_no_remarks(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A round in which neither critic has anything to say is still a round: it was spent."""
    write_round(tmp_path, 1, "Round 1 — verdict=ok style=ok", [])
    report, _ = run(capsys, monkeypatch, "--dir", str(tmp_path))
    assert report["measures"]["last_round"] == 1
    assert report["rounds"][0]["remarks"] == []


# --- --last-only: the limits of the channel through an agent ----------------------------


def test_last_only_emits_one_round_but_counts_all(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The output travels back through an agent, and the agent has a budget.

    Five rounds of verbatim remarks are about a hundred kilobytes of JSON; the carrier returned
    two rounds instead of five, the script read that as "two done" and ran four rounds instead
    of one. The counters must stay complete; the text is kept for the last round only.
    """
    for n in (1, 2, 3, 4, 5):
        write_round(tmp_path, n, f"Round {n} — verdict=revise style=revise", [f"remark {n}"])
    report, _ = run(capsys, monkeypatch, "--dir", str(tmp_path), "--last-only")
    assert {k: v for k, v in report["measures"].items() if k != "counts"} == {
        "rounds": 5,
        "last_round": 5,
    }
    assert len(report["rounds"]) == 1
    assert report["rounds"][0]["round"] == 5
    assert report["rounds"][0]["remarks"] == ["remark 5"]


def test_last_only_on_empty_directory_emits_nothing(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    report, _ = run(capsys, monkeypatch, "--dir", str(tmp_path), "--last-only")
    assert report["rounds"] == []
    assert report["measures"]["last_round"] == 0


def test_last_only_keeps_reporting_a_gap(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Truncated output must not hide a missing record, or a round disappears silently."""
    write_round(tmp_path, 1, "Round 1 — verdict=revise style=revise", ["x"])
    write_round(tmp_path, 3, "Round 3 — verdict=revise style=revise", ["y"])
    report, _ = run(capsys, monkeypatch, "--dir", str(tmp_path), "--last-only")
    assert report["ok"] is False
    assert any("not consecutive" in p for p in report["problems"])


def test_full_output_is_still_the_default(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for n in (1, 2, 3):
        write_round(tmp_path, n, f"Round {n} — verdict=ok style=ok", ["x"])
    report, _ = run(capsys, monkeypatch, "--dir", str(tmp_path))
    assert len(report["rounds"]) == 3


def test_counts_cover_every_round_even_with_last_only(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A plateau belongs to the article, not to the launch.

    A continued run that counts from zero calls the first round it sees the best and pays two
    more rounds to learn otherwise. Measured live: 16, 12, 16, 12, 16; the detector should have
    stopped at the second twelve. Numbers, not texts: this same channel once cut five rounds of
    verbatim remarks down to two.
    """
    write_round(tmp_path, 1, "revise", ["a", "b", "c"])
    write_round(tmp_path, 2, "revise", ["a"])
    report, _ = run(capsys, monkeypatch, "--dir", str(tmp_path), "--last-only")
    assert report["measures"]["counts"] == [
        {"round": 1, "items": 3},
        {"round": 2, "items": 1},
    ]
    assert len(report["rounds"]) == 1
