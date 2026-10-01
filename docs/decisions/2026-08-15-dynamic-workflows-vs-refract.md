# Dynamic Workflows versus the refract engine: testing the choice on live data

Date: 2026-08-15. The owner's question: does the Dynamic Workflows approach have advantages over
refract-claude, where the orchestrator is Python and the pipeline is described in YAML. The
subject is large documents: technical articles, solution designs, requirements analysis. That is,
orchestrating custom agents with their own skills and MCP tools.

The previous analysis (`docs/analysis-native-claude-vs-refract.md`, 13 August) chose path B —
moving the pipelines to workflows. It rested on the documentation and on one refract run. Since
then the workflow pipeline has worked through **a full day of live runs** of one and the same
article: nine revision rounds, four crashes for four different reasons, about 5.5 million tokens.
This is the first data on which the earlier predictions can be tested rather than repeated.

The report is laid out as follows: first the three premises of the previous analysis against the
facts, then the money account, then what neither approach solves, and at the end the
recommendation.

---

## 1. Three premises of the previous analysis

### Premise 1: "losing the resume after a failure is acceptable"

**Not confirmed. It cost a separate subsystem.**

The run crashed four times in a day, each time for its own reason:

| cause | what happened |
|---|---|
| CRLF in the script | the runtime refused: `script contains control characters` |
| agent registry | `agent type 'brief-writer' not found` — the registry is snapshotted once per human turn |
| process restart | the session moved into a background task, `adopt scriptPath rejected` |
| session limit | `You've hit your session limit` took down three agents in a row |

The built-in `resumeFromRunId` did not help once: its cache lives inside one session, and the
session was exactly what kept changing. Worse: resuming in a new session started from the brief,
the brief produced different aspect slugs, and eleven source files became orphans. **Resuming did
not merely fail to save the run — it wiped out forty minutes of work.**

A checkpoint on disk had to be built: the `Resume` stage polls the artifacts before spending,
`brief_writer` does not rewrite an existing brief and writes the slugs to a file, every revision
round is written to `rounds/round-<n>.md`, and `tools/rounds.py` reads them back. That is roughly
150 lines of script, 130 lines of tool and 16 tests — that is, **a scaled-down copy of refract's
`state.json` and ledger**, built anew under another name.

Conclusion: the property "a run survives a failure" is not free in either approach. In refract it
was bought in advance and works for everything; in workflows it is written into every script, and
writing it correctly the first time did not work out — three of the four checkpoint defects were
found only on live runs.

### Premise 2: "four failures out of six have nothing to do with the architecture"

**Today it is inverted: three out of four are precisely architectural, and precisely on the
workflow side.**

CRLF and NUL, the agent registry, dying together with the process — these are properties of the
workflow runtime. refract has none of them: there is no script at all, agents are taken from the
pipeline registry at start, the run lives in a Python process with a ledger on disk and survives
`resume`.

The only shared failure is the session limit.

This does not mean refract is more reliable in substance. It means that **the earlier conclusion
"the pain is not in the architecture" was drawn from a sample of one run and does not hold on our
sample.**

### Premise 3: "the Agent SDK requires an API key, so path C is dead"

**The statement about the SDK is correct, but it does not apply to refract.**

`refract/runtime/claude_code.py`, lines 11–13, verbatim:

> No API key is involved: the CLI runs on the Claude subscription it is logged into. That is the
> whole point of this fork — `--bare` is therefore never passed, since it would force key-based
> auth.

refract launches `claude.cmd -p` as a subprocess with `--output-format stream-json`,
`--system-prompt-file`, `--allowedTools`, `--mcp-config` and `--strict-mcp-config`. That is, it
already orchestrates the very same custom Claude Code agents, with their skills and MCP servers,
**on the corporate subscription and without a key**.

A key would be needed only if the runtime were replaced with the Agent SDK — and that was an
optional part of path C. So the hybrid was not closed by the argument that was used to close it.
This is a substantial correction to the 13 August analysis.

---

## 2. The account over two runs of the same article

| | refract, `run_20260811_121834` | collimator, `probe-runs/attn4` |
|---|---|---|
| tokens | 573,681 | ≈5,520,000 (measured over seven runs) |
| money | $47.58 in the ledger | no ledger, money is not counted |
| time | 26 hours | about 7 hours |
| revision rounds | 3 | 9 |
| size of the result | 8,452 characters of prose | 37,900 characters of prose |
| how it ended | `failed` at the figures node | accepted by the gate and the style critic |

A direct comparison of tokens is not valid, and that has to be said plainly. The article is four
times longer, there are three times as many rounds, and inside the 5.5 million sit pure debugging
costs: a zombie run of 740 thousand, four accidental rounds of 1.4 million because of a defect in
my own `rounds.py`, four dead launches. The steady-state cost of a round is about 500 thousand
tokens, and it **does not depend on the orchestrator**: it is set by the size of the article, the
number of critics and the number of rounds.

