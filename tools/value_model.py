#!/usr/bin/env python3
"""Recompute a value map: every formula, every total, every break-even budget.

A value map is read by the client's finance, and finance asks of every number where it comes
from. On the one hand-made value model of six live runs the range was twelvefold and no line
carried a cost; nothing had recomputed it. So the value-map profile writes every line as a
formula, "<expression> = <result>", and this tool evaluates the expression and compares it
with the result within 1%. The writer copies totals from this report, never from memory.

What it reads, by section number and by column position (headers may be translated):

- section 2, Pillars and SLAs: the SLA ids;
- section 3, Baseline: the values, and two estimates of one measure within 1.5 times;
- section 4, Value lines: the formulas, gain = now - with, the pain id, the pillar, the SLA id,
  hard or soft, a soft line's condition and its counted amount after the write-off, and where
  every number comes from: a star and a row in section 9, or a value of section 3, 5 or 9, or
  the result of another formula; an SLA threshold of section 2 is a target and sources nothing;
- section 5, Run cost: each driver against its monthly cost;
- section 6, Net value: the keys hard, soft, run, net, budget-12 and budget-24 against what
  sections 4 and 5 add up to;
- section 7, Sensitivity: each case's formulas, its net built from traced numbers (50%, 2 and
  the ends of an assumption's range), its budgets against its net, at least three cases;
- section 9, Assumption map: a range wider than --max-ratio is a warning, for the critic to judge
  against its plan to narrow it.

And anywhere outside code: a project price, a rate or hours of our work, by the patterns of
library/style/forbid/project-price.txt.

It measures and never decides: exit code 0, the verdict travels in the JSON.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import gate
import toollog

ROOT = Path(__file__).resolve().parent.parent
PRICE_FILE = ROOT / "library" / "style" / "forbid" / "project-price.txt"

TOLERANCE = 0.01
BASELINE_RATIO = 1.5
MIN_CASES = 3
PILLARS = {"efficiency", "transformation", "productivity", "cost"}
SECTION6_KEYS = ("hard", "soft", "run", "net", "budget-12", "budget-24")

HEADING = re.compile(r"^##\s+(\d+)\.", re.MULTILINE)
VALUE_ID = re.compile(r"^V-\d{2}\b")
PAIN_ID = re.compile(r"\bP-\d{2}\b")
SLA_ID = re.compile(r"\bSLA-\d{2}\b")
RANGE = re.compile(r"(\d[\d,.]*)\s*(?:–|—|-|\bto\b|\.\.)\s*(\d[\d,.]*)")

# A number as written: grouped thousands (4,000 or 4 000) or plain, with a decimal part.
GROUPED = re.compile(r"(\d{1,3}(?:[,   ]\d{3})+)(?![\d])(?:[.,](\d+))?")
PLAIN = re.compile(r"(\d+)(?:[.,](\d+))?")
WORD = re.compile(r"[^\W\d_][\w\-]*")
CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP", "₽": "RUB"}
CURRENCY_CODES = {
    "usd": "USD",
    "eur": "EUR",
    "gbp": "GBP",
    "rub": "RUB",
    "руб": "RUB",
    "chf": "CHF",
    "pln": "PLN",
    "aed": "AED",
    "sar": "SAR",
}
# Unit words, English and the Russian abbreviations a Russian value map writes. Each maps to a
# scale and a base: minutes and hours convert, months and years convert, nothing else does.
UNITS: dict[str, tuple[float, str]] = {
    "s": (1 / 3600, "h"),
    "sec": (1 / 3600, "h"),
    "min": (1 / 60, "h"),
    "mins": (1 / 60, "h"),
    "minute": (1 / 60, "h"),
    "minutes": (1 / 60, "h"),
    "h": (1.0, "h"),
    "hr": (1.0, "h"),
    "hrs": (1.0, "h"),
    "hour": (1.0, "h"),
    "hours": (1.0, "h"),
    "day": (1.0, "day"),
    "days": (1.0, "day"),
    "week": (1.0, "week"),
    "weeks": (1.0, "week"),
    "wk": (1.0, "week"),
    "month": (1.0, "month"),
    "months": (1.0, "month"),
    "mo": (1.0, "month"),
    "year": (12.0, "month"),
    "years": (12.0, "month"),
    "yr": (12.0, "month"),
    "сек": (1 / 3600, "h"),
    "мин": (1 / 60, "h"),
    "минут": (1 / 60, "h"),
    "ч": (1.0, "h"),
    "час": (1.0, "h"),
    "часа": (1.0, "h"),
    "часов": (1.0, "h"),
    "день": (1.0, "day"),
    "дня": (1.0, "day"),
    "дней": (1.0, "day"),
    "дн": (1.0, "day"),
    "нед": (1.0, "week"),
    "неделю": (1.0, "week"),
    "недель": (1.0, "week"),
    "мес": (1.0, "month"),
    "месяц": (1.0, "month"),
    "месяца": (1.0, "month"),
    "месяцев": (1.0, "month"),
    "год": (12.0, "month"),
    "года": (12.0, "month"),
    "лет": (12.0, "month"),
}


class FormulaError(ValueError):
    """A formula the tool cannot read; the place and the reason go to the problems."""


@dataclass
class Quantity:
    """A number with its dimensions: money, h, day, week, month, each to a power."""

    value: float
    dims: dict[str, int] = field(default_factory=dict)

    def times(self, other: Quantity, power: int = 1) -> Quantity:
        dims = dict(self.dims)
        for base, p in other.dims.items():
            dims[base] = dims.get(base, 0) + p * power
        dims = {b: p for b, p in dims.items() if p}
        value = self.value * other.value if power == 1 else self.value / other.value
        return Quantity(value, dims)


@dataclass
class Number:
    """One number of an expression as written: its quantity, its written magnitude, its star."""

    quantity: Quantity
    written: float
    star: bool
    currency: str | None
    percent: bool = False


@dataclass
class Formula:
    """An evaluated formula cell."""

    computed: Quantity
    stated: Quantity
    numbers: list[Number]
    currencies: set[str]


def unit_text(dims: dict[str, int]) -> str:
    """dims as a reader writes them: money/month, h, money."""
    if not dims:
        return "no unit"
    top = [b if p == 1 else f"{b}^{p}" for b, p in sorted(dims.items()) if p > 0]
    bottom = [b if p == -1 else f"{b}^{-p}" for b, p in sorted(dims.items()) if p < 0]
    text = "·".join(top) or "1"
    return text + ("/" + "/".join(bottom) if bottom else "")


def to_float(digits: str, decimals: str | None) -> float:
    whole = re.sub(r"\D", "", digits)
    return float(f"{whole}.{decimals}") if decimals else float(whole)


class Scanner:
    """Tokens of one expression: numbers with their units, operators and parentheses."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0

    def skip_space(self) -> None:
        while self.pos < len(self.text) and (
            self.text[self.pos].isspace() or self.text[self.pos] == ":"
        ):
            self.pos += 1

    def peek(self) -> str:
        return self.text[self.pos] if self.pos < len(self.text) else ""

    def tokens(self) -> list[Any]:
        out: list[Any] = []
        while True:
            self.skip_space()
            ch = self.peek()
            if not ch:
                return out
            if ch in "([":
                out.append("(")
                self.pos += 1
            elif ch in ")]":
                out.append(")")
                self.pos += 1
            elif ch == "×":
                out.append("*")
                self.pos += 1
            elif ch in "÷/":
                out.append("/")
                self.pos += 1
            elif ch == "+":
                out.append("+")
                self.pos += 1
            elif ch in "−-–":
                out.append("-")
                self.pos += 1
            elif ch in CURRENCY_SYMBOLS or ch.isdigit():
                out.append(self.number())
            elif WORD.match(self.text, self.pos):
                # a label before a number ("calls: 6,000") carries no value
                m = WORD.match(self.text, self.pos)
                assert m is not None
                self.pos = m.end()
            else:
                raise FormulaError(f"unexpected {ch!r}")

    def number(self) -> Number:
        currency: str | None = None
        ch = self.peek()
        if ch in CURRENCY_SYMBOLS:
            currency = CURRENCY_SYMBOLS[ch]
            self.pos += 1
            self.skip_space()
        m = GROUPED.match(self.text, self.pos) or PLAIN.match(self.text, self.pos)
        if m is None:
            raise FormulaError("a currency sign with no number")
        written = to_float(m.group(1), m.group(2))
        self.pos = m.end()
        nxt = self.peek()
        after = self.text[self.pos + 1] if self.pos + 1 < len(self.text) else ""
        if nxt and nxt in "kK" and not after.isalpha():
            written *= 1_000
            self.pos += 1
        elif nxt == "M" and not after.isalpha():
            written *= 1_000_000
            self.pos += 1
        star = False
        percent = False
        quantity = Quantity(written)
        for _ in range(2):
            if self.peek() == "*":
                star = True
                self.pos += 1
            elif self.peek() == "%":
                quantity = Quantity(quantity.value / 100)
                percent = True
                self.pos += 1
        currency = self.tail(quantity, currency)
        if currency:
            quantity.dims["money"] = quantity.dims.get("money", 0) + 1
        return Number(quantity, written, star, currency, percent)

    def tail(self, quantity: Quantity, currency: str | None) -> str | None:
        """Units written after a number: words, "/word" rates, a currency sign or code."""
        while True:
            start = self.pos
            self.skip_space()
            per = False
            if self.peek() == "/":
                self.pos += 1
                self.skip_space()
                per = True
            ch = self.peek()
            if ch in CURRENCY_SYMBOLS:
                if per or currency:
                    raise FormulaError(f"currency sign {ch} in a unit")
                currency = CURRENCY_SYMBOLS[ch]
                self.pos += 1
                continue
            m = WORD.match(self.text, self.pos)
            if m is None:
                self.pos = start
                return currency
            word = m.group(0)
            low = word.lower()
            self.pos = m.end()
            if low in CURRENCY_CODES and not per:
                currency = CURRENCY_CODES[low]
            elif low in UNITS:
                scale, base = UNITS[low]
                unit = Quantity(scale, {base: 1})
                merged = quantity.times(unit, -1 if per else 1)
                quantity.value, quantity.dims = merged.value, merged.dims
            # any other word is a label: "claims", "visit", "tokens"


