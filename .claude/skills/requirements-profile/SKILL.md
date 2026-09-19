---
name: requirements-profile
description: Document-type profile for a requirements document (level 3, solution-design.js requirements stage). Preloaded into the requirements writer, corrector and critic so all three read one contract - sections, tables, IDs, source cells, priorities, conflict rules, critic checklist and gate rules.
user-invocable: false
---

# Profile: requirements

This is the contract for one document type. The writer, the corrector and the critic of a
requirements document all receive this file at spawn, so whatever it says binds all three at
once. Where an agent's own instructions and this profile disagree about the document, the
profile wins; the agent's instructions describe its role, this file describes the document.

## Purpose and reader

A requirements document consolidates what the client's source material establishes — briefs,
RFPs, meeting notes, transcripts, chats, emails, spreadsheets, client answers — into one
document that two readers use for different things:

- the delivery team designs and estimates from it, so every statement has to be
  checkable and every scope boundary has to be explicit;
- the client checks it against their own words, so every statement carries the place where
  the client said it, and a conclusion the analyst drew is never dressed as a client statement.

It is a consolidation, not a transcription: one need stated once, with every source that
supports it named; disagreements between sources shown, not averaged.

## Section contract

The document has exactly these parts, in this order. Headings are written in the document's
language, but each numbered heading keeps its number and each sub-heading its `N.M` — the gate
checks the numbers, a reader checks the names.

```
# Requirements: <project> — v<n>
one line: Generated <date> | Sources: <N> documents | Output language: <language>
one paragraph "About this version": how Source cells are formed (see below), what the tags
  mean, and what was reconciled since the previous version (v2+)

## Document index            table: # | File | Type
## Domain grounding          PROSE, 1–5 sentences, no bullets
## 1. Stakeholders and roles table: Role | Description | Source
## 2. Business context       bullets; every bullet ends with a Source cell
## 3. Functional requirements
### 3.1 <area> … 3.N <area>  table: ID | Requirement | Priority | Source
### 3.(N+1) Out of scope     table: Feature | Source           (the LAST subsection of 3)
## 4. Non-functional requirements   table: ID | Requirement | Category | Source
## 5. Business rules and constraints table: ID | Rule | Source
## 6. Data model (derived)   table: Entity | Key attributes | Source / notes
## 7. Integration points     table: Integration | Purpose | Priority | Source
## 8. Open questions, conflicts and assumptions
### 8.1 Conflicts            table: # | Conflict | Sources in conflict | Resolution / status
### 8.2 Gaps                 table: # | Gap | Impact | Source
### 8.3 Assumptions          table: # | Assumption | Basis | Status
## 9. Confirmed environment and technical facts   table: Topic | Fact | Source
---
*End of requirements document.*
```

Rules that make the shape worth having:

- **No front matter, no metadata block, no counts.** A block that says `fr_count: 9` above ten
  requirements is a fact about the document that nothing checks and that goes stale on the
  next edit; a reader who catches one wrong number stops trusting the requirements. The first
  line of the file is the `# Requirements:` heading.
- **Section 1 lists roles, not people.** A row is a role — sponsor, clinic manager,
  administrator, doctor, accountant, IT contractor — with what that role does with the system;
  the person who holds it is named in the Description where the sources name them. Ten rows of
  named individuals is a contact list, and a design cannot be checked against a contact list.
- **Document index** lists every input document with its type: `brief`, `rfp`, `transcript`,
  `meeting notes`, `chat`, `email`, `spreadsheet`, `client answers`. The type is what the trust
  hierarchy below keys on.
- **Domain grounding is prose.** One to five sentences that teach a reader with no context
  what is being built, for whom, and in what setting. One dense sentence is enough when it
  carries everything; do not pad. No bullets here.
- **Section 3 is grouped by business area, never by source document**: scheduling, booking,
  notifications, records, billing, reporting, access, integrations — whatever the domain has.
  Each area is one `### 3.N` subsection with three to ten rows. `FR-NNN` numbers run
  sequentially across ALL subsections and never restart. The last subsection of 3 is
  **Out of scope**: what a source explicitly excludes from this version, with the excluding
  words in the Source cell. A document with no scope boundary has no scope.
- **Every requirement is one testable sentence** in the Requirement cell: one actor, one
  behaviour, one condition. Three checkable statements in one cell are three rows. A
  requirement whose ground is in the sources — the number, the defect, the legal position, the
  fact about the site — keeps that ground in the sentence or in the Source cell; a figure
  without its reason cannot be defended, questioned or retired later.
