# Handoff: stage 0, the probe

> **A historical document, carried out 2026-08-13.** The probe has been run, the results are in
> `docs/probe-findings.md`, the service files (`probe.mjs`, `probe.js`, `probe-researcher.md`)
> have been deleted. The instructions below do not need to be carried out; they are kept so that
> it is visible how the question was posed and which answers counted as proof. What to do next is
> in `docs/plan.md` and `docs/findings-stage1.md`.

The files were created in a session that worked in `refract-claude` and was doing the analysis.
The probe **was deliberately not launched in that session**: agent and workflow definitions are
discovered at session start, and that session would not have seen `probe-researcher`.

## What to do in a new session

Open a session with the working directory `C:\Users\achirikalov\Documents\agents\collimator` —
specifically one **started after** these files were created, because agent and workflow
definitions are read at start.

The prompt as the first message:

> Read `docs/handoff.md` and `docs/plan.md`. Launch the saved workflow `probe` with
> `args` = `{"runDir": "probe-runs/first"}`. When it finishes, look in `/workflows` at the
> tool calls of the `research` agent and fill in `docs/probe-findings.md` for all seven
> items, with proof for each.

`args` are given as an object deliberately: how a slash command turns the free text after
`/probe` into `args` is decided by the model, while an object is unambiguous. The script accepts
both a string and `{runDir}`, and the topic can be replaced with your own —
`{"runDir": "…", "topic": "…"}`.

The run directory is mandatory: `Date.now()` is unavailable in a workflow script, the timestamp is
supplied by the call.

The run goes in the background. Watch it through `/workflows`: choose the run, enter the phase,
enter the agent — its prompt, **tool calls** and result are visible there.

## Seven unknowns and what counts as proof

| Unknown | Proof | If not confirmed |
|---|---|---|
| 1. Our handwritten script launches as a command | `/probe` started at all | launch through the `Workflow` tool by `scriptPath` |
| 2. `agentType` picks up `.claude/agents/probe-researcher.md` | in `/workflows` the `research` agent shows the system prompt from our file | the generator inserts the whole prompt into the `agent()` call; there will be no reuse of definitions |
| 3. A workflow agent reaches the Tavily MCP | the `research` agent's call list contains `mcp__tavily-remote__tavily_search`; the `tool_used` field in the result names the same | declare MCP at the project level (`.mcp.json`) and keep the frontmatter as a restriction, not a permission |
| 4. Artifacts are written to the run directory | the file `probe-runs/first/sources.md` exists, with three sources with addresses in it | revise the directory convention from `docs/plan.md` |
| 5. The gate works as a separate stage | `log()` has the line `gate 1: ok=… | … | {"chars":…,"prose_chars":…}` | the gate inside the producing agent, a check by a separate agent on top |
| 6. The gate-retry loop with feedback brings the artifact to fit | `gate_rounds: 2` in the result and `gate 2: ok=true` in the log | a loop in the prompt instead of a loop in the script |
| 7. The run directory comes in through `args` | the file landed exactly in `probe-runs/first/` | the path as a constant, generate a script for every run |

The threshold `--min-prose 2500` is deliberately set higher than what the first write will give:
the correction round **must** fire, otherwise item 6 stays unchecked. If the gate unexpectedly
passed on the first try, raise the threshold and run again — otherwise the check is incomplete.

## Possible interference unrelated to the idea

- **`/probe` did not appear in autocomplete.** The script is saved as `probe.mjs`, and which
  extension Claude Code scans in `.claude/workflows/` the documentation does not state directly.
  Rename it to `probe.js` or launch the workflow by `scriptPath` through the `Workflow` tool.
  This is interference with launching, not with the idea under test — it does not affect the
  seven items.
- **A permission request in the middle of a run.** The gate command and two Tavily tools are
  pre-approved in `.claude/settings.json`. If rule matching does not match the exact form of the
  command, there will be one request — confirm it and add the rule.
- **`python` on PATH.** The gate is called as `python -X utf8 tools/gate.py`. Checked on this
  machine, but if the session has a different shell, fix the command in `probe.mjs`.
- **The `haiku` model on the gate stage.** If the organisation does not allow it, the runtime
  will substitute another and say so in the run's interface. For the check this does not matter.

## After the run

Fill in `docs/probe-findings.md`: for each of the seven items — confirmed or not, and what it
changes in the design of the generator. Then delete `.claude/workflows/probe.mjs` and
`.claude/agents/probe-researcher.md` — they are service files. `tools/gate.py` stays; it is a
working tool.

Next is stage 1 according to `docs/plan.md`: moving `graph.py`, `registry.py`, `models/`,
`prompt.py` and `library/` over from refract, plus two generators.

## What has already been checked and need not be asked again

- the MCP servers are declared **globally** in `~/.claude.json` (`tavily-remote`, `pdf-reader`,
  `ss-gateway` and others), not per project — a new session inherits them;
- `tools/gate.py` was run on samples: it counts the characters of the file and of the prose
  separately (tables, code blocks and images are subtracted), catches forbidden phrases, counts
  the entries of a directory, reports in the same wording as the old engine
  (`min_entries 5 not met (got 1)`), and returns code 0 even on failure — the verdict travels in
  the JSON, and `--strict` changes the code too.
