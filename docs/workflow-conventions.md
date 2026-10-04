# Script and tool rules carried over from collimator's CLAUDE.md

This is a reference for a human and for edits to scripts: the rakes paid for by live runs, and the
rules they grew out of. It was moved out of CLAUDE.md on 2026-09-20 because every subagent reads
CLAUDE.md at startup: 70 KB of this text cost about 16 thousand tokens for each of the 27 agents
of a run. The rules remain in force; a disagreement with SPEC.md is resolved in favour of SPEC.md.

# collimator — a compiler of document pipelines into Dynamic Workflows

A collimator turns scattered rays into one parallel beam. The input is a pipeline declaration
(`pipeline.yaml`), the output is a Dynamic Workflow script and subagent definitions for
Claude Code. The line of names: spectra → refract → collimator.

**The main rule of the project: we generate, we do not execute.** Claude Code runs the agents with
its own runtime. There is no scheduler, no ledger, no crash recovery and no runtime adapter here —
all of that existed in refract and died on purpose, because the platform does it better and
changes faster than we could keep up with it.

## Commands

```bash
uv run python -c "from pathlib import Path; from collimator.emit_agents import emit_all; print([p.name for p in emit_all(Path('library/agents'), Path('.claude/agents'), Path('.claude/skills'))])"   # agents from the library; fails if a named profile is missing from .claude/skills
uv run pytest                                          # tests, no network and no LLM
uv run ruff check --fix . && uv run ruff format .
uv run mypy collimator                                 # strict
python -X utf8 tools/gate.py --file <file> --max-length 14000   # gate by hand
python -X utf8 tools/gate.py --file <file> --forbid-file library/style/forbid/ru-slop.txt
node tools/dry_run.mjs .claude/workflows/<script>.js ok        # run on stubs
node tools/dry_run.mjs .claude/workflows/<script>.js bad       # the same, every failure branch
node tools/dry_run.mjs .claude/workflows/explainer-article.js ok '{"runDir":"d/r","brief":"t","config":{"fresh":true}}'
node tools/dry_run.mjs .claude/workflows/explainer-article.js ok '{"runDir":"d/r","brief":"t","config":{"stages":["research"]}}'
DRY_ORDER_MISMATCH=1 node tools/dry_run.mjs .claude/workflows/explainer-article.js ok '{"runDir":"d/r","brief":"t","config":{"continue":true}}'
python -X utf8 tools/rounds.py --dir <run>/rounds --last-only  # what to continue the loop with
python -X utf8 tools/listing.py --dir <run>/sources            # what the finders actually found
python -X utf8 tools/newrun.py --base docs-runs --label <what>  # directory name for a NEW run
python -X utf8 tools/snapshot.py --file <file> --to <dest>       # snapshot, refuses on mismatch
python -X utf8 tools/busy.py --file <run>/tools.jsonl --now "<ISO>"  # whether the directory is busy
python -X utf8 tools/gate.py --file <file> --no-empty-sections   # headings with no work under them
python -X utf8 tools/rounds.py --dir <run>/rounds            # which rounds are already done
python -X utf8 tools/sweep_junk.py --dry-run                   # what junk is in the root
python -X utf8 tools/confluence_publish.py --draft <file> --dry-run <dest.xml>  # conversion only
python -X utf8 tools/confluence_publish.py --draft <file> --parent-id <id> --json <dest.json>  # publishing
```

A workflow script is run through `dry_run.mjs` **before** a live launch, and not in two modes but in
every branch it has. `explainer-article` has nine: `ok` with `config.fresh`, `ok` without it
(continuation from disk), only `research`, `config.correctors:false`, `bad`, plus the switches
`DRY_BUSY` (directory busy), `DRY_ORDER_MISMATCH` (wrong order), `DRY_CARRIER_DROPS` (a carrier
truncated the list) and `DRY_PLATEAU` (the loop is already on a plateau). `solution-design` has its
own, including `DRY_EXISTS_OK` (the disk is in place, everything else fails). It replaces `agent()` with a stub that answers according to the call's schema, and executes the real
control flow. Otherwise an error in the last `return` line costs a full run:
`SOURCE_PATHS is not defined` cost 468 thousand tokens and twenty minutes. `node --check` is
useless here — it parses a `.js` with `export` as CommonJS and stays silent.

The definition of done for any edit: pytest green + mypy green + ruff clean +
generated files rebuilt and committed.

`tests/test_workflows.py` holds the launch invariants, and each one was paid for by a run: the
script has no control characters (CR and NUL — the runtime refuses), every `agentType` has a file in
`.claude/agents/`, the name in the frontmatter matches the file name, the run directory and the
path to the article come from `args` rather than living in the code, and the prompts of the ten
pipeline agents do not mention the subject domain. The last two tests each found a real defect on
the same day they were written.

## Layout

**What the package does NOT contain, although this file used to say it did.** No `graph.py`, no
`registry.py`, no `prompt.py`, no `emit_workflow.py`, no `collimate build` command. The package has
144 lines of Python: the agent definition generator and the agent model. The pipeline scripts are
written by hand, and that is the state of things, not a phase — the decision on the compiler is
made by measurement in the second archetype (see `docs/decisions/2026-08-17-dynamic-workflows-retrospective.md`).

