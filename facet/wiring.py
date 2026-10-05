"""Who hands what to whom: the agent registry and the wiring check.

The library is meant to be a set of parts any pipeline can be assembled from, and a part is only
reusable if what a script hands it is what its ``agent.yaml`` says it takes. That used to be a
comment ("documentation of the contract, not wiring") and it drifted: a client editor received
two ports it never declared, a figure check ran as a general-purpose agent with every tool and
the whole CLAUDE.md, and a rebuild "from scratch" reviewed the previous document because the old
file still counted as a draft. None of it was visible in any test.

So the check runs every stage of every script on stubs (``tools/dry_run.mjs``), reads the task
texts the stubs were handed, and compares:

- every call names an agent of the library;
- every INPUT port is one the agent declares, and every required port is there. A collection
  port (``collection<...>``) may be handed as one line per member, named by the singular with a
  ``:<stem>`` or ``_<n>`` suffix: ``extract:call`` and ``source_1`` are members of ``extracts``
  and ``sources``;
- every OUTPUT is read by a later call or returned by the script. A file nobody reads and nobody
  is told about is an artifact lost at the moment it is written;
- a file a call wrote reaches the next agent through a port of the same type: the producer's
  ``produces`` type against the consumer's port type, a member of ``collection<X>`` against
  ``X``. A pain map handed to a ``requirements`` port is a wrong connection that every other check
  passes. ``document@v1`` and ``source@v1`` take any file;
- a single (not collection) port receives one file, never several.

The registry is the same data turned into the README table, so the table cannot fall behind.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from facet.emit_agents import load_agent, slug_of
from facet.models.agent import AgentSpec, Port

NOW = "2026-09-28T10:00:00+03:00"


@dataclass(frozen=True)
class Scenario:
    name: str
    script: str
    args: dict[str, object]


# One per stage of every script: a stage no scenario reaches is a stage nothing checks.
SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        "lens+proposal",
        "solution-design.js",
        {"runDir": "r", "now": NOW, "config": {"stages": ["lens", "proposal"]}},
    ),
    Scenario(
        "panels",
        "solution-design.js",
        {
            "runDir": "r",
            "now": NOW,
            "config": {"fresh": True, "claimCheck": True, "rulePanel": True},
        },
    ),
    Scenario(
        "requirements",
        "solution-design.js",
        {"runDir": "r", "now": NOW, "config": {"fresh": True, "stages": ["requirements"]}},
    ),
    Scenario(
        "requirements+design",
        "solution-design.js",
        {"runDir": "r", "now": NOW, "config": {"fresh": True}},
    ),
    Scenario(
        "design",
        "solution-design.js",
        {"runDir": "r", "now": NOW, "config": {"stages": ["design"]}},
    ),
    Scenario(
        "discovery",
        "solution-design.js",
        {"runDir": "r", "now": NOW, "config": {"stages": ["discovery"]}},
    ),
    Scenario(
        "client",
        "solution-design.js",
        {"runDir": "r", "now": NOW, "config": {"stages": ["client"]}},
    ),
    Scenario(
        "req-pipeline",
        "requirements.js",
        {"runDir": "r", "now": NOW, "config": {"fresh": True}},
    ),
    Scenario(
        "req-pipeline-continue",
        "requirements.js",
        {"runDir": "r", "now": NOW, "config": {"continue": True}},
    ),
    Scenario(
        "prop-content",
        "proposal.js",
        {"runDir": "r", "now": NOW, "design": "r/design.md", "config": {"fresh": True}},
    ),
    Scenario(
        "prop-text",
        "proposal.js",
        {"runDir": "r", "now": NOW, "config": {"stages": ["text"]}},
    ),
    Scenario(
        "scene",
        "scene.js",
        {
            "runDir": "r",
            "slug": "pier-plan",
            "brief": "r/scene-brief.md",
            "document": "r/prop.md",
            "voice": "r/client-voice.md",
            "steps": 3,
            "config": {"fresh": True},
        },
    ),
    Scenario(
        "figures", "attn-figures.js", {"runDir": "r", "articlePath": "r/design.md", "figures": 3}
    ),
    Scenario(
        "proposal",
        "proposal-review.js",
        {"runDir": "r", "document": "r/prop.md", "sources": ["r/t.md"]},
    ),
    Scenario(
        "article",
        "explainer-article.js",
        {"runDir": "r", "now": NOW, "brief": "x", "config": {"fresh": True}},
    ),
)
MODES = ("ok", "bad")

INPUT_BLOCK = re.compile(r"^INPUT\n(.*?)(?:\n\n|\Z)", re.DOTALL | re.MULTILINE)
OUTPUT_LINE = re.compile(r"^OUTPUT\n(\S+)", re.MULTILINE)
MEMBER = re.compile(r"^(?P<base>[a-z_]+?)(?::[^\s]+|_\d+)?$")


@dataclass
class Call:
    label: str
    agent: str | None
    inputs: list[tuple[str, str]]
    output: str | None
    prompt: str


@dataclass
class Run:
    scenario: Scenario
    mode: str
    code: int
    calls: list[Call]
    returned: str
    stderr: str = ""


@dataclass
class AgentEntry:
    slug: str
    spec: AgentSpec
    used_by: set[str] = field(default_factory=set)


def load_specs(agents_dir: Path) -> dict[str, AgentSpec]:
    specs: dict[str, AgentSpec] = {}
    for d in sorted(p for p in agents_dir.iterdir() if (p / "agent.yaml").is_file()):
        spec, _ = load_agent(d)
        specs[slug_of(spec.name)] = spec
    return specs


def parse_call(entry: dict[str, object]) -> Call:
    prompt = str(entry.get("prompt", ""))
    inputs: list[tuple[str, str]] = []
    block = INPUT_BLOCK.search(prompt)
    if block:
        for line in block.group(1).splitlines():
            port, _, path = line.partition(": ")
            if path:
                inputs.append((port.strip(), path.strip()))
    out = OUTPUT_LINE.search(prompt)
    agent = entry.get("agentType")
    return Call(
        label=str(entry.get("label", "")),
        agent=str(agent) if agent else None,
        inputs=inputs,
        output=out.group(1) if out else None,
        prompt=prompt,
    )


def run_scenario(root: Path, scenario: Scenario, mode: str) -> Run:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "prompts.json"
        done = subprocess.run(
            [
                "node",
                "tools/dry_run.mjs",
                f".claude/workflows/{scenario.script}",
                mode,
                json.dumps(scenario.args),
            ],
            cwd=root,
            env={**os.environ, "DRY_PROMPTS_OUT": str(out)},
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        raw = json.loads(out.read_text(encoding="utf-8")) if out.is_file() else []
    returned = done.stdout.split("--- return ---", 1)[1] if "--- return ---" in done.stdout else ""
    return Run(scenario, mode, done.returncode, [parse_call(e) for e in raw], returned, done.stderr)


def singular(port: str) -> str:
    return port.removesuffix("s")


def port_problems(call: Call, spec: AgentSpec) -> list[str]:
    """Ports handed that the agent does not declare, and required ports not handed."""
    if not call.inputs:
        return []
    declared = {p.port: p for p in spec.consumes}
    handed: set[str] = set()
    problems: list[str] = []
    for port, _ in call.inputs:
        if port in declared:
            handed.add(port)
            continue
        m = MEMBER.match(port)
        base = m.group("base") if m else port
        collections = [p for p in spec.consumes if p.type.startswith("collection<")]
        owner = next((p for p in collections if p.port == base), None) or next(
            (p for p in collections if singular(p.port) == base), None
        )
        if owner is None:
            problems.append(f"{call.label}: port '{port}' is not declared by {slug_of(spec.name)}")
        else:
            handed.add(owner.port)
    for p in spec.consumes:
        if not p.optional and p.port not in handed:
            problems.append(
                f"{call.label}: required port '{p.port}' of {slug_of(spec.name)} not handed"
            )
    return problems


# Port types that take any file: a critic of "the document", an input document of the client.
GENERIC_TYPES = {"document@v1", "source@v1"}


def resolve_port(spec: AgentSpec, port: str) -> Port | None:
    """The declared port a handed port name stands for: itself, or the collection it is a member of."""
    for p in spec.consumes:
        if p.port == port:
            return p
    m = MEMBER.match(port)
    base = m.group("base") if m else port
    collections = [p for p in spec.consumes if p.type.startswith("collection<")]
    return next((p for p in collections if p.port == base), None) or next(
        (p for p in collections if singular(p.port) == base), None
    )


def item_type(port_type: str) -> str:
    return port_type[len("collection<") : -1] if port_type.startswith("collection<") else port_type


def connection_problems(run: Run, specs: dict[str, AgentSpec]) -> list[str]:
    """Files handed to a port of another type than the one they were written as; several files in a single port."""
    produced: dict[str, tuple[str, str]] = {}
    problems: list[str] = []
    for call in run.calls:
        spec = specs.get(call.agent) if call.agent else None
        if spec is None:
            continue
        singles: dict[str, int] = {}
        for port, path in call.inputs:
            declared = resolve_port(spec, port)
            if declared is None:
                continue
            if not declared.type.startswith("collection<"):
                singles[declared.port] = singles.get(declared.port, 0) + 1
            if path not in produced:
                continue
            expected = item_type(declared.type)
            actual, by = produced[path]
            if GENERIC_TYPES.isdisjoint({expected, actual}) and expected != actual:
                problems.append(
                    f"{call.label}: port '{port}' takes {expected}, but {path} was written as "
                    f"{actual} by {by}"
                )
        for port, n in singles.items():
            if n > 1:
                problems.append(f"{call.label}: single port '{port}' handed {n} files")
        if call.output and spec.produces:
            produced[call.output] = (spec.produces[0].type, call.label)
    return problems


def lost_outputs(run: Run) -> list[str]:
    """Outputs no later call mentions and the script does not return."""
    lost: list[str] = []
    for i, call in enumerate(run.calls):
        if call.output is None:
            continue
        later = any(call.output in c.prompt for c in run.calls[i + 1 :])
        if not later and call.output not in run.returned:
            lost.append(f"{call.label} -> {call.output}")
    return lost


def phase_problems(script: Path) -> list[str]:
    """Phases a script enters that its ``meta`` does not declare: the progress view loses them.

    Two did: the client stage and the resume check of the article ran under names the meta never
    listed, and nothing but a person watching /workflows would have noticed.
    """
    text = script.read_bytes().decode("utf-8")
    end = text.find("\n}\n")
    meta, body = (text[:end], text[end:]) if end >= 0 else ("", text)
    titles = set(re.findall(r"title: '([^']+)'", meta))
    used = set(re.findall(r"phase\('([^']+)'\)", body)) | set(re.findall(r"phase: '([^']+)'", body))
    return [f"[{script.name}] phase '{p}' is not declared in meta" for p in sorted(used - titles)]


def check(root: Path, runs: Iterable[Run]) -> list[str]:
    specs = load_specs(root / "library" / "agents")
    problems: list[str] = []
    for script in sorted((root / ".claude" / "workflows").glob("*.js")):
        problems.extend(phase_problems(script))
    for run in runs:
        where = f"[{run.scenario.name}/{run.mode}]"
        if (
            "SyntaxError" in run.stderr
            or "TypeError" in run.stderr
            or "ReferenceError" in run.stderr
        ):
            problems.append(f"{where} the script crashed: {run.stderr[:200]}")
        for call in run.calls:
            if call.agent is None:
                problems.append(
                    f"{where} {call.label}: no agentType, runs as a general-purpose agent"
                )
                continue
            spec = specs.get(call.agent)
            if spec is None:
                problems.append(f"{where} {call.label}: agent '{call.agent}' is not in the library")
                continue
            problems.extend(f"{where} {p}" for p in port_problems(call, spec))
        problems.extend(f"{where} lost: {x}" for x in lost_outputs(run))
        problems.extend(f"{where} {x}" for x in connection_problems(run, specs))
    return sorted(set(problems))


def all_runs(root: Path) -> list[Run]:
    return [run_scenario(root, s, m) for s in SCENARIOS for m in MODES]


# --- Registry ------------------------------------------------------------------------------

BEGIN = "<!-- agents:begin (generated by facet.wiring.render_registry; do not edit by hand) -->"
END = "<!-- agents:end -->"


def first_sentence(text: str) -> str:
    flat = " ".join(text.split())
    m = re.match(r"(.+?[.!?])(?:\s|$)", flat)
    return m.group(1) if m else flat


def ports_of(ports: Iterable[Port]) -> str:
    out = [f"`{p.port}`: `{p.type}`" + (" (opt.)" if p.optional else "") for p in ports]
    return "<br>".join(out) or "—"


def step_of(label: str) -> str:
    """A call label without the round number or the stub's placeholder: ``find:x`` is ``find``."""
    step = label
    while True:
        shorter = re.sub(r"(?::x|:\d+|/\d+)$", "", step)
        if shorter == step:
            return step
        step = shorter


