# Probe results (stage 0)

Run: `probe-runs/first` · date: 2026-08-13 · two runs of one script, `wf_d83f0776-0a8`.

The result of the second run (which is also the full one):

```json
{ "path": "…/collimator/probe-runs/first/sources.md",
  "tool_used": "mcp__tavily-remote__tavily_search",
  "sources": 3, "gate_ok": true, "gate_rounds": 2,
  "measures": { "chars": 8155, "prose_chars": 8113,
                "regex": { "it is worth noting|it is important to understand": 0 } } }
```

(The regex holds two Russian clichés: "it is worth noting", "it is important to understand".)

The first run passed the gate on the first try (a threshold of 2500 against 2770 characters of
prose), which means item 6 would have stayed unchecked. On the direct instruction of
`docs/handoff.md` the threshold was raised to 4500 and the run was resumed via `resumeFromRunId`:
the researcher was served from the cache, the gate and the correction round ran again. The only
edit to the script between the runs is `MIN_PROSE`.

| # | Unknown | Result | What is visible as proof | What it changes |
|---|---|---|---|---|
| 1 | Our handwritten script launches as `/probe` | **no** | `Workflow({name:'probe'})` → `Workflow "probe" not found. Available: deep-research, code-review`; launching by `scriptPath` started immediately | a segment does not get a slash command by itself: either a wrapper in `.claude/commands/` or launching by `scriptPath` |
| 2 | `agentType` picks up `.claude/agents/probe-researcher.md` | **yes** | `agentType: "probe-researcher"` in the run, the agent's `meta.json`, `attributionAgent` in the transcript, the model `claude-sonnet-5` from the frontmatter while the session is on opus | `emit_agents.py` stays as in the plan |
| 3 | A workflow agent reaches the Tavily MCP | **yes** | a `mcp__tavily-remote__tavily_search` call in `research`, `attributionMcpServer: "tavily-remote"`, `tool_used` names the same name; `expand` has four more `tavily_extract` | a per-project `.mcp.json` is not needed, the `"mcp:<server>"` mapping works |
| 4 | Artifacts are written to the run directory | **yes** | `probe-runs/first/sources.md`, 13,779 bytes, three sources with addresses, all three actually opened | the directory convention from the plan stays |
| 5 | The gate works as a separate stage | **yes** | `gate 1: ok=false \| min_prose 4500 not met (got 2770) \| {"chars":2782,…}`, the wording matches the old engine | permission rules must cover both Bash and PowerShell; the gate must accept any form of path |
| 6 | The gate-retry loop brings the artifact to fit | **yes** (on the second attempt) | `gate_rounds: 2`, `gate 2: ok=true` at 8113 characters of prose; the text of the gate's remark is in `expand`'s prompt | set the threshold in templates from measured facts, otherwise the loop goes unchecked |
| 7 | The run directory comes in through `args` | **yes** | `args = {"runDir":"probe-runs/first"}`, the file landed exactly in `probe-runs/first/` | there is no need to generate a script per run |

## Details on the disputed items

**Item 1 is the only failure.** It matters that this is not an effect of "a file created in the
middle of a session": the session started after commit `02583c8`, and it did see the agent
definition from `.claude/agents/` — `probe-researcher` was in the registry and launched. That is,
the agents directory is scanned, but `probe.mjs` did not appear in the list of workflows. A copy
`probe.js` made in the middle of this session did not appear either, but that is expected and does
not settle the question of the extension. **Open:** whether `.claude/workflows/*.js` is scanned.
It is checked with one line in the next session — `probe.js` has been left on disk for this.

**Item 2: the proof is indirect but unambiguous.** The text of the system prompt is not in the
transcript: only `assistant` and `user` records are written, and a search for lines from
`prompt.md` gives zero. Three independent things prove it: `agentType` and `attributionAgent`
name our agent; the model resolved to `claude-sonnet-5`, although the session and the script
itself run on opus — so `model: sonnet` from the frontmatter was applied; the file was written
exactly in the format from the body of the prompt (`# Sources: <topic>`,
a heading, an address, two or three sentences). The Tavily tool was available, and it is declared
in the same place, in `tools`.

