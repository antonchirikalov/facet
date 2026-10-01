"""Invariants of the workflow scripts and the generated agents.

Everything checked here was paid for by a live run. The checks are objective and repeatable: the
claim "nothing is hardcoded" is worth exactly as much as the way to recheck it a month later.

The tests read `.claude/`, that is, the **generated** files. This is deliberate: the runtime loads
exactly these files, and the question "does the build match the source" is not asked here;
`test_emit_agents` answers it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".claude" / "workflows"
AGENTS = ROOT / ".claude" / "agents"
SKILLS = ROOT / ".claude" / "skills"

AGENT_TYPE = re.compile(r"agentType:\s*'([a-z0-9-]+)'")
COMMENT_LINE = re.compile(r"^\s*//")

# Subject-matter words that have already leaked into agent prompts. The list is a tripwire, not a
# definition: it catches exactly the case that happened (examples from the article on attention
# left in a general-purpose agent's instructions) and grows when something else leaks. The
# Russian alternatives are data: they match Russian words in a prompt.
SUBJECT_WORDS = re.compile(
    r"attention|softmax|transformer|трансформер|d_k\b|d_model|QK\^?T|токенизац",
    re.IGNORECASE,
)

# The article pipeline's agents. They are the ones that must be indifferent to the subject: the
# same writer writes about attention and about invoices.
PIPELINE_AGENTS = [
    "brief-writer",
    "source-finder",
    "domain-analyst",
    "article-writer",
    "example-verifier",
    "article-fact-checker",
    "article-critic",
    "style-critic-ru",
    "gate-runner",
    "verbatim-writer",
]


def workflow_scripts() -> list[Path]:
    return sorted(WORKFLOWS.glob("*.js"))


def agent_files() -> list[Path]:
    return sorted(AGENTS.glob("*.md"))


def frontmatter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path.name}: the file does not start with frontmatter"
    parsed: dict[str, object] = yaml.safe_load(text.split("---\n", 2)[1])
    return parsed


def code_lines(path: Path) -> list[str]:
    """The script's lines without comments: what actually executes."""
    return [
        ln for ln in path.read_text(encoding="utf-8").splitlines() if not COMMENT_LINE.match(ln)
    ]


# --- control characters ---------------------------------------------------------------


@pytest.mark.parametrize("script", workflow_scripts(), ids=lambda p: p.name)
def test_no_control_characters(script: Path) -> None:
    """CR and NUL in a script refuse the launch; they are not cosmetic.

    The runtime answers "script contains control characters that would be hidden in the approval
    dialog" and does not start. It happened twice in one day: `autocrlf` brought CRLF back after a
    checkout, and a `\\u0000` in a patch's source was written as a real NUL byte, making the script
    binary. Both breakages are silent until the launch itself.
    """
    raw = script.read_bytes()
    bad = sorted({c for c in raw if c < 32 and c not in (9, 10)})
    assert not bad, f"{script.name}: control characters {bad} (13 is CR, a CRLF line ending)"


# --- agents the script calls ----------------------------------------------------------


@pytest.mark.parametrize("script", workflow_scripts(), ids=lambda p: p.name)
def test_every_agent_type_has_a_definition(script: Path) -> None:
    """An `agentType` without a file fails the run in its first second.

    The runtime resolves the agent from `.claude/agents/`, and a typo in the name shows only in a
    live launch: `agent type 'brief-writer' not found`.
    """
    wanted = sorted(set(AGENT_TYPE.findall(script.read_text(encoding="utf-8"))))
    missing = [name for name in wanted if not (AGENTS / f"{name}.md").is_file()]
    assert not missing, f"{script.name}: no definitions for {missing}"


@pytest.mark.parametrize("agent", agent_files(), ids=lambda p: p.name)
def test_agent_name_matches_its_filename(agent: Path) -> None:
    """The frontmatter name and the file name are the same, otherwise the runtime will not find the agent.

    The check guards against a typo and against file damage: four stray characters before `---`
    and it stops being frontmatter, and the agent silently disappears from the registry.
    """
    head = frontmatter(agent)
    assert head.get("name") == agent.stem, f"{agent.name}: name={head.get('name')!r}"
    assert str(head.get("tools", "")).strip(), f"{agent.name}: empty tool list"