- **Quantifiers are copied, not improved.** "one doctor per clinic", "each clinic", "any free
  slot", "at least", "no later than": the quantifier in the row is the quantifier in the source.
  Widening "one per clinic" into "every" is a meaning change, and it is the change a reviewer
  misses because the Source cell still points at the right place.
- **Section 4: every NFR has a number** or an equally checkable criterion. "Fast" and "secure"
  are not requirements. Where the client declined to fix a figure, keep the indicative value
  and tag the row `[PROVISIONAL]`; where no figure exists at all, the row is a gap in 8.2, not
  an NFR. Categories: Performance, Security, Scalability, Availability, Legal/Compliance, UX,
  Ops/Maintainability, Internationalisation, Data sovereignty, Business/Financial.
- **Section 5 holds what must always be true at runtime and what the project must live
  within**: business rules, regulatory constraints, budget, deadline, imposed technology,
  imposed integration direction. Not design decisions the team has yet to make.
- **Section 6 is derived and says so**: entities the sources actually mention with two or
  more attributes, the attributes as the sources name them, and per entity the source it came
  from. It is not a data design.
- **Section 7** names every external system, channel, identity provider, payment or messaging
  service and internal system the solution must talk to, with direction where the sources give
  it (read-only, write-back, hourly file drop).
- **Section 8 is where honesty lives.** 8.1 lists every contradiction between sources or
  within one source — including resolved ones — with the positions, who holds them, and the
  resolution or `UNRESOLVED`. 8.2 lists what no source answers and what depends on the
  answer. 8.3 lists every conclusion the writer drew that no source states, with its basis.
  "No conflicts found" is written only when none were found, and a document built from a
  meeting and a chat almost always has some.
- **Section 9** collects the confirmed facts about the client's environment that architecture
  and sizing need — existing systems, versions, volumes, hosting, network, devices, who
  operates what — with a source per row. Facts, not requirements.

## IDs, tags and priorities

- `FR-NNN`, `NFR-NNN`, `BR-NNN` — three-digit, zero-padded, sequential within their section
  (FR across all of section 3), no gaps, no duplicates, never renumbered between versions.
- `C-NNN`, `G-NNN`, `A-NNN` — conflicts, gaps, assumptions. A requirement affected by a
  conflict carries `[C-NNN]` in its Source cell; one affected by an assumption carries `[A-NNN]`.
- Tags in the ID or Requirement cell, square brackets, upper case: `[PROVISIONAL]` for a figure
  the client would not fix; `[CHANGED]`, `[NEW]`, `[REVISED]` for rows that moved since the
  previous version (v2+ only); `[C-NNN]` / `[A-NNN]` as above.
- Priority is `MUST`, `SHOULD` or `COULD`, and it traces like everything else: `MUST` when the
  source words it as required, decided or a condition of the deal; `SHOULD` when the source
  wants it but allows it to slip ("would be good", "if possible", "later if not now"); `COULD`
  when the source mentions it as a thought or a wish. A document where every row is `MUST` has
  not read its sources.

## The Source cell

Every row of every table and every bullet of section 2 ends with a source. A row without one
is not a requirement — it is a conclusion, and it moves to 8.3. The cell is built as

```
<doc-id>: <locator> — “<short verbatim quote>”
```

- `<doc-id>` is the input file's stem as listed in the document index, e.g. `03-chat`,
  `RFP_Questions` — the same identifier in every cell, never a paraphrase of the title.
- `<locator>` is what lets a reader open the document and find the sentence: a section or
  heading, a page, a question number (`Q123`), a date and time with the speaker for chats and
  transcripts (`08.09 11:20, Nastya`), a table name. A file name alone is not a locator.
- The quote is the source's own words for whatever carries the meaning — the number, the
  name, the threshold, the decisive phrase — kept short. Paraphrase in the Requirement cell,
  quote in the Source cell.
- Two sources supporting one row are two references separated by `;`. A row both documents
  support is stronger than one mentioned in passing, and only the cell shows which is which.
- When a later source changed an earlier position, the cell names both and says which won:
  `02-meeting: §2 — “not decided”; 03-chat: 08.09 11:30, Anton — “new phone: SMS code” (later,
  explicit)`.
- Where the input is a set of client answers, the reference is the answer id and the quote
  (`Q317 — “open to either a shared platform or independent solutions”`); where a requirement
  comes only from the brief and was neither confirmed nor changed by the answers, the cell says
  so (`brief: §4 (no Q&A delta)`) instead of inventing a citation.

## Reconciling sources