class Parser:
    """Recursive descent over the tokens: sums of products, parentheses, unary minus."""

    def __init__(self, tokens: list[Any]) -> None:
        self.tokens = tokens
        self.i = 0

    def peek(self) -> Any:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def take(self) -> Any:
        tok = self.peek()
        self.i += 1
        return tok

    def parse(self) -> Quantity:
        if not self.tokens:
            raise FormulaError("no expression")
        q = self.expr()
        if self.peek() is not None:
            raise FormulaError(f"unexpected {self.peek()!r}")
        return q

    def expr(self) -> Quantity:
        q = self.term()
        while self.peek() in ("+", "-"):
            op = self.take()
            r = self.term()
            if q.dims != r.dims:
                raise FormulaError(f"adds {unit_text(q.dims)} and {unit_text(r.dims)}")
            q = Quantity(q.value + r.value if op == "+" else q.value - r.value, dict(q.dims))
        return q

    def term(self) -> Quantity:
        q = self.factor()
        while True:
            tok = self.peek()
            if tok in ("*", "/"):
                self.take()
                r = self.factor()
                if tok == "/" and r.value == 0:
                    raise FormulaError("division by zero")
                q = q.times(r, 1 if tok == "*" else -1)
            elif tok == "(" or isinstance(tok, Number):
                raise FormulaError("two values with no operator between them")
            else:
                return q

    def factor(self) -> Quantity:
        tok = self.take()
        if tok == "-":
            q = self.factor()
            return Quantity(-q.value, dict(q.dims))
        if tok == "(":
            q = self.expr()
            if self.take() != ")":
                raise FormulaError("an unclosed parenthesis")
            return q
        if isinstance(tok, Number):
            return Quantity(tok.quantity.value, dict(tok.quantity.dims))
        raise FormulaError(f"expected a value, found {tok!r}")


