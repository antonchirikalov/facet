#!/usr/bin/env python3
"""Check an exact figure's brief against the document before anything is rendered.

A picture whose numbers are the point (posts along a fence under a spacing banner, a price list, a
disclaimer, week spans) is only right when every number on it is the document's number. On one
live proposal the brief itself was wrong: five posts on a 36 ft fence under a banner of 6'-0"
spacing and 2'-0" from the ends, which needs seven. Thirty renders later the figure was still
being corrected, and the error had been in the text given to the renderer from the start.

So an exact brief ends with a Facts block, and this tool checks it:

    Facts:
    - text: PRELIMINARY ESTIMATE: MAX 6'-0" POST SPACING
    - check: ceil((29 - 2 * 2) / 6) + 1 == 6

A "text" line must occur in the document verbatim (whitespace and quote styles normalised). A
"check" line is arithmetic over numbers only — + - * / // % ( ), ceil, floor, round, min, max,
abs and comparisons — and must be true. Anything else in a check is refused, not evaluated.
Exit code is 0; the verdict travels in the JSON.
"""

from __future__ import annotations

import argparse
import ast
import json
import math
import operator
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import toollog

FACT = re.compile(r"^\s*-\s*(text|check)\s*:\s*(.+?)\s*$", re.IGNORECASE)
FACTS_HEADER = re.compile(r"^\s*facts\s*:\s*$", re.IGNORECASE | re.MULTILINE)

FUNCTIONS: dict[str, Callable[..., Any]] = {
    "ceil": math.ceil,
    "floor": math.floor,
    "round": round,
    "min": min,
    "max": max,
    "abs": abs,
}
BINARY: dict[type, Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
}
COMPARE: dict[type, Callable[[Any, Any], bool]] = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}


def evaluate(node: ast.AST) -> Any:
    """Arithmetic only. Names, attributes, strings and every other node are refused."""
    if isinstance(node, ast.Expression):
        return evaluate(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        value = evaluate(node.operand)
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.BinOp) and type(node.op) in BINARY:
        return BINARY[type(node.op)](evaluate(node.left), evaluate(node.right))
    if isinstance(node, ast.Compare):
        left = evaluate(node.left)
        for op, right_node in zip(node.ops, node.comparators, strict=True):
            if type(op) not in COMPARE:
                raise ValueError("comparison not allowed")
            right = evaluate(right_node)
            if not COMPARE[type(op)](left, right):
                return False
            left = right
        return True
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in FUNCTIONS
        and not node.keywords
    ):
        return FUNCTIONS[node.func.id](*(evaluate(a) for a in node.args))
    raise ValueError(f"not arithmetic: {type(node).__name__}")


def normalise(text: str) -> str:
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip().lower()


def facts_of(brief: str) -> list[tuple[str, str]]:
    header = FACTS_HEADER.search(brief)
    if header is None:
        return []
    out = []
    for line in brief[header.end() :].splitlines():
        found = FACT.match(line)
        if found:
            out.append((found.group(1).lower(), found.group(2)))
        elif line.strip() and not line.strip().startswith("-"):
            break
    return out


def check(brief: str, document: str) -> tuple[list[str], dict[str, int]]:
    facts = facts_of(brief)
    problems: list[str] = []
    if not facts:
        problems.append("the brief has no Facts block")
    haystack = normalise(document)
    texts = checks = 0
    for kind, value in facts:
        if kind == "text":
            texts += 1
            if normalise(value) not in haystack:
                problems.append(f"text not in the document: {value}")
        else:
            checks += 1
            try:
                result = evaluate(ast.parse(value, mode="eval"))
            except (SyntaxError, ValueError, TypeError, ZeroDivisionError) as exc:
                problems.append(f"check refused ({exc}): {value}")
                continue
            if result is not True:
                problems.append(f"check is false: {value}")
    return problems, {"texts": texts, "checks": checks}


def main() -> int:
    p = argparse.ArgumentParser(
        description="An exact figure's Facts must hold against its document."
    )
    p.add_argument("--brief", type=Path, required=True, help="the figure brief")
    p.add_argument("--file", type=Path, required=True, help="the document the figure illustrates")
    toollog.add_argument(p)
    args = p.parse_args()

    missing = [s for s in (args.brief, args.file) if not s.is_file()]
    if missing:
        problems = [f"file missing: {m.as_posix()}" for m in missing]
        measures: dict[str, int] = {}
    else:
        problems, measures = check(
            args.brief.read_text(encoding="utf-8"), args.file.read_text(encoding="utf-8")
        )
    report = {"ok": not problems, "problems": problems, "measures": measures}
    toollog.append(args.log, "figure_facts", report, args.log_note, release=args.log_release)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
