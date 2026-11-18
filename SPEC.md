# facet — project specification

Version 0.2 · 2026-11-18 · status: accepted for work; sections 4-10 brought up to the repository

## 1. What this is

facet is the home of a practice for preparing pre-project and project analysis documents
(requirements, technical design, discovery, research and articles, one-off documents)
on Claude Code Dynamic Workflows with its own agents.

It is the direct successor of collimator: the same repository, the same git history, the same
scripts, agents and tools. The purpose has changed. collimator was conceived as a compiler of
`pipeline.yaml` into workflow scripts; the compiler was never finished, the scripts were written
by hand, and that is accepted as the state of things, not a phase. facet takes this as given and
adds what none of its predecessors had: a content layer — document-type profiles, exemplars, a
catalogue of types with weight levels, and the entry point "I want a document of type X".

The line of projects: prism → spectra → loom → refract → collimator → facet. Five orchestrators
were rewritten in three months; a sixth is not being written.

## 2. Decisions made before work began

**R1. The orchestrator is saved Dynamic Workflows, written by hand.** One script per heavy
pipeline. No script compiler is built. Only the subagent definitions are generated
(`facet/emit_agents.py`: `library/agents/*` → `.claude/agents/*.md`).

**R2. No orchestration code is written in the repository.** No scheduler, no ledger, no runtime,
no state machine, no compiler. This is the only protection against a sixth iteration. Python is
allowed only as a ruler tool that an agent calls (see §5).

**R3. Document quality is set by the shape of the revision round, not by the orchestrator.**
Proven by the collimator retrospective (`docs/decisions/2026-08-17-dynamic-workflows-retrospective.md`):
nine pipeline defects against four platform defects, and the first burned the tokens. The lessons
of the round are mandatory for all pipelines: corrector before critic; a numbered remark sheet with
the writer's answer to each remark; evidence instead of a verdict (the agent writes out what it
checked rather than declaring "all fine"); a plateau detector; whatever stays open is written down
explicitly.

**R4. The number of agents is set by the script text.** Roles are fixed by `agent()` calls; the
fan-out is bounded by a ceiling from `cfg`; rounds by `maxRounds` and the plateau. The upper bound
of a run is computed arithmetically before launch. The model takes no part in this decision.

**R5. Only files and `args` pass between pipelines and stages.** Script variables carry control
(paths, numbers, verdicts); files carry content.

**R6. Python decides everything deterministic, not the model.** Length, clichés, empty sections,
references, round number, directory listing, directory busyness.

**R7. One hook — an auditor, not control.** `SubagentStop → tools/stop_audit.py` stays.
Blocking hooks (`PreToolUse`, `Stop`) are not introduced: the script holds the order.

**R8. Client data does not enter the repository.** Exemplars are stored as skeletons; paths to the
real documents live in `exemplars.local.yaml` under `.gitignore`.

## 3. Three weight levels

The document type determines the level; the level determines what runs.

| Level | What | How it runs | Agents |
|---|---|---|---|
| 1 | One-off: memo, agenda, letter, TCO, solution overview, brief | ordinary session + profile + writer/critic subagents, gate called directly | 2–3 |
| 2 | Profiled, with rounds: gap analysis, roles and scenarios, architecture questions | skill `/doc <type> <folder>` in the session, 1–2 critic rounds | 3–6 |
| 3 | Heavy pipelines: requirements, design, article/research, illustrations | saved DW script | 10–20 |

Promotion rule: you made a document of a type by hand a second time — write a profile (level
1→2); the profile needs checking against sources and more than two rounds — it goes into a DW
script (2→3).

## 4. Level-3 pipelines

The document scripts in `.claude/workflows/`. The README holds how each is launched, its
arguments and how they combine; this table is the decision record.