- `collimator/emit_agents.py` — `agent.yaml` + `prompt.md` → `.claude/agents/<slug>.md`.
  The only working half of the compiler. The input/output tail that refract's `prompt.py` built
  from the port contract now lives as the `task()` function inside each pipeline script — one text
  for all agents instead of nine diverging variants;
- `library/` — data, not code: 28 agents (21 built), artifact types, seven pipeline templates;
- `library/style/author-voice.md` — the author's style profile. Data, edited by hand.
  It goes through the `voice` port to both the writer and the style critic: one description of the
  voice, not two;
- `tools/gate.py` — deterministic content gates, called by a workflow stage.
  Forbidden patterns arrive as files (`--forbid-file`), not in argv: Cyrillic on the command line
  on Windows depends on the code page and on which shell the carrier agent picked. The file searches
  **outside code**, the plain `--forbid` searches the whole file, because `d_k ** 0.5` is a power
  and `**important**` is bold, and only the caller knows which was
  meant. `--no-empty-sections` names the headings with nothing under them;
- `.claude/agents/`, `.claude/workflows/` — **generated**, but committed: then the diff shows
  exactly what changed in the orchestration after a YAML edit;
- `.claude/skills/<type>-profile/SKILL.md` — document-type profiles (SPEC §6). Data, edited by
  hand; they reach an agent through the `skills:` field of `agent.yaml`. **The document contract
  lives in the profile, not in prompts**: the writer, the corrector and the critic read one text,
  a prompt describes a role. The `requirements` profile is filled in (`docs/decisions/2026-09-19-requirements-profile.md`);
  the script passes its gate rules to the loop through `gateFlags`. The runtime skips a non-existent
  profile **silently**, so `emit_all` with a third argument checks each one on disk and fails.
  An agent reads the profile — so it is in English.

## What carried over from refract's invariants

Of the engine's ten invariants two survive; the rest belonged to the runtime:

- **a contract instead of hand-written instructions**: the input/output section of an agent's
  prompt is generated from `agent.yaml`, never written by hand in `prompt.md`;
- **an agent does not produce collections**: fan-out lives in the script (`pipeline()`); an agent
  consumes a collection but does not create one.

Isolation of the working directory (formerly I1) is provided by Claude Code itself through its
`PreToolUse` hook; secrets in the environment — `env` in `.claude/settings.json`.

## Workflow runtime constraints the generator must respect

Breaking any of them — the run does not start, or fails for the wrong reason:

- **everything an agent reads is in English.** This is a project rule, not only a runtime one, and
  it is broader than it seems: the agent's prompt in full, including comments in the generated file;
  task texts from the script; `description` in JSON schemas; command-line arguments; `meta`. The
  agent file **in its entirety** is its system prompt, so a "generated" marker in it is also prompt.
  That is exactly how the rule was broken most quietly: the marker was inserted in Russian, and
  twenty-one agents read a Russian line, with no way to see it. Held by
  `test_generated_agent_prompts_are_english`.

  The only exception is **quoted material in the target language**: the dictionary of clichés a
  critic looks for in a Russian text, the forms of address by which it recognises them, a sample
  figure caption. Such an agent cannot do its job without naming what it looks for in the language
  of the article. The list of such agents is closed and named in the test: adding a new one is a
  decision, not a side effect.

  Logs, error messages, `handoff.md`, comments and docs are English too: the one Russian
  document is README.md; the Russian description of each agent is written in its agent table
  by hand, and the generator keeps it. Held by `tests/test_language.py`;
- **the output language comes from the material, not from the prompt.** The requirements writer
  writes in the language of the sources: a document read by the people whose words it brings
  together cannot be checked against them in another language. So an English run means English
  input documents, not a flag in the config;
- `meta` in a script is a **pure literal**: no variables, no calls, no template strings;
- `import()` is forbidden: work with libraries lives inside agent tasks;
- `Date.now()`, `new Date()` and `Math.random()` are unavailable — timestamps arrive through
  `args`, variety is achieved by an index in the prompt;
- the script itself has no access to the filesystem or the shell: agents read and write files,
  the script only passes paths. **Paths are not asked for back**: the script invented the path,
  and a `path` field in the schema creates a channel where "report the path" looks like "write the
  file". The schema carries only what the script cannot know;
- there is no human input in the middle of a run — a human decision point is a **segment
  boundary**, that is, a separate command;
- 16 agents at once, 1000 per run; the default size guideline `medium` is fewer than
  15 agents, beyond that a warning appears in the interface.

## What in the pipeline depends on the topic and the language

Nothing — by construction, and this is checked, not assumed.

- **topic**: `grep -ciE "attention|softmax|d_k|transformer" library/agents/*/prompt.md` (plus the Russian
  word for "transformer") across all ten pipeline agents must give zero. An example in a prompt tied to the subject domain makes the
  agent unfit for the next article, and this is not noticeable right away;
