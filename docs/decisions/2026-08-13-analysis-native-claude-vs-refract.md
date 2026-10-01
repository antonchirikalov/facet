# refract versus native Claude: does it make sense to continue

Date: 2026-08-13. The owner's question: the goal is working with documents, sometimes large
ones; perhaps the ready-made features of Claude Code give the same result more simply, and we
are looking in the wrong direction.

The analysis rests on the Claude Code documentation (collected 2026-08-13 via Tavily: the pages
`workflows`, `agent-teams`, `cross-session-messaging`, `sub-agents`, `skills`,
`agent-sdk/sessions`, `agent-sdk/session-storage`) and on the facts of the live article run
`attn-article/runs/run_20260811_121834`, which lasted two days and is analysed separately.

---

## 1. What refract is today, in numbers

Important for the verdict: the project is **not halfway through, it is mostly built**.

| Fact | Value |
|---|---|
| Engine code | 11 197 lines of Python |
| Tests | 13 359 lines, 539 pass, mypy strict + ruff clean |
| Phases 0–5 of the roadmap | all closed: engine, gates, loop/select, map, HITL, checkpoints, access tiers |
| API + UI | REST/WS + React SPA, 12 Playwright e2e specs, `refract serve` |
| Live check | four pipelines were run on the real CLI, money accounting reconciled |

That is, the 12–16 weeks the roadmap budgeted have already been spent. The question is not
"is it worth starting" but "is it worth **keeping** 11 thousand lines of our own engine next to
a platform that over recent months has taken over half of its tasks".

---

## 2. What Claude can now do by itself

Four primitives, and the main difference between them is **who holds the plan**.

| | Subagents | Skills | Agent teams | Dynamic workflows |
|---|---|---|---|---|
| What it is | a worker Claude spawns | instructions it follows | a lead supervising peer sessions | a script the runtime executes |
| Who decides what comes next | Claude, turn by turn | Claude, by the prompt | the lead, turn by turn | the script |
| Where intermediate results live | Claude's context | Claude's context | a shared task list | script variables |
| What is reusable | the worker definition | the instructions | the team definition | **the orchestration itself** |
| Scale | a few tasks per turn | the same | a handful of long-lived peers | tens to hundreds of agents per run |
| Interruption | the turn starts over | starts over | teammates carry on | **resumable within the same session** |

### Dynamic workflows — the closest thing to refract

A JS script that Claude writes itself and the runtime executes in the background while the
session is free. The script holds the loop, the branching and the intermediate data, so only
the final result reaches Claude's context. There is `agent()` with a **JSON schema**, under
which the subagent must call structured output, and the runtime validates it and makes the
model retry on a mismatch; there is `pipeline()` without barriers between stages and
`parallel()` with a barrier. A run can be saved as your own `/<name>` command in
`.claude/workflows/`, given `args`, and distributed through a plugin.

Runtime limitations listed explicitly in the documentation:

- **no human input in the middle of a run** — "for sign-off between stages, run each stage as
  a separate workflow";
- **the script itself has no access to the filesystem or the shell** — agents read and write,
  the script only coordinates; `import()` is forbidden altogether;
- up to 16 concurrent agents, 1000 agents per run;
- resumption **only within the same session**: "if you exit Claude Code during a run, the next
  session will start the workflow over";
- on resumption the cache breaks at the first unfinished agent, and **everything that started
  after it is recomputed**, even if it managed to finish.

Requires v2.1.154+. The "large workflow" warning threshold is 25 agents or 1.5 million
tokens. By default the `medium` size guideline applies (fewer than 15 agents).

### Agent teams — experimental

