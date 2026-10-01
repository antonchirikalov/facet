# collimator — a compiler from pipeline.yaml to Dynamic Workflows

A collimator brings scattered rays into one parallel beam: one declaration in, a parallel
fan-out of agents out. The naming line continues: spectra → refract → collimator. Package
`collimator/`, command `collimate`.

## Context

refract is a personal tool for preparing documents (solution designs, requirements) with
illustrations via figgybanana. Over the course of its development Claude Code has taken over
almost everything our engine does: parallel fan-out, context isolation, retries, structured
output with a schema, orchestration by script (Dynamic Workflows), hooks, custom subagents.

The analysis in `docs/analysis-native-claude-vs-refract.md` (the numbers and links to the
documentation are there too) showed that natively only three things are missing — a run longer
than a session, a human in the middle of a run, and content gates. The owner agreed to treat the
first as an acceptable loss, the second is covered by splitting into stages, the third by our
own check script.

Decision: **no engine is needed, a compiler is needed**. `pipeline.yaml` remains the single
source of truth; the workflow script and the subagent definitions are generated from it. The
model does not write the scripts — our generator does, so the set and number of agents are
set by the YAML, and the generated script is committed and diffed.

The key fact about the Agent SDK that removes the alternative: the SDK requires authorisation
with an API key ("third-party developers are not permitted to use claude.ai login or
subscription limits for their products, including agents built on the Claude Agent SDK"), while
Dynamic Workflows run inside Claude Code on the corporate subscription we already have. No key
is needed.

Decided separately: **a new repository**; refract is frozen as a source of prompts, types,
templates and the validator. The reason is not the amount of code (although 78% of the engine
and 76% of the tests die), but the documents: `CLAUDE.md` declares `SPEC.md` the source of
truth, and that is 1277 lines about execution — the scheduler, the ledger, recovery. Of the
invariants I1–I10, one and a half survive.

---

## Stage 0 — a minimal check, before any compiler

Goal: remove with a single run all the unknowns on which the design of the generator depends.
The script is written **by hand**, short, and thrown away afterwards.

### CLOSED 2026-08-13: 6 items out of 7, details in `docs/probe-findings.md`

Items 2–7 were confirmed: `agentType` picks up our definition (the model resolved to
sonnet from the frontmatter while the session was on opus), a workflow agent reaches the Tavily
MCP, artifacts are written to the run directory, the gate works as a stage with the same wording
as the old engine, the retry loop brings the artifact to completion, `args` arrive as an object.
Commit `c087bef`.

Item 1 failed — and was **closed by the documentation, not by a guess**: a slash command is
created by the commands or skills directory, not by `.claude/workflows/`. Verbatim: "custom
commands have been merged into skills — `.claude/commands/deploy.md` and
`.claude/skills/deploy/SKILL.md` both create `/deploy` and work the same way". So
`.claude/workflows/` is a script store, and the generator must write **two** files per segment:
the script and a wrapper skill that launches it by `scriptPath`. The question about the `.mjs`
extension goes away along with this; `probe.js` can be deleted.

Three findings that were not in the plan and that change stage 1:

1. ~~**A separate gate stage is expensive.**~~ **Wrong, corrected 2026-08-13.** By actual
   spending from the transcripts, a gate on haiku costs **1.6–6.8 cents per call** (96% of the
   volume is cache reads at $0.10 per million). On a pipeline with eight checks this is less than
   thirty cents against $37 per run. The conclusion "pull the gate inside the producing agent" is
   withdrawn: it saved pennies and made the agent certify itself. The gate stays separate — see
   the hook below.
2. **A name collision in the schema gives a non-deterministic answer.** The schema field
   `measures` and the key `measures` inside the report: one run nested the report into the field,
   another returned it flat. One contract, two results.
3. **The ledger exists.** The run record
   `~/.claude/projects/<project>/<session>/workflows/wf_*.json` carries `runId`, `scriptPath`,
   `args`, `result`, `logs`, `phases`, `agentCount`, `totalTokens`, `totalToolCalls`,
   `durationMs`, `status`, plus `journal.jsonl` with each agent's return. That is,
   `collimate explain` is real, and "no money accounting" from the analysis is partly withdrawn.

Below is what was checked and how (the historical part; the "if not" column has already played out).

| Unknown | How we check | If not |
|---|---|---|
| A saved script written by us launches as `/probe` | file `.claude/workflows/probe.mjs`, call `/probe` | launch through the `Workflow` tool by `scriptPath` |
| `agentType` picks up our agent definition | `agent(…, {agentType: 'probe-researcher'})` | the generator inserts the whole prompt into the call, without reuse |
| A workflow agent reaches the Tavily MCP | the researcher must return three sources on the topic | declare the MCP at project level (`.mcp.json`), keep the frontmatter as a restriction |
| Artifacts are written to the run directory | the researcher writes `<run>/sources.md`, the schema returns the path | revise the directory convention |
| The gate works as a separate stage | a cheap agent runs `tools/gate.py` and returns its JSON by schema | the gate inside the producing agent, a check on top |
| A gate retry loop with feedback | an artificially raised threshold, one round of correction | a loop in the prompt instead of a loop in the script |
| The run directory arrives through `args` | `/probe` with the directory path | the path as a constant in the script, generated for each run |

The check takes place **already in the new repository** — which also checks the layout. The
stage's artifacts:

- `.claude/workflows/probe.mjs` — about 60 lines;
- `.claude/agents/probe-researcher.md` — frontmatter `tools`, `mcpServers`, `model` + body;
- `tools/gate.py` — **real**, not thrown away: `--file`, `--max-length`,
  `--min-prose`, `--forbid` (repeatable), `--min-entries`; prints
  `{ok, problems, measures}` in the same format the engine currently writes to `gate_report.json`;
- `docs/probe-findings.md` — what was confirmed and what was not.

Runtime restrictions the script must respect (otherwise the run does not start): `meta` is
a pure literal without variables or calls; `import()` is forbidden; `Date.now()`, `new Date()` and
`Math.random()` are unavailable; the script has no access to the filesystem or the shell.

Effort: half a day.

---

## Stage 1 — the compiler

A new repository. Carried over from refract as is, together with the tests:

| From refract | Lines | Why |
|---|---|---|
| `refract/graph.py` | 1055 | loading and validating the graph, all error codes; depends only on the models and the registry |
| `refract/registry.py` | 498 | the artifact type registry, JSON schema checking |
| `refract/models/` (except `ledger.py`) | ~640 | formats of `pipeline.yaml`, `agent.yaml`, types |
| `refract/prompt.py` | 278 | **already** generates the prompt tail from the port contract (I5) — exactly what the generator needs |
| `tests/test_graph_validation.py`, `test_registry.py`, `test_models.py`, `test_templates.py` | ~3100 | coverage of what is carried over |
| `library/` in full | ~2200 | 22 prompts, 22 `agent.yaml`, types, 7 templates — the main asset |

Not carried over: `scheduler.py`, `cli.py`, `api/`, `runtime/`, `steps.py`, `metanodes.py`,
`explain.py`, `state.py`, `snapshot.py`, `artifacts.py`, `patch.py`, `builtins/` and their tests.

New code:

- `emit_agents.py` — `agent.yaml` + `prompt.md` → `.claude/agents/<slug>.md`. Mapping of
  `needs` into the frontmatter: `read`→`Read`, `edit`→`Write, Edit`, `bash`→`Bash`,
  `webfetch`→`WebFetch`, `vision`→`Read`, `"mcp:<server>"`→ `mcp__<server>` in `tools` plus
  `<server>` in `mcpServers`. Five agents out of 22 need MCP: three Tavily, one pdf-reader,
  `source_finder` both;
- ~~`emit_commands.py`~~ — **withdrawn 2026-08-14, not needed.** The issue was the extension, not
  the absence of a wrapper: `.claude/workflows/*.js` becomes a command by itself, `.mjs` is not
  scanned. Verified with three files against two. The generator writes `.js` and makes no
  wrappers. Details in `docs/findings-stage1.md`;
- **build-time checks** that stage 1 requires (all from live failures):
  a port name must not produce a `.md` with the words `analysis`, `report`, `findings`, `summary` —
  the platform forbids a subagent to write such a file, and the failure is silent; the gate
  threshold in the brief's units (prose versus file characters) and a warning if there is no
  ceiling; overlap of agent names with `~/.claude/agents/`;
- `emit_workflow.py` — nodes into script constructs:

  | Node | Construct |
  |---|---|
  | `type: agent` | `agent(prompt, {agentType, schema, model, label, phase})` |
  | `map` / `map_over` | `pipeline(items, …)`, `.filter(Boolean)`, a `min_ok` check |
  | `loop` | `for` with a verdict through `schema`; **an unfulfilled `revise` must reach a file and `log()`** |
  | `select` | `parallel()` of candidates + a judge agent with a schema |
  | `gate_rules` | a stage with `tools/gate.py` + a retry round injecting `problems`, schema field `report`. **The `SubagentStop` hook was checked on 2026-08-14 and does not fit this role:** it fires and the payload is complete, but exit code 2 is ignored for workflow agents — the agent finishes as if nothing happened. The hook remains a free detector and record; enforcement is in the script |
  | `checkpoints` | a boundary between segments: **one** file per segment, `.claude/workflows/<segment>.js`. It is also the slash command |
  | `params.model` | `{model: …}` on the call |
  | `meta.phases` | from node ids, so that `/workflows` shows our names |

- `cli.py` — `collimate build <pipeline.yaml> --workflows <dir> --agents <dir>`; prints
  the number of agents per run, to compare against the size guideline (by default `medium` —
  fewer than 15):

  ```
  $ collimate build library/templates/explainer_article.yaml
    validated  explainer_article.yaml  (0 errors)
    agents     6 → .claude/agents/
    segments   3 → /article-research /article-write /article-figures
    agents per run: 9 + 8 (map) + 4 (figures) = 21
  ```

Guarantees that move from the engine into the generator: validation before generation (what does
not pass our validator will not compile), deterministic output (one YAML — one and the same
script, checked by a golden-file test), explicit policies (a silent pass through a loop is
impossible, because the generator does not emit it).

Effort: 3–4 days.

---

## Stage 2 — migrating a pipeline and reconciling

First — `explainer_article.yaml` (158 lines), the only one verified by a live run:
there is something to compare against. It also contains everything hard: a loop with a critic,
two checkpoints, a `map` over eight sources, an illustrator with an external CLI.

Segments by checkpoint give three commands: `/article-research`, `/article-write`,
`/article-figures`. This also removes the size problem — 23 steps in one workflow run into the
guideline.

Reconciliation with `attn-article/runs/run_20260811_121834`: the length of the final text (it was
13 662 characters against a brief of 8–12 thousand), the number and substance of the critic's
remarks (it was 11 over three rounds), four figures with a manifest, cost (it was $37.31, of which
57% was the writing loop).

Effort: 2 days.

---

## Handing work over between sessions

Agent and workflow definitions are discovered **at session start**: a file created in the middle
of a session does not get into its registry. Hence the order.

### Done (session in refract-claude, commit `02583c8`)

The repository `~/Documents/agents/collimator/` has been created, the tree is clean, 12 files:
`tools/gate.py` (run through all branches), `.claude/agents/probe-researcher.md`,
`.claude/workflows/probe.mjs` (the body and `meta` pass `node --check`, `meta` is a pure
literal), `.claude/settings.json` with `env` and pre-approved commands, `CLAUDE.md`,
`README.md`, `.gitignore`, `docs/` with the plan, two analyses, `handoff.md` and a stub of
`probe-findings.md`.

The probe was deliberately not launched: that session cannot see its own agent.

### Done: the probe was run (session in collimator, commit `c087bef`)

Two runs of one script, `wf_d83f0776-0a8`; results and evidence for each item are in
`docs/probe-findings.md`.

### Remaining: stage 1 in the collimator session

Development happens **in a session whose working directory is `collimator`**, and this is not
hygiene: in a refract session its `CLAUDE.md` is in force, declaring `SPEC.md` — the spec of the
closed engine — the source of truth. Working on the generator under the engine's instructions
means arguing with oneself.

```
cd C:\Users\achirikalov\Documents\agents\collimator
claude
```

As the first message:

> Read `docs/plan.md` and `docs/probe-findings.md`. Start with `tools/gate.py`: normalisation
> of an msys path (`/c/Users/…` → `C:\Users\…`, if the file is not found at the original path) plus
> tests for all branches. Then `emit_agents.py` as per the plan.

After that the scaffolding can be removed: `.claude/workflows/probe.mjs`, `probe.js` and
`.claude/agents/probe-researcher.md`. `tools/gate.py` stays, it is working code.

The note about the collimator decision lives in the memory of the **refract** project, and the
collimator session will not see it — memory is bound to the directory. Nothing essential is lost
by this: everything is in the repository (`docs/plan.md`, `handoff.md`, `probe-findings.md`, the
two analyses). The analysis session remains available through `/resume`.

## Checking the result

1. **Stage 0**: `/probe <directory>` completes, the directory holds a file from the researcher with
   three sources found through Tavily; the run log shows that the gate fired and that there was a
   correction round; `docs/probe-findings.md` is filled in.
2. **Stage 1**: `pytest` on the carried-over tests is green; `build` does not fail on any of the
   seven templates in `library/templates/`; a golden test for deterministic output; the generated
   agent definitions contain `mcp__tavily-remote` for exactly those three agents whose
   `needs` names it; **the wrapper is checked for free** — the first generated segment
   either appears in autocomplete as `/<segment>` or it does not; `gate.py` finds the file both by
   the path `C:\…` and by `/c/…`.
3. **Stage 2**: the three commands pass on the same article; the final text is ≤ 14 000 characters
   (gate), `UNRESOLVED.md` is either absent or lists the open remarks explicitly; four PNGs
   and a manifest; the total cost is comparable to $37 or lower.

---

## Risks

- **`mcpServers` on an agent inside a workflow.** For teammates in teams this frontmatter is
  explicitly ignored; there is no direct statement in the documentation about workflow agents.
  Stage 0 is needed exactly for this reason.
- **Losing a run on exiting the session** is accepted as tolerable. Mitigation: short
  segments and many small agents instead of one long one — on resumption the cache breaks at
  the first unfinished agent, and everything that started after it is recomputed.
- **The external CLI's environment.** `PAPERBANANA_BIN` and three `SS_GATEWAY_*` live in
  `.claude/settings.local.json` — a file in `.gitignore`, so machine paths and the profile UUID do
  not get into history. `KIMI_BASE_URL`, `GUIDELINES_PATH` and `REFERENCE_SET_PATH` were added to
  them: figgybanana resolves its data paths from the current directory, and we call it from
  another one, and without absolute paths the reference corpus is silently not used.
- **The compiler may turn out to be excessive** for seven templates of a personal tool. The decision
  is made after stage 0: if a hand-written segment reads better than a generated one, it is more
  honest to keep hand-written scripts and not drag along 2470 lines of validator.
- ~~**The workflow file extension.**~~ Withdrawn **twice, and the second time correctly**: first it
  was decided that a wrapper cures it, then it was checked — the issue is precisely the extension.
  `.claude/workflows/*.js` becomes a command by itself, `.mjs` is not scanned. No wrappers are
  needed.
- ~~**Passing `args` by slash command.**~~ Withdrawn: the wrapper substitutes `$ARGUMENTS[0]` into the
  `args` object, free text no longer takes part in the model's parsing.
- ~~**The `SubagentStop` hook — an unverified assumption.**~~ **Checked 2026-08-14, the assumption was
  not confirmed.** The hook fires for workflow agents, and the payload carries everything needed for
  branching (`agent_type`, `agent_id`, `agent_transcript_path`, `stop_hook_active`) — that is,
  both of the plan's concerns, applicability and a permanent block, would have been removed by it.
  But **exit code 2 is ignored**: an agent that claimed a non-existent file finished calmly. So the
  hook is a detector and a record at zero tokens, and enforcement remains a stage in the script.
  Implementation: `tools/gate_hook.py`.
- **A gate threshold that cannot be violated.** On the probe's first run the gate passed at once,
  and the retry loop would have remained unchecked — the threshold had to be raised by hand.
  `collimate build` must warn if a threshold is obviously met by the first draft: otherwise a whole
  branch of the pipeline is never executed, yet looks working.
- **The shape of a shell command is not reproducible.** One and the same line went sometimes to
  `Bash` with the path rewritten as `/c/Users/…`, sometimes to `PowerShell` with a `cd …;` prefix.
  Permissions have to be written for both; `gate.py` normalises the msys path itself, because
  through PowerShell such a path will not survive to Python (in git-bash it is rewritten
  automatically — checked).
- **`settings.json` in git.** It holds machine paths and the gateway profile UUID. For a local
  personal repository this is fine; if a public remote appears, the `env` block moves to
  `.claude/settings.local.json` and goes into `.gitignore`.

---

## Layout of the new repository

`~/Documents/agents/collimator/` — a separate repository; `refract-claude` is left untouched.

```
collimator/
  collimator/
    graph.py            ← from refract, unchanged
    registry.py         ← from refract, unchanged
    prompt.py           ← from refract: prompt tail from the port contract (I5)
    models/             ← from refract, without ledger.py
    emit_agents.py      ← new: agent.yaml + prompt.md → .claude/agents/<slug>.md
    emit_workflow.py    ← new: nodes → script, segments by checkpoint
    cli.py              ← new: collimate build …
  library/              ← from refract in full: 22 agents, types, 7 templates
  tools/gate.py         ← from stage 0
  tests/                ← the four carried-over suites + generator tests
  .claude/
    agents/             ← GENERATED, goes into git as a build result
    workflows/          ← GENERATED
    settings.json       ← env: PAPERBANANA_BIN, three SS_GATEWAY_*
  docs/                 ← probe-findings.md, the carried-over write-up of pitfalls
  CLAUDE.md             ← its own: "we generate for Claude Code, we do not run agents ourselves"
```

The generated output is committed: then the diff shows exactly what changed in the orchestration
when the YAML is edited, and this also serves as a golden test for determinism.

The new project's `CLAUDE.md` does not inherit refract's invariants: I3, I7, I9, I10 concerned
a runtime that no longer exists. I5 survives (instructions from the contract — now the generator's
job) and I6 (an agent does not produce collections — now `pipeline()` in the script). I1 is provided
by Claude Code itself with its hook.