- **language**: from the brief. `LANGUAGE_POLICY` in the script maps a language to a style critic
  and to gate presets. A language without an entry gets `no_bold` and **no** style critic, and the
  missing check goes into the unresolved items — "nobody looked" and "looked, all fine" coincide
  only for a report nobody reads. `cfg.styleCritic` and `cfg.gatePresets` override the table;
- **the author's voice**: a data file at `cfg.voicePath`; `null` is a legitimate answer, and then
  the general rules against AI slop apply;
- **topic, length, aspects, what goes in and what does not**: only from the order, through
  `brief_writer`. The script does not substitute length defaults: if the order is silent, the gate
  measures and does not judge.

## Traceability: every requirement names its source

A requirement without a source reference is indistinguishable from a conclusion the agent drew —
and these are different things with a different cost of error. So every requirement, constraint
and assumption ends with a reference in square brackets: the extract name plus a locator inside
it — a heading, a date, a speaker, a quote.

```
FR-7. When a file for the same day arrives again, the system keeps both and marks which one
the metrics were computed from.
[discussion-chat: 5 March 14:45–14:50, infrastructure admin and team lead]
```

(A sample requirement, translated from a Russian document.)

Three rules make a reference useful rather than decorative: two sources — two references (a
requirement both documents confirm is stronger than one mentioned in passing, and that is visible
only through the references); a locator, not only a file name (otherwise the reader searches for
the sentence themselves and usually does not find it); and **no source — no requirement**: what
the agent inferred goes into the assumptions section, marked as unverified.

This is checked not by the critic but by the corrector — the one checking against sources opens
every reference and fixes it in place. A wrong reference is worse than a missing one: it makes an
unconfirmed requirement look confirmed. And it is an edit, not a remark: a critic can only report,
and a report costs a round.

## Segments: one launch is one stage

A workflow lives inside the CLI process, and the process survives neither a restart, nor the
session moving into a background task, nor hitting a limit. A run that does everything risks
everything: forty minutes of search once died together with the process in the middle of writing.

So a launch is a stage, and it is chosen by `config.stages`:

- `research` — brief, sources, analysis. Ends with material on disk. Five agents;
- `draft` — writer, correctors, gate, critics, rounds. Ends with the article and the records. Thirteen;
- illustrations — a separate workflow, `attn-figures`.

Without `stages` both run. Nothing passes between stages except files: the brief carries the aspect
slugs, the slugs name the source files, the analysis is the writer's material. Nothing of value
remains in the process.

**One file, not two.** The stages share the configuration, the input/output tail, the schemas and
the gate commands — about a hundred and twenty lines. Without `import()`, splitting into files turns
them into two diverging copies, and that is exactly the trouble the project pays for most often.

## The research fan-out: two levels of names and a directory per finder

The script cannot read a directory, so the width of the fan-out must be known in advance. Only
**the aspects from the brief** are known in advance: their slugs become file names, and one source
finder is launched per aspect. Asking an agent where it put things is forbidden — the script
invented the path.

But the finder, by its contract, also writes **a file per source it keeps**, and those names the
script cannot know. A measured run: 4 per-aspect files of 79 KB reached the analyst, while 28 files
of 260 KB lay on disk. Seventy percent of what was found were orphans, and this is the most
plausible explanation of why attribution errors survived eleven rounds: the writer quoted the
per-aspect summary while the note on the specific work lay next to it unopened.

The cure is listing: `tools/listing.py`, through the same carrier, returns the list of files, and
from there **the analyst and the note checker get all of them**, while the writer still gets the
per-aspect summaries plus the material, so as not to pay for 260 KB every round. Listing is not
the same as asking for a path: the script still names everything it writes itself, and this is only
a report of what exists.

**Each finder has its own directory** `sources/<slug>/`. In a common heap, two finders working
different aspects of one topic inevitably reach the same well-known work and save it twice under
different names — `annotated-transformer-maskirovanie-kod.md` and
`annotated-transformer-scaling-masking-code.md` are one source saved by two agents. A directory
per finder makes the collision impossible, shows which aspect found what, and allows listing by
aspect rather than sorting one heap.

There are **six** aspects by default, not four: an aspect is a whole researcher, and a technical
design has more than four areas worth a researcher. The ceiling is set not by the machinery (the
platform holds sixteen agents at once) but by whether the aspects really are different questions.

## Run directory: a new one for every experiment

`Date.now()` is unavailable in a script — the runtime removes it, otherwise resumption breaks. So
the script **cannot** name a directory by its start time, and the name comes from outside, in
`args.runDir`.

This is a rake, and it went off: seven launches of one article went into `probe-runs/attn4`, where
reuse from disk honestly picked up the previous run. For continuing an interrupted run this is
exactly what is needed; for comparing two there is nothing to compare, the second inherits the
material and the draft of the first. Two runs aimed at one directory at the same time did worse:
one rewrote the other's article in the middle of a round, and whose text survived could not be
established.

So the directory name is minted outside, where there is a clock:

```
python -X utf8 tools/newrun.py --base docs-runs --label "<a Cyrillic label>"
docs-runs/vnimanie-v-transformerah-20260816-135918
```

