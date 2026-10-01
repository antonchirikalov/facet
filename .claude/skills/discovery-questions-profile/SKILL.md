---
name: discovery-questions-profile
description: Document-type profile for a client discovery questions document (level 3, solution-design.js discovery stage). Preloaded into the architecture probe and the curating critic so both read one contract - sections, question format, categories, traceability to requirement ids, what blocks an estimate, curation rules and gate rules.
user-invocable: false
---

# Profile: discovery questions

This is the contract for one document type. The probe that drafts the questions and the critic
that curates them both receive this file at spawn, so whatever it says binds both. Where an
agent's own instructions and this profile disagree about the document, the profile wins.

## Purpose and reader

The document is what a delivery team puts in front of a client before a discovery call, or
sends by email after one. Its reader is the client's business and technical people. Two things
follow:

- every question must prove that we read their material — it names a gap, a number or a
  contradiction that is actually in it. A question that could be asked of any project in the
  industry tells the client we did not read;
- the reader must be able to answer without us in the room, so every question is one question,
  in their words, with no jargon they did not use themselves.

It is a short document. Twelve sharp questions beat forty, and the ones that block an estimate
are marked so a call that runs short still covers them.

## Section contract

Numbered headings; the gate checks the numbers, a reader checks the names. Headings are in the
document's language.

```
# Discovery questions: <project> — <date>
one line: Based on <requirements document and its version> | Sources: <N> | Output language: <language>

## 1. What we read      table: # | Document | Type | What it establishes | How firm it is
## 2. Domain research   what was looked up, what came back, and which questions it changed
## 3. Questions
### 3.1 … 3.N           one subsection per category that has questions; Q-NN, ids, blocking marks
## 4. What happens with the answers   two to five lines: what each group of answers unblocks
---
*End of discovery questions.*
```

- **Section 1** characterises each source in one line: what kind of document it is, what it
  actually establishes, and how firm it is — a signed specification, a client-authored draft, a
  form filled in a hurry, a transcript of one person's opinion. The client recognises their own
  documents here, and the column about firmness is what justifies asking again about something
  they already "answered".
- **Section 2** names the searches that were run and what came back: standards, norms,
  manufacturer data, regulator names, typical figures for the trade. Then one line per finding
  that changed a question. A search that changed nothing is not listed. If no research was
  needed, the section says so in one line — it is not padded.
- **Section 3** is the document. One subsection per category, only the categories that have
  questions, in this order: scope and product boundaries; architecture and integration; data
  and ownership; non-functional requirements; security and compliance; team and governance;
  business context and priorities; migration and rollout; commercial and process.
- **Section 4** is two to five lines, not a summary of section 3: what the answers unblock —
  the estimate, the architecture, the contract, the plan.

## Question format

```
**Q-07.** * When a clinic loses its connection, must the app keep taking bookings and sync
later, or is a cached read of today's schedule enough? [G-004, NFR-002]
> Decision impact: full offline sync is a different architecture and a different estimate.
```

- **Q-NN**, numbered sequentially across the whole document, never restarting per category.
- **The asterisk** marks a question that blocks the estimate or the architecture. A call that
  runs short covers the asterisks. Do not mark more than a third of the questions; if
  everything blocks, nothing does.
- **The bracketed ids** name what in the requirements the question comes from: a requirement
  (FR-012), a gap (G-004), a conflict (C-002), an assumption (A-001), or a section. Every
  question carries at least one. A question with no id is a question about nothing in the
  material, and it is cut.
- **Decision impact** is one line and optional: add it only where the consequence is not obvious
  to a technical reader. Name the concrete consequence — a different architecture, a different
  team, a number that cannot be given. No abstract nouns (understanding, clarity, alignment).
- **One question per Q-NN.** Two question marks in one item is two items.
- No stock openers ("Could you elaborate", "It would be helpful", "We would like to understand").
  Ask the question.
- No backticks anywhere in the document; ids, product names and values are plain text.

## What is cut

- Anything the material plainly answers. The curator checks the requirements document itself,
  not the draft's claim about it.
- Anything that could be asked of any project in the industry.
- Duplicates, and two questions that would get one answer.
- Questions whose answer would not change a decision — interesting is not the bar.
- Questions that ask the client to design the solution for us.

## Where a contradiction becomes a question

A conflict the requirements record in 8.1 is the strongest question in the document, because
the client's own people disagree and only they can settle it. Ask it with both positions named
and neither one endorsed: "the form lists BIM and IoT; the scope document has neither — which
is the real near-term need?" A conflict asked as a leading question wastes it.

The same for an assumption in 8.3: the assumption is what we will build against if nobody
answers, so the question names it and says so.

## Gate rules

Deterministic, run by the script:

- headings `## 1.` … `## 4.` present (`--require-heading`);
- no heading with nothing under it (`--no-empty-sections`);
- no backtick character anywhere (`--forbid`).

## Level

3 — a stage of the saved workflow `solution-design.js`. It runs from documents in one launch
(`stages: ["requirements", "discovery"]`: extraction, the requirements loop, then the probe and
the curator), after a design (`["design"]`, on by default), or on a requirements document that
is already on disk (`["discovery"]`).

## Output language

The language of the requirements document, which is the language of the client's material,
unless the order says otherwise. These questions are read by the client.