def numbers_of(text: str) -> list[Number]:
    return [t for t in Scanner(text).tokens() if isinstance(t, Number)]


def evaluate(text: str) -> tuple[Quantity, list[Number]]:
    tokens = Scanner(text).tokens()
    return Parser(tokens).parse(), [t for t in tokens if isinstance(t, Number)]


def stated_of(text: str) -> Quantity:
    """The first number of a result, with its units: "$120,000/month"."""
    found = numbers_of(text)
    if not found:
        raise FormulaError("no number in the result")
    return found[0].quantity


def formula(cell: str) -> Formula:
    """Evaluate "<expression> = <result>"; FormulaError when it cannot be read."""
    left, sep, right = cell.rpartition("=")
    if not sep:
        raise FormulaError("no '='")
    computed, numbers = evaluate(left)
    result_numbers = numbers_of(right)
    if not result_numbers:
        raise FormulaError("no number in the result")
    currencies = {n.currency for n in numbers + result_numbers if n.currency}
    return Formula(computed, result_numbers[0].quantity, numbers, currencies)


def close(a: float, b: float) -> bool:
    return abs(a - b) <= TOLERANCE * max(abs(a), abs(b)) + 1e-9


def money(q: Quantity) -> str:
    return f"{q.value:,.2f} {unit_text(q.dims)}"


