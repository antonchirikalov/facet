"""Wiring between agents: the script hands over what the agent declared, and no output is lost.

The check runs every stage of every script on stubs. Its first run found four real breakages:
`fresh` reviewed the old requirements instead of the new ones, nobody read the proposal editor's
answers, the figure check ran on a general-purpose agent, and the contracts of the article agents
were two renames behind the script.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from facet import wiring
from facet.models.agent import AgentSpec, Port

ROOT = Path(__file__).resolve().parent.parent

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


@pytest.fixture(scope="module")
def runs() -> list[wiring.Run]:
    return wiring.all_runs(ROOT)


@needs_node
def test_every_stage_of_every_script_is_wired_to_its_agents(runs: list[wiring.Run]) -> None:
    assert wiring.check(ROOT, runs) == []


@needs_node
def test_every_scenario_ran(runs: list[wiring.Run]) -> None:
    """A scenario in which the script fell over before the first agent checks nothing."""
    assert all(r.calls for r in runs if r.mode == "ok")
    assert all(r.code == 0 for r in runs if r.mode == "ok")


@needs_node
def test_readme_registry_is_current(runs: list[wiring.Run]) -> None:
    readme = (ROOT / "README.md").read_bytes().decode("utf-8")
    table = wiring.render_registry(wiring.registry(ROOT, runs), wiring.descriptions_of(readme))
    assert wiring.splice(readme, table) == readme, "run: uv run python -m facet.wiring"


def test_every_library_agent_is_in_the_registry() -> None:
    readme = (ROOT / "README.md").read_bytes().decode("utf-8")
    for slug in wiring.load_specs(ROOT / "library" / "agents"):
        assert f"| `{slug}` |" in readme


def spec(*ports: Port) -> AgentSpec:
    return AgentSpec(name="demo_agent", version=1, consumes=list(ports))


def call(*inputs: tuple[str, str]) -> wiring.Call:
    return wiring.Call(
        label="step", agent="demo-agent", inputs=list(inputs), output=None, prompt=""
    )


def test_collection_members_are_accepted() -> None:
    s = spec(
        Port(port="extracts", type="collection<extract@v1>"),
        Port(port="sources", type="collection<source@v1>"),
    )
    assert wiring.port_problems(call(("extract:call", "a"), ("source_1", "b")), s) == []


def test_undeclared_and_missing_ports_are_named() -> None:
    s = spec(Port(port="draft", type="x@v1"), Port(port="extra", type="y@v1", optional=True))
    problems = wiring.port_problems(call(("id_map", "m.json")), s)
    assert any("'id_map' is not declared" in p for p in problems)
    assert any("required port 'draft'" in p for p in problems)
    assert not any("'extra'" in p for p in problems)


def test_exact_collection_name_wins_over_singular() -> None:
    """`sources:x` is a summary, `source:x/y` is the source itself: two different ports."""
    s = spec(
        Port(port="sources", type="collection<source_summary@v1>"),
        Port(port="source", type="collection<source@v1>", optional=True),
    )
    assert wiring.port_problems(call(("sources:x", "a"), ("source:x/one", "b")), s) == []


def test_an_output_nobody_reads_is_lost() -> None:
    scenario = wiring.SCENARIOS[0]
    run = wiring.Run(
        scenario,
        "ok",
        0,
        [
            wiring.Call("write", "w", [], "r/a.md", "OUTPUT\nr/a.md"),
            wiring.Call("answer", "w", [], "r/b.md", "INPUT\ndraft: r/a.md\n\nOUTPUT\nr/b.md"),
        ],
        returned='{"document": "r/other.md"}',
    )
    assert wiring.lost_outputs(run) == ["answer -> r/b.md"]


def connection_run(*calls: wiring.Call) -> wiring.Run:
    return wiring.Run(wiring.SCENARIOS[0], "ok", 0, list(calls), returned="")


CONNECTION_SPECS = {
    "pain-mapper": AgentSpec(
        name="pain_mapper",
        version=1,
        produces=[Port(port="map", type="pain_map@v1")],
    ),
    "writer": AgentSpec(
        name="writer",
        version=1,
        consumes=[
            Port(port="requirements", type="requirements@v1"),
            Port(port="pain_map", type="pain_map@v1"),
            Port(port="extracts", type="collection<extract@v1>"),
            Port(port="source", type="source@v1", optional=True),
        ],
        produces=[Port(port="proposal", type="proposal@v1")],
    ),
    "extractor": AgentSpec(
        name="extractor", version=1, produces=[Port(port="extract", type="extract@v1")]
    ),
}


def test_a_file_reaches_a_port_of_its_own_type() -> None:
    run = connection_run(
        wiring.Call("pains", "pain-mapper", [], "r/pains.md", ""),
        wiring.Call("x", "extractor", [], "r/extracts/a.md", ""),
        wiring.Call(
            "write",
            "writer",
            [
                ("requirements", "r/requirements.md"),
                ("pain_map", "r/pains.md"),
                ("extract:a", "r/extracts/a.md"),
            ],
            "r/prop.md",
            "",
        ),
    )
    assert wiring.connection_problems(run, CONNECTION_SPECS) == []


def test_a_file_in_a_port_of_another_type_is_a_wrong_connection() -> None:
    """The pain map handed as the requirements: every other check passes it."""
    run = connection_run(
        wiring.Call("pains", "pain-mapper", [], "r/pains.md", ""),
        wiring.Call(
            "write",
            "writer",
            [("requirements", "r/pains.md"), ("pain_map", "r/pains.md")],
            None,
            "",
        ),
    )
    problems = wiring.connection_problems(run, CONNECTION_SPECS)
    expected = (
        "write: port 'requirements' takes requirements@v1, but r/pains.md was written as "
        "pain_map@v1 by pains"
    )
    assert problems == [expected]


def test_several_files_in_a_single_port_are_named() -> None:
    run = connection_run(
        wiring.Call(
            "write",
            "writer",
            [("source", "r/a.md"), ("source", "r/b.md"), ("extract:a", "x"), ("extract:b", "y")],
            None,
            "",
        )
    )
    assert wiring.connection_problems(run, CONNECTION_SPECS) == [
        "write: single port 'source' handed 2 files"
    ]


def test_step_names_drop_round_numbers() -> None:
    assert wiring.step_of("req:write:1") == "req:write"
    assert wiring.step_of("find:x") == "find"
    assert wiring.step_of("verify:structure/2") == "verify:structure"


def test_undeclared_phase_is_named(tmp_path: Path) -> None:
    script = tmp_path / "demo.js"
    script.write_bytes(
        b"export const meta = {\n  phases: [{ title: 'A' }],\n}\nphase('A')\nphase('B')\n"
    )
    assert wiring.phase_problems(script) == ["[demo.js] phase 'B' is not declared in meta"]


CYRILLIC = re.compile("[Ѐ-ӿ]")


def test_every_agent_has_a_russian_description_in_the_readme() -> None:
    """The README is the one Russian document; an agent's own files are English."""
    readme = (ROOT / "README.md").read_bytes().decode("utf-8")
    described = wiring.descriptions_of(readme)
    for slug in wiring.load_specs(ROOT / "library" / "agents"):
        assert CYRILLIC.search(described.get(slug, "")), (
            f"{slug}: write its Russian description in README"
        )


def test_descriptions_survive_regeneration() -> None:
    row = "| `gate-runner` | Ручное | a | b |"
    readme = f"{wiring.BEGIN}\n| Agent | x |\n|---|---|\n{row}\n{wiring.END}"
    assert wiring.descriptions_of(readme) == {"gate-runner": "Ручное"}
