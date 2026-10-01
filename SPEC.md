# facet — project specification

Version 0.1 · 2026-09-17 · status: accepted for work

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

Four scripts in `.claude/workflows/`:

| Script | Input | Output | State |
|---|---|---|---|
| `requirements.js` | folder `input/` with the client's documents | `reqs/_requirements.md`, `_traceability.md`, `_open_questions.md`, `_unresolved.md` | **to be written** (modelled on `solution-design.js`) |
| `solution-design.js`, stage `design` | `requirements.md` | `design.md` + figure placeholders, candidates from two models, `discovery-questions.md` | exists |
| `solution-design.js`, stage `discovery` | the client's documents (with `stages: ["requirements","discovery"]`) or a finished `requirements.md` | `discovery-questions.md` — questions to the client on gaps and contradictions, with domain research and references to requirement items | exists (separate since 2026-09-21) |
| `solution-design.js`, step `voice` of stage `requirements` | the client's documents and extracts | `client-voice.md` — the client's words verbatim with the speaker's role, ranking by the call, translation into checkable commitments with weights, vocabulary, who wants what, proposal order, what was not said | exists (since 2026-09-30) |
| `solution-design.js`, stage `client` | accepted `requirements.md` and `design.md`, `extracts/` | `requirements.client.md`, `design.client.md`, `client-id-map.json` — client editions without sources, tags and traces of the process, with client quotes and continuous numbering | exists (since 2026-09-28) |
| `explainer-article.js` | a one-sentence order | article, sources, round records | exists |
| `attn-figures.js` | a document with placeholders | PNG + manifest | exists |

The shape of `requirements.js`: `extract` (one agent per document, in parallel, ceiling
`cfg.maxSources`) → `write` (writer → corrector → critic, up to `cfg.maxRounds`, plateau) →
output to `reqs/`. A human reads `reqs/` and launches `/doc-design`.

The common header of every script:

```javascript
const cfg = {
  maxSources: 8, extractWorkers: 4,
  maxRounds: 3, correctors: true,
  candidateModels: ['sonnet', 'opus'],
  ...args.config,
}
```

The common part (cfg, `task()`, verdict and selector schemas, gate commands, audit) is copied
between scripts — `import()` is forbidden; `tests/test_workflows.py` makes sure the copies do not
drift apart.

## 5. Python is a ruler, not a foreman

`tools/`: `gate.py` (schema, sections, prose length, clichés from a file, empty headings),
`rounds.py` (round sheet, plateau, "what to continue with"), `listing.py` (what is actually there),
`busy.py` (whether a directory is busy), `newrun.py` (run directory name), `snapshot.py`,
`stop_audit.py` (the auditor hook), `confluence_publish.py`. Everything is called by an agent inside
a workflow or by the session at levels 1–2. New tools are allowed if they measure rather than
control. The first candidate: a gate rule "every row of the requirements table has a source
reference" for the `requirements` profile.

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

The first three profiles: `requirements` (the contract is already written in the critic's prompt —
move it out), `solution-design` (from the designer's prompt), `gap-analysis` (the first level-2
profile).

## 7. Exemplars

`exemplars/<type>/skeleton.md` — headings, one anonymised row per table, notes on "what is
mandatory here and why". `exemplars/<type>/why.md` — why this particular document was chosen. One
exemplar per type, chosen rather than accumulated. `exemplars.local.yaml` (`.gitignore`) — type →
path to the real document on disk; the agent reads the full exemplar if the path is available.

## 8. Client folder standard

As it has settled in real folders, to be recorded in `docs/run-layout.md`:

```
<client>/
  input/                    the client's sources as they arrived
  reqs/                     requirements: _requirements.md, _traceability.md, _open_questions.md
  design_<date>/            design: _solution_design.md, illustrations/, logs/, prompts/
  estimates/
  illustrations/
  <one-off documents>.md    levels 1–2, alongside
```

## 9. Target repository layout

```
facet/
  README.md                 entry point: three levels, "I want a document of type X → document-types.md"
  SPEC.md                   this document
  CLAUDE.md                 rules for Claude Code (inherits from collimator, being cut down)
  docs/
    document-types.md       type catalogue: level, profile, exemplar, script
    run-layout.md           client folder standard
    workflow-conventions.md script rules (moved from collimator's CLAUDE.md) + cfg
    decisions/              dated retrospectives and write-ups (moved from docs/)
  library/agents/           source of truth for agents (28)
  library/types/, library/templates/, library/style/
  .claude/agents/           generated
  .claude/workflows/        four scripts
  .claude/skills/           profiles
  .claude/settings.json     env + auditor hook
  exemplars/
  tools/
  tests/
  facet/                    emit_agents.py + models (renamed from collimator 2026-09-20)
```

## 10. Work plan

| Step | What | Estimate | Done when |
|---|---|---|---|
| 0 | Copy of collimator with history into `facet`; renaming in `pyproject.toml`, README; refract marked frozen | 1 h | `uv run pytest` green in facet |
| 1 | One home for agents: reconcile `library/agents` with the copies in refract, rebuild `.claude/agents`, add `skills:` to writers and critics | 0.5 d | `emit_agents` with no manual edits in `.claude/agents` |
| 2 | Documentation: README, `workflow-conventions.md`, `decisions/` (done 2026-09-21); `document-types.md`, `run-layout.md` | 1 d | a new session finds from the README how to make any type |
| 3 | Profiles `requirements` (2026-09-19), `solution-design` (2026-09-20), `discovery-questions` (2026-09-21), `gap-analysis` | 1 d | the critic and the writer of one type read one profile |
| 4 | Exemplars for three types + `exemplars.local.yaml` (`requirements` 2026-09-19, `solution-design` skeleton 2026-09-20) | 0.5 d | no client data in the repository |
| 5 | `requirements.js` modelled on `solution-design.js`; a run on the control input, comparison with three refract runs | 1–2 d | the document is no worse than refract's; carriers in the log — counted |
| 6 | Skill `/doc` for levels 1–2; trial on a gap analysis or a memo | 0.5 d | the result compared with a hand-made document of the same type |

The first visible result is step 5.

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
