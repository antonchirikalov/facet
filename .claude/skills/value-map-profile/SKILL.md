---
name: value-map-profile
description: Document-type profile for the value map (level 3, the value stage of proposal.js, quoted by the proposal). Preloaded into the value modeler and the value critic. What the client gains in the units their business already counts - pillars guarded by SLAs, a sourced baseline, value lines as formulas a ruler recomputes, run cost per month, net value and the break-even build budget, the miss case, a verdict, the assumption map and what the pilot measures. Never a project price, a rate or hours.
user-invocable: false
---

# Profile: value map

The value map answers the question an owner and a finance reader decide by: is this worth
building, and how will we know it paid off? It is written after the requirements and the pain
map, before the proposal, and the proposal quotes it. Where an agent's own instructions and this
profile disagree about the document, the profile wins.

It carries no project price, no rate and no hours of our work: those depend on a team and a
contract this pipeline does not know. What bridges the gap without a price is the build budget
that would pay back in 12 and in 24 months.

## Reader

The client's sponsor and their finance. Finance asks one question of every number: where does
it come from? A map that cannot answer it for every line is redone from the start.

## The method

The method follows the business value material of the Anthropic CCAR-P course, restated here.

1. Translation first. The pain in the client's words, who feels it and how often, what "fixed"
   looks like, the limits, and what doing nothing costs. The pain becomes a baseline number in a
   unit the business already counts (minutes per case, days to a decision, errors a month).
   Without a baseline nothing can show the solution helped.
2. Four pillars, with an SLA under them:
   - efficiency: the same work with fewer resources;
   - transformation: work that was impossible or unaffordable before;
   - productivity: more output per person;
   - cost: the full economics, including the cost of being wrong.

   A solution usually serves two. Every value claim names its pillar and the SLA that guards
   it. An SLA has five parts: a metric defined precisely, a threshold, a segment (per segment,
   not only overall), a method (how, how often, on what sample) and a consequence of a miss. A
   value claim without a measured promise is marketing.
3. The value calculation, in four steps: the baseline "as now" in the business's unit, from the
   process owner's data; the forecast in the same unit, including the time of the people who
   check part of the output; minus the monthly run cost; and how the result moves when an
   assumption is wrong. "Can be built, but is not worth it" is a legitimate verdict.
4. Soft hours are not money. Time saved that removes no cost is written off by finance, by
   half to two thirds in the course's experience.
5. A baseline without client data: measure the system, not the people (created, taken and closed
   timestamps over a quarter), and cross-check top-down from full-time staff positions. Two
   estimates within 1.5 times of each other make a baseline. Best of all is a shadow month: the
   solution runs, nobody sees its answers, and they are logged next to the human's work.
6. Every assumption has a value, a source, a confidence, how it will be confirmed, an owner at
   the client and its impact if wrong. No economic effect is committed before they are confirmed.
7. The miss case is part of the calculation: below the accuracy SLA the gain shrinks or
   vanishes. A value calculation without it is not finished.

### The worked example

The course's insurance claims case; its numbers are the course's illustrative figures, not data
of any client. It is written in the formula notation below.

- As now: 4,000 claims/month × 45 min × $40/h = $120,000/month
- With the solution, where 30% of the claims still go to a person:
  (4,000 claims/month × 70% × 5 min + 4,000 claims/month × 30% × 20 min) × $40/h = $25,300/month
- Gain: $120,000/month − $25,300/month = $94,700/month, not $120,000: the forecast as full
  automation is the course's first trap
- Run cost: $200/month + $1,500/month = $1,700/month (tokens by the distribution of request
  sizes, plus infrastructure)
- Net: $94,700/month − $1,700/month = $93,000/month
- Break-even build budget: $93,000/month × 12 month = $1,116,000 in 12 months,
  $93,000/month × 24 month = $2,232,000 in 24 months

The course goes on to a build cost and a payback period; this document stops at the break-even
budget, because the build cost is not ours to state.

## Sources

The accepted requirements (their NFRs carry the SLAs), the pain map (every value line answers one
of its pains), the client voice sheet, the extracts, the order and, when there is one, the design
(section 5 of an ai-solution design gives tokens per request). Public data (a salary survey, a
benchmark, a price list) is used when the client gave nothing, and carries its URL and date.