def mismatch(place: str, computed: Quantity, stated: Quantity) -> str | None:
    """A problem when the stated result is not the computed one, in value or in units."""
    if computed.dims != stated.dims:
        return (
            f"{place}: units differ: computed {unit_text(computed.dims)}, "
            f"stated {unit_text(stated.dims)}"
        )
    if not close(computed.value, stated.value):
        return f"{place}: stated {money(stated)}, computed {money(computed)}"
    return None


@dataclass
class Table:
    rows: list[list[str]]


def sections_of(text: str) -> dict[int, str]:
    marks = list(HEADING.finditer(text))
    out: dict[int, str] = {}
    for k, m in enumerate(marks):
        end = marks[k + 1].start() if k + 1 < len(marks) else len(text)
        out.setdefault(int(m.group(1)), text[m.end() : end])
    return out


def table_of(section: str) -> list[list[str]]:
    """Body rows of the first table in a section: header and rule dropped."""
    rows: list[list[str]] = []
    started = False
    for line in section.splitlines():
        if gate.TABLE_LINE.match(line):
            if gate.TABLE_RULE.match(line.strip()):
                started = True
                continue
            if started:
                rows.append(gate.split_row(line))
        elif started:
            break
    return rows


def cell(row: list[str], i: int) -> str:
    return row[i] if i < len(row) else ""


def written_numbers(text: str) -> set[float]:
    """Every magnitude written in a cell, ranges included; unreadable text gives what it can."""
    found: set[float] = set()
    for m in re.finditer(r"\d[\d,.   ]*", text):
        chunk = m.group(0).strip()
        g = GROUPED.match(chunk) or PLAIN.match(chunk)
        if g is None:
            continue
        value = to_float(g.group(1), g.group(2))
        rest = chunk[g.end() :]
        found.add(value)
        if text[m.end() : m.end() + 1] in ("k", "K"):
            found.add(value * 1_000)
        if text[m.end() : m.end() + 1] == "M":
            found.add(value * 1_000_000)
        if rest:
            found |= written_numbers(rest)
    return found


def sources_of(text: str, main_only: bool = False) -> tuple[set[float], set[float]]:
    """The magnitudes a cell can source, split into plain numbers and shares.

    A number is a share when "%" follows it; a range in parentheses takes the kind of the value
    before it, so the ends of "60% (50-67)" are shares and those of "10 min (5-15)" are not.
    With main_only, the values alone and not the ends of their ranges: an assumption's value.
    """
    plain: set[float] = set()
    shares: set[float] = set()
    last_share = False
    for m in re.finditer(r"\d[\d,.   ]*", text):
        chunk = m.group(0).rstrip()
        g = GROUPED.match(chunk) or PLAIN.match(chunk)
        if g is None:
            continue
        inside = text[: m.start()].count("(") > text[: m.start()].count(")")
        if inside and main_only:
            continue
        values = {to_float(g.group(1), g.group(2))}
        tail = text[m.start() + g.end() :]
        if tail[:1] in ("k", "K"):
            values |= {v * 1_000 for v in values}
        elif tail[:1] == "M":
            values |= {v * 1_000_000 for v in values}
        share = tail.lstrip(" *").startswith("%")
        if inside:
            share = share or last_share
        else:
            last_share = share
        (shares if share else plain).update(values)
    return plain, shares