@pytest.mark.parametrize("agent", agent_files(), ids=lambda p: p.name)
def test_every_declared_skill_exists(agent: Path) -> None:
    """A profile without a file is not a failure but worse: the runtime skips it silently.

    The warning goes to the debug log, the agent starts without its document-type contract and
    works as if nothing happened. This checks the generated files, the ones the runtime actually
    reads.
    """
    skills = frontmatter(agent).get("skills", [])
    assert isinstance(skills, list), f"{agent.name}: skills must be a list"
    missing = [s for s in skills if not (SKILLS / str(s) / "SKILL.md").is_file()]
    assert not missing, f"{agent.name}: profiles {missing} missing from {SKILLS}"


def test_profile_names_do_not_shadow_saved_workflows() -> None:
    """A saved workflow is visible as a skill of its own name; a project skill would shadow it."""
    workflows = {p.stem for p in workflow_scripts()}
    profiles = {p.name for p in SKILLS.iterdir() if p.is_dir()}
    clash = workflows & profiles
    assert not clash, f"profiles shadow workflow entry points: {sorted(clash)}"


# --- independence from the run and from the subject -----------------------------------


@pytest.mark.parametrize("script", workflow_scripts(), ids=lambda p: p.name)
def test_no_run_directory_in_executable_code(script: Path) -> None:
    """The run directory arrives through `args`; it does not live in the script.

    In comments and in an error message an example path is allowed: it explains what to pass.
    In an executable line a path means the script can do exactly one run.
    """
    offenders = [
        ln.strip()
        for ln in code_lines(script)
        if re.search(r"probe-runs/|docs-runs/", ln) and "Error(" not in ln
    ]
    assert not offenders, f"{script.name}: run directory in code: {offenders[:3]}"


@pytest.mark.parametrize("name", PIPELINE_AGENTS)
def test_pipeline_agent_prompt_is_subject_neutral(name: str) -> None:
    """The same writer writes about attention and about invoices.

    A subject-matter example left in a general-purpose agent's instructions breaks nothing
    visibly; it just pulls the next article towards the previous subject. The library held four
    such traces: `QK^T` as a sample bold label, `h = 8, d_model = 512` as a sample number without
    a consequence, "How attention works" as a sample bad pair of aspects, and the slug `x-to-qkv`
    in a sample figure placeholder.

    The exception is the style critic's target-language dictionary: the clichés it looks for must
    be in the article's language. But they are not about the subject either.
    """
    path = AGENTS / f"{name}.md"
    if not path.is_file():
        pytest.skip(f"{name} is not built yet")
    hits = SUBJECT_WORDS.findall(path.read_text(encoding="utf-8"))
    assert not hits, f"{name}: subject matter in the prompt: {sorted(set(hits))}"


def test_voice_profile_default_exists() -> None:
    """The default path of the voice profile points at a file that exists.

    `voicePath` can be overridden and can be nulled, but a default pointing at nothing would give
    the writer a port with a missing file and not a single error.
    """
    script = (WORKFLOWS / "explainer-article.js").read_text(encoding="utf-8")
    match = re.search(r"cfg\.voicePath === undefined \? '([^']+)'", script)
    assert match, "voicePath default not found: the test went stale with the script"
    assert (ROOT / match.group(1)).is_file(), f"no voice profile file: {match.group(1)}"


@pytest.mark.parametrize("script", sorted(p.name for p in WORKFLOWS.glob("*.js")))
def test_tool_arguments_are_ascii(script: str) -> None:
    """Everything passed to a tool as an argument is ASCII; Cyrillic travels only in files.

    Cyrillic through argv on Windows depends on the code page and on which shell the carrier
    agent chose. That is why the forbidden-word lists moved from code into files, and right after
    that I wrote the `--log-note` call notes in Russian: the same argv and the same dependency.
    What can be checked mechanically is checked: single-quoted strings and templates inside a
    `noted(...)` call.
    """
    text = (WORKFLOWS / script).read_text(encoding="utf-8")
    bad = [n for n in re.findall(r"noted\((.*?)\)", text) if re.search("[а-яА-ЯёЁ]", n)]
    assert not bad, f"{script}: Cyrillic in a tool argument: {bad}"
