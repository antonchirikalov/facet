#!/usr/bin/env python3
"""Read a figgybanana log and say which critic actually judged the images.

The render tool prints the critic it was configured with in its banner ("Critic VLM: kimi /
k3"), a warning when that critic fails ("Critic provider failed, switching to the fallback
... raised PermissionDeniedError ... failed=kimi") and, per accepted image, "Critic satisfied
(<provider>)". On the Vista run the Kimi critic began answering 403 halfway through, the tool
switched to Claude on its own, and the illustrator reported "critic: Kimi K3" for figures Kimi
never saw. The agent read the banner; the log said otherwise three hundred lines further down.

This tool reads the whole log, so the report of who judged a figure comes from the evidence and
not from the configuration. Exit code is 0; the verdict travels in the JSON: ok is false when
the configured critic is not the one that judged, or when nothing judged at all.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import toollog

ANSI = re.compile(r"\x1b\[[0-9;]*m")
BANNER = re.compile(r"Critic VLM:\s*([A-Za-z_]+)\s*/\s*([\w.-]+)")
FALLBACK = re.compile(r"Critic provider failed, switching to the fallback(.*)")
RAISED = re.compile(r"raised (\w+)")
FAILED = re.compile(r"failed=(\w+)")
SATISFIED = re.compile(r"Critic satisfied \((\w+)\)")


def read(text: str) -> dict[str, object]:
    """What the log shows about its critic, as plain facts."""
    clean = ANSI.sub("", text)
    banner = BANNER.search(clean)
    configured = banner.group(1) if banner else None
    fallback = FALLBACK.search(clean)
    reason = None
    if fallback:
        raised = RAISED.search(fallback.group(1))
        failed = FAILED.search(fallback.group(1))
        reason = " ".join(x for x in (failed and failed.group(1), raised and raised.group(1)) if x)
    judged = SATISFIED.findall(clean)
    return {
        "configured": configured,
        "model": banner.group(2) if banner else None,
        "fell_back": fallback is not None,
        "fallback_reason": reason,
        "judged_by": sorted(set(judged)),
        "accepted": len(judged),
    }


def verdict(facts: dict[str, object]) -> list[str]:
    problems: list[str] = []
    judged = facts["judged_by"]
    assert isinstance(judged, list)
    if facts["fell_back"]:
        accepted_by = f"; accepted images were judged by {', '.join(judged)}" if judged else ""
        problems.append(
            f"critic {facts['configured']} failed ({facts['fallback_reason']}) and the rest of "
            f"the run was judged by the fallback critic{accepted_by}"
        )
    elif facts["configured"] and judged and judged != [facts["configured"]]:
        problems.append(f"configured {facts['configured']}, judged by {', '.join(judged)}")
    if not judged:
        problems.append('no image reached "Critic satisfied" in this log')
    return problems


def main() -> int:
    p = argparse.ArgumentParser(description="Which critic judged the images of a render log.")
    p.add_argument(
        "--log-file",
        type=Path,
        action="append",
        required=True,
        metavar="FILE",
        help="a figgybanana log; repeatable, one report per file",
    )
    toollog.add_argument(p)
    args = p.parse_args()

    per_file: dict[str, dict[str, object]] = {}
    problems: list[str] = []
    for path in args.log_file:
        if not path.is_file():
            problems.append(f"{path.name}: log missing")
            continue
        facts = read(path.read_text(encoding="utf-8", errors="replace"))
        per_file[path.name] = facts
        problems.extend(f"{path.name}: {p}" for p in verdict(facts))
    report = {"ok": not problems, "problems": problems, "measures": {"logs": per_file}}
    toollog.append(args.log, "critic_used", report, args.log_note, release=args.log_release)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