@dataclass
class Report:
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    formulas: int = 0
    currencies: set[str] = field(default_factory=set)
    results: set[float] = field(default_factory=set)

    def check(self, place: str, text: str) -> Formula | None:
        """Evaluate one formula cell and record its mismatch; None when it cannot be read."""
        try:
            f = formula(text)
        except FormulaError as exc:
            self.problems.append(f"{place}: cannot read the formula ({exc}): {text}")
            return None
        self.formulas += 1
        self.currencies |= f.currencies
        stated_numbers = numbers_of(text.rpartition("=")[2])
        if stated_numbers:
            self.results.add(stated_numbers[0].written)
        problem = mismatch(place, f.computed, f.stated)
        if problem:
            self.problems.append(problem)
        return f


def soft_formula(text: str) -> str:
    """The formula part of a soft line's condition cell: the last ';' part holding '='."""
    parts = [p for p in text.split(";") if "=" in p]
    return parts[-1].strip() if parts else ""


def measure(text: str, max_ratio: float = 3.0, pain_ids: set[str] | None = None) -> dict[str, Any]:
    """The whole report for one value map."""
    r = Report()
    sections = sections_of(text)
    for n in (2, 3, 4, 5, 6, 7, 9):
        if n not in sections:
            r.problems.append(f"section {n} missing")

    s2 = table_of(sections.get(2, ""))
    s3 = table_of(sections.get(3, ""))
    s4 = table_of(sections.get(4, ""))
    s5 = table_of(sections.get(5, ""))
    s6 = table_of(sections.get(6, ""))
    s7 = table_of(sections.get(7, ""))
    s9 = table_of(sections.get(9, ""))
    for n, rows in ((3, s3), (4, s4), (5, s5), (6, s6), (7, s7), (9, s9)):
        if n in sections and not rows:
            r.problems.append(f"section {n} has no table rows")

    sla_ids = {m.group(0) for row in s2 for m in [SLA_ID.match(cell(row, 0))] if m}
    for row in s2:
        if cell(row, 1).strip().lower() not in PILLARS:
            r.problems.append(
                f"{cell(row, 0) or 'section 2'}: pillar {cell(row, 1)!r} is none of {sorted(PILLARS)}"
            )

    # Where a number of a value line may come from, plain numbers and shares apart: 70% is not
    # sourced by EUR 70/h. A star needs the assumption's value, a star in a sensitivity case may
    # also take an end of its range.
    assumed: set[float] = set()
    for row in s9:
        assumed |= written_numbers(cell(row, 2))
    plain: set[float] = {1.0, 100.0}
    shares: set[float] = {100.0}
    for row in s9:
        p9, s9_ = sources_of(cell(row, 2), main_only=True)
        plain |= p9
        shares |= s9_
    for row in s3:
        p3, s3_ = sources_of(cell(row, 2))
        plain |= p3
        shares |= s3_
    for row in s5:
        for c in (cell(row, 1), cell(row, 2)):
            p5, s5_ = sources_of(c)
            plain |= p5
            shares |= s5_
    # A sensitivity case may also halve and double, and take the end of an assumption's range.
    case_plain = plain | {2.0}
    case_shares = shares | {50.0}
    for row in s9:
        p9, s9_ = sources_of(cell(row, 2))
        case_plain |= p9
        case_shares |= s9_
    # An SLA threshold is a target, not a source: a line that forecasts the target is met stars
    # it and gives the forecast its own row in section 9.
    thresholds: set[float] = set()
    for row in s2:
        thresholds |= written_numbers(cell(row, 3))

    # Section 3: two estimates of one measure agree within 1.5 times.
    for row in s3:
        estimates: list[float] = []
        for part in cell(row, 4).split(";"):
            if ":" in part:
                nums = numbers_of_safe(part.split(":", 1)[1])
                if nums:
                    estimates.append(nums[0].quantity.value)
        if len(estimates) >= 2:
            low, high = min(estimates), max(estimates)
            if low <= 0 or high / low > BASELINE_RATIO:
                r.problems.append(
                    f"baseline {cell(row, 0)!r}: two estimates differ more than "
                    f"{BASELINE_RATIO} times ({low:g} and {high:g})"
                )

    # Section 4: the value lines.
    hard = Quantity(0.0)
    soft = Quantity(0.0)
    lines = 0
    traced: list[tuple[str, list[Number]]] = []
    first_money: dict[str, int] | None = None
    for row in s4:
        vid = cell(row, 0)
        if not VALUE_ID.match(vid):
            continue
        lines += 1
        pains = PAIN_ID.findall(cell(row, 1))
        if not pains:
            r.problems.append(f"{vid}: no pain id")
        elif pain_ids is not None:
            for p in pains:
                if p not in pain_ids:
                    r.problems.append(f"{vid}: pain {p} is not in the pain map")
        if cell(row, 2).strip().lower() not in PILLARS:
            r.problems.append(f"{vid}: no pillar (found {cell(row, 2)!r})")
        slas = SLA_ID.findall(cell(row, 8))
        if not slas:
            r.problems.append(f"{vid}: no SLA id")
        for s in slas:
            if s not in sla_ids:
                r.problems.append(f"{vid}: {s} is not declared in section 2")
        kind = cell(row, 6).strip().lower()
        if kind not in ("hard", "soft"):
            r.problems.append(f"{vid}: hard or soft, found {cell(row, 6)!r}")

        now = r.check(f"{vid} now", cell(row, 3)) if "=" in cell(row, 3) else None
        with_ = r.check(f"{vid} with the solution", cell(row, 4)) if "=" in cell(row, 4) else None
        gain_cell = cell(row, 5)
        if "=" not in gain_cell and not any(n.currency for n in numbers_of_safe(gain_cell)):
            continue  # "not valued", with its reason, which may hold a number of its own
        gain = r.check(f"{vid} monthly gain", gain_cell) if "=" in gain_cell else None
        for f, name in ((now, "now"), (with_, "with the solution"), (gain, "monthly gain")):
            if f is not None:
                traced.append((f"{vid} {name}", f.numbers))
        if gain is None:
            if "=" not in gain_cell:
                r.problems.append(f"{vid}: the monthly gain is not a formula: {gain_cell}")
            continue
        if now is not None and with_ is not None:
            expected = Quantity(now.computed.value - with_.computed.value, now.computed.dims)
            if now.computed.dims == with_.computed.dims:
                problem = mismatch(f"{vid} gain against now minus with", expected, gain.stated)
                if problem:
                    r.problems.append(problem)
        elif now is None or with_ is None:
            r.problems.append(f"{vid}: a valued line needs now and with the solution as formulas")
        if first_money is None:
            first_money = gain.stated.dims
            hard = Quantity(0.0, dict(first_money))
            soft = Quantity(0.0, dict(first_money))
        if gain.stated.dims != first_money:
            r.problems.append(
                f"{vid}: gain in {unit_text(gain.stated.dims)}, other lines in {unit_text(first_money)}"
            )
            continue
        if kind == "hard":
            hard = Quantity(hard.value + gain.stated.value, hard.dims)
        elif kind == "soft":
            condition = cell(row, 7)
            part = soft_formula(condition)
            before = condition.split(part)[0] if part else condition
            if not part:
                r.problems.append(f"{vid}: a soft line with no counted amount after the write-off")
                continue
            if not WORD.search(before):
                r.problems.append(f"{vid}: a soft line with no condition for becoming money")
            counted = r.check(f"{vid} counted after the write-off", part)
            if counted is None:
                continue
            if counted.stated.dims != gain.stated.dims:
                r.problems.append(
                    f"{vid}: counted amount in {unit_text(counted.stated.dims)}, gain in {unit_text(gain.stated.dims)}"
                )
                continue
            if counted.stated.value >= gain.stated.value:
                r.problems.append(f"{vid}: a soft line counted in full, with no write-off")
            soft = Quantity(soft.value + counted.stated.value, soft.dims)
    if s4 and lines == 0:
        r.problems.append("section 4: no value line with a V- id")

    # Section 5: run cost.
    run: Quantity | None = None
    for row in s5:
        item = cell(row, 0) or "run cost"
        driver = r.check(f"run cost {item!r} driver", cell(row, 1)) if "=" in cell(row, 1) else None
        try:
            cost = stated_of(cell(row, 2))
        except FormulaError:
            r.problems.append(f"run cost {item!r}: no monthly cost")
            continue
        if driver is not None:
            problem = mismatch(f"run cost {item!r} monthly cost", driver.computed, cost)
            if problem:
                r.problems.append(problem)
        r.results |= written_numbers(cell(row, 2))
        if run is None:
            run = Quantity(0.0, dict(cost.dims))
        if cost.dims != run.dims:
            r.problems.append(
                f"run cost {item!r}: in {unit_text(cost.dims)}, other items in {unit_text(run.dims)}"
            )
            continue
        run = Quantity(run.value + cost.value, run.dims)

    # Section 6: totals against what sections 4 and 5 add up to.
    totals: dict[str, Quantity] = {}
    if first_money is not None:
        totals["hard"], totals["soft"] = hard, soft
    if run is not None:
        totals["run"] = run
    if first_money is not None and run is not None and run.dims == hard.dims:
        net = Quantity(hard.value + soft.value - run.value, dict(hard.dims))
        totals["net"] = net
        year = Quantity(1.0, {"month": 1})
        totals["budget-12"] = Quantity(net.value * 12, net.times(year).dims)
        totals["budget-24"] = Quantity(net.value * 24, net.times(year).dims)
    stated6: dict[str, Quantity] = {}
    for row in s6:
        key = cell(row, 0).strip().lower()
        if key not in SECTION6_KEYS:
            continue
        text6 = cell(row, 1)
        if "=" in text6:
            f6 = r.check(f"section 6 {key}", text6)
            if f6 is None:
                continue
            stated6[key] = f6.stated
        else:
            try:
                stated6[key] = stated_of(text6)
            except FormulaError:
                r.problems.append(f"section 6 {key}: no number")
                continue
            r.results |= written_numbers(text6)
    for key in SECTION6_KEYS:
        if key not in stated6:
            r.problems.append(f"section 6: key {key} missing")
        elif key in totals:
            problem = mismatch(
                f"section 6 {key} against sections 4 and 5", totals[key], stated6[key]
            )
            if problem:
                r.problems.append(problem)

    # Section 7: each case's budgets follow from its net.
    cases = 0
    for row in s7:
        name = cell(row, 0) or "case"
        if not any("=" in cell(row, i) for i in (2, 3, 4)):
            continue
        cases += 1
        net7 = r.check(f"case {name!r} net", cell(row, 2))
        if net7 is not None:
            traced.append((f"case {name!r} net", net7.numbers))
        b12 = r.check(f"case {name!r} budget 12", cell(row, 3))
        b24 = r.check(f"case {name!r} budget 24", cell(row, 4))
        if net7 is None:
            continue
        for months, b in ((12, b12), (24, b24)):
            if b is None:
                continue
            expected = Quantity(
                net7.stated.value * months, net7.stated.times(Quantity(1.0, {"month": 1})).dims
            )
            problem = mismatch(f"case {name!r} budget {months} against its net", expected, b.stated)
            if problem:
                r.problems.append(problem)
    if 7 in sections and cases < MIN_CASES:
        r.problems.append(
            f"section 7: {cases} sensitivity cases, at least {MIN_CASES} (with the miss case)"
        )

    # Where each number of a value line comes from.
    def sources_for(case: bool, percent: bool) -> set[float]:
        if case:
            return case_shares if percent else case_plain
        return shares if percent else plain

    unsourced = 0
    for place, numbers in traced:
        for num in numbers:
            if num.star:
                if not any(close(num.written, a) for a in assumed):
                    unsourced += 1
                    r.problems.append(f"{place}: {num.written:g}* is not in the assumption map")
            elif not any(
                close(num.written, s)
                for s in sources_for(place.startswith("case "), num.percent) | r.results
            ):
                unsourced += 1
                if any(close(num.written, t) for t in thresholds):
                    r.problems.append(
                        f"{place}: {num.written:g} is an SLA threshold, a target and not a forecast; "
                        "star it and give it a row in section 9"
                    )
                else:
                    r.problems.append(f"{place}: {num.written:g} has no source and no star")

    # Section 9: ranges wider than the ratio, for the critic to weigh against its plan.
    for row in s9:
        for m in RANGE.finditer(cell(row, 2)):
            low = to_float(*_parts(m.group(1)))
            high = to_float(*_parts(m.group(2)))
            if low <= 0 or high / low > max_ratio:
                r.warnings.append(
                    f"{cell(row, 0)}: range {m.group(0)} is wider than {max_ratio:g} times"
                )

    if len(r.currencies) > 1:
        r.problems.append(f"more than one currency: {sorted(r.currencies)}")

    patterns, missing = gate.patterns_of(PRICE_FILE)
    r.problems.extend(missing)
    prose = gate.outside_code(text)
    for pattern in patterns:
        found = re.findall(pattern, prose, flags=re.IGNORECASE)
        if found:
            sample = ", ".join(sorted({str(f) for f in found})[:3])
            r.problems.append(f"a project price, a rate or hours of our work: {sample}")

    return {
        "ok": not r.problems,
        "problems": r.problems,
        "warnings": r.warnings,
        "measures": {
            "value_lines": lines,
            "formulas": r.formulas,
            "sensitivity_cases": cases,
            "unsourced_numbers": unsourced,
            "currency": sorted(r.currencies),
        },
        "totals": {k: round(v.value, 2) for k, v in totals.items()},
    }


