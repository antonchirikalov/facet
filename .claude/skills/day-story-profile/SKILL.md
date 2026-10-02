---
name: day-story-profile
description: Document-type profile for the day story (level 3, solution-design.js lens stage). Preloaded into the story writer and the lens critic. The main user's day with the product, step by step in the client's words, each step traced to requirement ids, the screens a figure must show, the secondary scenarios, every role, and the gate rules.
user-invocable: false
---

# Profile: day story

The day story shows the product through the eyes of the person who will use it most, in the
words the client uses for their own work. It is what makes a proposal read as being about the
client's business: the reader recognises their own day before they read a word about the
system. It becomes section 3 of the proposal ("A day with the product"); the proposal writer
copies it nearly as it is, without the ids.

## Sources

The client voice sheet (who uses the product, their vocabulary, what matters), the pain map,
the requirements (what the product does) and the design (how a step works, where it needs a
signal, what is decided). The story invents no feature: every step is something a requirement
asks for.

## Section contract

```
# A day with <product>

## 1. <the main scenario, named by its start and end in the client's terms, e.g. "A visit, from the front desk to the quote">
numbered steps, 5 to 7; a step is one thing the person does, not one tap:
  N. <what the person does, in one short sentence, present tense> (FR-..., FR-...)
     <one to three sentences: what they see, what the product does, what changes for them>
after every two or three steps, a screen line:
  Screen: <slug> — <what the screen shows, with every number and word the text relies on>
what happens when things go wrong: no signal, a missing value, a case the product does not
cover; one short paragraph, traced to its ids

## 2. <each secondary scenario that the requirements carry, e.g. "The package for the head office">
the same form, shorter: 2 to 5 steps

## 3. Everyone else
table: Who | What they do with the product | Ids

## 4. How the product reaches them
how the users get it, start using it and are trained, from the requirements and the design;
traced to ids; "decided in discovery" where the sources leave it open
```

## Rules

- The person and their situation come from the voice sheet's ranking: the main scenario is
  the one the client spent the most time on.
- Present tense, the person as the subject ("The receptionist books the visit"), the client's
  terms for people, work, documents and money. No system-centric sentences ("The system
  allows the user to").
- Every step cites the ids it rests on; the gate checks that they exist. A step with no
  requirement behind it is not written.
- The ids are required here. This is an internal document: they are how the lens critic and
  the gate check every step against the requirements. The proposal writer drops them; a
  critic never reports them as a defect, whatever the voice sheet says about the client's
  reader.
- Every MUST requirement of the main area appears in some step, or the story says why not.
- A number or a word on a screen line is exactly what the text says; the screen line is the
  brief a figure is drawn from.
- What is open stays open: "decided in discovery", pointing to the open question.
- No bold, no backticks, no sentence about the document itself.

## Gate rules

- headings ## 1. to ## 4. present, none empty;
- every cited id declared in the requirements or the design (tools/trace_ids.py);
- no substitute word from the voice sheet's vocabulary (tools/vocab.py);
- no generated-text phrases (en-slop, ru-slop lists).

## Critic checklist

HIGH
1. A step with no requirement behind it, or a feature the requirements do not have.
2. A MUST requirement of the main area missing from every step without a reason.
3. The main scenario is not the one the voice sheet ranks first.
4. A screen line whose numbers or words disagree with the steps around it.
MEDIUM
5. A system-centric step instead of the person doing something.
6. Our word where the client has their own (the gate catches the listed ones; the critic
   catches the rest).
7. A decided-in-discovery point presented as settled.
LOW
8. Wording the critic would merely phrase differently: not a defect, do not report it.

## Output language

The language of the client's sources.
