"""Everything in the repository is English except README.md.

The README is for the Russian-speaking reader of the project; everything else is read by agents
or by developers, and one language keeps them from drifting apart. Russian is allowed only where
it is data: the clichés and examples a critic matches in Russian text, the `summary` fields that
feed the README agent table, string literals a tool or test needs (a Russian column name, a
Russian fixture), and one key in a script that maps a Russian language name.
"""

from __future__ import annotations

import ast
import io
import re
import subprocess
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CYRILLIC = re.compile("[Ѐ-ӿ]")

# Russian documents by design.
RUSSIAN_FILES = {"README.md", "docs/article-dynamic-workflows.md"}
# Language material: what critics match in Russian text, and archived agents kept for history.
MATERIAL_DIRS = ("library/style/", "library/agents-archive/")
# Script lines that carry Russian as data, verbatim.
SCRIPT_DATA_LINES = {"  { russian: RU, 'русский': RU },"}


def tracked() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    return [line for line in out.splitlines() if line]


def python_problems(path: Path) -> list[str]:
    """Cyrillic in a comment or a docstring; string literals are data and may hold it."""
    text = path.read_text(encoding="utf-8")
    problems: list[str] = []
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type == tokenize.COMMENT and CYRILLIC.search(tok.string):
            problems.append(f"{path.name}:{tok.start[0]} comment")
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            doc = ast.get_docstring(node)
            if doc and CYRILLIC.search(doc):
                problems.append(f"{path.name}:{getattr(node, 'lineno', 1)} docstring")
    return problems


def test_only_readme_is_russian() -> None:
    problems: list[str] = []
    for rel in tracked():
        if rel in RUSSIAN_FILES or rel.startswith(MATERIAL_DIRS):
            continue
        path = ROOT / rel
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue
        if not CYRILLIC.search(text):
            continue
        if rel.endswith(".py"):
            problems.extend(python_problems(path))
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if not CYRILLIC.search(line):
                continue
            if (
                rel.startswith("library/agents/")
                and rel.endswith("agent.yaml")
                and line.startswith("summary:")
            ):
                continue
            if rel.endswith((".js", ".mjs")) and line in SCRIPT_DATA_LINES:
                continue
            problems.append(f"{rel}:{n}")
    assert problems == [], "Russian outside README.md:\n" + "\n".join(problems[:40])
