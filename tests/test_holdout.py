"""The holdout ruler: shape and grounds, selection by quota, blind batches, the score.

The questions measure what the profile cannot: whether a document answers what the client's
people will ask. Everything here that is not judgement is this tool's, so it is held by tests:
a ground that is not the client's words, a quota a selection breaks, a batch that leaks where a
question came from, an answer whose quote the document does not contain.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import holdout

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "holdout.py"
PROFILE = ROOT / ".claude" / "skills" / "holdout-questions-profile" / "SKILL.md"

TRANSCRIPT = (
    "Owner: On Monday mornings the front desk is on the phone for two hours.\n"
    "Owner: We tried a chatbot two years ago and patients hated it.\n"
    "Office manager: Our IT is one person, and he is part time.\n"
    "Owner: Will it work with our booking system?\n"
)

HEAD = (
    "# Holdout questions: Acme Clinics\n\n"
    "## 1. Readers\n| Role | In the material | Wants | Fears | Source |\n|---|---|---|---|---|\n"
    "| Owner | yes | fewer calls | patients leave | call |\n\n"
    "## 2. Research log\n| # | Query | What came back | Question it changed |\n|---|---|---|---|\n"
    "| 1 | clinic chatbot complaints | https://example.org/a | Q-05 |\n\n"
    "## 3. Questions\n\n"
)


def block(
    qid: str,
    layer: str,
    ground: str,
    weight: str = "important",
    design: str = "answer",
    proposal: str = "answer",
) -> str:
    return (
        f"### {qid}\n- Layer: {layer}\n- Role: Owner\n- Situation: -\n"
        f"- Question: What happens with {qid}?\n- Ground: {ground}\n- Decides: whether to start\n"
        f"- Weight: {weight}\n- Design: {design}\n- Proposal: {proposal}\n\n"
    )


QUOTE = "“On Monday mornings the front desk is on the phone” (call, 00:01)"


def draft(per_layer: int = 9, asked: int = 2) -> str:
    text = HEAD
    n = 0
    for layer in ("asked", "implied", "role", "situation", "domain"):
        count = asked if layer == "asked" else per_layer
        for _ in range(count):
            n += 1
            ground = "https://example.org/a “complaints”" if layer == "domain" else QUOTE
            text += block(
                f"Q-{n:02d}", layer, ground, weight="blocking" if n % 4 == 0 else "important"
            )
    return text


def run(*argv: str) -> dict[str, object]:
    done = subprocess.run(
        [sys.executable, "-X", "utf8", str(TOOL), *argv],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    loaded: dict[str, object] = json.loads(done.stdout)
    return loaded


def write(tmp: Path, name: str, text: str) -> Path:
    path = tmp / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_profile_carries_the_quotas() -> None:
    values, problems = holdout.limits(PROFILE)
    assert not problems
    assert values["draft-min"] == 40 and values["layer-min"] == 4 and values["batch"] == 10


def test_a_sound_draft_passes(tmp_path: Path) -> None:
    f = write(tmp_path, "draft.md", draft(per_layer=10))
    src = write(tmp_path, "inputs/call.md", TRANSCRIPT)
    report = run(
        "--check", "--file", str(f), "--profile", str(PROFILE), "--source", str(src.parent)
    )
    assert report["ok"], report["problems"]
    measures = report["measures"]
    # Two asked and ten in each other layer; the domain grounds are sources, not quotes.
    assert (
        isinstance(measures, dict)
        and measures["questions"] == 42
        and measures["grounds_checked"] == 32
    )


def test_a_ground_that_is_not_the_clients_words_is_named(tmp_path: Path) -> None:
    text = draft().replace(QUOTE, "“On Monday the whole clinic is closed” (call, 00:01)", 1)
    report = run(
        "--check",
        "--file",
        str(write(tmp_path, "d.md", text)),
        "--profile",
        str(PROFILE),
        "--source",
        str(write(tmp_path, "inputs/call.md", TRANSCRIPT).parent),
    )
    assert not report["ok"]
    assert any(
        "Q-01: the ground is not in the client's material" in str(p) for p in report["problems"]
    )  # type: ignore[union-attr]


def test_shape_problems_are_named_by_id() -> None:
    bad = (
        HEAD
        + block("Q-01", "quiz", QUOTE)
        + block("Q-02", "domain", QUOTE)
        + block("Q-03", "implied", "absent role: finance")
    )
    bad += block("Q-04", "role", QUOTE, design="none", proposal="none").replace(
        "- Decides: whether to start\n", ""
    )
    _, _, problems = holdout.parse(bad)
    text = "\n".join(problems)
    assert "Q-01: Layer must be one of" in text
    assert "Q-02: a domain ground names its source URL" in text
    assert "Q-03: only a role question rests on an absent role" in text
    assert "Q-04: missing Decides" in text and "Q-04: no document is expected to answer it" in text


def test_a_draft_outside_the_range_is_refused(tmp_path: Path) -> None:
    report = run(
        "--check",
        "--file",
        str(write(tmp_path, "d.md", draft(per_layer=3))),
        "--profile",
        str(PROFILE),
    )
    assert any("a draft holds 40 to 60 questions" in str(p) for p in report["problems"])  # type: ignore[union-attr]
    final = run(
        "--check",
        "--final",
        "--file",
        str(write(tmp_path, "f.md", draft(per_layer=3))),
        "--profile",
        str(PROFILE),
    )
    assert final["ok"], final["problems"]


def test_select_keeps_every_asked_question_and_copies_blocks_verbatim(tmp_path: Path) -> None:
    src = draft()
    out = tmp_path / "questions.md"
    keep = ",".join(
        f"Q-{n:02d}" for n in (3, 4, 5, 6, 12, 13, 14, 15, 21, 22, 23, 24, 30, 31, 32, 33)
    )
    report = run(
        "--select",
        "--file",
        str(write(tmp_path, "d.md", src)),
        "--keep",
        keep,
        "--out",
        str(out),
        "--profile",
        str(PROFILE),
    )
    assert report["ok"], report["problems"]
    text = out.read_text(encoding="utf-8")
    assert "### Q-01" in text and "### Q-02" in text, "an asked question was dropped"
    for _, body in holdout.split_blocks(text)[1]:
        assert body in src
    assert text.startswith(HEAD)


def test_select_names_a_short_layer_and_too_much_blocking(tmp_path: Path) -> None:
    out = tmp_path / "q.md"
    report = run(
        "--select",
        "--file",
        str(write(tmp_path, "d.md", draft())),
        "--keep",
        "Q-03,Q-04,Q-08,Q-12",
        "--out",
        str(out),
        "--profile",
        str(PROFILE),
    )
    measures = report["measures"]
    assert (
        isinstance(measures, dict)
        and "role" in measures["short_layers"]
        and "domain" in measures["short_layers"]
    )
    assert any("blocking is" in str(p) for p in report["problems"])  # type: ignore[union-attr]


def test_blind_batches_carry_only_the_question_and_who_asks(tmp_path: Path) -> None:
    text = HEAD + "".join(
        block(f"Q-{n:02d}", "implied", QUOTE, design="none" if n == 3 else "answer")
        for n in range(1, 24)
    )
    out = tmp_path / "design"
    write(tmp_path, "design/answers-9.json", "[]")
    report = run(
        "--blind",
        "--file",
        str(write(tmp_path, "q.md", text)),
        "--for",
        "design",
        "--out-dir",
        str(out),
        "--profile",
        str(PROFILE),
    )
    assert report["measures"] == {"batches": 3, "questions": 22, "removed": 1}
    first = (out / "blind-1.md").read_text(encoding="utf-8")
    assert "### Q-01" in first and "- Question:" in first and "- Role:" in first
    for leaked in ("Ground", "Layer", "Weight", "Decides", "Design", "Proposal", "Monday"):
        assert leaked not in first
    assert "Q-03" not in "".join(p.read_text(encoding="utf-8") for p in out.glob("blind-*.md"))


def score(
    tmp_path: Path, answers: list[dict[str, object]], compare: Path | None = None
) -> dict[str, object]:
    text = (
        HEAD
        + block("Q-01", "asked", QUOTE, weight="blocking")
        + block("Q-02", "situation", QUOTE)
        + block("Q-03", "role", "absent role: finance pays", design="acknowledge")
        + block("Q-04", "domain", "https://example.org/a “x”")
    )
    doc = write(
        tmp_path,
        "design.md",
        "## 5. Infrastructure\nThe booking system is reached through its API, every night.\n## 7. Assumptions\nThe running cost is set after discovery.\n",
    )
    write(tmp_path, "design/answers-1.json", json.dumps(answers))
    argv = [
        "--score",
        "--file",
        str(write(tmp_path, "q.md", text)),
        "--for",
        "design",
        "--document",
        str(doc),
        "--answers-dir",
        str(tmp_path / "design"),
        "--out",
        str(tmp_path / "design" / "score.md"),
    ]
    if compare is not None:
        argv += ["--compare", str(compare)]
    return run(*argv)


def test_score_counts_quotes_the_document_holds(tmp_path: Path) -> None:
    report = score(
        tmp_path,
        [
            {
                "id": "Q-01",
                "outcome": "answered",
                "quote": "reached through its API, every night",
                "plain": True,
            },
            {"id": "Q-02", "outcome": "answered", "quote": "a nightly sync with automatic retries"},
            {
                "id": "Q-03",
                "outcome": "acknowledged",
                "quote": "The running cost is set after discovery",
            },
            {
                "id": "Q-04",
                "outcome": "acknowledged",
                "quote": "The running cost is set after discovery",
            },
        ],
    )
    m = report["measures"]
    assert isinstance(m, dict)
    assert m["met"] == 2 and m["expected"] == 4
    assert m["score"] == round((2 + 1) / (2 + 1 + 1 + 1), 2)
    assert m["downgraded_quote_not_found"] == ["Q-02"]
    assert m["acknowledged_instead_of_answered"] == ["Q-04"]
    assert m["absent_blocking"] == []
    table = (tmp_path / "design" / "score.md").read_text(encoding="utf-8")
    assert "| Q-02 | situation |" in table and "| absent |" in table


def test_a_short_quote_and_a_missing_answer_count_as_absent(tmp_path: Path) -> None:
    report = score(tmp_path, [{"id": "Q-01", "outcome": "answered", "quote": "booking"}])
    m = report["measures"]
    assert isinstance(m, dict) and m["met"] == 0 and m["absent_blocking"] == ["Q-01"]
    assert not report["ok"] and any(
        "no answer for Q-02, Q-03, Q-04" in str(p) for p in report["problems"]
    )  # type: ignore[union-attr]


def test_compare_names_what_a_later_pass_lost(tmp_path: Path) -> None:
    before = write(tmp_path, "before/score.json", json.dumps({"met_ids": ["Q-01", "Q-03"]}))
    report = score(tmp_path, [{"id": "Q-01", "outcome": "absent", "quote": ""}], compare=before)
    m = report["measures"]
    assert isinstance(m, dict) and m["lost_since_compared"] == ["Q-01", "Q-03"]


def test_two_readers_who_disagree_leave_the_lower_outcome(tmp_path: Path) -> None:
    first = [
        {"id": "Q-01", "outcome": "answered", "quote": "reached through its API, every night"},
        {
            "id": "Q-03",
            "outcome": "acknowledged",
            "quote": "The running cost is set after discovery",
        },
    ]
    write(tmp_path, "design/answers-1-2.json", json.dumps(first))
    report = score(
        tmp_path,
        [
            {
                "id": "Q-01",
                "outcome": "acknowledged",
                "quote": "The running cost is set after discovery",
            },
            {
                "id": "Q-03",
                "outcome": "acknowledged",
                "quote": "The running cost is set after discovery",
            },
        ],
    )
    m = report["measures"]
    assert isinstance(m, dict) and m["readers"] == 2
    assert m["readers_disagreed"] == ["Q-01"]
    assert m["met"] == 1 and m["absent_blocking"] == ["Q-01"]
    assert m["acknowledged_instead_of_answered"] == ["Q-01"]
    table = (tmp_path / "design" / "score.md").read_text(encoding="utf-8")
    assert "the lower outcome stands: Q-01." in table
