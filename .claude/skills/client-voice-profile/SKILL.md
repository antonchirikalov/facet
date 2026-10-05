---
name: client-voice-profile
description: Document-type profile for the client voice sheet (level 3, solution-design.js requirements stage, read by proposal-review.js). Preloaded into the client-voice agent. What the client said, in their words, ranked by what matters to them; each phrase translated into a checkable commitment with its weight; their vocabulary and the words not to replace it with; who wants what; a proposed proposal structure in their order; and what they never mentioned.
user-invocable: false
---

# Profile: client voice

This is the contract for one document type: the sheet that keeps the client's own voice in
front of everyone who writes for them. The requirements writer takes the weight of each
requirement from it, the client editor and the proposal author take the vocabulary and the
order, the coverage mapper and the proposal reviewer check against it.

It is an internal document. The client never reads it; the people writing to the client do.

## Why it exists

Three things were lost on one live run, and each cost a rework:

- the weight of what was said. "Losing the connection is rare, keep today's list" became a full
  offline store with synchronisation, because the requirement arrived without "rare";
- the client's words for their own trade. The drafts said "receptionist" and "appointment"
  where the client said "front desk" and "visit", and the proposal read like it was about someone
  else's business;
- the order of what mattered. The call spent most of its time on booking a visit in three taps
  and on the price quote; the first draft of the proposal opened with the architecture.

## What counts as the client's words

Only what the client said or wrote: the call transcript, their emails, their own documents.
Our notes, digests, summaries and pre-call write-ups are an interpretation — the task names
them when the inventory marked them — and nothing from them is quoted as the client's. They may
point you to a place in the transcript; the quote comes from the transcript.

Every quote is copied character for character from the source: an ellipsis marks a cut, square
brackets mark an inserted word. The gate checks every attributed quote against the extracts and
the text sources. People are named by role (owner, structural engineer, office manager), never
by name.

## Section contract

Headings are in the document's language; the gate checks the numbers.

```
# Client voice: <client>
one line: Sources: <the client's own sources, by name> | Our notes not quoted: <names or "none">

## 1. What matters to them, in order
numbered list, most important first; each item: the topic in their words, why it ranks here
(minutes of the call spent on it, how often it came back, who raised it, how strongly), one or
two quotes with role and timestamp or section

## 2. Their words and what they commit us to
table: # | In their words | Who, where | What it commits us to | Weight
- In their words: the verbatim quote
- Who, where: role; timestamp, section or file
- What it commits us to: the checkable form — a number, a behaviour, a limit ("fast" becomes
  "the quote is in the patient's inbox before they leave the front desk"); marked "our reading"
  when the translation is ours rather than theirs
- Weight: MUST / SHOULD / COULD, plus every frequency, volume or consequence they gave
  ("rare", "every visit", "nine visits out of ten", "loses the patient"). No frequency stated — say so.

## 3. Their vocabulary
table: Their term | What they mean by it | Do not replace with
the right column lists only words a draft would use for the same thing ("appointment" for
their "visit"); never a word that is a legitimate name of something else in their trade, and
never a generic word ("area", "case", "solution") that a sentence may need for its own
meaning: a gate flags every listed word, and a false alarm costs a round
the words they use for their people, their work, their documents and their money; the right
column holds the words our drafts tend to substitute

## 4. Who wants what
table: Role | What they want | What worries them | In their words

## 5. How to structure the proposal
the sections in the order that answers section 1: open with their problem in their words, then
what they spent the most time on; what they mentioned in passing goes late or to "Later"; one
line per section on why it stands there

## 6. What they did not say
what a project of this kind usually needs and nobody mentioned — volumes, integrations,
approvals, who pays — each with what depends on it. These are questions for discovery, not
assumptions.
```

## Rules

- Rank by evidence, not by what seems important to an engineer. Time on the call, repetition
  and who raised it are evidence; a topic we find interesting is not.
- Keep every weight word. "Rare", "sometimes", "every single job" are the most expensive words
  in the transcript: they decide whether a mechanism is built.
- One row per commitment. Two quotes that say the same thing go in one row; two commitments in
  one quote are two rows.
- Nothing invented: no weight, frequency or role the sources do not carry. What you infer is
  marked "our reading".
- No bold, no backticks, no sentence about the sheet itself.

## Gate rules

```gate
--require-heading "^##\s+1\." --require-heading "^##\s+2\." --require-heading "^##\s+3\."
--require-heading "^##\s+4\." --require-heading "^##\s+5\." --require-heading "^##\s+6\."
--no-empty-sections
--forbid "\x60"
```

- headings ## 1. … ## 6. present (--require-heading);
- no heading with nothing under it (--no-empty-sections);
- no backtick;
- every attributed quote found in the extracts or the text sources (tools/check_quotes.py).

## Output language

The language of the client's sources. Headings translate; the table column names may stay as
above when the sources are English.
