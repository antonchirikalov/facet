# Document pipelines on Dynamic Workflows: a detailed study

Date: 2026-08-13. The owner's clarification: the project is a **personal tool** for preparing
documents (solution designs, requirements and so on) with good illustrations through
figgybanana. Resuming after a failure is not critical. The question: can we have the same
pipelines on Dynamic Workflows, generating scripts from our pipelines, and can scripts save
intermediate artifacts.

Short answers: **no API key is needed**, **artifacts can be saved and this is the standard
way**, **the pipelines carry over almost one to one**. Below is exactly how, with caveats.

---

## 1. About the API key: needed or not

It is important here not to confuse two different scenarios, because the Anthropic documentation
separates them explicitly.

**Dynamic Workflows — no key is needed.** A workflow runs inside Claude Code, which is already
authorised by the corporate subscription. Workflow agents "use the session's model", and runs
"count against your plan's limits, like any other session". No separate authorisation, billing
or key appears. The same goes for skills, subagents, hooks and saved `/name` commands.

**Agent SDK — this is where a key appears, and it is not a technical detail but a licensing
one.** The SDK page: "Unless previously approved, Anthropic does not allow third-party developers
to offer claude.ai login or their rate limits for their products, including agents built on the
Claude Agent SDK. Use API key authentication." The legal page: OAuth authentication "is intended
exclusively for purchasers of the Free, Pro, Max, Team and Enterprise plans and is designed for
ordinary use of Claude Code and other native Anthropic applications", and "developers building
products or services, including those using the Agent SDK, should use API key authentication
through the Claude Console or a supported cloud provider".

A subtlety in favour of a personal tool: the usage policy section says that "the advertised
limits of the Pro and Max plans assume ordinary individual use of Claude Code **and the Agent
SDK**", and the `CLAUDE_CODE_OAUTH_TOKEN` token exists as a standard feature and is authorised by
the subscription (Pro, Max, Team, Enterprise), able to make only model requests. That is, a
personal tool for oneself fits within this frame; a product for colleagues or clients no longer
does, and there a key is needed.

**The conclusion for us.** The workflow path is clean both in licensing and technically: nothing
beyond the subscription we already have. The SDK path drags us into a conversation about keys and
about where "ordinary individual use" ends — while the runtime would have to be rewritten for
capabilities that workflows already provide. **This removes the SDK item from the
recommendation**: if the project is personal, there is no reason to switch refract's runtime to
the SDK.

---

## 2. Artifacts: they can be saved, but the contract moves into the prompt

The restriction "a script has no access to the filesystem" sounds fatal, but in practice it
means a different division of labour than in refract:

| | refract | Workflows |
|---|---|---|
| Who writes files | the agent into its `output/`, the engine lays out the inputs | the agent, with ordinary Write/Edit/Bash |
| Who sets the directory layout | the engine, mechanically | the prompt and a convention checked by the gate |
| Who passes data between steps | the engine via `input/` | the script: it passes **paths** and structured JSON |
| Who guarantees isolation | workdir + hook | `isolation: 'worktree'` on the agent, where parallel edits are needed |

A script does not read files — it **addresses** them. The schema on `agent()` is exactly that
mechanism: the agent must return a structured answer, and we put the path and the measurements
into it. The script then branches on those numbers without ever opening the file itself.

The working convention for our case:

```
docs-runs/<YYYYMMDD-HHMM>-<slug>/
  01-brief/brief.md
  02-sources/<slug>.md              ← fan-out, one file per source
  03-analysis/analysis.json
  04-draft/article.r1.md            ← a version per round, not an overwrite
  04-draft/verdict.r1.json
  04-draft/article.r2.md
  05-style/findings.json
  06-final/article.md
  07-figures/<slug>.png
  07-figures/manifest.json
  run.md                            ← what was done and with what, written by the last agent
```

A version per round instead of overwriting replaces our `attempts/<n>/`: the history of rounds
stays on disk, and `git diff` shows exactly what the critic corrected. The run directory gets a
timestamp — we pass it as `args`, because `Date.now()` is unavailable in a script.