def _parts(chunk: str) -> tuple[str, str | None]:
    g = GROUPED.match(chunk) or PLAIN.match(chunk)
    if g is None:
        return "0", None
    return g.group(1), g.group(2)


def numbers_of_safe(text: str) -> list[Number]:
    try:
        return numbers_of(text)
    except FormulaError:
        return []


def pain_ids_of(text: str) -> set[str]:
    ids: set[str] = set()
    for line in text.splitlines():
        if gate.TABLE_LINE.match(line):
            m = PAIN_ID.match(cell(gate.split_row(line), 0))
            if m:
                ids.add(m.group(0))
    return ids


def main() -> int:
    p = argparse.ArgumentParser(description="Recompute a value map: formulas, totals, budgets.")
    p.add_argument("--file", type=Path, required=True, help="the value map")
    p.add_argument("--max-ratio", type=float, default=3.0, help="widest assumption range, high/low")
    p.add_argument("--pains", type=Path, help="the pain map, to check every pain id exists")
    p.add_argument("--json", type=Path, help="also write the report here")
    toollog.add_argument(p)
    args = p.parse_args()

    target = gate.resolve_path(args.file)
    if not target.is_file():
        report: dict[str, Any] = {
            "ok": False,
            "problems": [f"file missing: {target.as_posix()}"],
            "warnings": [],
            "measures": {},
            "totals": {},
        }
    else:
        pain_ids = None
        if args.pains is not None:
            pains = gate.resolve_path(args.pains)
            pain_ids = pain_ids_of(pains.read_text(encoding="utf-8")) if pains.is_file() else set()
        report = measure(target.read_text(encoding="utf-8"), args.max_ratio, pain_ids)
    toollog.append(args.log, "value_model", report, args.log_note, release=args.log_release)
    out = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json is not None:
        gate.resolve_path(args.json).write_text(out + "\n", encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
