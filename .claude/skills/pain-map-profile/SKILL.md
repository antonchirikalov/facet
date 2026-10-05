---
name: pain-map-profile
description: Document-type profile for the pain map (level 3, the last step of requirements.js; solution-design.js lens stage). Preloaded into the pain mapper and the lens critic. The client's main pains in their words, what each costs them, how the proposed solution removes it with requirement and decision ids, how it will show, the worries a proposal must answer, and the gate rules.
user-invocable: false
---

# Profile: pain map

An internal document that sits between the requirements (and the design, when there is one)
and the proposal. It answers
one question before anything is written for the client: does the solution remove what actually
hurts them? A proposal built without it opens with the architecture; one built on it opens with
the client's problem in the client's words, and puts the mechanism they worry about most in a
section of its own.

The client never reads it; the proposal writer does, and so does the person who decides whether
the design is ready to be proposed.

## Sources

The client voice sheet (its ranking in section 1 and its commitments in section 2), the
extracts, the requirements and, when there is one, the design. Without a design the map is
written from the requirements alone; the proposal pipeline reads it as its spine. A pain is something the client said hurts or costs
them; our own notes may point to a place in the transcript but are never quoted as the client.

## Section contract

```
# Pain map: <product>

## 1. Pains, most important first
table: ID | The pain in their words | Who feels it | What it costs them | How the solution removes it | Ids | How it will show
- ID: P-01, P-02 … in rank order; the proposal cites every pain by this id
- The pain in their words: a verbatim quote, attributed to a role
- What it costs them: what they said it costs, or "not stated"; never invented
- How the solution removes it: one or two sentences in the client's terms
- Ids: the requirement ids (FR-, NFR-, BR-) and design decision ids (D-) that carry it
- How it will show: the moment of the day story or the result where the client sees it gone

## 2. What they worry about
table: ID | The worry in their words | Who | Why it matters to them | Where the proposal must answer it
- ID: WR-01, WR-02 …
worries are fears about the change, not requests: responsibility, control, cost of being
wrong, how the tool will be adopted, who owns what

## 3. The mechanism they care about most
one paragraph: the single piece of the solution the client's trust depends on (a calculation,
a rule, a control they keep), why, and which pains and worries hang on it

## 4. Pains the solution does not remove
table: ID | The pain in their words | Who feels it | What would answer it
every pain of the voice sheet with no answer in the requirements or the design, numbered on
from section 1 (P- ids run through sections 1 and 4 without a gap); one line saying every pain
is answered when none is left
```

## Rules

- Rank by the voice sheet's evidence, not by what is interesting to build.
- Every quote is verbatim from the sources; the gate checks it.
- Every pain in section 1 cites at least one id that exists in the requirements or the design;
  the gate checks that every cited id exists. A pain answered by nothing goes to section 4,
  never to section 1 with a vague answer.
- Use the client's terms (voice sheet section 3), never the substitutes.
- The ids are required here. This is an internal document: they are how the lens critic and
  the gate check every step against the requirements. The proposal writer drops them; a
  critic never reports them as a defect, whatever the voice sheet says about the client's
  reader.
- No bold, no backticks, no sentence about the document itself.

## Gate rules

```gate
--require-heading "^##\s+1\." --require-heading "^##\s+2\." --require-heading "^##\s+3\." --require-heading "^##\s+4\."
--no-empty-sections
--unique-ids "\b(?:P|WR)-\d{2}\b" --sequential-ids "\b(?:P|WR)-\d{2}\b"
--forbid "\x60"
```

- headings ## 1. to ## 4. present; no empty section except section 4 when every pain is
  answered (it then says so in one line);
- P- and WR- ids unique and without gaps (--unique-ids, --sequential-ids);
- every attributed quote found in the sources (tools/check_quotes.py);
- every cited id declared in the requirements, or in the design when there is one
  (tools/trace_ids.py);
- no substitute word from the voice sheet's vocabulary (tools/vocab.py).

## Critic checklist

HIGH
1. A pain the voice sheet ranks in its top three missing from section 1 or section 4.
2. A "how the solution removes it" that the cited requirements and decisions do not support.
3. A worry from the sources that section 2 leaves out, or a section 2 row whose "where the
   proposal must answer it" names nothing concrete.
4. A quote used outside the sense it had where it was said.
MEDIUM
5. A cost stated that the sources do not state.
6. A pain that is our idea of a pain, not the client's.
7. Section 3 naming something the client never showed concern about.
LOW
8. Wording the critic would merely phrase differently: not a defect, do not report it.

## Output language

The language of the client's sources.