---

## 3. Gates: deterministic, without an LLM judge

Our gates (`max_length`, `forbid_regex`, `min_entries`) are arithmetic and regular expressions;
there is no reason to hand them to a model. A script does not read files, but an agent can run
our own script:

```bash
python tools/gate.py --file 06-final/article.md \
  --max-length 14000 \
  --forbid "it is worth noting|it is important to understand|let us break it down" \
  --forbid "let us dive into|the key takeaway|in conclusion" \
  --min-prose 8000
```

(The forbidden phrases stand for Russian AI-text clichés, written here in English.)

`tools/gate.py` prints the same JSON the engine writes now: `{ok, problems, measures}`. The check
stage is the cheapest agent with a single task, "run the command and return its output by the
schema". In the script it is an ordinary loop with feedback:

```javascript
let article = await agent(writePrompt(brief), {agentType: 'writer', schema: DOC})
for (let round = 1; round <= 3; round++) {
  const gate = await agent(gateCmd(article.path), {model: 'haiku', schema: GATE})
  if (gate.ok) break
  log(`gate failed: ${gate.problems.join('; ')}`)
  article = await agent(fixPrompt(article.path, gate.problems), {agentType: 'writer', schema: DOC})
}
```

This is exactly our gate retry with remark injection, only the policy is visible as code. And
this is also where a defect we found in a live run gets fixed: when it ran out of rounds, refract
"passed silently", whereas in a script a silent pass has to be written explicitly — otherwise the
loop ends, and the unaddressed remarks stay in a variable that the script is obliged to put
somewhere.

Also: our YAML gate cannot currently check **prose without markup** (`--min-prose`), and the
brief's "8–12 thousand characters" means exactly that.

---

## 4. Checkpoints: stage boundaries instead of a stop in the middle

There is no human input in the middle of a run — the documentation advises splitting into
stages, and for documents this is rather a plus: there are only two points where you actually
want to look with your own eyes anyway.

```
/doc-research  <topic>      → 01-brief, 02-sources, 03-analysis
   ← you read analysis.json, edit by hand, decide: go on or reformulate the brief
/doc-write     <directory>  → 04-draft (loop with a critic), 05-style, 06-final
   ← you read the stylist's findings.json and decide which edits to accept
/doc-figures   <directory>  → 07-figures + manifest
```

Three saved commands in `.claude/workflows/`, each taking `args` with the run directory. Between
them you are in an ordinary session: you look at the artifacts, edit files, launch the next one.
This is more honest than our `waiting_human`: there the run hung as a process and died together
with it — this has already happened to us.

---

## 5. How our entities carry over

The mapping is almost mechanical, and this is the main argument that the approach is workable:

| refract | Where it moves |
|---|---|
| `library/agents/<name>/prompt.md` + `agent.yaml` | `.claude/agents/<name>.md`: frontmatter with `tools` and `model`, the body is the prompt |
| A `type: agent` node | a call `agent(prompt, {agentType: '<name>', schema})` |
| Input/output instructions generated from the contract (I5) | the same generator, but as text in the stage prompt; the schema is passed as `schema` |
| `map` over a collection, `workers`, `on_item_failure: skip`, `min_ok` | `pipeline(items, stage1, stage2)` + `.filter(Boolean)` + a length check |
| `loop` with `verdict@v1`, `max_rounds` | `for`/`while` in the script, the verdict via `schema` |
| `select` with `selection@v1` | `parallel()` of candidates + a judge agent with a schema |
| `gate_rules` | `tools/gate.py` + a cheap check stage (section 3) |
| `checkpoints` | boundaries between saved workflows (section 4) |
| Artifact types `artifact_types.yaml` | JSON Schema for control artifacts + a path convention for documents |
| The `PreToolUse` hook (I1) | stays a Claude Code hook, unchanged |
| Per-step secrets (I8, in our backlog) | `env` in `.claude/settings.json`, once per project |
| Model per node | `{model: 'opus'}` on the stage |
| The ledger and `refract explain` | `/workflows` during the run + `run.md`, written by the last agent |
| REST/WS API, React SPA, block catalogue | **does not move: not needed for a personal tool** |

