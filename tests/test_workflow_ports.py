"""What the pipeline's agents actually receive in their task text.

Agent counters and result shapes miss the main thing: whether what a person put into the launch
reached the agent. One live run finished successfully, yet no agent read the order text: it was
handed as a port to an `inputs` directory the script never writes. The test runs the real script
on stubs (`tools/dry_run.mjs`) and reads the task texts it handed out.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / ".claude" / "workflows" / "requirements.js"
DRY_RUN = ROOT / "tools" / "dry_run.mjs"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def prompts(tmp_path: Path, args: dict[str, object]) -> list[dict[str, str]]:
    out = tmp_path / "prompts.json"
    env = {**os.environ, "DRY_PROMPTS_OUT": str(out)}
    done = subprocess.run(
        ["node", str(DRY_RUN), str(SCRIPT), "ok", json.dumps(args)],
        cwd=ROOT,
        check=False,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert done.returncode == 0, done.stderr
    loaded: list[dict[str, str]] = json.loads(out.read_text(encoding="utf-8"))
    return loaded


def by_agent(items: list[dict[str, str]], agent_type: str) -> list[str]:
    return [p["prompt"] for p in items if p.get("agentType") == agent_type]


RUN = {"runDir": "dry/run", "now": "2026-09-28T10:00:00+03:00", "config": {"fresh": True}}


# --- attn-figures: what the illustrator is told --------------------------------------------------

FIGURES = ROOT / ".claude" / "workflows" / "attn-figures.js"
FIG_ARGS = {"runDir": "dry/run", "articlePath": "dry/run/design.md", "figures": 3}


def figure_prompts(
    tmp_path: Path, args: dict[str, object], mode: str = "ok"
) -> list[dict[str, str]]:
    out = tmp_path / "prompts.json"
    done = subprocess.run(
        ["node", str(DRY_RUN), str(FIGURES), mode, json.dumps(args)],
        cwd=ROOT,
        check=False,
        env={**os.environ, "DRY_PROMPTS_OUT": str(out)},
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert done.returncode == 0, done.stderr
    loaded: list[dict[str, str]] = json.loads(out.read_text(encoding="utf-8"))
    return loaded


def test_kimi_is_probed_before_the_first_render(tmp_path: Path) -> None:
    labels = [p["label"] for p in figure_prompts(tmp_path, FIG_ARGS)]
    assert labels[0] == "preflight"
    assert "tools/preflight.py --kimi" in figure_prompts(tmp_path, FIG_ARGS)[0]["prompt"]


def test_no_preflight_when_no_separate_critic(tmp_path: Path) -> None:
    labels = [p["label"] for p in figure_prompts(tmp_path, {**FIG_ARGS, "critic": "none"})]
    assert "preflight" not in labels


def test_renders_with_three_candidates_and_never_continues(tmp_path: Path) -> None:
    items = figure_prompts(tmp_path, FIG_ARGS, mode="bad")
    renders = [p["prompt"] for p in items if p["label"].startswith(("draw:", "redraw:"))]
    assert renders and all("--num-candidates 3" in t for t in renders)
    for text in renders:
        commands = [ln for ln in text.splitlines() if ln.lstrip().startswith("<bin> generate")]
        assert commands and not any("--continue-run" in c for c in commands)


def test_brief_carries_the_style_and_the_check_lists(tmp_path: Path) -> None:
    draw = next(p["prompt"] for p in figure_prompts(tmp_path, FIG_ARGS) if p["label"] == "draw:1")
    assert "Clean flat vector style" in draw
    assert "Connections:" in draw and "Boxes:" in draw


PROPOSAL = ROOT / ".claude" / "workflows" / "proposal-review.js"


def test_proposal_review_gates_carry_the_profile_rules(tmp_path: Path) -> None:
    """The proposal profile's rules are checked by the gate, not by a reader: "you", empty cells, links, figures, coverage."""
    out = tmp_path / "prompts.json"
    args = {"runDir": "dry/prop", "document": "dry/prop/prop.md", "sources": ["dry/prop/t.md"]}
    done = subprocess.run(
        ["node", str(DRY_RUN), str(PROPOSAL), "ok", json.dumps(args)],
        cwd=ROOT,
        check=False,
        env={**os.environ, "DRY_PROMPTS_OUT": str(out)},
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert done.returncode == 0, done.stderr
    items = json.loads(out.read_text(encoding="utf-8"))
    gate = next(p for p in by_agent(items, "gate-runner"))
    for flag in (
        "--forbid-outside-quotes",
        "--no-empty-cells",
        "--section-refs",
        "--figures-numbered",
    ):
        assert flag in gate
    assert "tools/coverage.py" in gate and "tools/check_quotes.py" in gate
    assert by_agent(items, "coverage-mapper") and by_agent(items, "proposal-reviewer")


def test_numbered_remarks_still_score_by_severity() -> None:
    """In one run the reviewer numbered its remarks itself ("1. [HIGH] ..."): rounds 2 and 3 counted 0 with
    HIGH remarks open, and the plateau compared zeros. The number is stripped before counting and before the round is recorded."""
    text = PROPOSAL.read_text(encoding="utf-8")
    funcs = [
        m.group(0)
        for m in re.finditer(r"^function (bare|scoreOf)\(.*?^\}", text, re.DOTALL | re.MULTILINE)
    ]
    assert len(funcs) == 2
    probe = (
        "\n".join(funcs)
        + "\nconst r = ['1. [HIGH] a', '2) [MEDIUM] b', '[LOW] c'].map(bare);"
        + "console.log(JSON.stringify([r, scoreOf(r, ['g'])]))"
    )
    done = subprocess.run(
        ["node", "-e", probe], check=True, capture_output=True, text=True, encoding="utf-8"
    )
    assert json.loads(done.stdout) == [["[HIGH] a", "[MEDIUM] b", "[LOW] c"], 12]


def test_client_voice_reaches_the_requirements_writer_and_critic(tmp_path: Path) -> None:
    """A requirement's weight comes from the client voice sheet: the sheet is written before the writer and reaches the critic."""
    items = prompts(tmp_path, RUN)
    labels = [p["label"] for p in items]
    assert labels.index("voice") < labels.index("req:write:1")
    voice = by_agent(items, "client-voice")[0]
    assert "OUTPUT\ndry/run/client-voice.md" in voice and "source:" in voice and "extract:" in voice
    for agent_type in ("requirements-writer", "requirements-critic"):
        prompt = by_agent(items, agent_type)[0]
        assert "client_voice: dry/run/client-voice.md" in prompt and "CLIENT VOICE" in prompt
    gate = next(p for p in by_agent(items, "gate-runner") if "client voice quotes" in p)
    assert 'check_quotes.py --file "dry/run/client-voice.md"' in gate


def word_prompts(tmp_path: Path, mode: str) -> list[dict[str, str]]:
    out = tmp_path / f"word-{mode}.json"
    args = RUN
    env = {
        **os.environ,
        "DRY_PROMPTS_OUT": str(out),
        "DRY_INPUTS": "scope.docx,call.md",
    }
    subprocess.run(
        ["node", str(DRY_RUN), str(SCRIPT), mode, json.dumps(args)],
        cwd=ROOT,
        check=False,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    loaded: list[dict[str, str]] = json.loads(out.read_text(encoding="utf-8"))
    return loaded


def test_word_documents_become_markdown_before_extraction(tmp_path: Path) -> None:
    """Read cannot read .docx: the pipeline converts it to .md itself and hands the agent the text."""
    items = word_prompts(tmp_path, "ok")
    convert = next(p for p in by_agent(items, "file-copier") if "to_text.py" in p)
    assert "--dir dry/run/inputs" in convert and "scope.docx" not in convert
    extracts = by_agent(items, "source-processor")
    assert any("source: dry/run/inputs/scope.docx.md" in p for p in extracts)
    assert not any("source: dry/run/inputs/scope.docx\n" in p for p in extracts)


def test_failed_conversion_never_hands_a_missing_markdown(tmp_path: Path) -> None:
    """If pandoc failed, the agent gets the original file, not a .md that does not exist."""

    items = word_prompts(tmp_path, "bad")
    extracts = by_agent(items, "source-processor")
    assert not any("scope.docx.md" in p for p in extracts)


@pytest.mark.parametrize("dead", ["plan", "draw", "critic-used", "look", "redraw", "gate", "*"])
def test_figures_survive_a_dead_agent(tmp_path: Path, dead: str) -> None:
    """agent() returns null when a subagent dies; the script names it, it never throws a TypeError."""
    for mode in ("ok", "bad"):
        done = subprocess.run(
            ["node", str(DRY_RUN), str(FIGURES), mode, json.dumps(FIG_ARGS)],
            cwd=ROOT,
            check=False,
            env={**os.environ, "DRY_NULL": dead},
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        crash = done.stdout + done.stderr
        assert "TypeError" not in crash and "ReferenceError" not in crash, crash[-600:]


def test_an_unchecked_figure_is_never_accepted(tmp_path: Path) -> None:
    """A figure critic that returned nothing has checked nothing: the figures are redrawn."""
    items = figure_prompts(tmp_path, FIG_ARGS)
    assert any(p["label"] == "look:1" for p in items)
    done = subprocess.run(
        ["node", str(DRY_RUN), str(FIGURES), "ok", json.dumps(FIG_ARGS)],
        cwd=ROOT,
        check=False,
        env={**os.environ, "DRY_NULL": "look"},
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert "counted as unchecked" in done.stdout and "redraw:1" in done.stdout


TREE = (
    "scope.docx,call/transcript.md,call/transcript.html,call/frames/f1.png,"
    "call/digest.md|ours,dup.md|client|call/transcript.md,rec.mp4,lone/pic.png"
)


def tree_run(tmp_path: Path, inputs: str = TREE) -> tuple[list[dict[str, str]], str]:
    out = tmp_path / "tree.json"
    args = RUN
    done = subprocess.run(
        ["node", str(DRY_RUN), str(SCRIPT), "ok", json.dumps(args)],
        cwd=ROOT,
        check=False,
        env={**os.environ, "DRY_PROMPTS_OUT": str(out), "DRY_INPUTS": inputs},
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    loaded: list[dict[str, str]] = json.loads(out.read_text(encoding="utf-8"))
    return loaded, done.stdout


def test_subfolders_are_read_not_only_named(tmp_path: Path) -> None:
    items, _ = tree_run(tmp_path)
    sources = [p.split("OUTPUT")[0] for p in by_agent(items, "source-processor")]
    assert any("source: dry/run/inputs/call/transcript.md" in s for s in sources)
    assert any("source: dry/run/inputs/call/digest.md" in s for s in sources)


def test_duplicates_formats_and_media_are_read_once(tmp_path: Path) -> None:
    items, log = tree_run(tmp_path)
    sources = "\n".join(by_agent(items, "source-processor"))
    assert "dup.md" not in sources and "transcript.html" not in sources and "rec.mp4" not in sources
    assert "another format of call/transcript.md" in log and "rec.mp4: audio or video" in log


def test_frames_go_with_the_client_transcript(tmp_path: Path) -> None:
    items, _ = tree_run(tmp_path)
    transcript = next(p for p in by_agent(items, "source-processor") if "call/transcript.md" in p)
    assert "images: dry/run/inputs/call/frames" in transcript
    lone = next(p for p in by_agent(items, "source-processor") if "lone/pic.png" in p)
    assert "images:" not in lone.split("OUTPUT")[0]


def test_our_notes_are_marked_down_to_the_requirements_writer(tmp_path: Path) -> None:
    items, _ = tree_run(tmp_path)
    digest = next(p for p in by_agent(items, "source-processor") if "call/digest.md" in p)
    assert "OUR NOTE" in digest
    writer = by_agent(items, "requirements-writer")[0]
    assert "OUR NOTES, NOT THE CLIENT'S WORDS" in writer and "extract:call__digest" in writer


def test_file_names_in_commands_are_quoted_and_ascii(tmp_path: Path) -> None:
    # A client file name with a space and one in Cyrillic, as client folders arrive.
    items, _ = tree_run(tmp_path, "Phase 1 Scope.md,Договор.md")
    gate = next(p["prompt"] for p in items if p["label"] == "extract:gate:Phase-1-Scope")
    assert '--file "dry/run/extracts/Phase-1-Scope.md"' in gate
    for prompt in by_agent(items, "gate-runner") + by_agent(items, "file-copier"):
        commands = prompt.split("COMMANDS", 1)[-1]
        assert all(ord(ch) < 128 for ch in commands)
