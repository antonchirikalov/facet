---
name: proposal-profile
description: Document-type profile for a client proposal (level 3, proposal-review.js). Preloaded into the coverage mapper, the proposal reviewer and the proposal editor so all three read one contract - reader, sections, voice, the client's words, preliminary notes, figures of three kinds, ideas for later, the reviewer checklist and the gate rules.
user-invocable: false
---

# Profile: client proposal

This is the contract for one document type: the proposal a client reads to decide whether to
start with us. It is written from the accepted requirements and design, but it is a different
document with a different reader. Where an agent's own instructions and this profile disagree
about the document, the profile wins; the agent's instructions describe its role, this file
describes the document.

One proposal took sixteen full revisions after the first draft. Almost every revision
answered a rule written below: an addressed reader, a bold lead-in, a quote nobody could place,
a word used in two senses, an empty table cell, a "preliminary" lost inside a paragraph, a
promise that read as a commitment, a figure whose numbers did not match the text, and one
client request after another that the draft had simply not covered. The profile exists so the
first draft already obeys them.

## Reader

The client's owner, their engineer and their partners. They are not technical (on one call
the owner said a line about the mobile framework meant nothing to them). They read to learn three
things: that we understood them, what they get and when, and what is still open. Technology
appears once, in one line addressed to their IT advisers.

## Sections

Numbered "## N." in this order; a document may merge or drop a section only when its material
is absent from the sources, never to shorten.

1. Overview: the client's situation in their terms, what one use of the product gives each
   party, the product as the client's own, the proposed start, and the preliminary note.
2. What was said: a table, the client's verbatim words on the left, what the product does about
   them on the right.
3. A day with the product: the main scenario step by step with its screens, the secondary
   scenarios, every role in one table, how the product reaches its users (distribution,
   onboarding, training).
4. The core mechanism the client worries about most (for Acme Clinics, the price quote), with
   a worked example and who controls it.
5. How it is built: the parts on the device, the backend service by service, the standard
   cloud services, where it runs, backup and environments, one technology line.
6. Plan and team: stages with weeks, milestones, what the project needs from the client with
   dates, the team by role and phase.
7. What we will decide together: every open decision and why it matters.
8. Assumptions and risks.
9. What comes next: the next step the client already asked for, then ideas for the client to
   consider.

References between sections are "section N" and must name an existing "## N." heading.

## Voice

- We are ScienceSoft: "we propose", "we expect". The client is named, never addressed:
  "Acme Clinics' engineer", not "your engineer"; no "you" or "your" outside a quote.
- Plain words. A term keeps one meaning in the whole document; when a second meaning appears,
  one of them is renamed (a "job" was a customer order and a queue entry at once).
- No bold anywhere. A lead-in that names an idea is set in italics.
- A proposal says what is proposed, not what is settled. Anything the sources leave open
  carries its decision in section 7 and points there.
- The future is conditional: the ideas of section 9 and anything outside the plan are written
  with "would" and "could" and are introduced as ideas to discuss, each with what the client
  gains and what it would need from them.
- No competitor product names, no people's names of the client (roles only), no costs in the
  body; costs, if any, live in the commercial part the company template adds.

## The client's words

Quotes are verbatim, in curly quotes, from the transcript or the client's documents, and a
quote is used in the sense it had where it was said. A quote without context is not used: the
cell next to it says what it answers, and a remark such as "oh, that would be neat" that only
reacts to our own idea is not a requirement and does not go in section 2.

## Preliminary

Every statement that the scope, design or plan is preliminary is a note of its own: a
blockquote line directly under the paragraph it qualifies, never a clause inside it. There are
at most three: the whole proposal (section 1), the design (section 5), the plan (section 6).
The publisher turns them into info panels, the Word build into shaded paragraphs.

## Coverage

Before the draft is accepted, every ask, worry and question the client raised is in the
coverage map with the place that answers it or an explicit "out of scope". On one live call
the owner asked how the app is distributed, said the front desk would need training, and liked
standard visit types; each came back from the reader as a separate question because the first
draft had no place for it.

## Figures

Each figure is ![caption](figures/<slug>.png) on its own line, followed by an italic line
*Figure N. <what the reader sees>.*, numbered 1, 2, 3 through the document. Three kinds, declared
in the figure plan (attn-figures.js):

- exact: a diagram whose value is which box connects to which, in what order or on which week
  (context, components, deployment, sequence, timeline); generated, then checked box by box;
- screen: a product screen whose numbers, counts or words the text relies on (posts along a fence,
  a price list, a banner, a disclaimer). Its brief ends with a Facts block checked against the
  document before anything is drawn (tools/figure_facts.py), and it is written as an HTML mockup
  and rendered by headless Chrome (tools/render_html.py), never generated: a generator does not
  keep counts or text;
- illustration: a scene or a hero picture whose value is the look; generated.

Every number a figure shows agrees with the text around it: a spacing banner, the posts placed
under it and the price that counts them are one example, not three.

## Exemplar

exemplars/proposal/skeleton.md: the anonymised skeleton of an accepted proposal, and why.md beside
it for what made that proposal work. exemplars.local.yaml names the full document under
"proposal" on a machine that has it (not in the repository). Take the shape and the tone from
it, never its content.

## Reviewer checklist

HIGH (any one forces revise)
1. A client ask, worry or question from the coverage map with no place in the document.
2. Two sections that contradict each other, or a figure that contradicts its text.
3. A promise the plan does not deliver (a screen needed in week 10 built in week 14, a feature
   in the text and in no sprint).
4. A claim about the client not supported by the sources; a quote used out of context.
5. A cost, a competitor name or a person's name of the client.

MEDIUM (three force revise)
6. An idea or next step written as a commitment.
7. A preliminary statement inside a paragraph instead of its own note.
8. A term with two meanings; jargon a non-technical reader cannot follow without help.
9. A role, stakeholder or partner the sources name that no table or paragraph covers.

LOW
10. Wording the reviewer would merely phrase differently: not a defect, do not report it.

Prefer a remark that closes by cutting or moving a sentence over one that asks for new text.

## Gate rules

Deterministic, run by the script before the reviewer sees the draft:

- no "you" or "your" outside quotes (--forbid-outside-quotes);
- no bold (--forbid-file library/style/forbid/no-bold.txt);
- no empty table cell, except columns the commercial part leaves for a manager (--no-empty-cells);
- every "section N" names a "## N." heading (--section-refs);
- every figure followed by its numbered caption (--figures-numbered);
- no heading with nothing under it (--no-empty-sections);
- every quote found in the sources (tools/check_quotes.py);
- every coverage row placed or marked out of scope (tools/coverage.py).

## Output language

The language of the client's material. A proposal is in English when the call and the
scope document are.
