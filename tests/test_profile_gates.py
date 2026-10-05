"""A document's rules live in its profile, not in the pipeline that runs it.

The pipelines are meant to be assembled from parts for any document. A script that spelled out
"headings 1 to 10" or "a preliminary note in sections 1, 5 and 6" held one document type's
contract in code shared by every document, and changing the document meant editing the
pipeline. The scripts below name a profile; its gate block holds the rules.
"""

from __future__ import annotations

import re
from pathlib import Path

import gate

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".claude" / "workflows"
# The scripts built on the rule; the older ones are kept for history and not held to it.
PROFILE_DRIVEN = ["requirements.js", "proposal.js", "scene.js", "design.js"]
DOCUMENT_RULES = (
    "--require-heading",
    "--unique-ids",
    "--sequential-ids",
    "--require-in-section",
    "--cell-forbid-file",
)


def test_profile_driven_scripts_hold_no_document_rules() -> None:
    for name in PROFILE_DRIVEN:
        text = (WORKFLOWS / name).read_text(encoding="utf-8")
        found = [flag for flag in DOCUMENT_RULES if flag in text]
        assert not found, (
            f"{name} spells out document rules {found}: put them in the profile's gate block"
        )


def test_every_profile_a_script_names_has_a_gate_block() -> None:
    named: set[str] = set()
    for name in PROFILE_DRIVEN:
        text = (WORKFLOWS / name).read_text(encoding="utf-8")
        named |= set(re.findall(r"profileFlags\('([a-z-]+)'\)", text))
    assert named, "no profile is named"
    for doc_type in sorted(named):
        profile = ROOT / ".claude" / "skills" / f"{doc_type}-profile" / "SKILL.md"
        flags, problems = gate.profile_flags(profile)
        assert not problems, problems
        assert flags, f"{doc_type}-profile has an empty gate block"