(The label is Cyrillic, Russian for "Attention in transformers"; the example shows its
transliteration.)

Cyrillic is transliterated, not thrown away: without that every run would be called
`run-<time>` — a name that distinguishes nothing.

And this is **a rule, not a convention**. The script refuses to start research in a directory that
already holds `material.md` or `article.md` until it is told explicitly what was meant:

```
the directory docs-runs/… already holds the result of a previous run.
A new run is a new directory: python -X utf8 tools/newrun.py --base docs-runs --label <what>.
To continue an interrupted one — config.continue=true. To rebuild from scratch right here — config.fresh=true.
```

Three intentions — three different actions, and none of them is guessed for the caller: a wrong
guess is expensive one way and invisible the other. The `draft` stage is not covered by the rule —
launching it alone is, by its meaning, a continuation.

**`continue` was a loophole, and a second lock closed it.** What is dangerous is not a reused
directory in itself, but a reused directory **under a different order**: then the article is built
half from one brief and half from another, and nothing in the result says so. Exactly one agent can
notice it — `brief_writer`, the only one that sees both the order and the brief written by the
previous run from a different order. It answers with the field `order_matches_existing_brief`, and
`false` stops the run. Under `config.fresh` the lock is off: there the old brief is not continued
but replaced.

## How it is checked that nothing was lost

Not by a promise but by subtraction. All four losses found in a day had one shape: **a file was
produced, and nobody read it.** None of them looked like a failure at the moment it happened.

- twenty-five source notes written by the finders — handed to nobody;
- the whole directory of a fallen finder — the aspect dropped out of the list, and nobody listed
  the directory;
- `_index.json` with the URL and status of every source — written from the very start, read for the
  first time;
- the agent's draft `rounds_output.json` — lying in the run directory.

So `touched` accumulates every path that reached an agent, and accumulates it **through the only
action by which a path can be consumed** — getting into a task. Bypassing the accounting while
handing a file to an agent is impossible: it is one and the same line of code.

At the end of each stage `tools/listing.py --recursive` lists the whole run directory, and the
script subtracts one from the other:

```
[audit] files in the directory 34, read by agents 34, read by nobody 0
[audit] no losses: everything produced was read by someone
```

Orphans are named **one by one**, not counted: a number says that something went missing, a name
says what. The audit runs on both stages — the research stage ends earlier, and that is exactly
where orphans used to appear.

The audit rule is "read by an agent **or** declared as a record". A draft snapshot is read by a
human, not an agent, so it is declared explicitly, with one line `touched.add(...)`. This is the
only exception, and it is named in the code: otherwise a record that exists for a human would be
counted as a loss in every run.

## The draft of every round is kept

`article.md` is overwritten by every round. The round records keep the verdicts — but not the text
they were passed on, and the question "what exactly changed between round eight and round nine"
stayed unanswered exactly when it mattered most: when the loop stopped converging.

Now `rounds/draft-<n>.md` is placed next to the round record. It is copied by `file_copier` — a
separate agent with one job, because `gate_runner` is explicitly forbidden to create files, and
that prohibition was worth keeping: having broken it once, it littered the run directory. The
snapshot **refuses** to overwrite an existing file with different content: a silently overwritten
snapshot destroys evidence, while a refusal merely fails to add it.

## Prohibitions are data, not code

The list of clichés lives in `library/style/forbid/*.txt`, one regex per line, next to the voice
profile. It is the editorial policy of one language — the same kind of data as the voice, and a
human edits it without opening the parser. The list used to be a dictionary inside `gate.py`, and
that was simply wrong.

Not in argv, for the earlier reason: Cyrillic on the command line on Windows depends on the code
page and on which shell the carrier agent picked. A file avoids this entirely — the path is ASCII,
the content is UTF-8, Python reads it.

A missing file is **a problem**, not an empty check: a gate that found no violations because it had
no patterns reads exactly like a gate that passed.

## Four records, and three of them survive a process crash

The full answer to "was everything passed correctly and was nothing lost" is assembled from four
independent sources. None of them is a model's recollection, and three are written **as the run
goes**, not at the end:

| record | what it says | who writes it | survives a crash |
|---|---|---|---|
| `logs/stop-audit.jsonl` | what an agent **actually wrote** and whether it is on disk | the platform hook | yes |
| `<run>/tools.jsonl` | what each deterministic check found | the tool that measured | yes |
| directory audit | whether anything was left unread | the script, by subtraction | yes, files on disk |
| `<run>/handoff.md` | what was **intended** to be handed to whom | composed by the script, written by an agent | **no** |

The last is the only one that accumulates in memory and is written at the end of a stage. This is
its honest limitation, and it is tolerable precisely because the first covers it in substance:
`handoff.md` speaks of intent, the hook of an accomplished fact, and the fact matters more.

**The `SubagentStop` hook is the sturdiest of the four.** It runs in Claude Code's own process after
every subagent, free in tokens, and an agent cannot skip it. It looks at what cannot be faked: the
agent's own `Write` and `Edit` calls from its transcript — and checks whether those files are on
disk **now**. An agent that called `Write` and left nothing gets into the log without anyone being
asked anything.

