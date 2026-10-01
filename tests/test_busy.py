"""Tests for the lock on a run directory.

The question "is another run working in this directory" had no answer, and that cost a run:
the log was silent for six minutes, the directory looked free, but the first run was alive;
the silent ones were the finders, which call no tools at all. Two processes wrote one analysis,
and which version the writer read can no longer be established.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import busy
import pytest

NOW = "2026-08-16T15:30:00+03:00"


def run(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    *argv: str,
) -> tuple[dict[str, Any], int]:
    monkeypatch.setattr(sys, "argv", ["busy.py", *argv])
    code = busy.main()
    report: dict[str, Any] = json.loads(capsys.readouterr().out)
    return report, code


def log_with(tmp_path: Path, *stamps: str) -> Path:
    target = tmp_path / "tools.jsonl"
    target.write_text(
        "".join(json.dumps({"at": s, "tool": "gate", "ok": True}) + "\n" for s in stamps),
        encoding="utf-8",
    )
    return target


def log_of(tmp_path: Path, *records: dict[str, Any]) -> Path:
    target = tmp_path / "tools.jsonl"
    target.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    return target


def test_release_line_frees_the_directory_however_young(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The end-of-stage audit writes release, so the next stage starts right away, not ten minutes later.

    Paid for by a launch: draft stopped because research had finished with its own audit 72
    seconds earlier, and the lock read that audit as someone else's work.
    """
    log = log_of(
        tmp_path,
        {"at": "2026-08-16T15:20:00+03:00", "tool": "gate", "ok": True},
        {"at": "2026-08-16T15:29:00+03:00", "tool": "listing", "ok": True, "release": True},
    )
    report, code = run(capsys, monkeypatch, "--file", str(log), "--now", NOW)
    assert report["busy"] is False
    assert report["measures"]["released"] is True
    assert code == 0


def test_work_after_a_release_is_busy_again(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """release ends THAT run; a receipt after it means the next one has started."""
    log = log_of(
        tmp_path,
        {"at": "2026-08-16T15:20:00+03:00", "tool": "listing", "ok": True, "release": True},
        {"at": "2026-08-16T15:29:00+03:00", "tool": "gate", "ok": True},
    )
    report, _ = run(capsys, monkeypatch, "--file", str(log), "--now", NOW)
    assert report["busy"] is True


def test_own_receipts_are_not_activity(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Asking "is it busy" is not work in the directory: the lock must not lock itself on its own receipt."""
    log = log_of(
        tmp_path,
        {"at": "2026-08-16T15:00:00+03:00", "tool": "gate", "ok": True},
        {"at": "2026-08-16T15:29:30+03:00", "tool": "busy", "ok": False},
    )
    report, _ = run(capsys, monkeypatch, "--file", str(log), "--now", NOW)
    assert report["busy"] is False
    assert report["measures"]["last_activity"] == "2026-08-16T15:00:00+03:00"


def test_log_release_flag_writes_the_marker(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The --log-release flag of any tool puts release into its receipt."""
    receipt = tmp_path / "receipts.jsonl"
    run(
        capsys,
        monkeypatch,
        "--file",
        str(tmp_path / "missing.jsonl"),
        "--now",
        NOW,
        "--log",
        str(receipt),
        "--log-release",
    )
    line = json.loads(receipt.read_text(encoding="utf-8").splitlines()[-1])
    assert line["release"] is True
    plain = tmp_path / "plain.jsonl"
    run(
        capsys,
        monkeypatch,
        "--file",
        str(tmp_path / "missing.jsonl"),
        "--now",
        NOW,
        "--log",
        str(plain),
    )
    assert "release" not in json.loads(plain.read_text(encoding="utf-8").splitlines()[-1])


def test_missing_log_is_free(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A fresh directory is the normal state, not a suspicious one."""
    report, code = run(capsys, monkeypatch, "--file", str(tmp_path / "missing.jsonl"), "--now", NOW)
    assert report["busy"] is False
    assert report["ok"] is True
    assert code == 0


def test_recent_line_means_busy(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log = log_with(tmp_path, "2026-08-16T15:28:00+03:00")
    report, _ = run(capsys, monkeypatch, "--file", str(log), "--now", NOW)
    assert report["busy"] is True
    assert report["measures"]["idle_seconds"] == 120
    assert "another run may be working here" in report["problems"][0]


def test_old_line_means_free(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log = log_with(tmp_path, "2026-08-16T15:00:00+03:00")
    report, _ = run(capsys, monkeypatch, "--file", str(log), "--now", NOW)
    assert report["busy"] is False
    assert report["measures"]["idle_seconds"] == 1800


def test_window_is_the_callers_to_set(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log = log_with(tmp_path, "2026-08-16T15:00:00+03:00")
    report, _ = run(capsys, monkeypatch, "--file", str(log), "--now", NOW, "--idle-seconds", "3600")
    assert report["busy"] is True


def test_last_line_wins_not_the_first(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log = log_with(tmp_path, "2026-08-16T14:00:00+03:00", "2026-08-16T15:29:00+03:00")
    report, _ = run(capsys, monkeypatch, "--file", str(log), "--now", NOW)
    assert report["busy"] is True


def test_truncated_final_line_falls_back_to_the_one_before(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A truncated last line is exactly what the log of a running run looks like."""
    log = log_with(tmp_path, "2026-08-16T15:29:00+03:00")
    with log.open("a", encoding="utf-8") as fh:
        fh.write('{"at": "2026-08-16T15:29')
    report, _ = run(capsys, monkeypatch, "--file", str(log), "--now", NOW)
    assert report["busy"] is True
    assert report["measures"]["last_activity"] == "2026-08-16T15:29:00+03:00"


def test_unreadable_now_is_busy_not_free(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A broken clock must not read as "free": that is the answer that lets a second run in."""
    log = log_with(tmp_path, "2026-08-16T15:29:00+03:00")
    report, code = run(capsys, monkeypatch, "--file", str(log), "--now", "yesterday", "--strict")
    assert report["busy"] is True
    assert code == 1


def test_future_line_does_not_read_as_free(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Clocks that drifted apart are no reason to declare the directory free."""
    log = log_with(tmp_path, "2026-08-16T16:00:00+03:00")
    report, _ = run(capsys, monkeypatch, "--file", str(log), "--now", NOW)
    assert report["busy"] is True


def test_strict_exits_one_when_busy(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log = log_with(tmp_path, "2026-08-16T15:29:00+03:00")
    _, code = run(capsys, monkeypatch, "--file", str(log), "--now", NOW, "--strict")
    assert code == 1
    _, code = run(capsys, monkeypatch, "--file", str(log), "--now", NOW)
    assert code == 0


def test_naive_and_aware_stamps_compare(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Not everyone who passes a time passes a time zone; failing on that is not allowed."""
    log = log_with(tmp_path, "2026-08-16T15:29:00")
    report, _ = run(capsys, monkeypatch, "--file", str(log), "--now", NOW)
    assert report["busy"] is True


def test_receipt_goes_to_its_own_log(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    receipt = tmp_path / "tools.jsonl"
    run(
        capsys,
        monkeypatch,
        "--file",
        str(tmp_path / "missing.jsonl"),
        "--now",
        NOW,
        "--log",
        str(receipt),
    )
    line = json.loads(receipt.read_text(encoding="utf-8").splitlines()[0])
    assert line["tool"] == "busy"
