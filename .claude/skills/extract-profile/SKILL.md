---
name: extract-profile
description: Document-type profile for an extract (requirements.js) - one source document turned into numbered, sourced tables. Preloaded into the source processor and the extract auditor so both read one contract - the header, the six tables, the row ids, the Source cell and the gate rules.
user-invocable: false
---

# Profile: extract

An extract is one input document turned into a structured record of what it says. The
requirements writer merges the extracts of all documents, a tool counts that every row of
every extract reaches the requirements or is set aside with a reason, and an auditor reads the
document again to find what the extract missed. All three rely on the shape below.

## The shape

The extract is a markdown file the requirements writer merges with the other extracts, so it
has the same shape as the requirements document's own tables: every item is a table row with a
Source cell. Start with a header block, then the tables, in this order.

```
# Extract: <source id>

- source: <the source id the task gives — exactly the identifier every downstream citation will use>
- type: brief | rfp | transcript | meeting notes | chat | email | spreadsheet | client answers
- date: <as the document gives it>
- participants: <names and roles as the document names them>
- trust_level: high | medium | low — <one sentence why>

## Requirements
| ID | Statement | Type | Source |
| --- | --- | --- | --- |
| R-01 | <one sentence, the source's own quantifiers and figures> | functional | <locator — “quote”> |

## Decisions
| ID | Decision | Who | Source |

## Constraints
| ID | Constraint | Source |

## Roles
| ID | Role | What the source says they do | Source |

## Facts
| ID | Topic | Fact | Source |

## Open questions
| ID | Question or contradiction | Positions (who says what) | Source |
```

- **requirements** — discrete things the system must do or satisfy; type functional,
  non_functional, constraint or assumption. One sentence each, keeping the source's own
  quantifiers and figures exactly ("one doctor in each clinic", not "doctors"). If the
  document states none, leave the table with only its header — do not manufacture rows.
- **decisions** — choices the source records as already made, and who made them.
- **constraints** — technical, budget, timeline or regulatory limits.
- **roles** — every actor or stakeholder the source names, with what it says they do.
- **facts** — statements about the client's environment, volumes, current process, existing
  systems and organisation that are not requirements but that a design or a sizing needs.
- **open questions** — gaps, contradictions and ambiguities. Where the same document disagrees
  with itself, or two speakers in it disagree, record both positions with who holds them.
  Where a statement is a wish or a passing thought rather than a decision, say so in the row:
  the writer must not promote it.

## Row ids

Every row of every table opens with its id: R-01, R-02 … in Requirements, DE- in Decisions,
CO- in Constraints, RO- in Roles, F- in Facts, Q- in Open questions; two digits, from 01,
without gaps, in the order the rows appear. The requirements cite a row by the source id and
this number (call-transcript#R-04), and a script counts that every row was either carried or set
aside with a reason, so a row without an id is a row nobody can account for.

## The Source cell

Every row ends with a locator inside the document and a short verbatim quote of the words that
carry the meaning: a section or heading, a page, a question number, or — for chats, transcripts
and meeting notes — the date, the time and the speaker. The writer downstream can only cite
what you give it; a row without a locator here becomes a requirement without a locator there,
and the gate rejects an extract whose Source column has an empty cell.

## Gate rules

Run on every extract after it is written, and again after a second pass:

```gate
# the six tables, by their English names (table headers are structure, not content)
--require-heading "^##\s+Requirements\b" --require-heading "^##\s+Decisions\b"
--require-heading "^##\s+Constraints\b" --require-heading "^##\s+Roles\b"
--require-heading "^##\s+Facts\b" --require-heading "^##\s+Open questions\b"
# every row sourced; at least one row in the whole extract
--rows-have-source --min-sourced-rows 1
# row ids unique and without gaps, per prefix
--unique-ids "\b(?:R|DE|CO|RO|F|Q)-\d{2,3}\b" --sequential-ids "\b(?:R|DE|CO|RO|F|Q)-\d{2,3}\b"
# an instruction planted in a source must not travel downstream inside an extract
--forbid-file library/style/forbid/injection.txt
--forbid "\x60"
```

Beside the gate: every quote of a text source occurs in it verbatim (tools/check_quotes.py),
and the extract is written in the language of its source (--language-of, given by the script
because it names the source).
