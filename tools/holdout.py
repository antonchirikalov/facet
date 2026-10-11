#!/usr/bin/env python3
"""The ruler of the holdout questions: what the client's people will ask of our documents.

A document's writer, corrector and critic read one profile, so a critic checks rules its writer
already knew. The holdout questions are the other measure. A questioner writes them from the
client's own material before any document exists, a skeptic keeps the ones that pass the
profile's criteria, and after the rounds a reader with nothing but the document looks for each
answer. This tool does every step of that which is not judgement, in four modes:

  --check    every question carries its nine keys with valid values, and every quoted ground is
             found verbatim in the client's material; a draft holds draft-min to draft-max
  --select   the final file from the draft and the skeptic's ids: every asked question kept,
             the quotas of the profile checked, the blocks copied byte for byte (a ground the
             skeptic rephrased would no longer be the client's words)
  --blind    the reader's batches for one document: the question and who asks, nothing about
             where it came from or what is expected of the document
  --score    each answer's quote looked up in the document (a quote that is not there makes the
             answer absent), then what was met, weighted and by layer

The quotas live in the profile's ```holdout block, not in a script. The output envelope matches
gate.py's.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import toollog
from check_quotes import SPLIT, expand, normalise

KEYS = (
    "Layer",
    "Role",
    "Situation",
    "Question",
    "Ground",
    "Decides",
    "Weight",
    "Design",
    "Proposal",
)
LAYERS = ("asked", "implied", "role", "situation", "domain")
WEIGHTS = {"blocking": 2, "important": 1}
EXPECTATIONS = ("answer", "acknowledge", "none")
DOCUMENTS = {"design": "Design", "proposal": "Proposal"}
OUTCOMES = ("answered", "acknowledged", "absent")

BLOCK = re.compile(r"^###\s+(Q-\d{2})\s*$", re.MULTILINE)
KEY_LINE = re.compile(r"^\s*-\s*([A-Za-z]+)\s*:\s*(.*?)\s*$")
HOLDOUT_BLOCK = re.compile(r"^```holdout[ \t]*\n(.*?)^```", re.MULTILINE | re.DOTALL)
CURLY = re.compile(r"“([^”]+)”")
STRAIGHT = re.compile(r'"([^"\n]{3,})"')
URL = re.compile(r"https?://\S+")
ABSENT = re.compile(r"^absent role\s*:", re.IGNORECASE)
# An answer quoting "yes" or a heading is found in any document; it proves nothing.
MIN_ANSWER_QUOTE = 12

DEFAULTS: dict[str, float] = {
    "draft-min": 40,
    "draft-max": 60,
    "layer-min": 4,
    "others-max": 24,
    "blocking-max": 0.34,
    "batch": 10,
}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def limits(profile: Path | None) -> tuple[dict[str, float], list[str]]:
    """The quotas of the profile's holdout block, over the defaults."""
    values = dict(DEFAULTS)
    if profile is None:
        return values, []
    if not profile.is_file():
        return values, [f"profile missing: {profile.as_posix()}"]
    match = HOLDOUT_BLOCK.search(read(profile))
    if not match:
        return values, [f"profile has no holdout block: {profile.as_posix()}"]
    problems: list[str] = []
    for line in match.group(1).splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 2 or parts[0] not in DEFAULTS:
            problems.append(f"holdout block: not a known setting: {line.strip()}")
            continue
        try:
            values[parts[0]] = float(parts[1])
        except ValueError:
            problems.append(f"holdout block: not a number: {line.strip()}")
    return values, problems


def split_blocks(text: str) -> tuple[str, list[tuple[str, str]]]:
    """The text before the first question, and each question's id with its block verbatim."""
    starts = list(BLOCK.finditer(text))
    if not starts:
        return text, []
    head = text[: starts[0].start()]
    blocks = []
    for i, m in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        blocks.append((m.group(1), text[m.start() : end]))
    return head, blocks