Client data first, then public data, then our assumptions. A client figure that the material
does not hold is asked of the client in the missing input file, never invented; until it comes
back, the line uses an assumption with a star and a confirmation plan.

## Section contract

Sections are numbered "## N.", in this order. Column order in every table is fixed: the ruler
reads columns by position, so a header may be translated, never moved.

```
# Value map: <product>

## 1. Scenario and boundary
one or two paragraphs: what the solution does in the client's process, and what it does not;
every value line stays inside this boundary

## 2. Pillars and SLAs
table: ID | Pillar | Metric | Threshold | Segment | Method | Consequence | Source
- ID: SLA-01, SLA-02 …
- Pillar: efficiency, transformation, productivity or cost
- Source: the requirement id (NFR-…) it comes from, or "our proposal"

## 3. Baseline
table: Measure | Unit the business counts | Value now | Source | How it was obtained | Confidence
- How it was obtained: a client figure, system timestamps, a top-down estimate from staff
  positions, or a public benchmark; with two independent estimates, both in the form
  "<method>: <number> <unit>; <method>: <number> <unit>"
- Confidence: high, medium or low

## 4. Value lines
table: ID | Pain | Pillar | Now (formula) | With the solution (formula) | Monthly gain (formula) | Hard or soft | Condition and write-off | SLA
- ID: V-01, V-02 …
- Pain: the pain map id (P-…) the line answers
- Now and With the solution: formulas in the business's unit and then in money; With the
  solution includes the time of the people who review part of the output
- Monthly gain: Now minus With the solution, as a formula
- Hard or soft: hard (a cost that disappears) or soft (time freed)
- Condition and write-off: empty for a hard line; for a soft line, the condition under which the
  time becomes money (fewer hires, overtime removed, capacity sold), then the counted amount as a
  formula: "<condition>; <gain> × (1 − 60%) = <counted>"
- SLA: the SLA id of section 2 the line depends on
a pain the line cannot value in money gets a row whose Monthly gain says "not valued" and why

## 5. Run cost per month
table: Item | Driver (formula) | Monthly cost | Source
items: model tokens; infrastructure; the time of the people who review output; evaluation
sampling and maintenance; never the build cost

## 6. Net value and the break-even build budget
table: Key | Formula
keys, in this order and spelled exactly so in any language: hard, soft, run, net, budget-12, budget-24
- hard: the sum of the hard lines' monthly gains
- soft: the sum of the soft lines' counted amounts
- run: the sum of section 5
- net: hard + soft − run
- budget-12 and budget-24: net × 12 month and net × 24 month

## 7. Sensitivity and the miss case
table: Case | What changes | Net (formula) | Budget 12 (formula) | Budget 24 (formula)
at least three cases: the volume halved; the review share doubled; the accuracy SLA missed, with
its effect on the work stated (misroutes add rework minutes per case)

## 8. Verdict
one paragraph: worth building, worth building if narrowed (to what), or not worth building now,
with the number that decides it

## 9. Assumption map
table: ID | Assumption | Value (range) | Source | Confidence | How confirmed | Owner at the client | Impact if wrong
- ID: A-01, A-02 …
- Value (range): "20 min (15–25)"
- How confirmed: phase 0, a shadow month, a log extract …
- Owner at the client: a role, never a person's name
closes with one line: no economic effect is committed before these are confirmed

## 10. What the pilot measures
table: Measure | Value line | Before | After, by the same definition | Control | Who measures
one row per value line: the measure before, the same measure after counted the same way, the
control that lets the comparison be rechecked, and the client role that measures it
```

## Formula notation

Every formula cell is "<expression> = <result>", and the ruler (tools/value_model.py) evaluates
the expression and compares it with the result within 1%. The result is what the ruler
reproduces, never a number typed from memory.

- Numbers: 4,000 or 4 000; 0.6 or 0,6 when the document's language writes decimals so; k and M
  for thousands and millions written onto the number (6k tokens, $3/1M tokens).
- A number that is ours carries a star directly after it (21* day/month) and has its row in
  the assumption map. Every other number in a value line is a value of section 3, section 5 or
  section 9, or the result of another formula; a share is matched only by a share. An SLA
  threshold of section 2 is what the client wants, not what will happen: a line that expects
  it to be met stars the number and gives the forecast its row in section 9, with its range and
  basis. A sensitivity case may also halve, double and take the end of a range.
