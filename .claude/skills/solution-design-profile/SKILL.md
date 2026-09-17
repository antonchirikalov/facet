---
name: solution-design-profile
description: Document-type profile for a solution design (level 3, solution-design.js). Preloaded into the solution designer and its critic so both read one contract.
user-invocable: false
---

# Profile: solution design

This is the profile of one document type. The designer and the critic of a solution design
both receive this file at spawn, so whatever it says binds both at once. It is being filled
in step by step (facet SPEC §6, plan step 3); the sections below that still say so are
carried, for now, by each agent's own instructions.

## Purpose and reader

A solution design turns an approved requirements document into the technical decisions a
delivery team implements and an architect reviews: components, data, integrations,
non-functional measures and the trade-offs behind each choice.

## Section contract

Carried by the agents' own instructions until this profile takes it over.

## Critic checklist

Carried by the critic's own instructions until this profile takes it over.

## Gate rules

Carried by the workflow script until this profile takes them over.

## Exemplar

No exemplar skeleton yet (plan step 4).

## Level

3 — a saved Dynamic Workflow (`solution-design.js`), candidate designs per model, a
selector and a criticised refinement loop.

## Output language

The language of the requirements document it is built from, not of these instructions,
unless the order says otherwise.