What compares fairly: **refract has money accounting, we do not.** `$47,58` is a fact from the
ledger, broken down by node. In workflows, tokens are visible in `/workflows` during the run and
disappear afterwards. For a personal tool that is tolerable; for answering the question "how much
did this article cost" it is not.

---

## 3. What workflows are objectively cheaper at

**No engine.** 11,197 lines of Python plus 13,359 lines of tests do not need to be maintained
against a platform that changes. Over a day of work the workflow pipeline was rewritten seven
times (correctors, the remark sheet, the stagnation detector, the language policy) — each time it
was an edit to one file with immediate checking on stubs. In refract such changes touch the
pipeline model, the scheduler and the validator.

**Orchestration reads as code.** The loop, the branching and the exit condition are directly
visible: `if
(verdict.verdict === 'ok' && styleOk && sizedReport.ok) break`. In YAML the same thing is expressed
as a `loop` with `max_rounds` and a verdict, and "what exactly counts as accepted" goes into the
engine. When three conditions were needed instead of one, in the script it was one line.

**Parallelism is free.** `parallel()` and 16 agents at once — without semaphores and throttling.

**Agents, skills and MCP are platform features.** Neither side has an advantage here: refract
provides the same, because it launches the same CLI.

## 4. What workflows are objectively more expensive at

**A script has no filesystem and no shell.** Every deterministic check needs a carrier agent:
`gate-runner` is called 4–6 times per run just to launch Python and return JSON. It is cheap in
tokens (haiku), but it is an extra layer where data can get distorted — and it already has been,
twice: the agent returned absolute paths instead of relative ones, and the same agent silently cut
the output of `rounds.py` from five rounds to two, costing 1.4 million tokens.

**There is no human in the middle of a run.** For a document pipeline this is exactly the point
where quality is decided. In refract the `style` stage parks the run, a human accepts some of the
findings, an editor applies only the accepted ones. We have a style critic in the loop instead —
and nine rounds of oscillation: round 6 style `ok` / substance `revise`, round 8 substance `ok` /
style `revise`, round 9 back again. Each round fixed one axis and touched the other. A human would
have closed this in a single pass.

Tellingly: **today a checkpoint did happen after all — by hand.** The owner stopped the run,
looked at the state, asked a question, and the run was restarted with edits. That is HITL, only
not supported by the tool.

**There is no pre-launch validation of the graph.** YAML is diffed and checked against 40+ error
codes before launch. A script is checked by `dry_run.mjs` on stubs — which I do in four modes —
but that is a test, not typing. An `agentType` error with no file behind it is caught only by a
test that I had to write myself.

**There is no money accounting.**

---

## 5. What neither of the two solves

This matters more than the choice of orchestrator, and the day of work showed exactly that.

All the defects that actually cost rounds and tokens were **defects of the pipeline's design**,
not of orchestration:

- the writer silently lost remarks, because its schema had no field for what was not done;
- the substance critic did six jobs at once and did the attribution check worst of all;
- the arithmetic of the example was read by eye for six rounds, until an agent that runs Python
  appeared;
- the corrector fixed a fact and picked up a style defect, until it was given the voice profile;
- an overrun in length, handed over as an item in a list, was treated by writing more text.

Neither YAML nor JS has anything to do with this. All of it is expressed the same way in both
approaches, and equally goes undetected without a live run.

The conclusion worth remembering: **the choice of orchestrator affects reliability and the cost
of maintenance, but not the quality of the document.** Quality is set by the shape of the
revision round.

---

## 6. Recommendation

**The direction was chosen correctly — stay on Dynamic Workflows.** But the current shape, "the
whole pipeline in one script", is wrong for documents of this size, and it has to change.

### What to do

**1. Cut the pipeline into segments along the boundaries of human decisions.** The workflow
documentation says it directly: there is no human input in the middle of a run, split into
separate workflows. Today this already happens by hand. I propose three commands instead of one:

- `research` — brief, sources, analysis. Ends with material on disk;
- `draft` — writer, correctors, gate, critics, rounds. Ends with the article and the round records;
- `polish` — illustrations and acceptance.

This gives three things at once: a human looks at the result at each boundary; a process crash
costs one segment, not everything; and the `medium` guideline of 15 agents stops being violated.

**2. Count money.** The only thing we lack and refract has for free. It is enough to write, at
the end of a segment, a line into `<run>/spend.jsonl` from what the runtime already knows.

**3. Do not port the rest.** The type registry, the graph validator, the UI, REST — that is value
for someone else's user, and there is none.

### When the answer changes to refract

Three conditions, any one of which brings the engine back into play:

- **a run must live longer than a session** — a day or more, surviving an exit from the CLI. Our
  refract run went for 26 hours; workflows have no such mode by construction;
- **the pipeline is launched by a colleague without a terminal** — then REST, WS and the SPA stop
  being dead weight;
