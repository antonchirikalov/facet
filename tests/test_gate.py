"""Tests of the deterministic gate.

The gate is called by a workflow stage and its JSON is the only thing the script looks at, so
both sides are tested: the wording of the problems (the fix loop branches on it) and the
measurements (thresholds in the templates are set from them). The wording matches the old engine
on purpose: reports stay comparable between the two implementations.

Russian forbidden phrases (the shipped ru-slop list) stay Russian: they are
the language material the gate exists to match.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import gate
import pytest

WINDOWS_ONLY = pytest.mark.skipif(
    sys.platform != "win32", reason="the msys path form exists only next to a drive letter"
)


def run(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    *argv: str,
) -> tuple[dict[str, Any], int]:
    """Call the gate as a shell would and parse its JSON."""
    monkeypatch.setattr(sys, "argv", ["gate.py", *argv])
    code = gate.main()
    printed = capsys.readouterr().out
    report: dict[str, Any] = json.loads(printed)
    return report, code


def msys_form(path: Path) -> str:
    """`C:\\Users\\x\\f.md` -> `/c/Users/x/f.md`, which is what Git Bash puts into argv."""
    drive, rest = path.as_posix().split(":", 1)
    return f"/{drive.lower()}{rest}"


def write(tmp_path: Path, text: str, name: str = "doc.md") -> Path:
    target = tmp_path / name
    target.write_text(text, encoding="utf-8")
    return target


# --- prose_of: what is subtracted from a file before prose is counted ---------------


def test_prose_drops_fenced_block() -> None:
    assert gate.prose_of("text\n```\nprint(1)\n```\nmore") == "text\nmore"


def test_prose_drops_html_comment() -> None:
    assert gate.prose_of("before <!-- a note\non two lines --> after") == "before  after"


def test_prose_drops_table_rows() -> None:
    """Table rows go together with their newlines; the paragraph break stays."""
    text = "head\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\ntail"
    assert gate.prose_of(text) == "head\n\n\ntail"


def test_prose_drops_images_but_keeps_link_text() -> None:
    assert gate.prose_of("![caption](fig.png)") == ""
    assert gate.prose_of("see [the docs](https://example.com/docs)") == "see the docs"


def test_prose_drops_heading_and_list_marks() -> None:
    assert gate.prose_of("## Heading") == "Heading"
    assert gate.prose_of("- item\n* second\n+ third\n1. numbered") == (
        "item\nsecond\nthird\nnumbered"
    )


def test_prose_drops_backticks_and_emphasis() -> None:
    assert gate.prose_of("call `gate.py` and **loud** and _quiet_") == (
        "call gate.py and loud and quiet"
    )


def test_prose_trims_around_newlines_and_strips_edges() -> None:
    """Indentation around newlines goes, and the blank line between paragraphs stays:
    paragraph division is part of the readable text, and its characters fairly enter the count."""
    assert gate.prose_of("\n\n  first  \n   \n  second  \n\n") == "first\n\nsecond"


def test_prose_counts_less_than_file() -> None:
    """The lesson itself: a file carries markup, a brief asks for readable text."""
    text = "# Heading\n\n| a | b |\n|---|---|\n\n```\ncode\n```\n\nOne sentence."
    assert len(gate.prose_of(text)) < len(text)


# --- --file: measurements and thresholds ----------------------------------------------


def test_file_measures_chars_and_prose(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc = write(tmp_path, "# Head\n\nExactly one sentence.")
    report, code = run(capsys, monkeypatch, "--file", str(doc))
    assert report["ok"] is True
    assert report["problems"] == []
    assert report["measures"]["chars"] == len(doc.read_text(encoding="utf-8"))
    assert report["measures"]["prose_chars"] == len("Head\n\nExactly one sentence.")
    assert code == 0


def test_file_missing_is_a_problem_without_measures(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    absent = tmp_path / "absent.md"
    report, code = run(capsys, monkeypatch, "--file", str(absent))
    assert report["ok"] is False
    assert report["problems"] == [f"output missing: {absent.as_posix()}"]
    assert report["measures"] == {}
    assert code == 0


def test_max_length_exceeded_and_met(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc = write(tmp_path, "x" * 50)
    report, _ = run(capsys, monkeypatch, "--file", str(doc), "--max-length", "10")
    assert report["problems"] == ["max_length 10 exceeded (got 50)"]
    report, _ = run(capsys, monkeypatch, "--file", str(doc), "--max-length", "50")
    assert report["ok"] is True


def test_min_length_not_met_and_met(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc = write(tmp_path, "x" * 50)
    report, _ = run(capsys, monkeypatch, "--file", str(doc), "--min-length", "200")
    assert report["problems"] == ["min_length 200 not met (got 50)"]
    report, _ = run(capsys, monkeypatch, "--file", str(doc), "--min-length", "50")
    assert report["ok"] is True


def test_max_prose_exceeded_and_met(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc = write(tmp_path, "word " * 20)
    prose = len(gate.prose_of(doc.read_text(encoding="utf-8")))
    report, _ = run(capsys, monkeypatch, "--file", str(doc), "--max-prose", "10")
    assert report["problems"] == [f"max_prose 10 exceeded (got {prose})"]
    report, _ = run(capsys, monkeypatch, "--file", str(doc), "--max-prose", str(prose))
    assert report["ok"] is True


def test_min_prose_not_met_matches_probe_wording(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Exactly this wording went into the fix round prompt in a live run."""
    doc = write(tmp_path, "briefly")
    report, _ = run(capsys, monkeypatch, "--file", str(doc), "--min-prose", "4500")
    assert report["problems"] == ["min_prose 4500 not met (got 7)"]


