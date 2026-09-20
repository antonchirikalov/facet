---
name: solution-design-profile
description: Document-type profile for a solution design (level 3, solution-design.js design stage). Preloaded into the solution designer, the selector and the design critic so all three read one contract - sections, tables, one committed architecture, no estimates, figure placeholders, traceability to requirement ids, critic checklist and gate rules.
user-invocable: false
---

# Profile: solution design

This is the contract for one document type. The designer, the selector and the critic of a
solution design all receive this file at spawn, so whatever it says binds all three at once.
Where an agent's own instructions and this profile disagree about the document, the profile
wins; the agent's instructions describe its role, this file describes the document.

## Purpose and reader

A solution design turns an accepted requirements document into the technical decisions a
delivery team implements and an architect or a client's technical staff review. It is a
client-facing technical proposal: one committed architecture, demonstrated through concrete
scenarios and module tables, every decision traceable to the requirement it serves, every
guess labelled as a guess. It is read by two people with different questions: the engineer
asks "can I build from this without re-deriving the core decisions?", the client asks "does
this do what we asked, within what we said we must live with, and what did they assume?".

## Three rules that override everything below

1. **One architecture, not several.** The document puts forward ONE design. A credible
   alternative is dismissed in a single prose sentence where the decision is made — never
   laid out as options for the reader to weigh, never as a pro/con table per aspect.
2. **No estimates of any kind.** No money, no durations, no T-shirt sizes, no story points,
   no team sizes. Phases are defined by what they deliver and their exit criterion, never by
   how long or how much. The only permitted hedge in the document is the one caveat on the
   infrastructure section.
3. **Know from chose, on every page.** A reader tells, without leaving the document, which
   statements come from the requirements (cite the id: `FR-012`, `BR-004`, `C-003`) and which
   are the designer's proposal (marked as decisions `D-NN` and, where they rest on something
   unconfirmed, collected in section 7). A specific version, product, vendor tool or fact about
   the client's environment that no requirement states is a proposal, not a fact.

## Section contract

Numbered headings; the gate checks the numbers, a reader checks the names. Headings are in
the document's language.

```
# Solution design: <project> — v<n>
one line: Based on requirements v<n> of <date> | Output language: <language>

## 1. Solution overview
### 1.1 Business context           2–4 paragraphs; what the system is and deliberately is not
### 1.2 Stakeholders and systems    table: # | Role or system | Type | Role in the solution | Key interest | Source (requirement id + short quote)
### 1.3 Core architecture           the central design named; table: Layer or component | What it establishes; the context figure
### 1.4 The core technical bet      the one decision the rest hangs on, and how it propagates
## 2. Technology and structure
### 2.1 Architecture pattern        ONE pattern, the alternative dismissed in one sentence, why it fits THESE NFRs
### 2.2 Modules                     table: # | Module | Responsibility | Requirements (ids) ; heavy or isolated services marked with their runtime
### 2.3 Data                        the model as the sources name it; integrity guarantees; volumes from section 9 of the requirements
### 2.4 Key interfaces and integrations   table per external system: direction, protocol, what flows, requirement ids
## 3. Design by requirement area
### 3.1 … 3.N                       one subsection per area of section 3 of the requirements; each names the requirement ids it satisfies, the decision, and the reading taken where a requirement was ambiguous; at least one end-to-end scenario walkthrough per major area, naming the actual components invoked
## 4. Non-functional requirements   table: Requirement (id + target value quoted) | Design mechanism | How it is verified
## 5. Infrastructure and deployment  deployment model from the requirements, the one caveat, topology figure, table: Category | Service or component | Usage
## 6. Risks and mitigations         table: # | Risk | Where it bites | Mitigation | Requirement or decision it touches
## 7. Assumptions to confirm        table: # | Assumption | Rests on | Who confirms ; plus every open question the design does not close, with what depends on it
---
*End of solution design.*
```

Rules that make the shape worth having:

- **No front matter, no metadata block, no counts.** The first line is the `# Solution
  design:` heading. A block that counts figures or modules is a fact nothing checks.
- **Business context is prose**, two to four paragraphs, and ends with one plain sentence:
  what the system is and what it deliberately is not.
- **Stakeholders and systems** has one row per human role and per external system the
  requirements name, with a short quote from the requirements in the Source cell.
- **Modules** table lists every module with the requirement ids it serves; a requirement id
  that appears in no module row is unmet until section 3 shows otherwise. Heavy or isolated
  services (a worker, a reporting engine, a model service) are marked and pinned to their
  runtime.
- **Section 3 follows the requirements' own areas**, in their order, so a reader with the
  requirements open can walk both documents side by side. Each subsection: which ids it
  satisfies; the decision (`D-NN`) and why; the reading taken where a requirement was
  ambiguous or where 8.1 of the requirements left a conflict open — the design resolves it as
  a configurable setting or a documented reading, never silently. At least one scenario
  walkthrough per major area: a named, concrete flow through the modules, naming what is
  invoked at each step. The walkthrough is the data-flow narrative; do not add a second one.