In one working day it collected 261 entries and, in particular, recorded `source-finder` writing
seven or eight files per call — those very orphans, long before anyone noticed that nobody read
them.

## Tool log

Everything a deterministic tool measured otherwise lives only in the workflow's `log()`: readable
while someone watches the run, and unavailable once it has ended. A finished run had to be
reconstructed from the transcripts of individual agents, matched up by hand — and once the evidence
survived only because the tool could be run again on the same directory.

So every tool writes its own receipt: `--log <run>/tools.jsonl`, one line per call.

```
14:28:38  gate      ok=False {"chars": 27572, "prose_chars": 24387, …}
                    problems: max_prose 100 exceeded (got 24387)
14:28:38  listing   ok=True  {"files": 8}
14:28:39  rounds    ok=True  {"rounds": 13, "last_round": 13}
14:28:39  snapshot  ok=True  {"copied": true, "bytes": 46026}
```

**The tool writes it, not the agent**: a carrier is forbidden to create files, and the prohibition
has already justified itself twice. It is the measurement that leaves the receipt, and the one who
measured writes it.

The line is limited on purpose: arguments, verdict, measurements, problems — and never content.
A listing of two hundred files belongs in the answer to the caller, not in a log that must stay
readable after fifty of them. And a broken log does not bring down the check: losing a run because
of a receipt is worse than losing the receipt.

## The shape of the revision round

A round is a chain and then a fan-out: writer → two correctors → gate → two critics in parallel.

The correctors (`example_verifier`, `article_fact_checker`) fix what is **decidable**: they
recompute the example's arithmetic in Python and check claims against the notes. The critics judge
what is decidable only by judgement. The shape was hard-won: with a writer and two general critics a
live run ate six rounds and five million tokens, and the same five remarks came back verbatim.
A critic can only report a wrong attribution, and a report costs a round to fix.
**Anything a corrector can close must not become a remark.**

**The acceptance condition cannot be "both critics are silent".** Requiring two independent judges
to simultaneously find nothing in a forty-thousand-character text is a condition that is not met:
over eleven live rounds the critics accepted in turn, never together, and the total number of
remarks sat on a plateau of 8–10. A hint to the writer about which axis had already been accepted
did not change this, because the problem was not the writer. So the loop also stops on a
**plateau**: two rounds in a row did not improve the best score reached — the work is over, the
author decides the rest from `UNRESOLVED.md`. Rounds 9–11 of one run cost two and a half million
tokens and did not beat the result of round eight.

Four things keep the loop from idling:

- **the remark sheet**: remarks go in one numbered list, the writer answers line by line
  `fixed`/`declined`, the script checks the numbers and carries over what was not covered;
- **what was declined reaches the critics** together with the reason: a critic that does not know
  why a remark was declined raises it again, and the pair burns a round agreeing to disagree;
- **the stagnation detector**: a round whose remark set matches the previous one ends the loop. The
  next would give the same, and the items will reach the report anyway;
- **the plateau detector**: a round that did not beat the best score counts as wasted;
  `plateauRounds` of these in a row — and the loop stops. The report names the best round and its
  score.

## What the correctors gave in the first live round

The numbers the round shape was changed for. `example_verifier` ran Python and found what six
rounds of two Opus models had not seen: `exp(2.887)` written as 17.940 against 17.939,
`exp(1.732)` as 5.651 against 5.652 together with the sum, "8.34% for 12 heads" instead of 8.33%.
Reading by eye cannot catch this in principle. `article_fact_checker` made eight edits in a round,
including spaces in a code quote and a damaged matrix row.

And a side effect showed up right away: the substance critic accepted, while the style critic slid
back from `ok` to `revise` on the same draft. Five softened overstatements arrived in one and the
same hedge — the checker was fixing a fact and acquiring a style defect. So it was given the
`voice` port and told to vary the way it softens. **A corrector edits a text that has a voice.**

## Rakes paid for by live runs

- **`$PAPERBANANA_BIN` before PATH.** An agent told "the tool is in a variable" stopped twice out
  of three times with "not on PATH" without looking at the variable. In prompts the resolution order
  is given as a numbered list with an explicit prohibition on stopping.
- **The long form of the path for the temporary directory.** A path with a `~1` segment (an 8.3
  short name) is rejected as suspicious by the paperbanana vision critic, which declares itself
  satisfied without seeing the picture. The loop passed outwardly and in fact checked nothing.
- **PowerShell 5.1 reads a `.ps1` without a BOM as ANSI.** Cyrillic in a launcher script breaks the
  parser, and the detached process looks launched. Keep the launcher in pure ASCII, non-ASCII strings
  in Python or in a data file.
- **A gate on the file ≠ a gate on the prose.** The brief asks for 8–12 thousand characters of
  readable text, and the file also carries markup, tables and captions: 13,662 characters of file
  against 11,111 without spaces. `tools/gate.py` counts both, `--min-prose` measures the prose
  specifically.