def test_min_prose_met(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc = write(tmp_path, "x" * 100)
    report, _ = run(capsys, monkeypatch, "--file", str(doc), "--min-prose", "100")
    assert report["ok"] is True


def test_all_four_length_rules_report_together(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Failures do not short-circuit: the fix round agent must see all of them at once."""
    doc = write(tmp_path, "short")
    report, _ = run(
        capsys,
        monkeypatch,
        "--file",
        str(doc),
        "--max-length",
        "1",
        "--min-length",
        "99",
        "--max-prose",
        "1",
        "--min-prose",
        "99",
    )
    assert len(report["problems"]) == 4


# --- --forbid ------------------------------------------------------------------------


def test_forbid_reports_count_and_sample(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc = write(tmp_path, "стоит отметить раз, стоит отметить два")
    report, _ = run(
        capsys, monkeypatch, "--file", str(doc), "--forbid", "стоит отметить|важно понимать"
    )
    assert report["ok"] is False
    assert report["problems"] == [
        "forbidden pattern matched 2x: стоит отметить|важно понимать (стоит отметить)"
    ]
    assert report["measures"]["regex"] == {"стоит отметить|важно понимать": 2}


def test_forbid_is_case_insensitive(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc = write(tmp_path, "Стоит Отметить")
    report, _ = run(capsys, monkeypatch, "--file", str(doc), "--forbid", "стоит отметить")
    assert report["measures"]["regex"] == {"стоит отметить": 1}


def test_forbid_sample_is_capped_at_three_distinct(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc = write(tmp_path, "word1 word2 word3 word4 word5")
    report, _ = run(capsys, monkeypatch, "--file", str(doc), "--forbid", r"word\d")
    assert report["problems"] == [r"forbidden pattern matched 5x: word\d (word1, word2, word3)"]


def test_forbid_repeatable_and_independent(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc = write(tmp_path, "first and third")
    report, _ = run(
        capsys,
        monkeypatch,
        "--file",
        str(doc),
        "--forbid",
        "first",
        "--forbid",
        "second",
        "--forbid",
        "third",
    )
    assert len(report["problems"]) == 2
    assert report["measures"]["regex"] == {"first": 1, "second": 0, "third": 1}


def test_forbid_clean_still_records_zero(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A zero in measures is the proof that the rule was checked rather than skipped."""
    doc = write(tmp_path, "clean text")
    report, _ = run(capsys, monkeypatch, "--file", str(doc), "--forbid", "стоит отметить")
    assert report["ok"] is True
    assert report["measures"]["regex"] == {"стоит отметить": 0}


def test_no_forbid_means_no_regex_key(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc = write(tmp_path, "short")
    report, _ = run(capsys, monkeypatch, "--file", str(doc))
    assert "regex" not in report["measures"]


# --- --forbid-file ---------------------------------------------------------------------
#
# Patterns live in files, not in code: they are the editorial policy of a language, data a
# person edits. And not in argv: Cyrillic through a command line on Windows depends on the
# codepage and on which shell the carrying agent picked.


def slop(tmp_path: Path, *patterns: str, name: str = "slop.txt") -> Path:
    target = tmp_path / name
    target.write_text("\n".join(patterns) + "\n", encoding="utf-8")
    return target


def test_pattern_from_file_is_found(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc = write(tmp_path, "Здесь стоит отметить одну вещь.")
    rules = slop(tmp_path, "стоит отметить")
    report, _ = run(capsys, monkeypatch, "--file", str(doc), "--forbid-file", str(rules))
    assert report["ok"] is False
    assert any("slop.txt matched 1x" in p for p in report["problems"])


def test_missing_pattern_file_is_a_problem(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A gate without patterns found no violations, which reads exactly like a gate that passed."""
    doc = write(tmp_path, "short")
    report, _ = run(
        capsys, monkeypatch, "--file", str(doc), "--forbid-file", str(tmp_path / "absent.txt")
    )
    assert report["ok"] is False
    assert any("pattern file missing" in p for p in report["problems"])


def test_comments_and_blank_lines_are_ignored(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rules = slop(tmp_path, "# a comment", "", "стоит отметить", "   # and this")
    doc = write(tmp_path, "стоит отметить")
    report, _ = run(capsys, monkeypatch, "--file", str(doc), "--forbid-file", str(rules))
    assert len(report["measures"]["forbidden"]) == 1


def test_bold_file_ignores_python_power_in_a_fenced_block(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """This is why the search runs outside code: `d_k ** 0.5` is a power, not bold."""
    doc = write(tmp_path, "text\n```python\nscores = q @ k.T / d_k ** 0.5\n```\nmore")
    rules = slop(tmp_path, r"\*\*[^\n*]+\*\*", name="bold.txt")
    report, _ = run(capsys, monkeypatch, "--file", str(doc), "--forbid-file", str(rules))
    assert report["ok"] is True


def test_several_files_are_independent(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    a = slop(tmp_path, "first", name="a.txt")
    b = slop(tmp_path, "second", name="b.txt")
    doc = write(tmp_path, "only first")
    report, _ = run(
        capsys, monkeypatch, "--file", str(doc), "--forbid-file", str(a), "--forbid-file", str(b)
    )
    assert len(report["problems"]) == 1
    assert report["measures"]["forbidden"] == {"first": 1, "second": 0}


def test_clean_text_still_records_every_pattern(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Zeros in measures are the proof that the rule was checked rather than skipped."""
    rules = slop(tmp_path, "стоит отметить", "важно понимать")
    doc = write(tmp_path, "Plain text.")
    report, _ = run(capsys, monkeypatch, "--file", str(doc), "--forbid-file", str(rules))
    assert report["ok"] is True
    assert set(report["measures"]["forbidden"].values()) == {0}


def test_shipped_files_load_and_are_not_empty() -> None:
    """The files the pipeline uses must load and contain something."""
    root = Path(__file__).resolve().parent.parent
    for name in ("ru-slop.txt", "no-bold.txt"):
        patterns, problems = gate.patterns_of(root / "library" / "style" / "forbid" / name)
        assert problems == []
        assert patterns


def test_shipped_ru_slop_keeps_the_authors_own_transition(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The author's own transition "let us figure it out" is allowed; "let us go through each item" is filler."""
    root = Path(__file__).resolve().parent.parent
    doc = write(tmp_path, "Давайте разбираться. Поехали.")
    report, _ = run(
        capsys,
        monkeypatch,
        "--file",
        str(doc),
        "--forbid-file",
        str(root / "library" / "style" / "forbid" / "ru-slop.txt"),
    )
    assert report["ok"] is True


def test_shipped_ru_slop_catches_a_dead_phrase(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = Path(__file__).resolve().parent.parent
    doc = write(tmp_path, "Здесь стоит отметить одну вещь.")
    report, _ = run(
        capsys,
        monkeypatch,
        "--file",
        str(doc),
        "--forbid-file",
        str(root / "library" / "style" / "forbid" / "ru-slop.txt"),
    )
    assert report["ok"] is False


# --- --dir ---------------------------------------------------------------------------


def test_dir_missing(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    absent = tmp_path / "absent"
    report, _ = run(capsys, monkeypatch, "--dir", str(absent))
    assert report["problems"] == [f"output directory missing: {absent.as_posix()}"]
    assert report["measures"] == {}


def test_dir_is_a_file_counts_as_missing(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc = write(tmp_path, "short")
    report, _ = run(capsys, monkeypatch, "--dir", str(doc))
    assert report["problems"] == [f"output directory missing: {doc.as_posix()}"]


def test_dir_empty(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    report, _ = run(capsys, monkeypatch, "--dir", str(empty))
    assert report["problems"] == ["output directory has no content"]
    assert report["measures"]["entries"] == 0


def test_dir_empty_with_min_entries_reports_both(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    report, _ = run(capsys, monkeypatch, "--dir", str(empty), "--min-entries", "5")
    assert report["problems"] == [
        "output directory has no content",
        "min_entries 5 not met (got 0)",
    ]


def test_min_entries_not_met_matches_old_engine_wording(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    d = tmp_path / "figures"
    d.mkdir()
    (d / "fig1.png").write_bytes(b"")
    report, _ = run(capsys, monkeypatch, "--dir", str(d), "--min-entries", "5")
    assert report["problems"] == ["min_entries 5 not met (got 1)"]


def test_min_entries_met(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    d = tmp_path / "figures"
    d.mkdir()
    for i in range(5):
        (d / f"fig{i}.png").write_bytes(b"")
    report, _ = run(capsys, monkeypatch, "--dir", str(d), "--min-entries", "5")
    assert report["ok"] is True
    assert report["measures"]["entries"] == 5


def test_entries_counts_direct_children_only(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    d = tmp_path / "dir"
    (d / "nested").mkdir(parents=True)
    (d / "nested" / "deep.png").write_bytes(b"")
    (d / "beside.png").write_bytes(b"")
    report, _ = run(capsys, monkeypatch, "--dir", str(d))
    assert report["measures"]["entries"] == 2


def test_file_and_dir_measured_in_one_call(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc = write(tmp_path, "article text")
    d = tmp_path / "figures"
    d.mkdir()
    (d / "fig.png").write_bytes(b"")
    report, _ = run(capsys, monkeypatch, "--file", str(doc), "--dir", str(d))
    assert report["measures"]["chars"] == 12
    assert report["measures"]["entries"] == 1


def test_no_arguments_at_all_passes_empty(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    report, code = run(capsys, monkeypatch)
    assert report == {"ok": True, "problems": [], "measures": {}}
    assert code == 0


# --- exit code -----------------------------------------------------------------------


def test_failure_exits_zero_by_default(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An agent would read a non-zero code as "the command broke": the verdict travels in JSON."""
    doc = write(tmp_path, "briefly")
    report, code = run(capsys, monkeypatch, "--file", str(doc), "--min-prose", "999")
    assert report["ok"] is False
    assert code == 0


def test_failure_exits_one_under_strict(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc = write(tmp_path, "briefly")
    report, code = run(capsys, monkeypatch, "--file", str(doc), "--min-prose", "999", "--strict")
    assert report["ok"] is False
    assert code == 1


def test_success_exits_zero_under_strict(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc = write(tmp_path, "long enough text")
    _, code = run(capsys, monkeypatch, "--file", str(doc), "--min-prose", "5", "--strict")
    assert code == 0


def test_output_keeps_cyrillic_readable(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """ensure_ascii=False: the remark goes into an agent prompt and must stay readable."""
    doc = write(tmp_path, "стоит отметить")
    monkeypatch.setattr(sys, "argv", ["gate.py", "--file", str(doc), "--forbid", "стоит отметить"])
    gate.main()
    assert "стоит отметить" in capsys.readouterr().out


# --- resolve_path: the msys path form ------------------------------------------------


def test_resolve_keeps_existing_path_untouched(tmp_path: Path) -> None:
    doc = write(tmp_path, "short")
    assert gate.resolve_path(doc) == doc


def test_resolve_leaves_non_msys_missing_path_alone(tmp_path: Path) -> None:
    absent = tmp_path / "absent.md"
    assert gate.resolve_path(absent) == absent


def test_resolve_leaves_msys_path_alone_when_windows_form_also_missing() -> None:
    """Do not turn "no such file" into "no other file": the message must name argv."""
    absent = Path("/c/no/such/directory/doc.md")
    assert gate.resolve_path(absent) == absent


@WINDOWS_ONLY
def test_resolve_finds_file_behind_msys_path(tmp_path: Path) -> None:
    doc = write(tmp_path, "short")
    assert gate.resolve_path(Path(msys_form(doc))) == doc


@WINDOWS_ONLY
def test_resolve_finds_directory_behind_msys_path(tmp_path: Path) -> None:
    d = tmp_path / "figures"
    d.mkdir()
    assert gate.resolve_path(Path(msys_form(d))) == d


@WINDOWS_ONLY
def test_resolve_accepts_uppercase_drive_letter(tmp_path: Path) -> None:
    doc = write(tmp_path, "short")
    upper = msys_form(doc).replace("/c/", "/C/", 1)
    assert gate.resolve_path(Path(upper)) == doc


@WINDOWS_ONLY
def test_resolve_handles_drive_root() -> None:
    assert gate.resolve_path(Path("/c")) == Path("C:/")


def test_resolve_ignores_multi_letter_first_segment(tmp_path: Path) -> None:
    """One letter is a drive; `/cygdrive/...` and `/usr/...` do not fall under the rule."""
    absent = Path("/cygdrive/c/Users/x/doc.md")
    assert gate.resolve_path(absent) == absent


@WINDOWS_ONLY
def test_gate_measures_file_given_in_msys_form(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The end-to-end case from a run: gate:1 received `/c/Users/.../sources.md`."""
    text = "enough text to be measured"
    doc = write(tmp_path, text)
    report, code = run(capsys, monkeypatch, "--file", msys_form(doc), "--min-prose", "5")
    assert report["ok"] is True
    assert report["measures"]["chars"] == len(text)
    assert code == 0


@WINDOWS_ONLY
def test_gate_counts_dir_given_in_msys_form(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    d = tmp_path / "figures"
    d.mkdir()
    (d / "fig.png").write_bytes(b"")
    report, _ = run(capsys, monkeypatch, "--dir", msys_form(d), "--min-entries", "1")
    assert report["ok"] is True
    assert report["measures"]["entries"] == 1


def test_missing_msys_file_message_names_the_path_as_given(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    given = "/c/no/such/directory/doc.md"
    report, _ = run(capsys, monkeypatch, "--file", given)
    assert report["problems"] == [f"output missing: {Path(given).as_posix()}"]


# --- call log ------------------------------------------------------------------------
#
# Otherwise everything the tool measured lives only in the workflow's `log()`: readable while
# someone watches the run, and gone once it has ended. The receipt is written by whoever measured.


def test_log_line_carries_the_call_and_the_verdict(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc = write(tmp_path, "short")
    log = tmp_path / "tools.jsonl"
    run(capsys, monkeypatch, "--file", str(doc), "--max-length", "2", "--log", str(log))
    line = json.loads(log.read_text(encoding="utf-8").strip())
    assert line["tool"] == "gate"
    assert line["ok"] is False
    assert line["measures"]["chars"] == 5
    assert any("max_length" in p for p in line["problems"])
    assert "--max-length" in line["argv"]
    assert line["at"]


def test_log_appends_rather_than_replaces(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc = write(tmp_path, "short")
    log = tmp_path / "tools.jsonl"
    run(capsys, monkeypatch, "--file", str(doc), "--log", str(log))
    run(capsys, monkeypatch, "--file", str(doc), "--log", str(log))
    assert len(log.read_text(encoding="utf-8").strip().splitlines()) == 2


def test_log_holds_no_payload(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A line must stay readable after fifty more like it, so the content does not go into it."""
    doc = write(tmp_path, "text " * 5000)
    log = tmp_path / "tools.jsonl"
    run(capsys, monkeypatch, "--file", str(doc), "--log", str(log))
    assert len(log.read_text(encoding="utf-8")) < 600


def test_without_log_nothing_is_written(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc = write(tmp_path, "short")
    run(capsys, monkeypatch, "--file", str(doc))
    assert list(tmp_path.glob("*.jsonl")) == []


def test_unwritable_log_does_not_fail_the_check(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Losing a run to a broken receipt is worse than losing the receipt."""
    doc = write(tmp_path, "short")
    blocked = tmp_path / "taken"
    blocked.write_text("not a directory", encoding="utf-8")
    report, code = run(
        capsys, monkeypatch, "--file", str(doc), "--log", str(blocked / "tools.jsonl")
    )
    assert report["ok"] is True
    assert code == 0


def test_no_problem_message_spells_a_path_the_windows_way(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The script passed `docs-runs/x.md`, so the complaint says `docs-runs/x.md` too.

    The message is read later both by eye and by searching the log: the only question asked of
    it, "what was written in this run", is a substring match against the run directory, and a
    path with backslashes does not match it.
    """
    absent, _ = run(
        capsys,
        monkeypatch,
        "--file",
        str(tmp_path / "absent" / "absent.md"),
        "--dir",
        str(tmp_path / "also-absent"),
    )
    # Missing rules show only on an existing file: without a file there is nothing to check,
    # and the gate never gets as far as reading the patterns.
    rules, _ = run(
        capsys,
        monkeypatch,
        "--file",
        str(write(tmp_path, "short")),
        "--forbid-file",
        str(tmp_path / "no-rules.txt"),
    )
    problems = absent["problems"] + rules["problems"]
    assert len(problems) == 3
    assert not [p for p in problems if "\\" in p]


def test_log_note_records_what_the_call_was_for(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A missing file at the input of a run is an answer, at the output a defect. Only the note tells them apart."""
    log = tmp_path / "tools.jsonl"
    run(
        capsys,
        monkeypatch,
        "--file",
        str(tmp_path / "absent.md"),
        "--log",
        str(log),
        "--log-note",
        "resume: what is already done",
    )
    line = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert line["note"] == "resume: what is already done"


def test_log_note_is_optional(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc = write(tmp_path, "short")
    log = tmp_path / "tools.jsonl"
    run(capsys, monkeypatch, "--file", str(doc), "--log", str(log))
    assert json.loads(log.read_text(encoding="utf-8").splitlines()[0])["note"] is None


# --- --no-empty-sections ---------------------------------------------------------------
#
# A length floor catches "the agent wrote nothing" and misses what actually happens: the agent
# writes the SHAPE of the artifact, every heading of the contract in the right order, and leaves
# the work outside it. Measured live: an analysis of 25 sources came back as 1748 bytes of
# headings alone, far above any floor such a document would be given.


def test_heading_without_content_is_named(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc = write(tmp_path, "# Analysis\n\n## established\n\n## implications\n\nThis one is here.\n")
    report, _ = run(capsys, monkeypatch, "--file", str(doc), "--no-empty-sections")
    assert report["ok"] is False
    assert report["measures"]["empty_sections"] == ["established"]
    assert "established" in report["problems"][0]


def test_filled_document_passes(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc = write(tmp_path, "# Heading\n\ntext\n\n## Section\n\nmore text\n")
    report, _ = run(capsys, monkeypatch, "--file", str(doc), "--no-empty-sections")
    assert report["ok"] is True
    assert report["measures"]["empty_sections"] == []


def test_parent_is_filled_by_a_filled_child(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """This is how a reader sees it: a section whose subsection is filled is not empty."""
    doc = write(tmp_path, "# Top\n\n## Bottom\n\ncontent\n")
    report, _ = run(capsys, monkeypatch, "--file", str(doc), "--no-empty-sections")
    assert report["measures"]["empty_sections"] == []


def test_trailing_heading_counts_as_empty(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Exactly what an agent that died midway through filling the skeleton leaves behind."""
    doc = write(tmp_path, "# Top\n\ntext\n\n## Last\n")
    report, _ = run(capsys, monkeypatch, "--file", str(doc), "--no-empty-sections")
    assert report["measures"]["empty_sections"] == ["Last"]


def test_line_floor_ignores_a_token_line(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A dash instead of work is an empty section too, when the caller names a meaningful length."""
    doc = write(tmp_path, "# Top\n\n## Section\n\n—\n")
    lenient, _ = run(capsys, monkeypatch, "--file", str(doc), "--no-empty-sections")
    strict, _ = run(capsys, monkeypatch, "--file", str(doc), "--no-empty-sections", "20")
    assert lenient["measures"]["empty_sections"] == []
    assert strict["measures"]["empty_sections"] == ["Section"]


def test_check_is_off_unless_asked(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc = write(tmp_path, "# Empty\n")
    report, _ = run(capsys, monkeypatch, "--file", str(doc))
    assert report["ok"] is True
    assert "empty_sections" not in report["measures"]


def test_require_line_found_and_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    target = write(tmp_path, "# Requirements run\n\n1. Accepted: yes; rounds: 2 of 3\n")
    report, _ = run(
        capsys, monkeypatch, "--file", str(target), "--require-line", r"^1\. Accepted: yes"
    )
    assert report["ok"] and report["measures"]["missing_lines"] == []
    report, _ = run(capsys, monkeypatch, "--file", str(target), "--require-line", r"Accepted: no")
    assert not report["ok"] and "required line missing" in report["problems"][0]


def test_require_in_section_finds_the_note_in_its_own_section(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    doc = (
        "## 1. Overview\ntext\n> Everything here is preliminary.\n"
        "## 5. How it is built\n### 5.1 Parts\nparts\n"
        "## 6. Plan\n> The plan is preliminary.\n"
    )
    target = write(tmp_path, doc)
    rules = [
        r"^##\s+1\.::^>.*[Pp]reliminary",
        r"^##\s+5\.::^>.*[Pp]reliminary",
        r"^##\s+6\.::^>.*[Pp]reliminary",
    ]
    argv = ["--file", str(target)]
    for r in rules:
        argv += ["--require-in-section", r]
    report, _ = run(capsys, monkeypatch, *argv)
    assert not report["ok"]
    assert report["measures"]["missing_in_sections"] == [rules[1]]


def test_require_in_section_names_a_missing_section() -> None:
    assert gate.missing_in_sections("## 1. A\nx\n", [r"^##\s+9\.::x"]) == [
        r"^##\s+9\.::x (no such section)"
    ]


def test_a_profile_gate_block_supplies_the_flags(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    profile = write(
        tmp_path,
        "# Profile\n\n## Gate rules\n\n```gate\n# headings by number\n"
        r'--require-heading "^##\s+1\." --require-heading "^##\s+2\."' "\n"
        r'--forbid "\x60"' "\n```\n",
        name="SKILL.md",
    )
    doc = write(tmp_path, "## 1. One\ntext\n")
    report, _ = run(capsys, monkeypatch, "--file", str(doc), "--profile", str(profile))
    assert not report["ok"]
    assert report["measures"]["missing_headings"] == [r"^##\s+2\."]


def test_a_profile_without_a_gate_block_is_a_problem(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    profile = write(tmp_path, "# Profile\nno block\n", name="SKILL.md")
    doc = write(tmp_path, "## 1. One\n")
    report, _ = run(capsys, monkeypatch, "--file", str(doc), "--profile", str(profile))
    assert any("no gate block" in p for p in report["problems"])