- **Every NFR row quotes the target value** from the requirements and names the mechanism
  that reaches it and how it will be verified (a test, a measurement, an inspection). An NFR
  the requirements tag `[PROVISIONAL]` stays provisional here.
- **Infrastructure** picks the deployment model the requirements impose (cloud vendor, on
  premises, hybrid, sovereign) and says so in the first line. It opens with the one caveat that
  the topology is a first pass to refine during discovery; that is the only hedge in the
  document. Then a topology figure and the service reference table: compute, storage,
  database, cache or queue, ingress, networking, the security stack (edge protection, key
  management, secrets, identity and access), notifications, monitoring, artifact registry.
  Every entry is something the designer confirmed exists — never a remembered version number;
  "a current LTS release" beats a wrong number.
- **Personal data paths are traced to the end**, including notifications, exports and
  third-party channels. Declaring a residency or protection constraint satisfied "by
  construction" while an unanalysed egress path exists is a defect, not a detail.
- **Never assert what a vendor plans or recommends**, or where a product stands in a market:
  neither the designer nor the reader can check it from here, and one such claim discredits
  the parts that are solid.
- **Risks** are real exposures of THIS design with a mitigation each, not generic project
  risks.
- **Section 7 is where honesty lives**: every unconfirmed proposal, every assumption about the
  client's environment, every open question of the requirements the design carried forward,
  with what depends on it and who can confirm it.

## Figures

Wherever a diagram explains better than prose, the designer declares a placeholder of the form
`![caption](figures/<slug>.png)` directly after the paragraph it explains, three to five in all:
the context view (who talks to the system), the component or container view, the main data
flow, the deployment topology, and one sequence or state that prose carries badly. The caption
is in the document's language and names the elements the figure must show; the slug is Latin
and hyphenated. A separate illustration step draws them from the caption and the surrounding
section. **The placeholder is the deliverable at this stage**: a reviewer never flags a figure
as missing because the file is not there yet.

## Style

No bold text anywhere in the body (`library/style/forbid/no-bold.txt` is in the gate);
structure comes from headings and tables. Three or more items in sequence are a list, not a
comma-separated sentence. No marketing language — nothing is "cutting-edge", "robust" or
"best-in-class" without a mechanism behind it. Requirement ids and decision ids are inline in
backticks. The document is in the language of the requirements document.

## Critic checklist

In order of severity. `HIGH` alone forces `revise`; three or more `MEDIUM` force `revise`;
`LOW` never does. Every finding names the section and, for a requirement defect, the id.

HIGH
1. A requirement (FR, NFR, BR) with no module, section-3 decision or explicit deferral to
   section 7 — read the requirements id by id, do not sample.
2. More than one architecture presented for the reader to choose between.
3. Any estimate: money, duration, size, team.
4. A constraint declared satisfied over an unanalysed path (a personal-data egress, an
   integration direction the requirements forbid).
5. A fact about the client's environment, a vendor's plans, a version or a benchmark stated
   as established when no requirement states it and no search confirmed it.
6. A missing top-level section, or 1.1–1.4 missing from section 1.
7. A conflict the requirements left open in 8.1 that the design resolves silently, without a
   decision id and without a setting or a stated reading.

MEDIUM
8. A functional area of the requirements without a scenario walkthrough.
9. An NFR row without the quoted target value or without a verification method.
10. A mandated table rendered as prose; bold in the body; inline enumerations of three or more.
11. A technology or service that looks invented or stale.
12. The infrastructure section without the deployment-model statement, the caveat, the
    topology figure or the service table.
13. A risk table with generic project risks instead of this design's exposures.

LOW
14. Marketing language; a figure caption that does not say what the figure shows.
15. Wording the critic would merely phrase differently — not a defect; do not report it.

IGNORE: a placeholder whose PNG does not exist yet. The placeholder is the deliverable.

Prefer remarks that close by cutting or by moving a claim to section 7 over remarks that
demand new text: the design grew from 24 000 to 34 000 characters of prose across three
rounds once while the remark count did not fall, because every remark was answered with a
paragraph. A remark closable in one sentence should say so.

The critic writes its remarks in the language of the document.

## Gate rules

Deterministic, run by the script before the critic sees the draft:

- headings `## 1.` … `## 7.` and `### 1.1` … `### 1.4` present (`--require-heading`);
- no heading with nothing under it (`--no-empty-sections`);
- no bold in the body (`--forbid-file library/style/forbid/no-bold.txt`);
- a prose floor from the order when the order gives one; no ceiling the order did not name.

## Exemplar

`exemplars/solution-design/skeleton.md` — the anonymised skeleton distilled from the
template this profile descends from and from the strongest live design produced by this
pipeline. The path to a full reference document, when one is available on this machine, is in
`exemplars.local.yaml` (not in the repository).

## Level

3 — a saved Dynamic Workflow (`solution-design.js`, stage `design`): one candidate per model
in parallel, a selector, then designer → gate → critic in rounds up to the configured limit,
with a plateau stop; then a discovery step that turns what the design could not close into
questions for the client.

## Output language

The language of the requirements document the design is built from, unless the order says
otherwise. Headings translate; ids, tags and the `# Solution design:` marker do not.