| Script | Input | Output | Since |
|---|---|---|---|
| `requirements.js` | `inputs/` with the client's documents | `extracts/`, `client-voice.md`, `requirements.md`, `pains.md`, `holdout/questions.md`, `critic-remarks.md`, `UNRESOLVED.md`, `missing-input.md`, `outcome.md` | 2026-10-03; holdout and missing input 2026-10-10 |
| `design.js` | an accepted `requirements.md` and a design type (`solution-design`, `ai-solution`) | `design.md` with figure placeholders, `design-outcome.md`, `design-remarks.md`, `design-unresolved.md`, `design-missing-input.md`, `holdout/design/score.md` | 2026-10-05 |
| `proposal.js` | accepted requirements, `pains.md`, `client-voice.md`, optionally `design.md` | three stages, one per launch: `value` (optional) writes `value.md` under the value-map profile and the `value_model.py` ruler; `content` and `text` write `prop.md`; each stage has its outcome, remarks and `holdout/<stage>/score.md` | 2026-10-04; value stage 2026-10-26 |
| `scene.js` | a scene brief with Facts, the accepted proposal | one HTML page and a still of every step | 2026-10-04 |
| `proposal-review.js` | a proposal written elsewhere, the client's sources | the edited proposal, `coverage-map.md`, round records | 2026-09-29 |
| `explainer-article.js` | a one-sentence order | article, sources, round records | 2026-08-14, from collimator |
| `attn-figures.js` | a document with figure placeholders | PNG + manifest | 2026-08-14, from collimator |

A script cannot `import()`, so the common part (cfg, `task()`, verdict schemas, gate commands,
records, audit) is copied between scripts. `facet.wiring` runs every stage of every script on stubs
and checks the ports, lost outputs and meta phases, so a copy that drifts from the contracts fails
there.

## 5. Python is a ruler, not a foreman

`tools/` holds the rulers: gates (`gate.py` and the checks it is paired with: `extract_trace.py`,
`must_covered.py`, `pain_coverage.py`, `structure_kept.py`, `check_quotes.py`, `figure_facts.py`,
`value_model.py`, `holdout.py`), the round sheet (`rounds.py`), listings, busyness and run names
(`listing.py`, `busy.py`, `newrun.py`), file hands (`snapshot.py`, `apply_edits.py`, `to_text.py`,
`intake.py`), the auditor hook (`stop_audit.py`), rendering (`render_html.py`, `shrink_png.py`) and
Confluence (`confluence_publish.py`, `confluence_fetch.py`). Everything is called by an agent inside
a workflow or by the session. New tools are allowed if they measure rather than control; each one
records its own call in `<run>/tools.jsonl` through `toollog.py`.

## 6. Document-type profiles

A profile is a skill `.claude/skills/<type>-profile/SKILL.md`, preloaded into agents through the
`skills:` field in the frontmatter (the writer and the critic of one type get the same profile).
The `-profile` suffix is mandatory: the saved workflows `.claude/workflows/<name>.js` already take
the skill names `solution-design`, `explainer-article`, `attn-figures`, and a project skill
`<type>` would shadow the pipeline's launch point (`docs/decisions/2026-09-17-agents-one-home.md`).
The runtime skips a non-existent profile silently, so the agent build checks that it exists;
`disable-model-invocation: true` in a profile is forbidden — such a skill is not loaded.

Mandatory sections of a profile: purpose and reader; section contract (structure, what is
mandatory, what is forbidden); critic checklist (what to check, in order of importance); gate rules
with thresholds; link to the exemplar skeleton; weight level; output language (the rule: the
language of the sources, not of the prompt).

The profiles in the repository: `extract`, `requirements`, `client-voice`, `pain-map`,
`holdout-questions`, `solution-design`, `ai-solution`, `value-map`, `proposal`, `animated-scene`.
Level-2 profiles (`gap-analysis` and others) are not written yet.

## 7. Exemplars

`exemplars/<type>/skeleton.md` — headings, one anonymised row per table, notes on "what is
mandatory here and why". `exemplars/<type>/why.md` — why this particular document was chosen. One
exemplar per type, chosen rather than accumulated. `exemplars.local.yaml` (`.gitignore`) — type →
path to the real document on disk; the agent reads the full exemplar if the path is available.

## 8. Client folder standard

A run directory is made by `tools/newrun.py --base <folder> --label <what>`: `docs-runs/` in the
repository for trial runs, the client's own working folder for real ones (never the repository).
Inside it every pipeline writes to fixed names:

