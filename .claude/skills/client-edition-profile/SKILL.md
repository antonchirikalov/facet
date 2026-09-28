---
name: client-edition-profile
description: Document-type profile for the client edition of a requirements document or a solution design (level 3, solution-design.js client stage). Preloaded into the client editor. States what the traceable internal version keeps and the client edition drops, what must survive the cut, renumbering with an id map, the client's words as verbatim attributed quotes, and the gate rules.
user-invocable: false
---

# Profile: client edition

This is the contract for one derived document type. The pipeline produces a traceable internal
version of the requirements and of the design: every row cites its source, every guess is
tagged, conflicts and assumptions are numbered. That version is the record and stays as it is.
The client edition is written FROM it, for the client, and is never edited back into it.

Where the editor's own instructions and this profile disagree about the document, the profile
wins.

## Purpose and reader

The reader is the client's owner, engineer or product person. They read about their product,
not about how the document was made. They must be able to:

- recognise their own words where a requirement rests on them;
- see what is required, how important it is, and what is still open;
- sign off or correct it without asking us what a tag or a column means.

A Vista run published the traceable versions first; they were 65 000 and 62 000 characters, full
of source locators, tags and notes about our own materials, and they were rewritten by hand into
16 000 and 26 000 characters the client could read. This profile is that rewrite.

## What goes

- The document index, the "about this version" note, the generated/sources/output-language
  line, every note on how sources were cited or weighed.
- The Source column and every source locator (file stems, section codes, timestamps).
- Tags in brackets: [PROVISIONAL], [INFERRED], [C-NNN], [A-NNN] and the like. What a tag said is
  kept in words where the reader needs it: a provisional figure becomes "preliminary, to be
  confirmed", an assumption the row relies on is simply in the assumptions list.
- Every mention of our internal materials: pre-call summaries, call digests, our notes,
  paraphrases of them, "our reading". The client did not write them and does not know them.
- Every mention of the process: drafts, rounds, critics, checks, extracts, versions of the
  pipeline.
- Repetition: a requirement stated twice in the traceable version is stated once.

## What must survive

- Every requirement, business rule, constraint, quality target, open question and assumption.
  Cutting a row is merging it with its duplicate, never dropping its content. A requirement
  missing from the client edition is a requirement the client never confirms.
- Its weight: MUST / SHOULD / COULD as the traceable version has it, and every stated frequency,
  volume or consequence ("rare", "every job", "loses the sale"). The weight is what keeps a
  design proportionate; an edition that drops it hands the next reader a flat list.
- Every number exactly as the traceable version has it.
- The figure placeholders ![caption](figures/<slug>.png), with the same slugs; a caption may be
  shortened.
- For a design: every decision, the timeline section if the traceable version has one, the
  risks, the assumptions to confirm. Decision ids may stay if the design text refers to them.

## The client's words

Where a requirement rests on something the client said or wrote, the row carries a short quote
in a column named "In the client's words" (in the document's language), attributed to a role, not
a name: “you type in 48 feet” (owner). The quote is copied character for character from the
traceable version's Source cell, which copied it from the source; an ellipsis marks a cut, square
brackets mark an inserted word. A quote that cannot be found in the sources is removed, not
repaired — the gate checks every attributed quote against the extracts. Rows resting on our own
materials have an empty quote cell: our interpretation is never presented as the client's words.

## Numbering

After merging, ids are renumbered so that each prefix runs 1, 2, 3 in document order with no
gaps: a skipped number reads as a removed requirement. The editor of the requirements writes the
map from the traceable ids to the client ids as a JSON object {"FR-047": "FR-008", ...}, one
entry per traceable id; a merged id maps to the id that absorbed it. The editor of the design
edition applies that map to every requirement reference, so the two client documents agree with
each other.

## Shape

Requirements:

```
# <Product>: Requirements for the First Version
one line: <working name> · Version <n> · <date> · Based on <the client's own sources, by name>

## Context              2–4 paragraphs: the business, who the product serves, what changes for them
## 1. Who uses it       table: Role | What they do with the product
## 2. Functional requirements   one line on what MUST / SHOULD / COULD mean; then one subsection per area,
                        table: ID | Requirement | Priority | In the client's words
## 3. Quality requirements      table: ID | Requirement | Target | Priority
## 4. Rules the product must keep   business rules and constraints, table: ID | Rule | In the client's words
## 5. Decisions for discovery   the open conflicts and questions, each with what depends on the answer
## 6. Assumptions       table: # | Assumption | What changes if it is wrong
```

Design:

```
# <Product>: Solution Design
one line: <working name> · Version <n> · <date> · Built on the Requirements for the First Version, v<n>

## 1. The solution in one page
## 2. How it is built                modules and data, with the figures
## 3. Key design decisions           one subsection per decision: what, why, which requirements (client ids)
## 4 … N-1                           the remaining sections of the traceable design, same order, retitled
                                     in the client's terms (security, technology and hosting, timeline, risks)
## N. Assumptions to confirm
```

Headings are in the document's language. The section numbers above are the shape; the gate
checks only that no section is empty.

## Style

The client reads plain prose and tables. No bold in the body, no backticks, no marketing words,
no sentence about the document itself ("this document describes", "below we present"). Short
sentences, the client's vocabulary for their own trade. The edition is shorter than the
traceable version, typically a third to a half; it adds no fact the traceable version does not
have.

## Gate rules

Deterministic, run by the script on each client edition:

- no heading with nothing under it (--no-empty-sections);
- no process or internal-material trace (--forbid-file library/style/forbid/client-meta.txt);
- no bold, no backtick;
- ids unique and sequential per prefix (--unique-ids, --sequential-ids);
- every attributed quote found in the extracts (tools/check_quotes.py).

## Output language

The language of the traceable version. Headings translate; ids do not.
