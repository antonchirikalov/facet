# The requirements profile: where the contract came from and what was added

Date: 2026-09-19. Steps 3 and 4 of the plan (`SPEC.md` §10) for the `requirements` type.

## The occasion

The demo run of 18 September (a fictional chain of veterinary clinics, five documents) produced a
document of 86 items in prose with references in square brackets. A comparison with the reference
document — an RFP-stage requirements document, checked against several hundred written answers
from the client — showed the gap was not in traceability (we had that) but in form and
completeness: the reference has nine sections and tables with the columns ID / requirement /
priority / source, while ours had FR/NFR/CON/ASM/OQ as a list, with no roles, no scope boundary,
no data model, no integrations, no statuses on conflicts.

## Where the contract came from

The reference document was made by our own previous-generation pipeline, spectra, from the
template `.github/skills/requirements-template/SKILL.md`: nine sections, the id scheme
`FR-/NFR-/BR-/C-/G-/A-`, conflict rules, a fifteen-item critic checklist with severities. In the
move to refract the contract was deliberately cut down to "heading, FR-n, Open questions", and the
structural checks were moved into the type's regex gates. Both schools turned out to be half
right: spectra gave the form, refract the rigour about facts (a corrector between the writer and
the critic, "no source — no requirement", a ban on a YAML metadata block with invented counters).

The facet profile (`.claude/skills/requirements-profile/SKILL.md`) is the spectra template plus
refract's rigour plus three things that were in neither:

- **a locator and a quote in every reference**, not just the file name: date, time and speaker
  for chats and meetings, the answer number for Q&A, the section or page for documents;
- **quantifiers are copied, not improved** — a critical defect in the checklist and an explicit
  check for the corrector: the demo run turned "one doctor in every clinic" into "every doctor"
  with a correct reference, and three agents did not see it;
- **the language of the critic's remarks is the language of the document**: in the demo the
  critic wrote in English with transliterated Russian quotes, and `UNRESOLVED.md` could not be
  shown to the client.

## What the gate does

Three new rules in `tools/gate.py`, all mechanical and independent of the document's language:
`--require-heading` by section numbers (`## 1.` … `## 9.`, `### 8.1`–`8.3`),
`--rows-have-source` (in a table with a `Source` column, every row fills it in; the gate also accepts the Russian column name),
`--unique-ids`. The `solution-design.js` script passes them to the requirements loop through
`gateFlags`. The gate rejects the old demo document on its headings; the reference skeleton passes
all the rules.

## The reference

`exemplars/requirements/skeleton.md` — an anonymised skeleton: the headings, one placeholder row
per table, notes on "what is mandatory here and why". `why.md` — why exactly this document was
chosen. The link to the full document is in `exemplars.local.yaml` under `.gitignore` (SPEC R8:
client data does not get into the repository).

## What was not done

The `solution-design` profile remains a skeleton; `gap-analysis` has not been started. The
extractor got the fields "roles" and "facts about the environment", but its `extract@v1` schema
does not require them — they will become mandatory when the writer shows that without them it
loses sections 1 and 9.
