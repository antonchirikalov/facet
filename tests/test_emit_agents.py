"""Тесты генератора определений подагентов.

Две части. Первая — отображение возможностей контракта в инструменты: таблица из
`docs/plan.md`, включая слипание `read` и `vision` в один `Read`. Вторая — сборка на
настоящей библиотеке: 22 агента, и MCP ровно у тех пяти, у которых его называет `needs`.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from facet.emit_agents import (
    emit_agent,
    emit_all,
    load_agent,
    mcp_servers_of,
    missing_skills,
    render_agent,
    slug_of,
    tools_of,
)
from facet.models.agent import AgentSpec

ROOT = Path(__file__).resolve().parent.parent
LIBRARY_AGENTS = ROOT / "library" / "agents"
SKILLS = ROOT / ".claude" / "skills"

# Кто читает какой профиль (SPEC §6): писатель, корректор и критик одного типа — один профиль.
PROFILE_AGENTS = {
    "requirements-profile": {
        "requirements_writer",
        "requirements_fact_checker",
        "requirements_critic",
    },
    "solution-design-profile": {"solution_designer", "solution_design_critic"},
}

# Кто требует MCP по состоянию библиотеки: три Tavily, один pdf-reader, source_finder оба.
TAVILY_AGENTS = {"arch_probe", "requirements_writer", "solution_designer", "source_finder"}
PDF_AGENTS = {"source_processor", "source_finder"}


def spec_of(
    needs: list[str], name: str = "some_agent", skills: list[str] | None = None
) -> AgentSpec:
    return AgentSpec.model_validate(
        {
            "name": name,
            "version": 1,
            "description": "Описание агента.",
            "produces": [{"port": "out", "type": "brief@v1"}],
            "needs": needs,
            "skills": skills or [],
        }
    )


def frontmatter_of(text: str) -> dict[str, Any]:
    assert text.startswith("---\n")
    head = text.split("---\n", 2)[1]
    parsed: dict[str, Any] = yaml.safe_load(head)
    return parsed


def body_of(text: str) -> str:
    return text.split("---\n", 2)[2]


# --- отображение возможностей ---------------------------------------------------------


@pytest.mark.parametrize(
    ("needs", "expected"),
    [
        (["read"], ["Read"]),
        (["edit"], ["Write", "Edit"]),
        (["bash"], ["Bash"]),
        (["webfetch"], ["WebFetch"]),
        (["vision"], ["Read"]),
        (["read", "edit"], ["Read", "Write", "Edit"]),
        (["read", "edit", "bash"], ["Read", "Write", "Edit", "Bash"]),
        ([], []),
    ],
)
def test_capability_maps_to_tools(needs: list[str], expected: list[str]) -> None:
    assert tools_of(needs) == expected


def test_read_and_vision_collapse_into_one_read() -> None:
    """Картинки читает тот же инструмент, дубля в списке быть не должно."""
    assert tools_of(["read", "vision"]) == ["Read"]
    assert tools_of(["vision", "read", "edit"]) == ["Read", "Write", "Edit"]


def test_tool_order_is_fixed_regardless_of_needs_order() -> None:
    """Один контракт — один файл: порядок не наследуется из YAML."""
    assert tools_of(["bash", "edit", "read", "webfetch"]) == tools_of(
        ["webfetch", "read", "edit", "bash"]
    )
    assert tools_of(["bash", "edit", "read"]) == ["Read", "Write", "Edit", "Bash"]


def test_mcp_server_becomes_one_prefixed_tool() -> None:
    assert tools_of(["read", "mcp:tavily-remote"]) == ["Read", "mcp__tavily-remote"]


def test_mcp_servers_sorted_and_deduplicated() -> None:
    needs = ["read", "mcp:tavily-remote", "mcp:pdf-reader", "mcp:tavily-remote"]
    assert mcp_servers_of(needs) == ["pdf-reader", "tavily-remote"]
    assert tools_of(needs) == ["Read", "mcp__pdf-reader", "mcp__tavily-remote"]


def test_no_mcp_means_no_servers() -> None:
    assert mcp_servers_of(["read", "edit"]) == []


def test_unmapped_capability_breaks_the_build() -> None:
    """Возможность без отображения — ошибка сборки, а не агент без инструментов."""
    with pytest.raises(ValueError, match="возможности без отображения"):
        tools_of(["read", "telepathy"])


def test_model_rejects_unknown_capability() -> None:
    """Первая линия — валидатор контракта, перенесённый из refract без изменений."""
    with pytest.raises(ValueError, match="unknown capability"):
        spec_of(["read", "telepathy"])


def test_slug_uses_hyphens() -> None:
    assert slug_of("article_critic") == "article-critic"
    assert slug_of("illustrator") == "illustrator"


# --- форма файла ----------------------------------------------------------------------


def test_frontmatter_carries_name_description_and_tools() -> None:
    spec = spec_of(["read", "edit"], name="article_critic")
    head = frontmatter_of(render_agent(spec, "Тело промпта."))
    assert head["name"] == "article-critic"
    assert head["description"] == "Описание агента."
    assert head["tools"] == "Read, Write, Edit"
    assert "mcpServers" not in head


def test_every_agent_omits_claude_md(tmp_path: Path) -> None:
    """CLAUDE.md — инструкция сессии разработчика; агенту она стоит токенов и ничего не даёт.

    По умолчанию Claude Code кладёт всю иерархию CLAUDE.md в контекст каждого подагента:
    40 КБ блоком instructions на момент замера, у писателя — на каждом ходу. Роль агента
    описывает промпт, документ — профиль, входы и выходы — задача из скрипта.
    """
    for path in emit_all(LIBRARY_AGENTS, tmp_path):
        head = frontmatter_of(path.read_text(encoding="utf-8"))
        assert head.get("omitClaudeMd") is True, path.name


def test_frontmatter_lists_mcp_servers_when_contract_names_them() -> None:
    spec = spec_of(["read", "edit", "mcp:tavily-remote"])
    head = frontmatter_of(render_agent(spec, "Тело."))
    assert head["mcpServers"] == ["tavily-remote"]
    assert "mcp__tavily-remote" in head["tools"]


def test_multiline_description_collapses_to_one_line() -> None:
    spec = AgentSpec.model_validate(
        {
            "name": "some_agent",
            "version": 1,
            "description": "Первая строка\nвторая строка\n\nи третья.\n",
            "produces": [{"port": "out", "type": "brief@v1"}],
            "needs": ["read"],
        }
    )
    head = frontmatter_of(render_agent(spec, "Тело."))
    assert head["description"] == "Первая строка вторая строка и третья."


def test_description_with_colon_stays_valid_yaml() -> None:
    """Двоеточие в описании — обычное дело; фронтматтер обязан остаться разбираемым."""
    spec = AgentSpec.model_validate(
        {
            "name": "some_agent",
            "version": 1,
            "description": "Пишет так: коротко, по делу.",
            "produces": [{"port": "out", "type": "brief@v1"}],
            "needs": ["read"],
        }
    )
    head = frontmatter_of(render_agent(spec, "Тело."))
    assert head["description"] == "Пишет так: коротко, по делу."


def test_body_keeps_prompt_verbatim() -> None:
    prompt = "Ты критик.\n\n1. Первый пункт\n2. Второй пункт\n"
    text = render_agent(spec_of(["read"]), prompt)
    assert prompt.strip() in body_of(text)


def test_body_marks_the_file_as_generated() -> None:
    text = render_agent(spec_of(["read"], name="article_critic"), "Тело.")
    assert "Generated by facet/emit_agents.py from library/agents/article_critic/" in text


def test_render_is_deterministic() -> None:
    spec = spec_of(["edit", "read", "mcp:pdf-reader", "mcp:tavily-remote"])
    assert render_agent(spec, "Тело.") == render_agent(spec, "Тело.")


def test_file_ends_with_single_newline() -> None:
    text = render_agent(spec_of(["read"]), "Тело.\n\n\n")
    assert text.endswith("Тело.\n")
    assert not text.endswith("\n\n")


# --- чтение библиотеки ----------------------------------------------------------------


def test_load_agent_reads_contract_and_prompt() -> None:
    spec, prompt = load_agent(LIBRARY_AGENTS / "source_finder")
    assert spec.name == "source_finder"
    assert "mcp:tavily-remote" in spec.needs
    assert prompt.strip() != ""


def test_missing_contract_is_named_in_the_error(tmp_path: Path) -> None:
    (tmp_path / "prompt.md").write_text("Тело.", encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="нет контракта агента"):
        load_agent(tmp_path)


def test_missing_prompt_is_named_in_the_error(tmp_path: Path) -> None:
    (tmp_path / "agent.yaml").write_text(
        "name: a\nversion: 1\nproduces: [{port: out, type: brief@v1}]\n", encoding="utf-8"
    )
    with pytest.raises(FileNotFoundError, match="нет системного промпта"):
        load_agent(tmp_path)


# --- сборка на настоящей библиотеке ---------------------------------------------------


def test_emits_every_agent_of_the_library(tmp_path: Path) -> None:
    written = emit_all(LIBRARY_AGENTS, tmp_path)
    assert len(written) == 22
    assert len(list(tmp_path.glob("*.md"))) == 22


def test_every_emitted_file_parses_and_has_tools(tmp_path: Path) -> None:
    for path in emit_all(LIBRARY_AGENTS, tmp_path):
        head = frontmatter_of(path.read_text(encoding="utf-8"))
        assert head["name"] == path.stem
        assert head["description"].strip() != ""
        assert head["tools"].strip() != ""


def test_mcp_appears_exactly_where_the_contract_names_it(tmp_path: Path) -> None:
    """Проверка результата из `docs/plan.md`: ни одного лишнего разрешения на MCP."""
    emit_all(LIBRARY_AGENTS, tmp_path)
    with_tavily = set()
    with_pdf = set()
    for path in tmp_path.glob("*.md"):
        head = frontmatter_of(path.read_text(encoding="utf-8"))
        name = path.stem.replace("-", "_")
        if "mcp__tavily-remote" in head["tools"]:
            with_tavily.add(name)
        if "mcp__pdf-reader" in head["tools"]:
            with_pdf.add(name)
    assert with_tavily == TAVILY_AGENTS
    assert with_pdf == PDF_AGENTS


def test_mcp_servers_frontmatter_matches_tools(tmp_path: Path) -> None:
    for path in emit_all(LIBRARY_AGENTS, tmp_path):
        head = frontmatter_of(path.read_text(encoding="utf-8"))
        declared = head.get("mcpServers", [])
        from_tools = [
            tool[len("mcp__") :] for tool in head["tools"].split(", ") if tool.startswith("mcp__")
        ]
        assert list(declared) == from_tools


def test_agents_without_mcp_declare_no_servers(tmp_path: Path) -> None:
    emit_all(LIBRARY_AGENTS, tmp_path)
    plain = tmp_path / "article-writer.md"
    head = frontmatter_of(plain.read_text(encoding="utf-8"))
    assert "mcpServers" not in head
    assert head["tools"] == "Read, Write, Edit"


@pytest.mark.parametrize("critic", ["article-critic", "style-critic-ru"])
def test_critics_cannot_write(tmp_path: Path, critic: str) -> None:
    """Критик выносит вердикт, а не правит текст.

    Запрет держится списком инструментов, а не формулировкой в промпте: скрипт и так
    говорит «файла не пишешь», но правило, которое нельзя нарушить физически, не забывается
    в конце длинного круга. Критик с `Edit` — один неудачный вывод от того, чтобы «починить»
    статью, которую его позвали судить.
    """
    emit_all(LIBRARY_AGENTS, tmp_path)
    head = frontmatter_of((tmp_path / f"{critic}.md").read_text(encoding="utf-8"))
    tools = [t.strip() for t in head["tools"].split(",")]
    assert "Write" not in tools
    assert "Edit" not in tools
    assert "Read" in tools


def test_emit_all_is_deterministic(tmp_path: Path) -> None:
    """Golden-свойство: сгенерированное коммитится, значит повторный build даёт то же."""
    first = tmp_path / "one"
    second = tmp_path / "two"
    emit_all(LIBRARY_AGENTS, first)
    emit_all(LIBRARY_AGENTS, second)
    for path in sorted(first.glob("*.md")):
        assert path.read_bytes() == (second / path.name).read_bytes()


def test_emit_agent_creates_missing_output_directory(tmp_path: Path) -> None:
    target = emit_agent(LIBRARY_AGENTS / "illustrator", tmp_path / "нет" / "такого")
    assert target.is_file()
    assert target.name == "illustrator.md"


def test_emit_agent_overwrites_previous_output(tmp_path: Path) -> None:
    target = emit_agent(LIBRARY_AGENTS / "illustrator", tmp_path)
    target.write_text("устаревшее", encoding="utf-8")
    again = emit_agent(LIBRARY_AGENTS / "illustrator", tmp_path)
    assert "устаревшее" not in again.read_text(encoding="utf-8")


def test_illustrator_gets_bash_for_its_external_cli(tmp_path: Path) -> None:
    """Иллюстратор зовёт внешний CLI — без `Bash` он бесполезен."""
    emit_all(LIBRARY_AGENTS, tmp_path)
    head = frontmatter_of((tmp_path / "illustrator.md").read_text(encoding="utf-8"))
    assert "Bash" in head["tools"]


def test_source_processor_reads_images_without_duplicate_read(tmp_path: Path) -> None:
    """У него `read` и `vision` одновременно — в файле должен быть один `Read`."""
    emit_all(LIBRARY_AGENTS, tmp_path)
    head = frontmatter_of((tmp_path / "source-processor.md").read_text(encoding="utf-8"))
    assert head["tools"].split(", ").count("Read") == 1


# --- Всё, что читает агент, — по-английски -----------------------------------------------
#
# Правило проекта, и его пришлось закрепить тестом после того, как оно нарушилось самым тихим
# способом: маркер «сгенерировано» вставлялся в каждый файл по-русски, а файл агента — это
# целиком его системный промпт, вместе с комментарием. Двадцать один агент читал русскую строку,
# и заметно это не было ниоткуда.
#
# Исключение — цитируемый материал целевого языка: словарь штампов, которые критик ищет в русском
# тексте, и образцы формулировок, по которым он их узнаёт. Такой агент не может делать свою работу,
# не называя искомое на языке статьи. Список исключений закрыт и назван здесь: попадание в него
# нового агента — это решение, а не побочный эффект.

CYRILLIC = re.compile("[а-яА-ЯёЁ]")

# Агенты, которым цитировать целевой язык положено по работе.
# Пусто с 2026-09-20. Раньше здесь стояли стилевой критик (словарь русских штампов) и
# корректор статьи (пример ослабленной фразы): русский материал переехал в данные —
# library/style/ru-style-tells.md и library/style/forbid/ru-slop.txt — и критик читает его
# с диска. Промпт, которому нужен целевой язык, теперь называет файл, а не цитирует.
TARGET_LANGUAGE_AGENTS: set[str] = set()


def test_generated_agent_prompts_are_english(tmp_path: Path) -> None:
    """Инструкции агента — по-английски, без исключений; целевой язык только цитатой."""
    out = tmp_path / "agents"
    emit_all(LIBRARY_AGENTS, out)
    offenders = {}
    for path in sorted(out.glob("*.md")):
        if path.stem in TARGET_LANGUAGE_AGENTS:
            continue
        hits = [ln for ln in path.read_text(encoding="utf-8").splitlines() if CYRILLIC.search(ln)]
        if hits:
            offenders[path.name] = hits[:3]
    assert not offenders, f"кириллица в промпте агента: {offenders}"


# --- профили типов документов: поле `skills:` -------------------------------------------
#
# Рантайм подгружает `.claude/skills/<имя>/SKILL.md` в контекст агента при запуске, а
# несуществующий профиль ПРОПУСКАЕТ МОЛЧА — предупреждение только в debug-журнале. Агент без
# контракта стартует и работает, и прогон этого не покажет. Значит существование профиля —
# дело сборки, а не рантайма.


def test_frontmatter_lists_skills_when_contract_names_them() -> None:
    spec = spec_of(["read"], skills=["requirements-profile"])
    head = frontmatter_of(render_agent(spec, "Тело."))
    assert head["skills"] == ["requirements-profile"]


def test_no_skills_means_no_skills_key() -> None:
    head = frontmatter_of(render_agent(spec_of(["read"]), "Тело."))
    assert "skills" not in head


def test_model_rejects_malformed_or_duplicate_skill() -> None:
    with pytest.raises(ValueError, match="invalid skill name"):
        spec_of(["read"], skills=["Requirements Profile"])
    with pytest.raises(ValueError, match="duplicate skill"):
        spec_of(["read"], skills=["a-profile", "a-profile"])


def test_missing_skill_breaks_the_build(tmp_path: Path) -> None:
    """Профиль, которого нет на диске, — ошибка сборки, а не агент без контракта."""
    agent_dir = tmp_path / "lib" / "some_agent"
    agent_dir.mkdir(parents=True)
    (agent_dir / "agent.yaml").write_text(
        "name: some_agent\nversion: 1\nproduces: [{port: out, type: brief@v1}]\n"
        "needs: [read]\nskills: [ghost-profile]\n",
        encoding="utf-8",
    )
    (agent_dir / "prompt.md").write_text("Body.", encoding="utf-8")
    skills = tmp_path / "skills"
    skills.mkdir()
    with pytest.raises(FileNotFoundError, match="ghost-profile"):
        emit_agent(agent_dir, tmp_path / "out", skills)
    assert not (tmp_path / "out" / "some-agent.md").exists()
    # без каталога профилей проверка не делается — так собирает тест на чужой библиотеке
    assert emit_agent(agent_dir, tmp_path / "out").is_file()


def test_missing_skills_names_exactly_the_absent_ones(tmp_path: Path) -> None:
    (tmp_path / "present-profile").mkdir()
    (tmp_path / "present-profile" / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
    spec = spec_of(["read"], skills=["present-profile", "absent-profile"])
    assert missing_skills(spec, tmp_path) == ["absent-profile"]


def test_every_skill_the_library_names_exists(tmp_path: Path) -> None:
    """Сборка настоящей библиотеки против настоящего каталога профилей."""
    emit_all(LIBRARY_AGENTS, tmp_path, SKILLS)


def test_writer_and_critic_of_a_type_read_the_same_profile(tmp_path: Path) -> None:
    """Критерий SPEC §10 шага 3 в его механической части: один профиль на тип, а не копии."""
    emit_all(LIBRARY_AGENTS, tmp_path)
    readers: dict[str, set[str]] = {}
    for path in tmp_path.glob("*.md"):
        head = frontmatter_of(path.read_text(encoding="utf-8"))
        for skill in head.get("skills", []):
            readers.setdefault(skill, set()).add(path.stem.replace("-", "_"))
    assert readers == PROFILE_AGENTS


def test_profiles_are_preloadable_and_english() -> None:
    """`disable-model-invocation: true` рантайм не подгружает; профиль читает агент — по-английски."""
    profiles = sorted(SKILLS.glob("*/SKILL.md"))
    assert {p.parent.name for p in profiles} >= set(PROFILE_AGENTS)
    for path in profiles:
        text = path.read_text(encoding="utf-8")
        head = frontmatter_of(text)
        assert head["name"] == path.parent.name, f"{path}: name != directory"
        assert head.get("disable-model-invocation") is not True, f"{path}: not preloadable"
        assert path.parent.name.endswith("-profile"), f"{path}: a profile is named <type>-profile"
        hits = [ln for ln in text.splitlines() if CYRILLIC.search(ln)]
        assert not hits, f"кириллица в профиле {path.parent.name}: {hits[:3]}"


def test_style_critic_data_files_exist() -> None:
    """Критик читает русский материал с диска; отсутствие файла — молчаливо пустая проверка."""
    assert (ROOT / "library" / "style" / "ru-style-tells.md").is_file()
    assert (ROOT / "library" / "style" / "forbid" / "ru-slop.txt").is_file()
    prompt = (LIBRARY_AGENTS / "style_critic_ru" / "prompt.md").read_text(encoding="utf-8")
    assert "ru-style-tells.md" in prompt and "ru-slop.txt" in prompt


def test_claude_md_is_english() -> None:
    """CLAUDE.md кладётся в контекст каждого подагента как «instructions» — значит, он промпт."""
    hits = [
        ln
        for ln in (ROOT / "CLAUDE.md").read_text(encoding="utf-8").splitlines()
        if CYRILLIC.search(ln)
    ]
    assert not hits, f"кириллица в CLAUDE.md: {hits[:3]}"


def test_generated_marker_names_the_real_generator(tmp_path: Path) -> None:
    """Маркер обещал команду `collimate build`, которой нет ни сейчас, ни когда он писался."""
    out = tmp_path / "agents"
    emit_all(LIBRARY_AGENTS, out)
    text = (out / "gate-runner.md").read_text(encoding="utf-8")
    assert "emit_agents.py" in text
    assert "collimate build" not in text
