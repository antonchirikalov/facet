# Why this exemplar

Type: `requirements`. Skeleton: `skeleton.md` next to this file. The full document is a
Confluence page, its path is in `exemplars.local.yaml` (kept out of the repository: client data).

## What the document is

Version-two requirements for an enterprise AI platform for a financial company, gathered at the
RFP stage: ten input documents (a chat summary, four briefs on scenarios, the RFP, a transcript
of the kick-off meeting, an authorship review) and a file of some four hundred and fifty written
client answers to the vendor's questions. Version two is reconciled with the answers: every row
references an answer number and a short quote, changed rows are tagged `[CHANGED]`, figures the
client has not committed to are tagged `[PROVISIONAL]`.

## Why it was chosen over another

- **Traceability is checked, not declared.** Every row of every table has a Source cell with a
  locator and a quote. Where there is no confirmation, it says `brief (no Q&A delta)` rather than
  inventing a reference. This is exactly facet's rule "no source, no requirement", carried all
  the way into table form.
- **Nine sections cover everything a design needs.** Not only FR/NFR: roles, business context,
  the scope boundary (out of scope), business rules, a derived data model, integration points,
  conflicts with a status, gaps, assumptions with a status, confirmed facts about the
  environment. Our document for the vet-clinic demo of 18 September 2026 had, of all this, only
  FR/NFR/CON/ASM/OQ as prose and not a single table.
- **Conflicts, gaps and assumptions are kept apart and carry a status.** A resolved conflict
  stays in the table, marked RESOLVED, with the rule that resolved it; an assumption can be
  WITHDRAWN. The history of decisions is visible from the document, not from correspondence.
- **Priorities are traced.** MUST and SHOULD are set not by the writer's taste but by the
  client's words in the Source cell.
- **It was made by our own previous-generation pipeline** (spectra) from the
  `requirements-template` template, so the form is reachable by a model, not only by a person.
  The facet profile is that template plus refract's strictness: no YAML meta block with invented
  counters, a corrector between the writer and the critic, a locator and a quote in every
  reference instead of a bare file name.

## What the exemplar lacks and the profile adds

- In the exemplar a reference is the number of a client answer. For inputs without numbered
  answers (chats, meetings) the profile requires the date, the time and the speaker; otherwise
  the locator cannot find the phrase.
- The exemplar has no check of quantifiers. A demo run turned "one doctor in every clinic" into
  "every doctor" while keeping a correct reference; the profile calls this a critical defect and
  gives the corrector an explicit check.
- In the exemplar the critic's remarks are not visible. In facet they are written to
  `UNRESOLVED.md` in the language of the document.