```
<run>/
  inputs/                   the client's sources as they arrived (requirements.js reads them)
  extracts/                 one extract per source
  requirements.md, client-voice.md, pains.md, outcome.md, missing-input.md
  holdout/                  questions.md, the blind batches and the scores per stage
  design.md, design-*.md    design.js
  value.md, value-*.md      proposal.js, stage value
  prop.md, prop-<stage>-*.md proposal.js, stages content and text
  rounds/<stage>/           round records and the draft of every round
  figures/, figures-work/   attn-figures.js
  tools.jsonl               the receipt of every ruler call
```

## 9. Target repository layout

```
facet/
  README.md, README.en.md   entry point (Russian) and its English copy
  SPEC.md                   this document
  CLAUDE.md                 rules for the developer session
  docs/
    workflow-conventions.md script rules and the rakes paid for by live runs
    decisions/              dated write-ups
    figures/                the README's figures and their manifest
    article-dynamic-workflows.md
  library/agents/           source of truth for agents (40)
  library/style/            voice profile, tells of generated text, forbidden patterns
  .claude/agents/           generated
  .claude/workflows/        seven scripts
  .claude/skills/           profiles, and frontend-design from Anthropic
  .claude/settings.json     the auditor hook
  cases/                    invented cases for trial runs (Acme Clinics)
  exemplars/                anonymised skeletons
  tools/                    rulers
  tests/
  facet/                    emit_agents.py, wiring.py, models
```

## 10. Work plan

| Step | What | Done when | State |
|---|---|---|---|
| 0 | Copy of collimator with history into `facet`; renaming in `pyproject.toml`, README; refract marked frozen | `uv run pytest` green in facet | done |
| 1 | One home for agents: `library/agents` reconciled, `.claude/agents` rebuilt, `skills:` on writers and critics | `emit_agents` with no manual edits in `.claude/agents` | done |
| 2 | Documentation: README, `workflow-conventions.md`, `decisions/` | a new session finds from the README how to make any document | done 2026-09-21; README.en.md 2026-11-18; a separate type catalogue and run-layout file dropped: the README and section 8 carry them |
| 3 | Profiles for every level-3 document | the critic and the writer of one type read one profile | done for level 3; `gap-analysis` not written |
| 4 | Exemplars for three types + `exemplars.local.yaml` | no client data in the repository | done |
| 5 | `requirements.js`; a run on the control input | the document is no worse than refract's | done 2026-10-03 |
| 6 | Skill `/doc` for levels 1-2 | the result compared with a hand-made document of the same type | not started |

## 11. What the project does not have and will not have

A web interface, a REST/WS API, a block catalogue, a type registry with edge checking, its own
runtime, a script compiler, a state machine with a turnstile. The first five are of value to an
outside user who does not exist. The last two are orchestration code (R2).

## 12. Deferred options

Recorded so they are not reinvented; not part of the plan.

- **Turnstile**: a foreman session + `next.py` + hooks `PreToolUse`/`PostToolUse`/`Stop`.
  Removes the carriers and the cascading restart, puts a human in the middle of a run. It is
  orchestration code; considered only if the share of carriers in runs exceeds a threshold.
  **Threshold: 50 % of subagent calls per run** (`gate-runner` + `file-copier`, counted from
  `logs/stop-audit.jsonl`). Measured 2026-09-18, the transformer article, four launches:
  31 of 84, that is 37 %; behind them 73 tool receipts — a carrier already takes two or three
  commands per call.
- **Hook probe** (0.5 h): check blocking with exit code 2 for `PreToolUse(Agent)` and `Stop`,
  and `additionalContext` for `PostToolUse`. The result goes into `docs/decisions/`.
- **Quote registry** `Q-…` and "row → quote" pairs for the requirements corrector — a ruler
  (R6), added after the `requirements` profile is working.

## 13. Open questions

- ~~Renaming the package `collimator/` → `facet/`~~ — done 2026-09-20 together with archiving the
  remains of the compiler (`library/templates`, `library/types`, `which-file-all.js`).
- ~~94 uncommitted changes from collimator in the working tree~~ — sorted out 2026-09-17:
  by the start of work eleven substantive ones remained; the line-by-line rewrite turned out to be
  `autocrlf` warnings with no difference in content. They went in as two commits: Confluence
  publishing (`63cf532`) and the facet specification (`94fa779`).