Separately, about our perennial source of pain: `PAPERBANANA_BIN` and the three `SS_GATEWAY_*`
are declared once in `env` in `.claude/settings.json` — and no longer depend on which shell the
launch came from. Five of the twelve failures of the last run were about exactly this, and
natively it is cured better than in our setup.

---

## 6. A script skeleton for our case

The writing stage as an example of the shape. This is not a finished file, but a shape to be
agreed on:

```javascript
export const meta = {
  name: 'doc-write',
  description: 'Document draft with a critic loop, stylist, final',
  phases: [
    { title: 'Draft',  detail: 'writer + critic in rounds' },
    { title: 'Gate',   detail: 'deterministic checks' },
    { title: 'Style',  detail: 'stylist in report mode', model: 'opus' },
  ],
}

const run = args.runDir                    // the run directory comes from outside
const DOC = { type: 'object', required: ['path', 'chars'], properties: {
  path: { type: 'string' }, chars: { type: 'integer' } } }
const VERDICT = { type: 'object', required: ['verdict', 'issues'], properties: {
  verdict: { enum: ['approve', 'revise'] },
  issues: { type: 'array', items: { type: 'object', required: ['section', 'note'],
    properties: { section: { type: 'string' }, note: { type: 'string' } } } } } }

phase('Draft')
let doc = await agent(
  `Build a draft from ${run}/03-analysis/analysis.json and ${run}/01-brief/brief.md. ` +
  `Write it to ${run}/04-draft/article.r1.md and return the path and the number of characters.`,
  { agentType: 'writer', schema: DOC })

let unresolved = []
for (let r = 1; r <= 3; r++) {
  const v = await agent(
    `Check ${doc.path} against ${run}/01-brief/brief.md. Write the remarks ` +
    `to ${run}/04-draft/verdict.r${r}.json.`,
    { agentType: 'critic', model: 'opus', schema: VERDICT })
  if (v.verdict === 'approve') { unresolved = []; break }
  unresolved = v.issues
  log(`round ${r}: ${v.issues.length} remarks`)
  doc = await agent(
    `Fix ${doc.path} according to ${run}/04-draft/verdict.r${r}.json. ` +
    `The result is ${run}/04-draft/article.r${r + 1}.md.`,
    { agentType: 'writer', schema: DOC })
}

// what refract did silently: unaddressed remarks must be visible
if (unresolved.length) {
  await agent(
    `Write to ${run}/04-draft/UNRESOLVED.md the remarks that remained after three ` +
    `rounds: ${JSON.stringify(unresolved)}. Fix nothing.`,
    { model: 'haiku' })
  log(`WARNING: ${unresolved.length} remarks not closed, see UNRESOLVED.md`)
}

phase('Gate')
for (let attempt = 1; attempt <= 3; attempt++) {
  const g = await agent(
    `Run: python tools/gate.py --file ${doc.path} --max-length 14000 ` +
    `--forbid "it is worth noting|it is important to understand" --min-prose 8000 . Return its JSON.`,
    { model: 'haiku', schema: GATE })
  if (g.ok) break
  doc = await agent(`Fix ${doc.path}: ${g.problems.join('; ')}`,
    { agentType: 'writer', schema: DOC })
}

phase('Style')
const findings = await agent(
  `Review ${doc.path} as a critic of Russian text, as a report. Write ` +
  `${run}/05-style/findings.json, each remark with decision: pending.`,
  { agentType: 'article-critic', model: 'opus', schema: FINDINGS })

return { draft: doc.path, findings: findings.path, unresolved: unresolved.length }
```

What is important to notice here:

- the run directory comes in through `args` — there is no `Date.now()` in a script, it is
  forbidden so as not to break resuming;
- `meta` must be a **pure literal**: no variables, no calls, no template strings;
- `import()` is forbidden — all work with libraries lives inside the agents' tasks;
- fan-out over sources is done with `pipeline(sources, read, takeNotes)`, up to 16 at once, and this is exactly our `map` with `workers`;
- where agents edit files in parallel, the stage gets `isolation: 'worktree'`.

