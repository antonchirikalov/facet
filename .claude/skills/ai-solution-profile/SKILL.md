---
name: ai-solution-profile
description: Document-type profile for the technical design of an AI solution (design.js, type ai-solution) - an assistant, an agent, a retrieval system or a model step inside an ordinary product. Read by the solution designer and the design critic through their profile port, and by the rule panel one rule at a time. Where a model is needed and where code is, the pattern and its guardrails, knowledge, models and the shape of cost, the four stages, people in the loop, data and trust, how quality is measured, failure modes, decisions to take with the client, and the gate rules.
user-invocable: false
---

# Profile: AI solution design

The technical design of a solution in which a language model does part of the work. It is built
from accepted requirements and answers the question an RFP for an AI solution really asks: why
this design, and how will we know it works. A design that describes only the model call is not a
design; a design that uses a model where a rule or a search would do is a cost and a risk the
client pays for.

The reader is the client's technical lead and their IT and compliance advisers; the proposal
carries the conclusions to the business reader in plain words. Every decision cites the
requirement that decided it, in the requirements' ids (FR-012, NFR-003).

## Rules that override everything below

1. **A model only where judgement is needed.** A step goes to a model only when all four hold:
   the input is language or another unstructured signal; no rule written as code decides it; the
   cost of an error is bounded and known; something can check the result. Exact recall is a
   search, a binding rule (a limit, an approval, a price) is code, a bulk transformation is a
   script.
2. **The narrowest pattern that fits.** A single call before a workflow, a workflow before an
   agent, one agent before several. A wider pattern is justified by a property of the task, not
   by fashion, and carries its guardrails.
3. **No absolute promises.** Being available is not being right. Quality is a measured rate with
   a sample, a grader and what happens on a miss; "accurate", "safe", "eliminates errors" are not
   targets.
4. **Cost has a shape, not a price.** Tokens per request, what dominates the bill, what is cached,
   what runs in batch; money totals live in the commercial part.
5. **Every decision traces.** A pattern, a model tier, a hosting route or a data rule names the
   requirement id or the client's constraint that decided it; one with no reason is a guess.

## Section contract

```
# AI solution design: <product>
## 1. Overview
### 1.1 What the solution does and deliberately does not
### 1.2 Stakeholders and systems        table: Role or system | Role in the solution | Requirement ids
### 1.3 The core bet                     the one decision the rest hangs on
## 2. Decision points                   table: Step of the client's process | Model, code, search or person | Why (the four tests of rule 1) | Requirement ids
## 3. Pattern                           per model step: the pattern, the alternative dismissed in one sentence, the guardrails
## 4. Knowledge                         prompt, retrieval or fine-tuning, decided by how often the knowledge changes and how large it is; chunking by the shape of the data, search, keeping it fresh
## 5. Models and the shape of cost      table: Step | Model tier | Why this tier | Tokens in and out per request | Cached or batch
## 6. The four stages                   input (capture, validate, redact), model, output (validate, then act or present), feedback (logs, evaluation, human sampling)
## 7. People in the loop                table: Action | Reversible? | Who approves | What happens when no approver is available
## 8. Data and trust                    what leaves the client's boundary and to whom, what the model provider keeps, residency, retention and deletion in every store, access (the assistant acts as the user, with scoped rights), audit; the regulation-specific step where the sources trigger one
## 9. Quality                           table: Target | Segment | How it is measured (sample, grader, frequency) | What happens on a miss ; the evaluation set, who labels it, who owns it; acceptance criteria for a pilot; monitoring after launch
## 10. Failure modes and degraded operation   table: Failure | Where it bites | Control | Residual risk accepted ; one row per external dependency with its degraded mode
## 11. Non-functional requirements      table: Requirement (id + target quoted) | Mechanism | How it is verified ; latency per stage with headroom, at a percentile
## 12. Infrastructure                   where it runs, the hosting route chosen by the binding constraint, environments, backup and restore
## 13. Decisions to take with the client     one short memo each: options in the client's terms, our recommendation, the one fact that would change it
## 14. Assumptions to confirm           table: Assumption | Rests on | Who confirms
```

## What each section must carry

- **Section 2** lists every step of the client's process the requirements describe, not only
  the ones a model does; a step that goes to code or a person is half of the design's value.
- **Section 3**: for each model step, the answers that chose the pattern: can the steps be listed
  in advance; is there a cheap check between steps; how varied are the inputs; are the subtasks
  independent; does it fit in one context; is the path unknowable in advance. An agent carries a
  step cap, a full trace and approval gates; a routing step carries a fallback lane for the cases
  it is unsure about; an evaluator loop carries an iteration cap; several agents carry fan-out
  and depth caps, one writer per resource, and the rule that merges their results.
