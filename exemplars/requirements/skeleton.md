# Requirements: <Project> — v2

Generated: <date> | Reconciled: <date> against <client answers file> (<N> answers) | Output language: <language>

> About this version. Every row carries a Source cell naming the client's answer (Q<n>) or the
> input document with a locator, plus a short verbatim quote, so each item traces to a confirmed
> client statement. Rows that come only from the brief and were neither confirmed nor changed by
> the answers say brief (no Q&A delta) instead of a fabricated citation. Rows changed by the
> answers are tagged [CHANGED]; figures the client declined to fix are tagged [PROVISIONAL].

<!-- WHY: the reader learns the citation convention before the first table, and learns that a
     missing citation is a deliberate statement, not an omission. -->

## Document index

| # | File | Type |
| --- | --- | --- |
| 1 | 00_chat_summary.md | chat |
| 2 | <client> Brief v0.1.docx | brief |
| 3 | <client> RFP v0.1.docx | rfp |
| 4 | <kick-off>.docx | transcript |
| 5 | Questions_v1.0.md | client answers (<N> Q&A) |

<!-- WHY: the type column is what the trust hierarchy keys on; the list is what "no source
     was dropped" is checked against. -->

## Domain grounding

<One paragraph, three to five sentences: what is being procured or built, the named use cases or
business areas, the regulatory and language setting, what already exists (greenfield or not,
with the answer ids that say so), how delivery is phased.>

<!-- WHY: prose, because a reader with no context needs a story, not a list; the answer ids in
     the paragraph make even the framing checkable. -->

## 1. Stakeholders and roles

| Role | Description | Source |
| --- | --- | --- |
| Sponsor / business owner | Owns the programme, selects use cases, approves the phased rollout. | rfp: §1; Q310 |
| Platform administrator | Manages the console, governance rules, source configuration, user roles. | Q36 — “surfaced to the administrator” |
| <role> | <what they do with the system> | <source> |

<!-- WHY: every role named anywhere in the sources appears once; a role the requirements
     mention but this table lacks is a gap. -->

## 2. Business context

- Programme scope: <the use cases or areas under one initiative>. Source: Q310 — “<quote>”
- Delivery model: <vendor / custom / hybrid; how proposals are packaged>. Source: Q316; Q368 — “<quote>”
- Deployment model [CHANGED]: <on-prem / cloud / hybrid and the binding constraint>. Source: Q3; Q92; Q318 — “<quote>”
- Data residency: <where sensitive data and its processing must stay>. Source: Q415 — “<quote>”
- Language coverage: <languages, dialects, mixed queries>. Source: Q276 — “<quote>”
- Regulatory context [EXPANDED]: <which regulators apply and which do NOT>. Source: Q189; Q418 — “No”
- Commercial: <currency, pricing rules, penalties, support term>. Source: Q365; Q269 — “<quote>”

<!-- WHY: each bullet is one fact with one source; the tags show what moved since v1. -->

## 3. Functional requirements

### 3.1 <Area, e.g. Programme delivery and administration>

| ID | Requirement | Priority | Source |
| --- | --- | --- | --- |
| FR-001 | <One actor, one behaviour, one condition.> | MUST | Q317 — “<quote>” |
| FR-002 | <…> | MUST | Q1 — “<quote>”; Q373 — <what it adds> |
| FR-009 | <…> | SHOULD | Q230 — “<quote>” |

### 3.2 <Area, e.g. Knowledge, content and source management>

| ID | Requirement | Priority | Source |
| --- | --- | --- | --- |
| FR-010 | <…> | MUST | Q64 — “<quote>” |

<!-- 3.3 … 3.N: one subsection per business area, three to ten rows each, FR numbers continue
     across subsections. -->

### 3.N Out of scope (next phase and beyond)

| Feature | Source |
| --- | --- |
| <feature a stakeholder excluded> | Q258 — “<the excluding words>” |
| <feature deferred to a later phase> | Q313 — “future roadmap items rather than Phase 1” |

<!-- WHY: the boundary is a requirement too, and it is the one most often lost. -->

## 4. Non-functional requirements

> Figures tagged [PROVISIONAL] are indicative: the client declined to fix them and will agree
> them in design. They are sizing baselines, not commitments.

| ID | Requirement | Category | Source |
| --- | --- | --- | --- |
| NFR-001 [PROVISIONAL] | <availability with an indicative figure and how it will be fixed> | Availability | Q205 — “<quote>” |
| NFR-004 | <a measurable rule: e.g. audit-log 100% of interactions of listed kinds> | Security | Q260 — “<quote>” |
| NFR-006 [EXPANDED] | <compliance scope with named regulations, including the ones excluded> | Legal/Compliance | Q189; Q418 |

<!-- WHY: a number or a checkable criterion in every row; provisional is a tag, not an excuse. -->

## 5. Business rules and constraints

| ID | Rule | Source |
| --- | --- | --- |
| BR-001 | <what must always be true at runtime, or what the project must live within> | brief (no Q&A delta) |
| BR-004 [REVISED] | <a rule the answers changed> | Q318 — “<quote>” |

## 6. Data model (derived from sources)

| Entity | Key attributes | Source / notes |
| --- | --- | --- |
| <Entity> | <attributes as the sources name them> | Q70; Q191 — <what confirmed them> |
| <Entity> | <…> | Q64; Q262 |

<!-- WHY: derived and labelled as such; only entities with two or more sourced attributes. -->

## 7. Integration points

| Integration | Purpose | Priority | Source |
| --- | --- | --- | --- |
| <System of record> | <what flows, direction, phase: read-only now, write-back later> | MUST | Q338 — “<quote>” |
| <Channel> | <…> | MUST | Q339 |

## 8. Open questions, conflicts and assumptions

### 8.1 Conflicts

| # | Conflict | Sources in conflict | Resolution / status |
| --- | --- | --- | --- |
| C-001 | <what contradicts what, with both positions> | brief vs Q316; Q368 | RESOLVED — <rule applied: later explicit answer wins>. |
| C-005 | <…> | <a> vs <b> | UNRESOLVED — <the question that resolves it>. |

### 8.2 Gaps

| # | Gap | Impact | Source |
| --- | --- | --- | --- |
| G-004 | <what no source answers> | <what depends on the answer> | <where it was raised> |
| G-007 | <…> | <…> | Q360 — “start small, scale on demand” |

### 8.3 Assumptions

| # | Assumption | Basis | Status |
| --- | --- | --- | --- |
| A-001 | <a conclusion the writer drew> | <which phrase or rule led to it> | Holds / Confirmed (Q317) / WITHDRAWN (Q3) |

<!-- WHY: 8.1 is where silent choices would hide; 8.3 is where inference is quarantined. -->

## 9. Confirmed environment and technical facts

| Topic | Fact | Source |
| --- | --- | --- |
| Existing AI / tooling | <what exists in production today, and what does not> | Q86; Q88; Q90 |
| Hosting / hardware | <what the client owns, what the vendor must size> | Q94; Q6 |
| Identity | <SSO / MFA / directory situation> | Q191; Q74 |
| Data availability | <depth, gaps, samples, documentation, who is available> | Q232; Q231 |

<!-- WHY: facts architecture and sizing need, separated from requirements so nobody has to
     guess which is which. -->

---
*End of requirements document.*
