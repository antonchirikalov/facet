# Solution design: <Project> — v1

Based on requirements v1 of <date> | Output language: <language>

<!-- WHY: no front matter and no counts — the first line is the heading, and every fact about
     the document that nothing checks goes stale on the next edit. -->

## 1. Solution overview

### 1.1 Business context

<Two to four paragraphs: the problem the client has today, why the current tools fall short,
the regulatory and organisational setting, and one plain sentence — what the system is and what
it deliberately is not. Cite requirement ids inline: `FR-004`, `BR-002`.>

### 1.2 Stakeholders and systems

| # | Role or system | Type | Role in the solution | Key interest | Source |
| --- | --- | --- | --- | --- | --- |
| 1 | <Sponsor> | human | approves scope, reads reports across all sites | <…> | `FR-039 — “<quote>”` |
| 2 | <Accounting system> | external system | read-only source of receipts and price list | <…> | `BR-005 — “<quote>”` |

<!-- WHY: one row per human role and per external system the requirements name; the quote is
     what lets the client recognise their own words. -->

### 1.3 Core architecture

<Name the central design in one sentence. Then the table, then the context figure.>

| Layer or component | What it establishes |
| --- | --- |
| <Web application> | <…> |
| <Background worker> | <…> |
| <Database> | <…> |

![Context view: <who talks to the system, which external systems, direction of each flow>](figures/context-diagram.png)

### 1.4 The core technical bet

<The one decision the rest hangs on — a consistency guarantee, an integration contract, a data
model — and how it propagates through the design and what it buys. Decision id `D-01`.>

## 2. Technology and structure

### 2.1 Architecture pattern

<One pattern. Open with the one-sentence dismissal of the main alternative. Then why this
pattern fits these NFRs and this domain.>

![Component view: <modules, stores, workers, and the interfaces between them>](figures/component-diagram.png)

### 2.2 Modules

| # | Module | Responsibility | Requirements |
| --- | --- | --- | --- |
| 1 | <Scheduling and booking> | <…> | `FR-001`–`FR-013`, `FR-027` |
| 2 | <Background worker> (isolated: <runtime>) | <…> | `FR-020`, `FR-035` |

<!-- WHY: a requirement id that appears in no row is unmet until section 3 shows otherwise. -->

### 2.3 Data

<The model as the sources name it; the integrity guarantee that carries the core bet; volumes
quoted from section 9 of the requirements.>

### 2.4 Key interfaces and integrations

| External system | Direction | Protocol or mechanism | What flows | Requirements |
| --- | --- | --- | --- | --- |
| <1C> | inbound only | <hourly file drop to object storage> | <receipts, price list> | `BR-005`, `BR-006` |

![Data flow: <the one flow prose carries worst, e.g. receipt reconciliation>](figures/data-flow.png)

## 3. Design by requirement area

### 3.1 <Area, in the requirements' own order>

<Requirement ids satisfied. The decision `D-NN` and why. The reading taken where a requirement
was ambiguous, or the setting introduced where 8.1 left a conflict open (`C-002` → setting per
clinic). One scenario walkthrough: a named flow through the modules, naming what is invoked at
each step.>

### 3.2 <Area>

<…>

## 4. Non-functional requirements

| Requirement | Design mechanism | How it is verified |
| --- | --- | --- |
| `NFR-001` — “<target value quoted>” | <mechanism> | <test, measurement or inspection> |
| `NFR-004 [PROVISIONAL]` — “<value>” | <mechanism> | <stays provisional until …> |

## 5. Infrastructure and deployment

<First line: the deployment model the requirements impose and why. Second line: the one caveat
— this topology is a first pass to refine during discovery.>

![Deployment view: <zones, nodes, managed services, ingress, where personal data rests>](figures/deployment-diagram.png)

| Category | Service or component | Usage |
| --- | --- | --- |
| Compute | <…> | <…> |
| Database | <…> | <…> |
| Security | <edge protection, key management, secrets, identity> | <…> |
| Monitoring | <…> | <…> |

## 6. Risks and mitigations

| # | Risk | Where it bites | Mitigation | Touches |
| --- | --- | --- | --- | --- |
| R-01 | <an exposure of THIS design> | <component or flow> | <what reduces it> | `D-04`, `NFR-008` |

## 7. Assumptions to confirm

| # | Assumption | Rests on | Who confirms |
| --- | --- | --- | --- |
| A-01 | <a proposal no requirement states> | <what led to it> | <role> |

<Open questions the design does not close, each with what depends on the answer.>

---
*End of solution design.*