def registry(root: Path, runs: Iterable[Run]) -> list[AgentEntry]:
    specs = load_specs(root / "library" / "agents")
    entries = {slug: AgentEntry(slug, spec) for slug, spec in specs.items()}
    for run in runs:
        for call in run.calls:
            if call.agent in entries:
                entries[call.agent].used_by.add(
                    f"{run.scenario.script.removesuffix('.js')} | {step_of(call.label)}"
                )
    return sorted(entries.values(), key=lambda e: e.slug)


def used_by(entry: AgentEntry) -> str:
    by_script: dict[str, list[str]] = {}
    for item in sorted(entry.used_by):
        script, step = item.split(" | ")
        by_script.setdefault(script, []).append(step)
    lines = [f"`{script}`: {', '.join(steps)}" for script, steps in sorted(by_script.items())]
    return "<br>".join(lines) or "пока ни один скрипт — деталь для следующего конвейера"


def descriptions_of(readme: str) -> dict[str, str]:
    """The "what it does" cell of every agent row already in the README table, by slug.

    The README is the one Russian document; an agent's own files are English. So the Russian
    description is written in the table by hand and kept on every regeneration, while the
    columns that come from the contract are rebuilt.
    """
    start, end = readme.find(BEGIN), readme.find(END)
    if start < 0 or end < start:
        return {}
    found: dict[str, str] = {}
    for line in readme[start:end].splitlines():
        m = re.match(r"^\| `([a-z0-9-]+)` \| (.*?) \| ", line)
        if m:
            found[m.group(1)] = m.group(2)
    return found