- **Section 4**: knowledge that changes weekly rules out fine-tuning; a corpus that does not fit
  one context rules out the prompt alone. Tables are chunked as rows, records as one unit,
  prose by section; search that combines keywords and meaning, with a reranker where the corpus
  is large; how an updated source reaches the index, and how stale it may be.
- **Section 5**: the cheapest tier that meets the step's binding constraint; output tokens cost
  several times input tokens and tool definitions are paid on every turn, so the table says which
  part dominates. A cache saving is claimed only where the same prefix recurs within the cache's
  lifetime.
- **Section 6**: a model output never triggers an action without an output check (schema, policy,
  confidence) between them.
- **Section 7**: every action that writes, sends, books or moves money has its reversibility and,
  above "reversible", a named approver; "a person watches every step" does not scale and is not
  an answer.
- **Section 8**: the trigger list the sources set (personal health data, data of EU residents,
  public sector, financial records) each with the mechanism it requires.
- **Section 9**: targets per segment the sources name (input type, language, user group), never
  one average; the evaluation set built from the client's real cases, with the questions the
  sources cannot answer included; a model judge only with a rubric and agreement measured against
  people; a model or prompt change goes through the evaluation set before release, never both at
  once.
- **Section 10**, for the pattern chosen: an answer invented where the sources hold none; a
  citation the model did not read; a stale index; instructions injected through a document or a
  tool's output; an agent acting on unchecked output; a loop with no cap; a hard case routed to
  the cheap lane. Each named, controlled, or explained as not applying.
- **Section 13**: decisions only the client can take; a choice the requirements let us make is
  proposed in its section, not listed here.

## Critic checklist

In order of severity. HIGH alone forces revise; three or more MEDIUM force revise; LOW never
does. Every finding names the section and the requirement id it concerns.

HIGH
1. A MUST requirement that no section answers.
2. A model step whose input is not language or another unstructured signal, or that a rule written
   as code decides, or whose error cost is unbounded, or whose result nothing checks: a rule, a
   search or a script would do the work; or a binding client rule (a limit, an approval, a price)
   left to the model.
3. A pattern wider than the task needs, or a pattern without its guardrails (an agent with no step
   cap or trace, a router with no fallback lane, several agents with no merge rule or caps).
4. A model output that triggers an action with no output check between them; an irreversible or
   money-moving action with no named human approver.
5. An absolute promise of quality or safety, or a quality target with no measurement.
6. Data leaving the client's boundary with no statement of what the provider keeps; a regulation
   the sources trigger with no matching mechanism.
7. A decision with no requirement or constraint behind it, or a fact about a model, a provider or
   a price stated as established that no source confirms.

MEDIUM
8. A quality or latency target stated only as an average or only overall, where the sources name
   segments.
9. A knowledge choice that ignores how often the knowledge changes or how large it is; chunking
   that ignores the shape of the data.
10. A model tier chosen without its binding constraint; a cache saving claimed without recurring
    prefixes.
11. A failure mode of the chosen pattern neither controlled nor explained away; a dependency with
    no degraded mode.
12. An evaluation plan without its set, its owner, or acceptance criteria for a pilot.
13. A decision for the client without a recommendation, or a choice we could make listed as one.

LOW
14. Wording the critic would merely phrase differently: not a defect; do not report it.

The critic writes its remarks in the language of the document. A remark that closes by cutting or
moving a claim is preferred over one that asks for new text.

## Gate rules

```gate
--require-heading "^##\s+1\." --require-heading "^##\s+2\." --require-heading "^##\s+3\."
--require-heading "^##\s+4\." --require-heading "^##\s+5\." --require-heading "^##\s+6\."
--require-heading "^##\s+7\." --require-heading "^##\s+8\." --require-heading "^##\s+9\."
--require-heading "^##\s+10\." --require-heading "^##\s+11\." --require-heading "^##\s+12\."
--require-heading "^##\s+13\." --require-heading "^##\s+14\."
--no-empty-sections --figures-numbered
# absolute promises are measurements, not judgements
--forbid-file library/style/forbid/absolute-promises.txt
--forbid-file library/style/forbid/no-bold.txt
--forbid "\x60"
```

Beside the gate: every requirement id the design cites exists (tools/trace_ids.py), and every MUST
requirement is cited somewhere in the design (tools/must_covered.py).

## Exemplar

None yet; the invented Acme Clinics case in cases/ is the test material.

## Output language

The language of the requirements.
