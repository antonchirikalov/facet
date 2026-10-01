"""Tests for the observer of subagent completion.

The hook blocks nothing; its only result is a line in the log, so the tests check that the line
tells the truth: how many files the agent wrote, and whether they are on disk at the moment it
finishes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import stop_audit


def transcript(tmp_path: Path, calls: list[tuple[str, str]], name: str = "agent.jsonl") -> Path:
    """A transcript of (tool, path) pairs, in the format the runtime writes."""
    path = tmp_path / name
    lines = []
    for tool, file_path in calls:
        lines.append(
            json.dumps(
                {
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"type": "tool_use", "name": tool, "input": {"file_path": file_path}}
                        ],
                    }
                },
                ensure_ascii=False,
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_agent_that_wrote_nothing(tmp_path: Path) -> None:
    """A critic writes no files, and that is not a defect."""
    t = transcript(tmp_path, [])
    record = stop_audit.audit({"agent_type": "article-critic", "agent_transcript_path": str(t)})
    assert record["verdict"] == "no_writes"
    assert record["agent_type"] == "article-critic"


def test_written_file_that_exists(tmp_path: Path) -> None:
    target = tmp_path / "material.md"
    target.write_text("material", encoding="utf-8")
    t = transcript(tmp_path, [("Write", str(target))])
    record = stop_audit.audit({"agent_type": "domain-analyst", "agent_transcript_path": str(t)})
    assert record["verdict"] == "ok"
    assert record["wrote"] == 1
    assert record["files"] == [Path(target).as_posix()]


def test_written_file_that_vanished(tmp_path: Path) -> None:
    """The main case: there was a Write, but there is no file. The hook exists for this case."""
    target = tmp_path / "material.md"
    t = transcript(tmp_path, [("Write", str(target))])
    record = stop_audit.audit({"agent_type": "domain-analyst", "agent_transcript_path": str(t)})
    assert record["verdict"] == "MISSING_AFTER_WRITE"
    assert record["missing"] == [Path(target).as_posix()]


def test_edit_counts_as_writing(tmp_path: Path) -> None:
    target = tmp_path / "article.md"
    target.write_text("article", encoding="utf-8")
    t = transcript(tmp_path, [("Edit", str(target))])
    record = stop_audit.audit({"agent_type": "article-writer", "agent_transcript_path": str(t)})
    assert record["verdict"] == "ok"


def test_repeated_edits_of_one_file_count_once(tmp_path: Path) -> None:
    target = tmp_path / "article.md"
    target.write_text("article", encoding="utf-8")
    t = transcript(tmp_path, [("Write", str(target)), ("Edit", str(target)), ("Edit", str(target))])
    record = stop_audit.audit({"agent_type": "article-writer", "agent_transcript_path": str(t)})
    assert record["wrote"] == 1


def test_reading_tools_are_not_writing(tmp_path: Path) -> None:
    t = transcript(tmp_path, [("Read", str(tmp_path / "brief.md"))])
    record = stop_audit.audit({"agent_type": "source-finder", "agent_transcript_path": str(t)})
    assert record["verdict"] == "no_writes"


def test_missing_transcript_is_reported_not_crashed(tmp_path: Path) -> None:
    record = stop_audit.audit(
        {"agent_type": "x", "agent_transcript_path": str(tmp_path / "missing.jsonl")}
    )
    assert record["verdict"] == "no_writes"


def test_payload_without_transcript_path(tmp_path: Path) -> None:
    record = stop_audit.audit({"agent_type": "x"})
    assert record["verdict"] == "no_transcript"


def test_broken_lines_in_transcript_are_skipped(tmp_path: Path) -> None:
    target = tmp_path / "material.md"
    target.write_text("material", encoding="utf-8")
    t = transcript(tmp_path, [("Write", str(target))])
    t.write_text("not json\n" + t.read_text(encoding="utf-8"), encoding="utf-8")
    record = stop_audit.audit({"agent_type": "x", "agent_transcript_path": str(t)})
    assert record["verdict"] == "ok"


def test_main_appends_a_line_and_always_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "material.md"
    target.write_text("material", encoding="utf-8")
    t = transcript(tmp_path, [("Write", str(target))])
    log = tmp_path / "log" / "stop-audit.jsonl"
    monkeypatch.setattr(stop_audit, "LOG", log)

    payload = json.dumps({"agent_type": "domain-analyst", "agent_transcript_path": str(t)})
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(payload))
    assert stop_audit.main() == 0

    written = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert len(written) == 1
    assert written[0]["verdict"] == "ok"
    assert "at" in written[0]


def test_garbage_on_stdin_does_not_break_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A hook that crashed on garbage would take the run down with it."""
    monkeypatch.setattr(stop_audit, "LOG", tmp_path / "stop-audit.jsonl")
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO("{not json"))
    assert stop_audit.main() == 0


# --- the form of a path in the record --------------------------------------------------
#
# The only question anyone asks of this log is "what did the agents of THIS run write", and
# that is a plain substring match against the run directory. An absolute path with backslashes
# cannot answer it and ties the log to one machine.


def test_path_inside_the_repo_is_recorded_relative() -> None:
    inside = stop_audit.REPO / "docs-runs" / "x-20260816" / "brief.md"
    assert stop_audit.relative(inside) == "docs-runs/x-20260816/brief.md"


def test_path_outside_the_repo_stays_absolute_but_posix(tmp_path: Path) -> None:
    outside = tmp_path / "foreign.md"
    got = stop_audit.relative(outside)
    assert "\\" not in got
    assert got.endswith("foreign.md")


def test_log_path_is_overridable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """`probe-runs/` was doubly wrong: it is one particular run, not a place for logs."""
    monkeypatch.setenv("COLLIMATOR_STOP_AUDIT", str(tmp_path / "own.jsonl"))
    import importlib

    reloaded = importlib.reload(stop_audit)
    assert reloaded.LOG == tmp_path / "own.jsonl"
    monkeypatch.delenv("COLLIMATOR_STOP_AUDIT")
    importlib.reload(stop_audit)