- **Trust hierarchy**, highest first: formal decision (signed spec, contract, approved
  decision) → written requirements document or RFP → client answers to written questions →
  transcript or meeting notes → chat or email → informal notes. A higher-trust source wins
  unless a lower-trust source is later AND explicit — then the later statement wins and 8.1
  records both.
- **Never choose silently.** Every contradiction goes to 8.1 with both positions, both sources
  and the resolution rule applied — or `UNRESOLVED` and the question that would resolve it.
  The requirement row states the position taken and carries `[C-NNN]`.
- **Scope conflict** (one source includes, another excludes): the requirement stays in the
  document, its Source cell carries `[C-NNN]`, and 8.1 says who wants it out.
- **Quantitative conflict** (two figures for one thing): the row takes the more constraining
  figure, names both in the Source cell, and 8.1 holds the conflict. Never average.
- **Gap is not conflict.** Missing from all sources → 8.2. Different in two sources → 8.1.
- **Forced choice** — the document cannot be finished without picking a value nobody gave —
  is an assumption in 8.3 with its basis, and the row carries `[A-NNN]`.
- **Wishes stay wishes.** "It would be great if", "just a thought": a `COULD` row if a
  stakeholder with authority said it, otherwise a gap in 8.2 asking whether it is wanted.

## Critic checklist

In order of severity. `CRITICAL` alone forces `revise`; three or more `MAJOR` force `revise`;
`MINOR` never does. Every finding names the row (ID) and, for a source defect, both what the
row says and what the source says.

CRITICAL
1. A row whose Source cell does not support the statement: wrong document, wrong place,
   quote that says something else, or a quantifier changed ("one per clinic" → "every").
   Open the locator; do not count citations, read them.
2. A requirement, constraint or decision that an extract clearly establishes and the document
   lost — including the ground of a requirement (the number, defect, legal fact) that the
   source gives and the row dropped.
3. A conflict between sources that the document resolved silently: one position taken, no
   `C-NNN`, nothing in 8.1.
4. A conclusion the writer drew presented as a client statement — a row with a Source cell
   pointing at something that does not say it, instead of an assumption in 8.3.
5. A mandatory section missing, or section 3 without an Out of scope subsection.

MAJOR
6. An NFR with no number and no checkable criterion, not tagged `[PROVISIONAL]`, not moved to
   8.2.
7. A row with several independently checkable statements bundled into one.
8. Every row `MUST`; or a priority the source does not support.
9. 8.2 missing an open question that an extract raised; 8.3 missing an assumption the text
   relies on; an assumption without a basis.
10. Section 3 grouped by source document rather than by business area; or a single flat table.
11. Domain grounding as bullets, or absent.

MINOR
12. ID sequence with gaps or duplicates; a tag misspelled.
13. Headings not matching the numbered contract; the closing line missing.
14. Wording the critic would merely phrase differently — not a defect at all; do not report it.

The critic writes its remarks in the language of the document. A remark in another language,
or with the document's words transliterated, is unusable by the reader who has to act on it.

## Gate rules

Deterministic, run by the script before the critic sees the draft; what the gate settles never
costs a round:

- headings `## 1.` … `## 9.` and `### 8.1`, `### 8.2`, `### 8.3` present (`--require-heading`);
- no heading with nothing under it (`--no-empty-sections`);
- every body row of a table that has a Source column has a non-empty Source cell
  (`--rows-have-source`);
- no duplicate `FR-`, `NFR-`, `BR-`, `C-`, `G-`, `A-` ids (`--unique-ids`);
- a floor on file length (`--min-length`), not on prose: the document is tables, and a
  prose floor made a table-complete draft fail its first round and grow two thousand
  characters of filler to pass the second. No ceiling the order did not name.

## Exemplar

`exemplars/requirements/skeleton.md` — the anonymised skeleton of the reference document this
profile was distilled from: an RFP-stage requirements document reconciled against several
hundred written client answers, nine sections, every row sourced to an answer id and a quote.
Read it for shape and density; the content there is placeholders. The path to the full
reference document, when one is available on this machine, is in `exemplars.local.yaml`
(not in the repository).

## Level

3 — a saved Dynamic Workflow (`solution-design.js`, stage `requirements`): one extractor per
input document in parallel, then writer → fact-checker → gate → critic in rounds up to the
configured limit, with a plateau stop.

## Output language

The language of the source material, unless the order says otherwise. The people whose words
the document consolidates must be able to check it against what they said. Headings translate;
IDs, tags and the `# Requirements:` marker do not.