---

## 7. What we lose and what covers it

| Loss | How painful | What covers it |
|---|---|---|
| Resuming a run after leaving the session | accepted as tolerable | the stages are short; artifacts are on disk, the next stage can be relaunched from the same directory |
| Resuming cuts the cache off at the first unfinished agent, and everything that started after it is recomputed | noticeable on fan-out | many small agents instead of one long one — the documentation advises exactly this |
| Pre-launch validation of the graph (40+ error codes) | moderate | a saved script has a stable shape; an error in the schema surfaces at the first stage, not the seventh |
| A ledger with money per step and `refract explain` | moderate | `/workflows` shows tokens per agent live; `run.md` writes the summary |
| `waiting_human` in the middle of a run | not painful | stage boundaries, and they are more reliable: our process with a checkpoint has already died |
| The type registry and port compatibility checking | moderate | JSON Schema on control artifacts + a gate on the path convention |
| UI, REST, WS, block catalogue | not painful | a personal tool does not need them |

A limit worth remembering in advance: the default workflow size guideline is `medium`, that is,
fewer than 15 agents, and the "large workflow" warning fires at 25 agents or 1.5 million tokens.
Our article run is 23 steps, and as a single workflow it runs into this guideline. Splitting into
three stages solves this too.

---

## 8. Migration plan

The order is such that at every step there is something usable.

1. **`tools/gate.py`** — move the checks out of the engine into a standalone script with the same
   JSON output. Half a day, and it is useful regardless of the outcome: it can be called from
   refract too.
2. **Agents in `.claude/agents/`** — move `writer`, `critic`, `article-critic`, `style-editor`,
   `illustrator`, `source-finder` from `library/agents/` into subagent definitions. The prompts
   are already written; the wrapper changes. A day.
3. **`env` in `.claude/settings.json`** — declare `PAPERBANANA_BIN` and the three
   `SS_GATEWAY_*`. Half an hour, and it closes the most frequent source of failures.
4. **`/doc-figures`** — start with the most isolated stage: the input is a finished document, the
   output is PNGs and a manifest. This is what I already did by hand in this session with
   parallel calls; in a workflow it is a `pipeline` over four figures. A day.
5. **`/doc-write`** — the loop with the critic and gates following the skeleton above. Two to
   three days; all the substantive logic is here.
6. **`/doc-research`** — fan-out over sources, the analogue of `discover` + `study`. Two days.
7. **Comparison on the same article.** Run `attn-article` in full through the three commands and
   compare with what refract produced: length, the critic's remarks, the number of figures,
   money.

About a week of work in total. After the comparison — a decision on refract: mothball the
repository or keep it as a reference for prompts and the spec.

---

## 9. What is worth taking from refract in any case

The engine can be mothballed, but it contains things that are worth more than the code:

- **the agents' prompts** — they were refined by live runs; this is the main asset;
- **the artifact type spec** — it stays useful as documentation of the contracts;
- **the wording of the gates** with thresholds learned on real runs (`max_length: 14000` and why
  exactly that much, the three `forbid_regex`, `min_entries: 5`);
- **the run post-mortem** from `docs/PROGRESS.md`: why `attempts` are archived, why heartbeats
  move `running` to `pending`, why read-only directories break Windows. On the new stack some of
  these rakes lie in the same place.

---

## 10. The verdict on this approach

The approach is workable, and for a personal tool it is better than our engine for three reasons
that are not a matter of taste: **no API key is needed**, **artifacts are saved in the standard
way**, **the mapping of our pipelines onto a script is almost mechanical**. The price is losing
resume between sessions, which you agreed to consider tolerable, and losing the UI, which a
personal tool does not need.

The only thing I would warn against: do not move everything at once. Start with `/doc-figures` —
the most isolated stage with a checkable result, and on it it will immediately be visible how a
workflow behaves with an external CLI, the environment and parallel fan-out. If this stage lands
cleanly, the rest is the same scheme at a larger scale.