- **A POSIX path in `TEMP` looks like stale credentials.** `$PWD` in Git Bash is
  `/c/Users/…`; Windows does not resolve such a path, PowerShell does not start, the gateway bridge
  reads tokens **through** PowerShell and gets nothing for every account, the gateway answers 401
  `missing bearer token`. The diagnosis "the tokens need reissuing" is wrong; the cure is `pwd -W`.
- **Every Bash call of an agent is a new shell.** Exports from the previous call are dead.
  The environment and the command must be in one call, otherwise the failure flickers: one round
  works, the next fails on the same code.
- **A file name can be forbidden by the platform.** A subagent may not write a `.md` whose name
  contains `analysis`, `report`, `findings` or `summary`: `Write` answers
  "Subagents should return findings as text". A directory does not save it, an extension does. The
  failure is silent — the agent returns the result through the schema, the pipeline moves on. The
  generator must catch this at build time.
- **An empty fan-out must stop the pipeline, not only warn.** Losing one extract out of five is
  cheaper than throwing away four — so the fan-out tolerates partial failure. Zero out of five is
  something else: the writer has nothing to read, and it either invents the document or dies. In a
  live run it died three stages later, when the run had already paid for resumption, listing and
  round preparation — 111 thousand tokens on a path that was doomed from the first fan-out.
- **A new agent is not available in the same turn in which it was created.** The runtime takes the
  `agentType` list once and keeps it until the next human message. The file in `.claude/agents/`
  is there, `emit_agents` has run, `dry_run` is green — and the run fails instantly:
  `agent type 'brief-writer' not found. Available agents: ...`, and that list shows the agent built
  a turn earlier but not today's. Retrying in the same turn does not help.
  Working order: build the agents, wait for the next message, launch.
- **CRLF in a workflow script — the launch is refused.** `script contains control characters that
  would be hidden in the approval dialog`. On Windows `autocrlf` brings CRLF back on every
  checkout, so the line ending is declared in `.gitattributes` rather than left to the global git
  setting.
- **A verdict gets rubber-stamped, evidence does not.** A checking agent gave `ok` with an empty
  defect list to three pictures, two of which carried English captions in a Russian article. What
  helped was not stronger wording but a schema field that cannot be filled without doing the work:
  "write out every label verbatim". After that both the captions and a substituted multiplication
  sign were found.
- **A verdict is a literal, not a synonym.** The article critic's prompt demanded `approved` be
  returned, the schema in the script allowed only `ok` and `revise`. The agent sat between two
  descriptions of its own output; at best this costs a repeated call, at worst the model picks
  `revise` and the round is wasted. The verdict value is set in one place and quoted in the prompt
  verbatim, together with a prohibition on synonyms.
- **"There is no file" and "the file is your result" in one prompt.** The input/output tail was
  appended to all tasks the same way, and the critic got `OUTPUT (no file)` followed by
  "write the file with the Write tool". The very same error that brought down the analyst — only
  further down the script. A task without a file has its own tail.
- **A run lives inside the CLI process.** Restarting the process or moving the session into a
  background task kills the workflow halfway (`adopt scriptPath rejected`), and `resumeFromRunId`
  rescues only within one session — in a new one the cache is empty. A live run lost forty minutes
  this way: resumption started from the brief, the brief invented new aspect slugs, and eleven
  source files became orphans. So the checkpoint is not the cache but **the disk**: before spending,
  the script asks what is already done and skips such stages with an explicit entry in `log()`.
  The condition for robustness: the brief writes the aspect slugs TO A FILE, otherwise after a
  restart there is nowhere to get them from and research starts over. Critics' verdicts do not
  survive the process on their own either — each round is written to `<run>/rounds/round-<n>.md`,
  and `tools/rounds.py` reads them back. Without this `max_rounds` is a limit per launch, not per
  article: three crashes give six revision rounds where the brief allowed two.
- **A session limit looks like an agent breaking.** `You've hit your session limit · resets 17:20`
  comes from three agents in a row, and the script sees only `null`. A writer that died on the limit
  managed to write the file but not to answer — that is, the artifact exists but the result does
  not. Hence the rule: acceptance looks at the file, not at whether the agent returned.
- **Two runs on one directory corrupt the state.** A run killed according to the report went on
  working: it added fifteen files to `sources/` under its own slugs, overwrote `material.md` and
  `article.md`. The provenance of the draft after that is unprovable — what exactly the second round
  edited and on whose remarks cannot be established. It happened a second time, this time my fault:
  the directory log was silent for six minutes, I read the silence as the end of the run — but the
  silent ones were the finders, which call no tools at all. The recorded rake did not help, because
  "is the run going" was not observable in any way. Now it is: `tools/busy.py` looks at the age of
  the last line of `tools.jsonl`, the script asks before the first spend, the time arrives in
  `args.now`. Without `args.now` the check is skipped and says so out loud.
- **A path returned by an agent is not equal to the path the script passed.** The disk check
  returned absolute paths with backslashes, the script compared them with relative POSIX ones —
  nothing matched, `present` came out empty, and four finders and the analyst worked over what was
  already done. The previous run of the same code returned relative paths and worked: a bug that
  fires every other time waits for an expensive run. The invariant "paths are not asked for back"
  exists exactly for this — the result is matched **by index**, because the script set the order of
  the commands, and the `path` field has been removed from the schema altogether.
