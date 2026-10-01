# Why this exemplar

Type: `solution-design`. Skeleton: `skeleton.md` next to this file. There is no full client
document to serve as the exemplar yet; its path will appear in `exemplars.local.yaml` once we
choose one.

## What it is built from

Two sources. The first is the spectra pipeline's `solution-design-template`: one architecture
with no options to choose from, no estimates of time or money, tables of stakeholders, modules,
phases, NFRs and infrastructure services, end-to-end scenarios per phase, figure placeholders as
a mandatory part, a critic checklist with severities and a verdict rule. The second is the best
live design of this pipeline (the vet-clinic demo, 20.09.2026, the winning candidate on opus):
decisions with `D-NN` ids, readings of ambiguous requirements in a section of their own, a full
map of personal-data flows, settings instead of hypotheses where the requirements left a
conflict open.

## What was taken from spectra and what was changed

- Taken: one architecture; zero estimates; tables instead of prose where things are compared; a
  scenario per area; infrastructure from the requirements, not by default, with one caveat
  sentence; the critic ignores a placeholder's missing PNG.
- Changed: no YAML header and counters (facet's rule: a meta block nobody checks goes stale at
  the next edit); placeholders in the format of facet's illustrator,
  `![caption](figures/<slug>.png)`, not an HTML comment; sections are numbered so the gate checks
  them by number in any language; section 3 follows the requirement areas in their order so the
  two documents read side by side; "Risks" and "Assumptions to confirm" sections added from the
  facet designer's prompt; delivery phases are optional: an RFP proposal needs them, not every
  design.
- Added from a live run: the critic is required to prefer remarks that close by cutting or by
  moving into assumptions, because the design grew from 24 to 34 thousand characters over three
  rounds while the number of remarks did not fall.
