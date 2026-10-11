"""Missing input and the holdout questions, as the pipelines run them on stubs.

Two mechanisms that only work if their boundaries hold. A writer may answer a remark
needs_context when the inputs hold no data, which takes it out of the rounds onto a record of
what to ask the client; a measurement can never be answered so, and a remark the critic contests
cannot be answered so twice. The holdout questions are written from the client's material and
scored after the rounds; the moment a writer or a critic is handed them, they measure nothing.
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
WORKFLOWS = ROOT / ".claude" / "workflows"
DRY_RUN = ROOT / "tools" / "dry_run.mjs"
NOW = "2026-10-10T12:00:00+03:00"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

# The only agents that may see a holdout path: the three of the holdout, and the carriers that run
# its tool or write its record.
HOLDOUT_AGENTS = {
    "client-questioner",
    "question-skeptic",
    "answer-finder",
    "gate-runner",
    "file-copier",
    "verbatim-writer",
}


def dry(
    tmp_path: Path, script: str, mode: str, args: dict[str, object], **env: str
) -> tuple[list[dict[str, str]], str]:
    out = tmp_path / f"{script}-{mode}.json"
    done = subprocess.run(
        ["node", str(DRY_RUN), str(WORKFLOWS / script), mode, json.dumps(args)],
        cwd=ROOT,
        check=False,
        env={**os.environ, "DRY_PROMPTS_OUT": str(out), **env},
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert done.returncode == 0, done.stderr
    loaded: list[dict[str, str]] = json.loads(out.read_text(encoding="utf-8"))
    return loaded, done.stdout


def prompt(items: list[dict[str, str]], label: str) -> str:
    found = [p["prompt"] for p in items if p["label"] == label]
    assert found, f"no call {label}: {[p['label'] for p in items]}"
    return found[0]


REQ = {"runDir": "dry/r", "now": NOW, "config": {"fresh": True}}
DESIGN = {"runDir": "dry/r", "now": NOW, "type": "ai-solution", "config": {"fresh": True}}
PROP = {
    "runDir": "dry/r",
    "now": NOW,
    "client": "Acme Clinics",
    "config": {"fresh": True, "mediumLimit": 1},
}
ANSWER_ALL = {"DRY_ANSWER_ALL": "1", "DRY_ENUM": "needs_context"}


@pytest.mark.parametrize(
    ("script", "mode", "args", "env"),
    [
        ("requirements.js", "ok", REQ, {}),
        ("requirements.js", "bad", REQ, {}),
        ("design.js", "ok", DESIGN, {}),
        ("design.js", "bad", DESIGN, {"DRY_EXISTS_OK": "1"}),
        ("proposal.js", "ok", PROP, {}),
        ("proposal.js", "ok", {**PROP, "config": {"stages": ["text"]}}, {}),
    ],
)
def test_no_writer_or_critic_is_handed_the_holdout(
    tmp_path: Path, script: str, mode: str, args: dict[str, object], env: dict[str, str]
) -> None:
    items, _ = dry(tmp_path, script, mode, args, **env)
    assert any("/holdout/" in p["prompt"] for p in items), "the holdout step did not run"
    leaked = [
        p["label"]
        for p in items
        if p["agentType"] not in HOLDOUT_AGENTS and "/holdout/" in p["prompt"]
    ]
    assert not leaked, f"handed the holdout: {leaked}"


def test_the_questions_are_written_from_the_clients_material_alone(tmp_path: Path) -> None:
    items, _ = dry(tmp_path, "requirements.js", "ok", {**REQ, "designType": "ai-solution"})
    write = prompt(items, "holdout:write")
    ports = write.split("OUTPUT")[0]
    assert "source:" in ports
    for ours in ("extract:", "requirements", "client_voice", "pains", "profile"):
        assert ours not in ports
    assert "a model does part of the work" in write
    labels = [p["label"] for p in items]
    assert labels.index("pains:critic") < labels.index("holdout:write") < labels.index("report")
    assert "DOCUMENTS THE QUESTIONS WILL BE PUT TO" in prompt(items, "holdout:skeptic:1")


def test_a_short_layer_is_added_to_once_and_selected_again(tmp_path: Path) -> None:
    items, _ = dry(tmp_path, "requirements.js", "bad", REQ)
    labels = [p["label"] for p in items]
    assert labels.count("holdout:add") == 1 and "holdout:select:2" in labels
    assert "LAYERS THAT CAME UP SHORT after selection: domain" in prompt(items, "holdout:add")


def test_holdout_can_be_switched_off(tmp_path: Path) -> None:
    for script, args in (("requirements.js", REQ), ("design.js", DESIGN), ("proposal.js", PROP)):
        off = {**args, "config": {**args["config"], "holdout": False}}  # type: ignore[dict-item]
        items, _ = dry(tmp_path, script, "ok", off)
        assert not [p["label"] for p in items if p["label"].startswith("holdout:")], script


def test_the_text_stage_is_scored_against_the_content_stage(tmp_path: Path) -> None:
    items, _ = dry(tmp_path, "proposal.js", "ok", {**PROP, "config": {"stages": ["text"]}})
    score = prompt(items, "holdout:score")
    assert '--compare "dry/r/holdout/prop-content/score.json"' in score
    assert '--answers-dir "dry/r/holdout/prop-text"' in score
    content, _ = dry(tmp_path, "proposal.js", "ok", PROP)
    assert "--compare" not in prompt(content, "holdout:score")


def test_requirements_writer_may_say_the_inputs_hold_no_data(tmp_path: Path) -> None:
    items, log = dry(tmp_path, "requirements.js", "bad", REQ, **ANSWER_ALL)
    assert "needs_context when the inputs hold no data" in prompt(items, "req:write:2")
    assert "refused for 1: a measurement is answered by a fix" in log
    critic = prompt(items, "req:critic:2")
    assert "NO DATA IN THE INPUTS" in critic and "CONTESTED-<n>:" in critic
    record = prompt(items, "missing-input")
    assert "FILE\ndry/r/missing-input.md" in record and "missing: x — searched: x" in record


def test_design_sends_a_fact_of_practice_to_the_domain_checker(tmp_path: Path) -> None:
    items, log = dry(tmp_path, "design.js", "bad", DESIGN, DRY_EXISTS_OK="1", **ANSWER_ALL)
    assert "QUESTIONS OF PRACTICE" in prompt(items, "design:numbers:2")
    assert "practice to look up 3" in log
    assert "Carried: [DESIGN] x — practice for" in prompt(items, "design:record:2")
    assert not [p for p in items if p["label"] == "missing-input"]


def test_design_records_a_clients_fact_and_tells_the_rule_skeptic(tmp_path: Path) -> None:
    env = {**ANSWER_ALL, "DRY_ENUM": "needs_context,client"}
    items, _ = dry(tmp_path, "design.js", "bad", DESIGN, DRY_EXISTS_OK="1", **env)
    assert "GAPS THE DESIGNER DECLARED" in prompt(items, "design:skeptic:2")
    assert "NO DATA IN THE INPUTS" in prompt(items, "design:critic:2")
    assert "FILE\ndry/r/design-missing-input.md" in prompt(items, "missing-input")


def test_proposal_records_what_the_inputs_did_not_hold(tmp_path: Path) -> None:
    items, _ = dry(tmp_path, "proposal.js", "ok", PROP, **ANSWER_ALL)
    assert "FILE\ndry/r/prop-content-missing-input.md" in prompt(items, "missing-input")


def functions(script: str, names: tuple[str, ...]) -> str:
    text = (WORKFLOWS / script).read_text(encoding="utf-8")
    found = [
        m.group(0)
        for m in re.finditer(r"^function (\w+)\(.*?^\}", text, re.DOTALL | re.MULTILINE)
        if m.group(1) in names
    ]
    rx = re.search(r"^const CONTESTED = .*$", text, re.MULTILINE)
    assert rx and len(found) == len(names), script
    return rx.group(0) + "\n" + "\n".join(found)


@pytest.mark.parametrize("script", ["requirements.js", "design.js", "proposal.js"])
def test_refusals_and_contests_are_the_same_in_every_script(script: str) -> None:
    probe = functions(script, ("refusalOf", "contestedOf")) + (
        "\nconst ok = { missing: 'the weekly volume', searched: 'all extracts', owner: 'client' };"
        "\nconsole.log(JSON.stringify(["
        "refusalOf({ kind: 'GATE' }, ok), refusalOf({ measured: true }, ok), refusalOf({ contested: true }, ok),"
        "refusalOf({}, { ...ok, missing: ' ' }), refusalOf({}, { ...ok, searched: '' }), refusalOf({}, ok),"
        "contestedOf('CONTESTED-2: the call, 14:32, gives 300 a week'), contestedOf('[HIGH] no volume')]))"
    )
    done = subprocess.run(
        ["node", "-e", probe], check=True, capture_output=True, text=True, encoding="utf-8"
    )
    got = json.loads(done.stdout)
    assert got[0] == got[1] == "a measurement is answered by a fix, not by missing input"
    assert got[2] == "the critic named where the inputs hold it"
    assert (
        got[3] == "what is missing was not named"
        and got[4] == "where it was looked for was not named"
    )
    assert got[5] == ""
    assert got[6] == {"n": 2, "text": "the call, 14:32, gives 300 a week"} and got[7] is None


def test_design_refuses_a_second_look_up_of_practice() -> None:
    probe = functions("design.js", ("refusalOf",)) + (
        "\nconst a = { missing: 'usual load', searched: 'requirements', owner: 'domain' };"
        "\nconsole.log(JSON.stringify([refusalOf({ practiceAsked: true }, a), refusalOf({ practiceAsked: true }, { ...a, owner: 'client' }),"
        " refusalOf({}, { ...a, owner: '' })]))"
    )
    done = subprocess.run(
        ["node", "-e", probe], check=True, capture_output=True, text=True, encoding="utf-8"
    )
    assert json.loads(done.stdout) == [
        "practice was already looked up for it",
        "",
        "whose fact it is was not named",
    ]


def test_every_batch_has_two_readers_and_a_design_reader_resolves_ids(tmp_path: Path) -> None:
    items, _ = dry(tmp_path, "design.js", "ok", DESIGN)
    finders = [p for p in items if p["agentType"] == "answer-finder"]
    assert [p["label"] for p in finders][:2] == ["holdout:find:1:1", "holdout:find:1:2"]
    assert all("references: dry/r/requirements.md" in p["prompt"] for p in finders)
    assert "answers-1-2.json" in finders[1]["prompt"]
    prop, _ = dry(tmp_path, "proposal.js", "ok", PROP)
    assert not [
        p for p in prop if p["agentType"] == "answer-finder" and "references:" in p["prompt"]
    ]