def render_registry(
    entries: Iterable[AgentEntry], descriptions: dict[str, str] | None = None
) -> str:
    rows = [
        "| Агент | Что делает | Берёт | Отдаёт | Профиль | Кто вызывает (скрипт: шаги) |",
        "|---|---|---|---|---|---|",
    ]
    for e in entries:
        what = (descriptions or {}).get(e.slug) or first_sentence(e.spec.description)
        profile = ", ".join(f"`{s}`" for s in e.spec.skills) or "—"
        rows.append(
            f"| `{e.slug}` | {what} | {ports_of(e.spec.consumes)} | {ports_of(e.spec.produces)} | "
            f"{profile} | {used_by(e)} |"
        )
    return "\n".join(rows)


def splice(readme: str, table: str) -> str:
    """The README with the table between the markers replaced; the markers must exist."""
    start, end = readme.find(BEGIN), readme.find(END)
    if start < 0 or end < start:
        raise ValueError("README has no agents markers")
    return readme[: start + len(BEGIN)] + "\n" + table + "\n" + readme[end:]


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    runs = all_runs(root)
    problems = check(root, runs)
    readme = root / "README.md"
    text = readme.read_bytes().decode("utf-8")
    new = splice(text, render_registry(registry(root, runs), descriptions_of(text)))
    if new != text:
        readme.write_bytes(new.encode("utf-8"))
        print("README: agent registry updated")
    for p in problems:
        print(p)
    print(f"wiring problems: {len(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