def fields_of(block: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for line in block.splitlines()[1:]:
        m = KEY_LINE.match(line)
        if m and m.group(1) in KEYS and m.group(1) not in found:
            found[m.group(1)] = m.group(2)
    return found


def parse(text: str) -> tuple[str, list[dict[str, str]], list[str]]:
    """Questions as dicts with their id and raw block; problems of their shape."""
    head, blocks = split_blocks(text)
    questions: list[dict[str, str]] = []
    problems: list[str] = []
    seen: set[str] = set()
    for qid, block in blocks:
        if qid in seen:
            problems.append(f"{qid}: the id is used twice")
            continue
        seen.add(qid)
        f = fields_of(block)
        missing = [k for k in KEYS if not f.get(k)]
        if missing:
            problems.append(f"{qid}: missing {', '.join(missing)}")
        layer, weight = f.get("Layer", ""), f.get("Weight", "")
        if layer and layer not in LAYERS:
            problems.append(f"{qid}: Layer must be one of {', '.join(LAYERS)}, got {layer}")
        if weight and weight not in WEIGHTS:
            problems.append(f"{qid}: Weight must be blocking or important, got {weight}")
        for key in DOCUMENTS.values():
            value = f.get(key, "")
            if value and value not in EXPECTATIONS:
                problems.append(f"{qid}: {key} must be answer, acknowledge or none, got {value}")
        if all(f.get(k) == "none" for k in DOCUMENTS.values()):
            problems.append(f"{qid}: no document is expected to answer it")
        problems.extend(ground_shape(qid, layer, f.get("Ground", "")))
        questions.append({"id": qid, "block": block, **f})
    return head, questions, problems


def quote_of(ground: str) -> str | None:
    m = CURLY.search(ground) or STRAIGHT.search(ground)
    return m.group(1) if m else None


def ground_shape(qid: str, layer: str, ground: str) -> list[str]:
    if not ground:
        return []
    if layer == "domain":
        return [] if URL.search(ground) else [f"{qid}: a domain ground names its source URL"]
    if ABSENT.match(ground):
        return [] if layer == "role" else [f"{qid}: only a role question rests on an absent role"]
    if quote_of(ground) is None:
        return [f"{qid}: the ground quotes the client's words, in quotation marks"]
    return []


def found_in(quote: str, haystack: str) -> bool:
    fragments = [f for f in SPLIT.split(quote) if normalise(f)]
    return bool(fragments) and all(normalise(f) in haystack for f in fragments)


def check_grounds(questions: list[dict[str, str]], sources: str) -> tuple[int, list[str]]:
    haystack = normalise(sources)
    checked, problems = 0, []
    for q in questions:
        ground = q.get("Ground", "")
        if q.get("Layer") == "domain" or ABSENT.match(ground):
            continue
        quote = quote_of(ground)
        if quote is None:
            continue
        checked += 1
        if not found_in(quote, haystack):
            problems.append(f"{q['id']}: the ground is not in the client's material: “{quote}”")
    return checked, problems


def by_layer(questions: list[dict[str, str]]) -> dict[str, int]:
    return {layer: sum(1 for q in questions if q.get("Layer") == layer) for layer in LAYERS}


def blocking_share(questions: list[dict[str, str]]) -> float:
    if not questions:
        return 0.0
    return round(sum(1 for q in questions if q.get("Weight") == "blocking") / len(questions), 2)


def do_check(args: argparse.Namespace, lim: dict[str, float]) -> dict[str, Any]:
    _, questions, problems = parse(read(args.file))
    checked = 0
    if args.source:
        files = expand(args.source)
        if not files:
            problems.append("no source files")
        else:
            checked, missing = check_grounds(questions, "\n".join(read(f) for f in files))
            problems.extend(missing)
    if not args.final and not lim["draft-min"] <= len(questions) <= lim["draft-max"]:
        problems.append(
            f"a draft holds {lim['draft-min']:g} to {lim['draft-max']:g} questions, got {len(questions)}"
        )
    if args.final and not questions:
        problems.append("no questions")
    return {
        "ok": not problems,
        "problems": problems,
        "measures": {
            "questions": len(questions),
            "by_layer": by_layer(questions),
            "blocking_share": blocking_share(questions),
            "grounds_checked": checked,
        },
    }


def do_select(args: argparse.Namespace, lim: dict[str, float]) -> dict[str, Any]:
    head, questions, problems = parse(read(args.file))
    wanted = [k.strip() for k in (args.keep or "").split(",") if k.strip()]
    known = {q["id"] for q in questions}
    problems.extend(f"{k}: not in the draft" for k in wanted if k not in known)
    asked = [q["id"] for q in questions if q.get("Layer") == "asked"]
    keep = set(wanted) | set(asked)
    kept = [q for q in questions if q["id"] in keep]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(head + "".join(q["block"] for q in kept), encoding="utf-8", newline="\n")
    layers = by_layer(kept)
    short = [layer for layer in LAYERS if layer != "asked" and layers[layer] < lim["layer-min"]]
    for layer in short:
        problems.append(f"layer {layer}: {layers[layer]} kept, at least {lim['layer-min']:g}")
    others = len(kept) - layers["asked"]
    if others > lim["others-max"]:
        problems.append(f"{others} kept beyond the asked ones, at most {lim['others-max']:g}")
    share = blocking_share(kept)
    if share > lim["blocking-max"]:
        problems.append(f"blocking is {share:g} of the kept, at most {lim['blocking-max']:g}")
    return {
        "ok": not problems,
        "problems": problems,
        "measures": {
            "kept": len(kept),
            "asked_kept": layers["asked"],
            "by_layer": layers,
            "short_layers": short,
            "blocking_share": share,
        },
    }


def expected_for(questions: list[dict[str, str]], document: str) -> list[dict[str, str]]:
    key = DOCUMENTS[document]
    return [q for q in questions if q.get(key) in ("answer", "acknowledge")]


def do_blind(args: argparse.Namespace, lim: dict[str, float]) -> dict[str, Any]:
    _, questions, problems = parse(read(args.file))
    expected = expected_for(questions, args.document_kind)
    size = int(args.batch or lim["batch"])
    out: Path = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    # A batch file or an answer from an earlier blinding would be read with this one's.
    stale = sorted(out.glob("blind-*.md")) + sorted(out.glob("answers-*.json"))
    for f in stale:
        f.unlink()
    batches = [expected[i : i + size] for i in range(0, len(expected), size)]
    for n, batch in enumerate(batches, 1):
        lines = ["# Questions", ""]
        for q in batch:
            lines += [
                f"### {q['id']}",
                f"- Role: {q.get('Role', '')}",
                f"- Question: {q.get('Question', '')}",
                "",
            ]
        (out / f"blind-{n}.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    if not expected:
        problems.append(f"no question is expected of the {args.document_kind}")
    return {
        "ok": not problems,
        "problems": problems,
        "measures": {"batches": len(batches), "questions": len(expected), "removed": len(stale)},
    }


def load_answers(directory: Path) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    """Every reader's answer per question: a batch read by two readers gives two answers."""
    answers: dict[str, list[dict[str, Any]]] = {}
    problems: list[str] = []
    for f in sorted(directory.glob("answers-*.json")):
        seen: set[str] = set()
        try:
            items = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            problems.append(f"{f.name}: not JSON: {exc}")
            continue
        if not isinstance(items, list):
            problems.append(f"{f.name}: not a list of answers")
            continue
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                problems.append(f"{f.name}: an answer without an id")
                continue
            if item["id"] in seen:
                problems.append(f"{f.name}: {item['id']} answered twice")
                continue
            seen.add(item["id"])
            answers.setdefault(item["id"], []).append(item)
    return answers, problems


# Lower first: of two readers who disagree, the lower outcome stands, as it does for one reader
# in doubt. A reader who has to argue that a document answered them was not answered.
RANK = {"absent": 0, "acknowledged": 1, "answered": 2}


def cell(text: object) -> str:
    return str(text or "").replace("|", "\\|").replace("\n", " ")


def do_score(args: argparse.Namespace, _lim: dict[str, float]) -> dict[str, Any]:
    _, questions, problems = parse(read(args.file))
    expected = expected_for(questions, args.document_kind)
    document = normalise(read(args.document))
    answers, answer_problems = load_answers(args.answers_dir)
    problems.extend(answer_problems)
    key = DOCUMENTS[args.document_kind]
    rows, met_ids, downgraded, unanswered, instead, unplain = [], [], [], [], [], []
    disagreed: list[str] = []
    readers = 0
    total = met_weight = 0
    layers = {layer: {"met": 0, "of": 0} for layer in LAYERS}
    for q in expected:
        said = answers.get(q["id"], [])
        readers = max(readers, len(said))
        if not said:
            unanswered.append(q["id"])
        judged: list[tuple[str, str, dict[str, Any]]] = []
        for a in said:
            outcome = str(a.get("outcome"))
            quote = str(a.get("quote") or "")
            if outcome not in OUTCOMES:
                problems.append(
                    f"{q['id']}: outcome must be answered, acknowledged or absent, got {outcome}"
                )
                outcome = "absent"
            if outcome in ("answered", "acknowledged") and (
                len(normalise(quote)) < MIN_ANSWER_QUOTE or not found_in(quote, document)
            ):
                if q["id"] not in downgraded:
                    downgraded.append(q["id"])
                outcome = "absent"
            judged.append((outcome, quote, a))
        if len({o for o, _, _ in judged}) > 1:
            disagreed.append(q["id"])
        outcome, quote, a = min(judged, key=lambda j: RANK[j[0]]) if judged else ("absent", "", {})
        expectation = q.get(key, "")
        met = outcome == "answered" or (outcome == "acknowledged" and expectation == "acknowledge")
        if outcome == "acknowledged" and expectation == "answer":
            instead.append(q["id"])
        if outcome == "answered" and a.get("plain") is False:
            unplain.append(q["id"])
        weight = WEIGHTS.get(q.get("Weight", ""), 1)
        total += weight
        layer = q.get("Layer", "")
        if layer in layers:
            layers[layer]["of"] += 1
        if met:
            met_weight += weight
            met_ids.append(q["id"])
            if layer in layers:
                layers[layer]["met"] += 1
        rows.append((q, expectation, outcome, quote))
    if unanswered:
        problems.append(f"no answer for {', '.join(unanswered)}")
    score = round(met_weight / total, 2) if total else 0.0
    absent_blocking = [
        q["id"] for q, _, _, _ in rows if q.get("Weight") == "blocking" and q["id"] not in met_ids
    ]
    lost: list[str] = []
    if args.compare is not None:
        try:
            before = json.loads(args.compare.read_text(encoding="utf-8"))
            lost = [i for i in before.get("met_ids", []) if i not in met_ids]
        except (OSError, json.JSONDecodeError) as exc:
            problems.append(f"the score to compare with is unreadable: {exc}")
    measures = {
        "score": score,
        "met": len(met_ids),
        "expected": len(expected),
        "by_layer": layers,
        "absent_blocking": absent_blocking,
        "acknowledged_instead_of_answered": instead,
        "downgraded_quote_not_found": downgraded,
        "answered_not_plain": unplain,
        "lost_since_compared": lost,
        "readers": readers,
        "readers_disagreed": disagreed,
    }
    out: Path = args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Holdout score: {args.document.as_posix()}",
        "",
        f"Score {score:g} (weighted: blocking 2, important 1); met {len(met_ids)} of {len(expected)}.",
        "By layer: "
        + "; ".join(f"{k} {v['met']} of {v['of']}" for k, v in layers.items() if v["of"]),
        f"Blocking not met: {', '.join(absent_blocking) or 'none'}.",
        f"Answers whose quote is not in the document, counted absent: {', '.join(downgraded) or 'none'}.",
        (
            f"Readers per question: {readers}; where they disagreed the lower outcome stands: "
            f"{', '.join(disagreed) or 'none'}."
        ),
    ]
    if args.compare is not None:
        lines.append(f"Met before and not now: {', '.join(lost) or 'none'}.")
    lines += [
        "",
        "| Q | Layer | Role | Weight | Expected | Outcome | Question | Quote |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for q, expectation, outcome, quote in rows:
        lines.append(
            f"| {q['id']} | {cell(q.get('Layer'))} | {cell(q.get('Role'))} | {cell(q.get('Weight'))} | "
            f"{cell(expectation)} | {outcome} | {cell(q.get('Question'))} | {cell(quote)} |"
        )
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    out.with_suffix(".json").write_text(
        json.dumps({**measures, "met_ids": met_ids}, ensure_ascii=False, indent=1),
        encoding="utf-8",
        newline="\n",
    )
    return {"ok": not problems, "problems": problems, "measures": measures}


def main() -> int:
    p = argparse.ArgumentParser(description="Check, select, blind and score the holdout questions.")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="shape of every question and its ground")
    mode.add_argument("--select", action="store_true", help="the final file from the skeptic's ids")
    mode.add_argument("--blind", action="store_true", help="the reader's batches for one document")
    mode.add_argument("--score", action="store_true", help="the answers against the document")
    p.add_argument("--file", type=Path, required=True, help="the questions file")
    p.add_argument(
        "--profile", type=Path, default=None, help="the profile whose holdout block sets the quotas"
    )
    p.add_argument(
        "--source",
        type=Path,
        action="append",
        metavar="PATH",
        help="--check: client material, repeatable",
    )
    p.add_argument("--final", action="store_true", help="--check: a selected file, no draft range")
    p.add_argument("--keep", default="", help="--select: the ids the skeptic kept, comma-separated")
    p.add_argument("--out", type=Path, help="--select: the final file; --score: the score file")
    p.add_argument(
        "--for",
        dest="document_kind",
        choices=sorted(DOCUMENTS),
        help="--blind, --score: which document",
    )
    p.add_argument(
        "--batch", type=int, default=0, help="--blind: questions per batch, over the profile"
    )
    p.add_argument("--out-dir", type=Path, help="--blind: where the batches go")
    p.add_argument("--document", type=Path, help="--score: the document the answers quote")
    p.add_argument(
        "--answers-dir", type=Path, help="--score: where the reader's answers-*.json are"
    )
    p.add_argument(
        "--compare",
        type=Path,
        default=None,
        help="--score: an earlier score.json of the same questions",
    )
    toollog.add_argument(p)
    args = p.parse_args()

    lim, problems = limits(args.profile)
    needed = {
        "select": ["out"],
        "blind": ["document_kind", "out_dir"],
        "score": ["document_kind", "document", "answers_dir", "out"],
    }
    chosen = next(m for m in ("check", "select", "blind", "score") if getattr(args, m))
    absent = [n for n in needed.get(chosen, []) if getattr(args, n) is None]
    files = [args.file] + ([args.document] if chosen == "score" and args.document else [])
    missing = [f for f in files if not f.is_file()]
    if absent or missing:
        report: dict[str, Any] = {
            "ok": False,
            "problems": [f"--{n.replace('_', '-')} is required" for n in absent]
            + [f"file missing: {f.as_posix()}" for f in missing],
            "measures": {},
        }
    else:
        run = {"check": do_check, "select": do_select, "blind": do_blind, "score": do_score}[chosen]
        report = run(args, lim)
        report["problems"] = problems + report["problems"]
        report["ok"] = not report["problems"]
    toollog.append(args.log, f"holdout-{chosen}", report, args.log_note, release=args.log_release)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
