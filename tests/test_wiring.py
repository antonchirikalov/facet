"""Связи между агентами: скрипт передаёт то, что агент объявил, и ни один выход не теряется.

Проверка прогоняет каждый этап каждого скрипта на заглушках. Первый прогон нашёл четыре
настоящие поломки: `fresh` рецензировал старые требования вместо новых, ответы редактора
пропозала никто не читал, проверка рисунков шла агентом общего назначения, контракты статейных
агентов отстали от скрипта на два переименования.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from facet import wiring
from facet.models.agent import AgentSpec, Port

ROOT = Path(__file__).resolve().parent.parent

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node не установлен")


@pytest.fixture(scope="module")
def runs() -> list[wiring.Run]:
    return wiring.all_runs(ROOT)


@needs_node
def test_every_stage_of_every_script_is_wired_to_its_agents(runs: list[wiring.Run]) -> None:
    assert wiring.check(ROOT, runs) == []


@needs_node
def test_every_scenario_ran(runs: list[wiring.Run]) -> None:
    """Сценарий, в котором скрипт упал до первого агента, ничего не проверяет."""
    assert all(r.calls for r in runs if r.mode == "ok")
    assert all(r.code == 0 for r in runs if r.mode == "ok")


@needs_node
def test_readme_registry_is_current(runs: list[wiring.Run]) -> None:
    readme = (ROOT / "README.md").read_bytes().decode("utf-8")
    table = wiring.render_registry(wiring.registry(ROOT, runs))
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
    """`sources:x` — сводка, `source:x/y` — сам источник: два разных порта."""
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
