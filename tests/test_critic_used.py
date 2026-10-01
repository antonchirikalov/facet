"""Кто на самом деле судил картинку: по логу целиком, а не по баннеру.

На одном живом прогоне критик Kimi начал отвечать 403 посреди прогона, инструмент сам переключился на Claude,
а иллюстратор отчитался «критик Kimi K3» — он прочёл баннер, а лог триста строк ниже говорил другое.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import critic_used
import pytest

BANNER = "\x1b[1m│ Critic VLM: kimi / k3                        │\x1b[0m\n"
FALLBACK = (
    "\x1b[2m2026-09-29 11:24:10\x1b[0m [warning] Critic provider failed, switching to the "
    "fallback for the rest of the run error='RetryError[<Future at 0x1 state=finished raised "
    "PermissionDeniedError>]' failed=kimi\n"
)


def test_clean_kimi_run_passes() -> None:
    facts = critic_used.read(BANNER + "Critic satisfied (kimi)\n" * 2)
    assert facts["judged_by"] == ["kimi"] and facts["accepted"] == 2
    assert critic_used.verdict(facts) == []


def test_silent_fallback_is_a_problem_with_its_reason() -> None:
    facts = critic_used.read(
        BANNER + "Critic satisfied (kimi)\n" + FALLBACK + "Critic satisfied (claude_code)\n"
    )
    assert facts["fell_back"] is True
    assert facts["fallback_reason"] == "kimi PermissionDeniedError"
    assert critic_used.verdict(facts) == [
        (
            "critic kimi failed (kimi PermissionDeniedError) and the rest of the run was judged "
            "by the fallback critic; accepted images were judged by claude_code, kimi"
        )
    ]


def test_nothing_accepted_is_a_problem() -> None:
    assert critic_used.verdict(critic_used.read(BANNER)) == [
        'no image reached "Critic satisfied" in this log'
    ]


def test_cli_reports_each_log(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    good = tmp_path / "a.log"
    good.write_text(BANNER + "Critic satisfied (kimi)\n", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        ["critic_used.py", "--log-file", str(good), "--log-file", str(tmp_path / "x.log")],
    )
    critic_used.main()
    report = json.loads(capsys.readouterr().out)
    assert report["measures"]["logs"]["a.log"]["judged_by"] == ["kimi"]
    assert report["problems"] == ["x.log: log missing"]
