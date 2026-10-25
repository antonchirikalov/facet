"""The value map is recomputed by a ruler, never trusted.

On the one hand-made value model of six live runs the range was twelvefold and no line carried
a cost. The fixtures are the invented Acme Clinics: one good map, and one change of it per
failure the ruler must name.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import value_model

ROOT = Path(__file__).resolve().parent.parent
GOOD = (Path(__file__).parent / "fixtures" / "value_map" / "good.md").read_text(encoding="utf-8")


def changed(old: str, new: str) -> str:
    assert old in GOOD, f"fixture text not found: {old}"
    return GOOD.replace(old, new, 1)


def test_the_good_map_passes_with_its_totals() -> None:
    report = value_model.measure(GOOD)
    assert report["problems"] == []
    assert report["ok"] is True
    assert report["totals"] == {
        "hard": 20250.0,
        "soft": 3360.0,
        "run": 1064.0,
        "net": 22546.0,
        "budget-12": 270552.0,
        "budget-24": 541104.0,
    }
    assert report["measures"]["value_lines"] == 3
    assert report["measures"]["sensitivity_cases"] == 3
    assert report["measures"]["currency"] == ["USD"]


def test_the_course_example_in_the_profile_notation() -> None:
    """The profile's worked example must be readable by the ruler that holds the writer to it."""
    lines = [
        "4,000 claims/month × 45 min × $40/h = $120,000/month",
        (
            "(4,000 claims/month × 70% × 5 min + 4,000 claims/month × 30% × 20 min) × $40/h"
            " = $25,300/month"
        ),
        "$120,000/month − $25,300/month = $94,700/month",
        "$94,700/month − $1,700/month = $93,000/month",
        "$93,000/month × 12 month = $1,116,000",
    ]
    for line in lines:
        f = value_model.formula(line)
        assert value_model.mismatch("x", f.computed, f.stated) is None, line
    profile = (ROOT / ".claude" / "skills" / "value-map-profile" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "4,000 claims/month × 45 min × $40/h = $120,000/month" in profile


def test_russian_notation_and_suffixes() -> None:
    f = value_model.formula("4 000 заявок/мес × 45 мин × 2 400 ₽/ч = 7 200 000 ₽/мес")
    assert value_model.mismatch("x", f.computed, f.stated) is None
    f = value_model.formula("6,000 conversations/month × 8k tokens × $3/1M tokens = $144/month")
    assert value_model.mismatch("x", f.computed, f.stated) is None
    f = value_model.formula("0,5 ч × 2 = 1 ч")
    assert value_model.mismatch("x", f.computed, f.stated) is None


def test_a_year_is_twelve_months_and_days_do_not_convert() -> None:
    f = value_model.formula("$12,000/year = $1,000/month")
    assert value_model.mismatch("x", f.computed, f.stated) is None
    f = value_model.formula("600 tickets/day × 2 min = 20 h/month")
    assert "units differ" in str(value_model.mismatch("x", f.computed, f.stated))


MISS_CASE = next(ln for ln in GOOD.splitlines(True) if ln.startswith("| Accuracy SLA missed |"))

FAILURES = [
    pytest.param(
        "| $16,800/month − $8,400/month = $8,400/month |",
        "| $16,800/month − $8,400/month = $9,400/month |",
        "V-01 monthly gain: stated 9,400.00",
        id="a-line-the-ruler-does-not-reproduce",
    ),
    pytest.param(
        "= $22,546/month |\n| budget-12",
        "= $23,546/month |\n| budget-12",
        "section 6 net: stated 23,546.00",
        id="a-total-the-ruler-does-not-reproduce",
    ),
    pytest.param(
        "| net | $20,250/month + $3,360/month − $1,064/month = $22,546/month |",
        "| net | $20,250/month + $3,360/month − $64/month = $23,546/month |",
        "section 6 net against sections 4 and 5: stated 23,546.00",
        id="a-net-that-is-not-the-sum-of-the-lines",
    ),
    pytest.param(
        "6,000 calls/month × 6 min × $28/h = $16,800/month",
        "6,000 calls/month × 6 min × $30/h = $18,000/month",
        "V-01 now: 30 has no source and no star",
        id="a-number-with-no-source-and-no-star",
    ),
    pytest.param(
        "900 no-shows/month × (1 − 25%*) × $90/visit = $60,750/month",
        "900 no-shows/month × (1 − 20%*) × $90/visit = $64,800/month",
        "V-02 with the solution: 20* is not in the assumption map",
        id="a-star-with-no-assumption-row",
    ),
    pytest.param(
        "becomes money when front desk overtime stops; $8,400/month",
        "$8,400/month",
        "V-01: a soft line with no condition for becoming money",
        id="a-soft-line-with-no-condition",
    ),
    pytest.param(
        "$8,400/month × (1 − 60%) = $3,360/month",
        "$8,400/month × 1 = $8,400/month",
        "V-01: a soft line counted in full",
        id="a-soft-line-counted-as-cash",
    ),
    pytest.param(
        "becomes money when front desk overtime stops; $8,400/month × (1 − 60%) = $3,360/month",
        "becomes money when front desk overtime stops",
        "V-01: a soft line with no counted amount",
        id="a-soft-line-with-no-write-off",
    ),
    pytest.param(
        "| V-02 | P-02 | cost |",
        "| V-02 | missed visits | cost |",
        "V-02: no pain id",
        id="a-value-line-with-no-pain",
    ),
    pytest.param(
        "| V-02 | P-02 | cost |",
        "| V-02 | P-02 | savings |",
        "V-02: no pillar",
        id="a-value-line-with-no-pillar",
    ),
    pytest.param(
        "| hard | | SLA-02 |",
        "| hard | | SLA-07 |",
        "V-02: SLA-07 is not declared in section 2",
        id="an-sla-that-is-not-declared",
    ),
    pytest.param(
        "| hard | | SLA-02 |",
        "| hard | | |",
        "V-02: no SLA id",
        id="a-value-line-with-no-sla",
    ),
    pytest.param(
        "900 no-shows/month × $90/visit = $81,000/month |",
        "900 no-shows/month × $90/visit = $81,000 |",
        "V-02 now: units differ",
        id="a-monthly-figure-without-its-period",
    ),
    pytest.param(
        "| 1 environment × $400/month = $400/month | $400/month |",
        "| 1 environment × $400/month = $400/month | $500/month |",
        "run cost 'Hosting' monthly cost: stated 500.00",
        id="a-run-cost-that-is-not-its-driver",
    ),
    pytest.param(
        "| $10,813/month × 12 month = $129,756 |",
        "| $10,813/month × 10 month = $108,130 |",
        "case 'Volume halved' budget 12 against its net",
        id="a-case-budget-that-is-not-its-net",
    ),
    pytest.param(
        "| timestamps: 5.5 min; staff top-down: 6.5 min |",
        "| timestamps: 4 min; staff top-down: 6.5 min |",
        "two estimates differ more than 1.5 times",
        id="two-baseline-estimates-that-disagree",
    ),
    pytest.param(
        "| 1 environment × $400/month = $400/month | $400/month |",
        "| 1 environment × €400/month = €400/month | €400/month |",
        "more than one currency",
        id="two-currencies",
    ),
    pytest.param(
        "## 8. Verdict\n",
        "## 8. Verdict\n\nThe project cost of $150,000 pays back in seven months.\n",
        "a project price, a rate or hours of our work",
        id="a-project-price",
    ),
    pytest.param(
        "## 8. Verdict\n",
        "## 8. Verdict\n\nA team of 4 builds it in 1,200 person-hours.\n",
        "a project price, a rate or hours of our work",
        id="hours-of-our-work",
    ),
    pytest.param(
        "6,000 calls/month × 6 min × $28/h = $16,800/month",
        "6,000 calls/month × 6 min $28/h = $16,800/month",
        "V-01 now: cannot read the formula (two values with no operator",
        id="a-formula-that-cannot-be-read",
    ),
    pytest.param(
        MISS_CASE,
        "",
        "section 7: 2 sensitivity cases, at least 3",
        id="no-miss-case",
    ),
]


@pytest.mark.parametrize(("old", "new", "expected"), FAILURES)
def test_each_failure_is_named(old: str, new: str, expected: str) -> None:
    report = value_model.measure(changed(old, new))
    assert report["ok"] is False
    assert any(expected in p for p in report["problems"]), report["problems"]


def test_a_wide_assumption_range_is_a_warning_not_a_failure() -> None:
    report = value_model.measure(changed("| 25% (15–35) |", "| 25% (5–35) |"))
    assert report["ok"] is True
    assert report["warnings"] == ["A-02: range 5–35 is wider than 3 times"]
    narrow = value_model.measure(changed("| 25% (15–35) |", "| 25% (5–35) |"), max_ratio=8)
    assert narrow["warnings"] == []


def test_the_clients_hourly_cost_is_not_a_rate_of_ours() -> None:
    """$28/h is the client's loaded hour, a value input; the price patterns must leave it alone."""
    assert not any("project price" in p for p in value_model.measure(GOOD)["problems"])


def test_pain_ids_are_checked_against_the_pain_map() -> None:
    report = value_model.measure(GOOD, pain_ids={"P-01", "P-02"})
    assert report["problems"] == ["V-03: pain P-03 is not in the pain map"]
    report = value_model.measure(
        changed("| V-02 | P-02 |", "| V-02 | P-09 |"), pain_ids={"P-01", "P-02", "P-03"}
    )
    assert "V-02: pain P-09 is not in the pain map" in report["problems"]


def test_cli_writes_the_report_and_names_a_missing_file(tmp_path: Path) -> None:
    doc = tmp_path / "value.md"
    doc.write_text(GOOD, encoding="utf-8")
    out = tmp_path / "value-model.json"
    run = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            str(ROOT / "tools" / "value_model.py"),
            "--file",
            str(doc),
            "--json",
            str(out),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    assert json.loads(run.stdout)["ok"] is True
    assert json.loads(out.read_text(encoding="utf-8"))["totals"]["net"] == 22546.0
    missing = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            str(ROOT / "tools" / "value_model.py"),
            "--file",
            str(tmp_path / "none.md"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    assert json.loads(missing.stdout)["problems"][0].startswith("file missing")
