"""Что агенты конвейера действительно получают в тексте задачи.

Счётчики агентов и формы результатов не видят главного: дошло ли до агента то, что человек
положил в запуск. Прогон Vista 27.09 закончился успешно, а текст заказа не прочитал ни один агент —
он уходил портом на каталог `inputs`, которого скрипт не пишет. Тест гоняет настоящий скрипт на
заглушках (`tools/dry_run.mjs`) и читает тексты задач, которые тот раздал.
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
SCRIPT = ROOT / ".claude" / "workflows" / "solution-design.js"
DRY_RUN = ROOT / "tools" / "dry_run.mjs"

ORDER = "ORDER-MARK scope and audience"
DECISION = "DEC-MARK backend in Go"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node не установлен")


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


def test_order_reaches_requirements_and_design_agents(tmp_path: Path) -> None:
    items = prompts(tmp_path, {**RUN, "order": ORDER})
    for agent_type in (
        "requirements-fact-checker",
        "requirements-critic",
        "solution-designer",
        "solution-design-selector",
        "solution-design-critic",
    ):
        texts = by_agent(items, agent_type)
        assert texts, f"{agent_type} не вызывался"
        assert all(ORDER in t for t in texts), f"{agent_type} не получил текст заказа"


def test_decisions_reach_every_design_agent_and_only_them(tmp_path: Path) -> None:
    decisions = [{"id": "D1", "title": "Backend", "mode": "decided", "brief": DECISION}]
    items = prompts(tmp_path, {**RUN, "decisions": decisions})
    for agent_type in ("solution-designer", "solution-design-selector", "solution-design-critic"):
        texts = by_agent(items, agent_type)
        assert texts and all(DECISION in t and "[decided]" in t for t in texts), agent_type
    for agent_type in ("requirements-critic", "requirements-fact-checker"):
        assert not any(DECISION in t for t in by_agent(items, agent_type)), (
            f"{agent_type}: решения по дизайну не должны влиять на требования"
        )


def test_without_order_no_order_block(tmp_path: Path) -> None:
    items = prompts(tmp_path, RUN)
    assert not any(p["prompt"].startswith("ORDER") or "\nORDER\n" in p["prompt"] for p in items)


def test_malformed_decision_is_refused(tmp_path: Path) -> None:
    out = tmp_path / "prompts.json"
    env = {**os.environ, "DRY_PROMPTS_OUT": str(out)}
    bad = {**RUN, "decisions": [{"id": "D1", "title": "Backend", "mode": "decide"}]}
    done = subprocess.run(
        ["node", str(DRY_RUN), str(SCRIPT), "ok", json.dumps(bad)],
        cwd=ROOT,
        check=False,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert done.returncode != 0
    assert "decided" in done.stderr


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


def test_client_stage_passes_the_id_map_and_checks_quotes(tmp_path: Path) -> None:
    """Редакция дизайна получает карту номеров от редакции требований; цитаты сверяются с извлечениями."""
    items = prompts(tmp_path, {**RUN, "config": {"stages": ["client"]}})
    editors = by_agent(items, "client-editor")
    assert len(editors) == 2
    assert (
        "dry/run/client-id-map.json" in editors[0]
        and "OUTPUT\ndry/run/requirements.client.md" in editors[0]
    )
    assert "id_map: dry/run/client-id-map.json" in editors[1]
    assert "OUTPUT\ndry/run/design.client.md" in editors[1]
    gate = next(p for p in by_agent(items, "gate-runner") if "client-meta.txt" in p)
    assert gate.count("check_quotes.py") == 2 and "--source dry/run/extracts" in gate
    assert gate.count("--sequential-ids") == 1


def test_design_and_client_gates_check_figure_numbers(tmp_path: Path) -> None:
    """Каждый рисунок подписан «Figure N.» по порядку: это проверяет гейт, а не критик."""
    design = prompts(
        tmp_path, {**RUN, "config": {"stages": ["requirements", "design"], "fresh": True}}
    )
    design_gates = [
        p for p in by_agent(design, "gate-runner") if "--require-heading" in p and r"1\.1" in p
    ]
    assert design_gates and all("--figures-numbered" in p for p in design_gates)
    client = prompts(tmp_path, {**RUN, "config": {"stages": ["client"]}})
    client_gate = next(p for p in by_agent(client, "gate-runner") if "client-meta.txt" in p)
    assert client_gate.count("--figures-numbered") == 2


def test_client_stage_runs_alone(tmp_path: Path) -> None:
    done = subprocess.run(
        [
            "node",
            str(DRY_RUN),
            str(SCRIPT),
            "ok",
            json.dumps({**RUN, "config": {"stages": ["client", "design"]}}),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert done.returncode != 0 and "client" in done.stderr


PROPOSAL = ROOT / ".claude" / "workflows" / "proposal-review.js"


def test_proposal_review_gates_carry_the_profile_rules(tmp_path: Path) -> None:
    """Правила профиля пропозала проверяет гейт, а не читатель: «you», пустые ячейки, ссылки, рисунки, покрытие."""
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
    """Проверяющий Vista нумеровал замечания сам («1. [HIGH] ...»): счёт кругов 2 и 3 вышел 0 при
    открытых HIGH, а полка сравнивала нули. Номер снимается до подсчёта и до записи круга."""
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
    """Вес требования берётся из листа голоса заказчика: лист пишется до писателя и доходит до критика."""
    items = prompts(tmp_path, {**RUN, "config": {"fresh": True, "stages": ["requirements"]}})
    labels = [p["label"] for p in items]
    assert labels.index("voice") < labels.index("req:write:1")
    voice = by_agent(items, "client-voice")[0]
    assert "OUTPUT\ndry/run/client-voice.md" in voice and "source:" in voice and "extract:" in voice
    for agent_type in ("requirements-writer", "requirements-critic"):
        prompt = by_agent(items, agent_type)[0]
        assert "client_voice: dry/run/client-voice.md" in prompt and "CLIENT VOICE" in prompt
    gate = next(p for p in by_agent(items, "gate-runner") if "client voice quotes" in p)
    assert "check_quotes.py --file dry/run/client-voice.md" in gate