- **a per-node cost audit is needed** — a ledger that is diffed and kept.

None of them holds today.

### What to keep from refract regardless of the choice

The hybrid is not dead, contrary to the 13 August analysis: refract drives the same CLI on the
same subscription, without a key. If durability and a human in the middle are ever needed, **the
right step is not to rewrite refract on the SDK, but to keep it as the Python orchestrator and
delegate wide fan-out to it as a single workflow**. This remains an open door, and it is worth
keeping open: the cost of keeping the repository is zero, the cost of rebuilding is 27 thousand
lines.

---

## 7. What to do next week

1. Cut `explainer-article` into three segments and run the article again — this at the same time
   closes HITL and makes a crash cheap.
2. Add per-segment token accounting.
3. Move into `library/` the lessons about the shape of the round that have already been
   confirmed: correctors before critics, a remark sheet by number, the stagnation detector,
   approval as a constraint.

---

## Appendix: sources of the facts

- `refract/runtime/claude_code.py:11–13` — running on the subscription without an API key;
- `attn-article/runs/run_20260811_121834/state.json` and `events.jsonl` — 26 hours, $47.58,
  573,681 tokens, `failed` at the figures node;
- `probe-runs/attn4/rounds/round-1..9.md` — nine rounds, verdicts, remarks;
- the completion notifications of the seven runs of this session — `subagent_tokens`;
- `CLAUDE.md`, the section "Rakes paid for by live runs" — fourteen failures with their causes;
- `docs/analysis-native-claude-vs-refract.md` — the 13 August analysis whose premises are tested
  here.

---

# Addendum of 16 August: three facts the analysis did not have

The analysis above compared the two approaches on an article. The target work is different —
technical designs, requirements, research — and on it three facts surfaced that change the weight
of the arguments.

## Fact 1. Hieroglyph directories exist in refract too

Today four empty directories with unpaired surrogates in their names were deleted from the root of
`collimator`, and this was charged to Dynamic Workflows. A check showed the opposite:

```
refract-claude/attn-article/runs/run_20260811_121834/steps/figures/main/
  ⎀ℑ翺
  Identity Verification Root Certificate Authority 2020
  1.3.6.1.4.1.311.10.3.37!7
```

The name `⎀ℑ翺` matches literally. Plus scraps of the Windows certificate store — the same
signature described in `tools/sweep_junk.py`: the text of the system prompt passes through
`cmd.exe`, because `claude` on Windows is a `.cmd` wrapper. **A figgybanana defect, reproduced in
both projects.** One point against workflows is cancelled.

## Fact 2. `solution_design.yaml` has no `checkpoints`

The main way refract differs from workflows is stopping a run for a human decision. The user's
target template does not have it. Of the library's eight templates, `checkpoints` are declared in
two: `explainer_article` and `requirements_to_design`.

The analysis credited refract with an advantage that the target pipeline does not use. And
everything that `solution_design.yaml` does have maps onto workflow primitives one to one:

| refract node | in a Dynamic Workflow |
|---|---|
| `map: scan.sources` with `workers: 3` | `parallel()` or `pipeline()` |
| `map_over: {models: [sonnet, opus]}` | `parallel()` of two `agent()` with different `model` |
| `type: select` + selector | a judge agent over an array of candidates |
| `type: loop` + `critic` + `max_rounds` | a `for` loop with a verdict and `break` |
| `gate_rules` | `tools/gate.py` via `gate-runner` |

Not a single construct that requires an engine.

## Fact 3. The engine is 24,556 lines that have to be maintained

11,197 lines of `refract/` plus 13,359 lines of tests. Against a platform that changes. In one
working day the workflow pipeline was rewritten seven times — each time an edit to one file with
checking on stubs in a second.

## Decision

**Stay on Dynamic Workflows.** The three facts above remove two of the three arguments for
refract, and the third — the long-lived run — is removed by segmentation, which is needed
regardless.

But that is not the main point, and it is worth saying plainly, because the question was not
asked about it.

**The orchestrator is not an asset. The asset is the agent library and the shape of the revision
round.** Over the day, nine defects of the pipeline's design were established against six defects
of the substrate, and it was the former that cost rounds and tokens: the writer that silently lost
remarks; the critic that did six jobs; arithmetic read by eye; the corrector that fixed a fact and
picked up a style defect; an unreachable acceptance condition. **None of them has anything to do
with the choice between YAML and JS**, all nine are expressed the same way in both approaches, and
none is detected without a live run.

The twenty-seven agents in `library/agents/` are portable between substrates without edits. The
lessons about the shape of the round — correctors before critics, a remark sheet by number,
approval as a constraint, the plateau detector — are too. The choice of substrate is reversible in
a day; the choice of the round's shape was paid for with a week of runs.

So the decision is made on the cost of maintenance, not on capabilities: **one page of script
against twenty-four thousand lines of engine, with the same set of capabilities.**