- Units: min, h, day, week, month, year and %, or their usual abbreviations in the document's
  language; "/" before a unit makes a rate ($40/h, 4,000 claims/month). Minutes and hours
  convert, and so do months and years; nothing else does: days to months is a starred factor
  written in the formula.
- Money: one currency per document, its symbol before the number or its code after it.
- Words after a number are labels and do not count (4,000 claims/month).
- Operators: ×, ÷, +, −, and parentheses; "/" before a number divides.
- The result carries its unit, and the units agree: a monthly amount is written /month.

## Rules

- Every value line names a pain map id, a pillar and an SLA id.
- A pain whose cost is "not stated" either gets a baseline assumption with a confirmation plan,
  or a row in section 4 marked "not valued" with the reason.
- A transformation line (coverage from X% to Y%) is money only through a sourced loss or revenue
  figure; otherwise it is stated in its unit and marked "not valued".
- The loaded cost of an hour comes from the client, or from a public salary source for the
  client's country and role times a loaded factor, marked as an assumption.
- A soft line becomes money only under its stated condition, and is counted after the finance
  write-off: 60% by default, the client's figure when the material has one.
- A value line covers the solution's scope and no more: when the pilot covers one channel or one
  site, the line counts that channel or site.
- A public benchmark from another country or setting says why it fits this client.
- No project price, rate or hours of our work anywhere, and no total the ruler does not
  reproduce.
- Roles, never people's names. No bold, no backticks, no sentence about the document itself.

## Exemplar

None yet. This is a new document type; take the shape from the section contract above and the
worked example. After the first value map an author accepts, its anonymised skeleton goes to
exemplars/value-map/ and this note names it.

## Gate rules

```gate
# headings by number: the names translate with the document's language
--require-heading "^##\s+1\." --require-heading "^##\s+2\." --require-heading "^##\s+3\."
--require-heading "^##\s+4\." --require-heading "^##\s+5\." --require-heading "^##\s+6\."
--require-heading "^##\s+7\." --require-heading "^##\s+8\." --require-heading "^##\s+9\."
--require-heading "^##\s+10\."
--no-empty-sections --rows-have-source
--unique-ids "\b(?:V|A|SLA)-\d{2}\b" --sequential-ids "\b(?:V|A|SLA)-\d{2}\b"
--forbid-file library/style/forbid/no-bold.txt
--forbid "\x60"
```

- headings ## 1. to ## 10. present, none empty;
- every row of a table with a Source column has a source (sections 2, 3, 5 and 9);
- V-, A- and SLA- ids unique and without gaps;
- no bold, no backticks;
- every formula, total, budget and sensitivity case reproduced within 1%, every number of a value
  line sourced or starred, every value line with its pain, pillar and SLA, every soft line with
  its condition and write-off, at least three sensitivity cases, one currency, and no project
  price, rate or hours of our work (tools/value_model.py --file <doc> --pains <pain map>; an
  assumption range wider than --max-ratio, 3 by default, is a warning for the critic).

## Critic checklist

HIGH (any one forces revise)
1. A forecast as full automation when the design or the requirements send part of the work to a
   person.
2. A baseline with no source, or a source that does not hold the number.
3. A total or a line the ruler does not reproduce.
4. A soft line counted as cash with no condition or no write-off.
5. Value stated in technical metrics (requests, latency, uptime) instead of the business's unit.
6. No miss case in section 7.
7. A project price, a rate or hours of our work.

MEDIUM (three force revise)
8. A value line with no pillar or no SLA.
9. A pain of the pain map with a stated cost and no value line, and no "not valued" reason.
10. A public benchmark from another country or setting applied without saying why it fits (one
    live run applied a manual-to-electronic saving where submissions were already electronic).
11. A range in the assumption map wider than three times with no plan to narrow it.
12. A line whose scope differs from the solution's scope (one live run valued every prescription
    while the pilot covered home delivery only).

LOW
13. Wording the critic would merely phrase differently: not a defect, do not report it.

The first question of every line is where its number comes from.

## Level

Level 3: the value stage of proposal.js, in rounds under a critic, with the ruler as part of the
gate.

## Output language

The language of the client's material. Pillar names, the hard and soft labels and the keys of
section 6 stay as written above in any language: they are read by the ruler.
