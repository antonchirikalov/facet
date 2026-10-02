#!/usr/bin/env python3
"""List the rules of a profile's critic checklist, one per item, with its severity.

The rule panel checks a document with one verifier per rule, each in a clean context: a single
critic holding a fifteen-item checklist reads the first items carefully and skims the rest. The
rules are not copied into the script; they are read from the profile, so the profile stays the
one place a rule is written.

A checklist is the section whose heading names a critic, reviewer or checklist. Inside it a line
that is only a severity word (CRITICAL, MAJOR, MINOR or HIGH, MEDIUM, LOW, optionally followed by a
note in brackets) opens a tier, and a sentence that merely starts with one does not; a line starting "<n>." or "<n><letter>." opens a rule; indented lines continue
it. ``--top`` keeps the first tier only: the rules that alone force a revise.

The output envelope matches gate.py's; the rules are in ``measures.rules``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import toollog

SECTION = re.compile(r"^##\s+.*\b(critic|reviewer|checklist)\b", re.IGNORECASE)
TIER = re.compile(r"^(CRITICAL|MAJOR|MINOR|HIGH|MEDIUM|LOW)\s*(\(.*\))?\s*$")
ITEM = re.compile(r"^(\d+[a-z]?)\.\s+(.*\S)")


def rules_of(text: str) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    inside = False
    tier: str | None = None
    tier_rank = -1
    for line in text.splitlines():
        if line.startswith("## "):
            inside = bool(SECTION.match(line))
            tier, tier_rank = None, -1
            continue
        if not inside:
            continue
        severity = TIER.match(line)
        if severity:
            tier = severity.group(1)
            tier_rank += 1
            continue
        item = ITEM.match(line)
        if item and tier is not None:
            rules.append(
                {"id": item.group(1), "severity": tier, "rank": tier_rank, "text": item.group(2)}
            )
            continue
        if rules and line.startswith("   ") and line.strip():
            rules[-1]["text"] += " " + line.strip()
    return rules


def main() -> int:
    p = argparse.ArgumentParser(description="List the critic checklist rules of a profile.")
    p.add_argument(
        "--profile", type=Path, required=True, help="a .claude/skills/<type>-profile/SKILL.md"
    )
    p.add_argument("--top", action="store_true", help="only the first severity tier")
    toollog.add_argument(p)
    args = p.parse_args()
    problems: list[str] = []
    rules: list[dict[str, Any]] = []
    if not args.profile.is_file():
        problems.append(f"profile missing: {args.profile.as_posix()}")
    else:
        rules = rules_of(args.profile.read_text(encoding="utf-8"))
        if args.top:
            rules = [r for r in rules if r["rank"] == 0]
        if not rules:
            problems.append("no checklist rules found")
    report = {
        "ok": not problems,
        "problems": problems,
        "measures": {"count": len(rules), "rules": rules},
    }
    toollog.append(args.log, "rules", report, args.log_note, release=args.log_release)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