**Item 3: a caveat about the scope of the check.** The MCP servers are declared globally in
`~/.claude.json`. The run proved that a workflow agent reaches them and that the `mcpServers`
frontmatter does **not get in the way**. It did not prove that the frontmatter by itself
**permits** anything — for the generator this does not matter (we rely on the global declaration
anyway), but it is worth writing down: the risk from `docs/plan.md` has been removed not fully,
but in the part that matters.

**Item 5: the form of the command does not reproduce.** The script gives one string every time,
but different things go to the shell: in the first run `Bash` with the path rewritten as
`/c/Users/…`, in the second `gate:1` took `PowerShell` with a `cd …;` prefix, and `gate:2` took
`Bash` with a quoted path. Permission was not asked once. So a rule of the kind "exact form of
the command" is unreliable, and the gate must not depend on which shell called it.

## Observations nobody expected

- **A name collision in the schema gives a non-deterministic answer.** The gate's JSON has a key
  `measures`, and the schema field is named the same. In the first run haiku nested the whole
  report inside the field: `measures: {ok, problems, measures:{…}}`. In the second run a prompt
  of the same structure gave a flat, correct object. One and the same contract, two different
  results — for the generator this is an edit: name the field `report`, and normalise in the
  script (`m.measures?.measures ?? m.measures`).
- **Resuming a run loses the metadata of a cached agent.** For `research` served from the cache,
  the interface shows the model `claude-opus-5[1m]` and an empty `agentType`, although in fact it
  ran on sonnet under our definition. The cached result itself is correct. A display artifact,
  but misleading when debugging the generator through the interface.
- **`resumeFromRunId` is a working tool, not an emergency one.** Edit one constant, resume, the
  expensive stage comes from the cache, only the tail is replayed. For debugging
  `emit_workflow.py` this is cheaper than a full run.
- **A declared phase with no agents is allowed.** In the first run `Expand` stayed empty, and the
  runtime did not complain about it.
- **The correction round works by edits, not by rewriting.** `expand` did a `Read`, four
  `tavily_extract` and three targeted `Edit`s — the addresses were not touched, as the prompt
  required. 13 tool calls against 3 for `research`.
- **Cost and time.** The first run: 2 agents, 43,750 tokens, 39 s. The second: 4 agents (one from
  the cache), 96,998 tokens, 129 s. The gate on haiku is about 23,800 tokens per call, that is,
  the cheap stage does not get any cheaper: almost all of it is the agent's system prompt.

## Decision on stage 1

The compiler idea is confirmed: 6 items of 7, and the failed one is about the way of launching,
not about the design. Against `docs/plan.md` the following changes.

1. **The node table, the `checkpoints` row.** "A separate script file per segment" is not
   enough: a file in `.claude/workflows/` does not become a command. The generator either
   additionally writes a wrapper in `.claude/commands/<segment>.md`, or `collimate build` prints
   a ready `Workflow` call by `scriptPath`. Choose after checking the `.js` extension.
2. **`gate_rules` in `emit_workflow.py`.** The schema field is `report`, not `measures`;
   normalisation of the nesting in the script; the threshold is taken from the template, but
   `collimate build` warns if the threshold cannot be violated by the first write — otherwise
   the loop is never checked.
3. **Permissions.** The generator prints rules for both `Bash` and `PowerShell`.
4. **`emit_agents.py` — no changes.** Items 2 and 3 were confirmed in the form the plan counted
   on.

## Not closed

- ~~whether `.claude/workflows/*.js` is scanned~~ **Closed 2026-08-14: yes, it is scanned, and
  this is the answer to item 1.** `ext-js.js` appeared in the command list, `tools-probe.mjs`
  never did, and `attn-article.js`, `attn-figures.js` and `critic-check.js` all appeared. The
  extension is what matters: `.mjs` is not scanned, `.js` becomes a command by itself. Wrapper
  skills are not needed, details in `docs/findings-stage1.md`;
- the string form of `args` (`/probe probe-runs/first`) was not checked — the object was;
- the stage 0 service files (`probe.mjs`, `probe.js`, `probe-researcher.md`) were deleted after
  item 1 was closed.