- **The audit must tell a loss from another stage's files.** A design-only run reported six
  orphans: the input documents, the extracts and the requirements round records. All six are
  correct — this launch did not read them and must not, its input is `requirements.md`. An audit
  that is wrong six times in a row teaches the reader to skip the audit line, and it exists in order
  to be read. Directories are assigned to stages, and files of a stage that did not run in this
  launch are counted and named separately from losses.
- **A revision loop without a ceiling is a growth loop.** The flip side of the previous rakes, and
  measured by the same run in English: there is no ceiling, and over the rounds the design grew
  37,595 → 50,633 → 73,978 characters of prose, that is, it doubled, while the remark count went
  11 → 12 → 8. Round 2 bought thirteen thousand characters and one extra remark. The reason is
  simple: every critic's remark is closed by a clarification, a clarification is text, and without a
  ceiling nothing pushes back against it.
  Both conclusions are true together: an invented ceiling makes acceptance unreachable, and the
  absence of any gives monotonic growth. The script does not judge — it **measures and tells**: the
  prose growth per round stands in the log and in the round record's header, next to the number of
  items. The question "what did the last round buy" needs both halves of the answer in one line.
- **A length ceiling the order did not ask for makes acceptance unreachable.** I gave the design a
  default of 40,000 characters of prose. Round 2 closed four blocking defects by writing more
  specification and grew to 42,126; round 3 got "cut 2,126 and add nothing" — and grew to 44,590.
  No agent was wrong: the critic demands clarification, the gate demands cutting, and together this
  is impossible. In the article pipeline the same budget block worked the first time, because there
  the ceiling was named by the order. The script **does not substitute a ceiling of its own** — only
  a floor; if the order is silent, the gate measures and does not judge.
- **A length overrun served as an item in a list is cured by writing more.** A round got
  `max_prose 30000 exceeded (got 30616)` as item sixteen of sixteen and answered it with nine
  thousand characters of well-argued material: every edit added a meaningful sentence, and the draft
  grew instead of shrinking. The ceiling is arithmetic the script knows, so it is the script that
  says how much to cut and forbids adding in that round.
- **An `ok` verdict with remarks is not a work order.** A critic accepted the draft and attached six
  notes; they got into the round record and in the next round were served as mandatory. They are
  exactly what filled the round that was supposed to cut. The remarks of a critic that accepted are
  served marked as optional.
- **The writer silently loses remarks.** Five items came back verbatim in two rounds in a row: the
  same corpus named wrongly, the same config field values without a source, the same dropped line
  in a "complete" code quote. A requirement in the order did not help — the writer's contract had no
  place to write what it did NOT do: the schema asked for `changes`, that is, only what was done.
  The cure is the remark sheet: remarks are numbered in **one list** per round (three sections, each
  numbered from one, make the number meaningless), the writer must return a line for every number
  with the status `fixed` or `declined`, and the script checks the numbers against those it issued.
  What was not covered and what was declined carries over into the next round and into
  `UNRESOLVED.md`.
- **Agents leave scratch files in the repository root.** In one day `temp_data.py`,
  `rounds_output.json`, `final_structured_output.json`, `rounds_structured.json` were found there —
  and three of them got into a commit, because of `git add -A`. `sweep_junk.py` did not see them,
  because it looked **only at directories**; now it looks at files too, but deletes only with
  `--files` and never files git tracks. The mechanism for files is different from that of the
  garbled-name directories: an agent redirects a command's output into a file to read it back,
  instead of returning it. The prohibition on this stands in the `gate_runner` prompt.
- **A channel through an agent has a budget.** `tools/rounds.py` printed all remarks of all rounds
  verbatim — five rounds is about a hundred kilobytes of JSON. The carrier returned two rounds
  instead of five through the schema, the script read it as "two done", started the loop from the
  third and ran four rounds instead of one: 1.4 million tokens. The volume must be limited where it
  is produced (`--last-only`), not by hoping for the carrier. The symptom: a stage that reads,
  through an agent, something that grows with the number of rounds or files.
- **A silent pass through the loop.** When rounds ran out, the old engine let through a node with
  an unfulfilled `revise` verdict, and the article shipped with three unresolved remarks. The
  generator does not emit this: unresolved remarks must reach a file and `log()`.
- **A length floor cannot tell work from the form of work.** The analyst writes the artifact's
  frame — all the contract's headings, in the right order — and fills them pass by pass. Both stages
  were caught: 1748 bytes of headings alone, and 68 KB with three empty aspects out of six. Either
  would have passed `--min-length`, and the writer would have built those article sections on
  nothing. `--no-empty-sections` names the empty headings one by one; acceptance hands the list back
  to the analyst rather than ordering the analysis anew: it has `Edit`, and there is no reason to
  rewrite what is filled.
- **A port for an extension the listing did not look for.** The script always gave the analyst a
  port for `_index.json`, while the listing ran with `--ext .md` and could not see the index. For two
  aspects the finder put everything into one summary and wrote no index — the agent got a path to an
  unwritten file, that is, a question that cannot be answered. A port is created only for what the
  listing actually saw; the listing filter and the set of ports must ask about the same thing.