Off by default, enabled with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`. A lead plus
independent teammate sessions, a shared task list with file locks for claiming, mailboxes in
`~/.claude/teams/{team}/inboxes/{agent}.json`, hooks `TeammateIdle`, `TaskCreated`,
`TaskCompleted` (exit code 2 = block and return a remark). The stated limitations are
substantial: **`/resume` does not restore in-process teammates**, one team per session, no
nested teams, the lead cannot be changed, task statuses lag, shutdown is slow. The
documentation recommends 3–5 teammates, and "noticeably more tokens than a single session".

### Cross-session messaging

`ListAgents` + `SendMessage` between your sessions. The important part: **plain text only**, not
history and not files; repeats are throttled, the unread buffer is 50 messages per session.
This is a notification channel ("I broke what you are building on"), not an artifact transport.

### Agent SDK — what matters most for us

A library that runs the agent loop **in your process**, in Python or TypeScript. It provides
out of the box: built-in tools, hooks on lifecycle events, subagents, MCP, permissions,
**sessions with continue/resume/fork**, automatic loading of skills, commands and memory from
`.claude/`. Separately there is `SessionStore` — an adapter that mirrors transcripts to S3,
Redis or a database, so that a session started on one host can continue on another; the
documentation motivates this explicitly by durability, multi-host and audit. There are
ready-made reference adapters for S3, Redis and Postgres. Plus a separate product, Managed
Agents — hosted REST for long-running agents without your own sandbox.

---

## 3. Component-by-component comparison

| What refract does | Native counterpart | Remainder that does not exist natively |
|---|---|---|
| DAG from `pipeline.yaml`, topological sort, scheduler | a workflow script | declarativeness: YAML is diffed and validated with 40+ error codes before launch; a JS script is written by Claude anew for each task |
| Artifact types and port contracts | `schema` on `agent()` — JSON Schema with retry on mismatch | a type registry shared by all pipelines, and edge compatibility checking **before** the run |
| Content gates (`max_length`, `forbid_regex`, `min_entries`) with gate retry and remark injection | — | entirely a remainder: in a workflow this is written by hand in the script every time |
| `loop` with `verdict@v1` and rounds | a loop in the script + a verdict schema | nothing substantial: natively it is even more honest — the loop is visible as code |
| `map` over a collection, `on_item_failure`, `min_ok` | `pipeline()` / `parallel()`, `.filter(Boolean)` | assembly of the collection by the engine (I6) and marking of failed items in the output collection |
| Per-step workdir isolation, materialisation of `input/` | agents work in the repository; `isolation: 'worktree'` on a workflow agent | deterministic assembly of `input/`, immutability of terminal directories, the `attempts/<n>/` archive |
| The `PreToolUse` hook as the mechanical guarantee of I1 | **this is a native Claude Code hook** | nothing: we already stand on the platform |
| Ledger, `resume`, recovery after a crash | workflow resumption **within a session** | a large remainder: a run that lives for days and survives exiting the CLI |
| HITL checkpoints in the middle of a run (`waiting_human`, editing artifacts by hand, `answer … continue`) | forbidden inside a workflow | a large remainder |
| Per-step money accounting, `refract explain` | `/workflows` shows tokens per agent | durable, diffable accounting in the ledger after the run |
| Model per node | model override on an agent | nothing |
| Throttling, backoff on 429/529, retries | the CLI and SDK retry by themselves | nothing |
| Per-step secret injection (I8 — **not implemented** in refract) | permissions and request environment in the SDK | nothing; for us this is a debt, not an advantage |
| `AgentRuntime` + parsing the CLI's stream-json | the Agent SDK runs the loop in-process | nothing; pure duplication |
| REST/WS API + React SPA for a colleague without a terminal | **nothing at all** | a large remainder |
| Block catalogue for assembling a pipeline | — | a remainder, but its value depends on whether anyone assembles pipelines |

---

## 4. Where the native tools objectively fall short

Four points, each confirmed by the documentation and by our run.

**1. A run that outlives the session.** Our article run began on 11 August at 12:18 and
ended on 12 August at 14:38 — 26 hours, with crashes, a killed process and four
`resume`s. A workflow would not have survived it: "resumption works within the same session; if
you exit Claude Code during a run, the next session starts over". For documents where a
single analysis node takes 764 seconds and the writing loop an hour and more, this is no trifle.

**2. A human in the middle of a run.** Two checkpoints fired in our run — after `analyse` and
after `style` — and at them a human looked at the output and edited it by hand before letting
it go further. The workflow documentation rules this out in so many words: there is no human
input in the middle of a run, split it into separate workflows. For a document pipeline this is
exactly the point where quality is decided: the stylist produced findings, the human accepted
some of them, the editor applied only the accepted ones.

**3. Content gates with automatic retry.** A schema in a workflow checks the **shape** of the
JSON. Checking "the text is no longer than 14 000 characters", "the text does not contain
"it is worth noting" (a Russian cliché)", "the directory holds five files" and on
failure handing the agent its own remark back — in the native stack this is written by hand in
every script. For us it is a one-line rule in YAML, with separate counters for gate retries and
infrastructure retries.

**4. A human without a terminal.** Nothing native launches a pipeline for a colleague who
does not open the CLI. The desktop app is a chat, not a run panel with a graph and artifacts.

---

## 5. Where refract duplicates the platform — and that is pure cost

The honest half of the picture. What is duplicated is precisely what is most expensive to maintain:

- **our own runtime on top of the CLI**: launching a subprocess, parsing stream-json, killing
  processes in `close()`, heartbeats, auto-confirmations. The Agent SDK does this in-process and
  is maintained by Anthropic. The risk has already materialised once: the runtime had to be
  replaced entirely when opencode was swapped for Claude Code;
- **parallelism and throttling**: we have per-provider semaphores, the platform has 20
  concurrent subagents by default and 16 for workflows, plus its own retries;
- **assembling the prompt from the contract** — the SDK itself loads skills, commands and memory
  from `.claude/`;
- **the isolation hook** — already a platform mechanism, we simply use it;
- **secret injection** — on our debt list (`create_subprocess_exec` without `env=`, the agent
  receives the whole environment, including corporate MCP tokens); in the SDK it has its
  standard place.

The same category includes the unimplemented "our own minimal runner on litellm" from phase 5
and the Electron packaging: both ideas compete with the platform on its own field.

---

## 6. Checking against the live run: would the native stack have saved us?

Six failures of this session, and for each one — what would have happened on a workflow.

| Failure | On the native stack |
|---|---|
| 401 from the gateway: the bridge did not read the PAT from Credential Manager | **the same**, the cause is external |
| `resume` from a clean shell, environment variables not declared | **the same**: a skill can carry a preflight script, but there is no native environment declaration either |
| the engine killed together with a background command at minute 15 | **worse**: a workflow does not survive exiting the session at all |
| the agent looked for `paperbanana` on PATH, ignoring `$PAPERBANANA_BIN` | **the same**: this is prompt-following, it does not depend on the platform |
| the loop passed with an unfulfilled `revise` verdict on the round limit | **better**: the loop lives in the script, "skip silently" would have had to be written explicitly |
| my `.ps1` without a BOM broke the PowerShell 5.1 parser | my mistake, outside both systems |

The conclusion is uncomfortable but important: **four failures out of six have nothing to do with
whether our engine is our own or native**. The pain of this session was not in the architecture
but in an undeclared environment, an external gateway and prompts. The argument "our own engine
is more reliable" is not confirmed by our own data.

---

## 7. Three paths

### A. Continue as is

Everything is built, works, is covered by tests. The cost is maintaining 11 thousand lines
against a moving platform: every new Claude feature turns part of the engine into dead weight,
and every CLI change hits the runtime.

Makes sense if refract is a product for other people, not a personal tool.

### B. Tear down the engine, move the pipelines to native

The article pipeline = one saved dynamic workflow (`.claude/workflows/article.mjs`) plus
skills for the agents plus hooks for mechanical checks. Estimate: 1–2 weeks to move one
pipeline and debug it.

What is lost irrecoverably: a run longer than a session; a checkpoint with manual editing in the
middle of the pipeline (cured by splitting into three workflows and gluing them together by
hand); the UI for colleagues; pre-launch graph validation. Gates and types are rewritten into
the script, but anew in each one.

### C. Hybrid: refract as a thin durable orchestrator

Keep what does not exist natively: the DSL and validator, the type registry, gates,
checkpoints, the ledger with money accounting, the UI. Replace what duplicates the platform:

1. `refract/runtime/claude_code.py` — from driving a CLI subprocess to the **Agent SDK** (sessions,
   hooks, permissions, in-process subagents). This also closes debt I8;
2. wide fan-out (`map` over eight sources, four figures) — delegate to a **dynamic
   workflow as a single step**: the platform runtime already handles 16 in parallel and 1000 per run;
3. strike from the plans our own litellm runner, Electron and the chat builder.

Estimate: 2–4 weeks to replace the runtime, minus roughly 2–3 thousand lines of our own code.
Durability and HITL remain ours, the agent loop becomes the vendor's.

---

## 8. Verdict

**The project is worth continuing, but not in its current role.** refract is valuable for exactly
one layer — a durable pipeline with a human in the middle, typed artifacts and gates, plus a
face for whoever does not open a terminal. Everything else in it today competes with the
platform and loses to it on pace of development.

I recommend **path C**, and the decisive argument is not architectural but factual: our own
run lasted 26 hours, survived killed processes and relied on two human
checkpoints. A native workflow can do neither the first nor the second and, according to the
documentation, does not intend to: resumption within a session and the ban on input in the
middle of a run are declared properties, not unfinished work.

**The condition under which the answer changes to B.** If the answer to the question "should a
colleague without a terminal launch these pipelines themselves" is "no, it is a personal tool" —
then the UI, REST, WS, the catalogue and half of the spec cease to be of value, and the remainder
is honestly covered by saved workflows and skills. In that case continuing the engine means
paying in maintenance for what the platform gives for free, and the right step is to mothball
the engine, move one pipeline to a workflow and compare the result on the same article.

### UPDATED 2026-08-13: the owner answered — path B

The owner's clarification: refract is a **personal tool** for preparing documents (solution
designs, requirements) with illustrations via figgybanana; there are no colleagues without a
terminal; losing resume after a failure is acceptable. This triggers the condition above, and
the recommendation changes from C to **B**.

An additional argument found while working this through, which removes path C entirely: **the
Agent SDK requires authorisation with an API key, not a subscription**. The SDK page: third-party
developers are not permitted to use claude.ai login or subscription limits for their products,
including agents built on the Agent SDK; the legal FAQ page sends such developers to a key via
the Claude Console. Dynamic Workflows do not have this problem at all — they run inside Claude
Code on the corporate subscription we already have. That is, replacing the runtime with the SDK
would cost a separate key and billing for capabilities the workflow gives for free.

The working-through of path B, with a mapping of our entities, an artifact storage convention,
deterministic gates and a one-week migration plan, is in
`docs/plan-pipelines-as-dynamic-workflows.md`.

### What to do next week, regardless of the choice

Three things are useful in both scenarios, because they are defects of process, not of
architecture:

1. **Do not let a node with a `revise` verdict through.** Right now `max_rounds` means "give up
   silently": in our run the third-round verdict cost $2.05 and was thrown away, and the article
   shipped with three open remarks, including the softmax denominator, which does not add up for
   a reader with a pencil. An explicit `on_max_rounds: fail | checkpoint | pass` is needed.
2. **Declare environment requirements.** Five attempts out of twelve died on something that is
   checked in a millisecond: `PAPERBANANA_BIN` and three `SS_GATEWAY_*` are declared nowhere,
   and `validate` does not know about them. In the native stack this hole is exactly the same —
   so it has to be fixed either way, whether in `agent.yaml` or in a skill's preamble.
3. **Gate wording into the event stream.** Of the run's 1778 events exactly one carries the
   reason for a failure. Answering "what happened" requires opening twelve `gate_report.json` files.

---

## Appendix: sources

- `code.claude.com/docs/en/workflows` — runtime limits, resumption, saving
  workflows, size guidelines, cost
- `code.claude.com/docs/en/agent-teams` — architecture, hooks, limitations, v2.1.178+
- `code.claude.com/docs/en/cross-session-messaging` — `ListAgents`/`SendMessage`, limits
- `code.claude.com/docs/en/sub-agents` — limits of parallelism and nesting
- `code.claude.com/docs/en/skills` — skill structure, progressive file loading
- `code.claude.com/docs/en/agent-sdk/overview`, `/sessions`, `/session-storage` — the loop in
  your own process, continue/resume/fork, `SessionStore` for S3/Redis/Postgres
- `attn-article/runs/run_20260811_121834` — ledger, events, gate reports, critic verdicts
- `docs/PROGRESS.md`, `docs/pipeline-project-roadmap.md` — phase status and original estimates