- **A warning only in `log()` is a warning into nowhere.** An aspect without a single source means
  the article's section stands on one unconfirmed summary. A line in `log()` lives in the run's
  transcript, and the transcript is exactly what is already gone by the time someone asks why a
  section is thinner than the rest. Everything that changes how the result is read goes to disk
  next to it.
- **The busy lock locked itself against the previous stage.** Stages are launched back to back: a
  human reads the result of `research` and two minutes later launches `draft`, and the lock sees the
  previous stage's audit receipt, 72 seconds old, and declares the directory busy. The run is stopped
  on a false alarm, and the `ignoreBusy` flag removes the lock entirely, that is, the real one too.
  Now the closing audit of a stage writes a receipt with `release: true` (`--log-release`), and
  `busy.py` reads it as "free", however many seconds old it is. A run that crashed does not reach
  the audit and is still held by the window. `busy`'s own receipts do not count as work:
  otherwise a launch that failed right after asking locked its restart with its own question.
- **A number that is not in the figure brief is invented by the generator.** The brief for the
  "no scaling" panel named only the peak 0.9013, the generator copied the other weights from the
  neighbouring panel, and the Kimi K3 critic let it through. A figure with wrong numbers passed as
  finished. Now the brief must list every number that is to appear in the picture — for a
  comparison panel, both sets; the looking agent checks every number in the figure against the
  section text and names a discrepancy with both values.
- **The hook is blind to files created by a Bash redirect.** The example corrector left five
  `scratchpad_check*.py` in the repository root, and `stop_audit` recorded `no_writes` for it: the
  hook sees only `Write` and `Edit`. The corrector's prompt now requires Python from stdin or from
  the system temporary directory; `sweep_junk.py --files` removes whatever still leaks through.
- **A limit of two rounds is one revision round.** The first round is always `revise`: the critics
  see the text for the first time. The loop ended on the limit with both critics on `revise` and
  14 items; a manual restart up to four rounds closed it. The `maxRounds` default is now 4; idling is
  held off by the plateau, not by the limit.
- **Figures are drawn next to the article, not in a copy.** The illustrator copied the article into
  its own directory and drew there, the original article referred to a non-existent `figures/`, and
  the pictures "did not display". When the run directory is the article's directory, the script
  copies nothing and writes nothing into the text. The 4K render stays in the tool's directory; a
  copy 2000 wide goes into `figures/` through `tools/shrink_png.py`.
- **Cyrillic in argv comes back through the back door.** The prohibitions moved into files precisely
  because of the code page, and right after that I put call notes (`--log-note`) in Russian — the
  same argv, the same carrier agent's Bash, the same dependence on the shell. Everything that goes
  to a tool as an argument is ASCII; Cyrillic travels only in a file.

- **The platform passes every subagent the human's last chat message as "a user request that
  outranks the task".** A carrier on haiku read "check that the prompts are in English, then check
  with a new run" as its own task: for eight minutes it ran pytest, dry-run and grep, wrote
  `VALIDATION_REPORT.txt` into the repository root and returned an invented report of three
  completed rounds. The script believed it and skipped the loop entirely (2026-09-20).
  Three locks: carriers on sonnet; the carriers' prompts and the shared task tail say that the
  relayed request is context, not an instruction; the script trusts the rounds report and the gate
  report only in the form the tool prints (the number of rounds matches the length of the list, the
  gate's report has `chars`). The saving on haiku was about 1% of a run; the failure cost a run.

### Rakes of 2026-10-04 (requirements, pains, proposal, scene)

- **A named launch can run a stale script.** After an edit in the same session,
  `Workflow({name})` ran the copy one commit older. Launch by `scriptPath` and grep the run's
  script copy for the change.
- **`rounds.py --last-only` lists one round.** Its measures count every round, so a shape check
  "list length equals the count" rejected every history of two rounds or more, and a continued
  run judged its accepted requirements from round 1 again, letting the corrector edit them and
  overwriting the round record. The report is matched by the newest round's number; the dry-run
  stub answers a rounds.py command the way rounds.py does.
- **A subagent may not write a file named `report.md`.** The harness refuses it, and the writer
  still answered "written". Run summaries are `outcome.md`, and every record is checked on disk
  by the gate after it is written.
- **Without the client's name an agent writes a placeholder.** "Client A" reached a client
  proposal seventy-six times. `args.client` goes into every writing and judging task.
- **A quote located in an image cannot be found in a text source.** check_quotes skips quotes
  whose cell or attribution names an image, and checks straight quotes that carry an
  attribution (a voice sheet had passed with zero quotes checked).
- **Our own shared screens are not the client's words.** Frames of our prototype became
  requirements; the extractor now records only what the client said about them.
- **HIGH only is too loose for a client document.** A proposal accepted with seven MEDIUM kept a
  worked example without numbers and the client's main question deferred; three MEDIUM send it
  back, as the proposal profile says.
- **A critic writes confirmations into its defects list** unless told not to; each one then
  reads as a remark and sends the work back.
