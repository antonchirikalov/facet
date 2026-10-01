# What turned out to be hard: a document pipeline on Dynamic Workflows, taken apart

Material for an article. Collected here is what came to light while building collimator — a
generator of document pipelines for Claude Code — and above all: why it went hard, what exactly
failed, and why nobody read the files that were written.

Every number below is taken from a live run or from a log. Where a claim is about the behaviour
of the platform, it has been checked by an experiment, and the experiment is named.

If you do not want to read further, here is the one idea. It was hard not because of the
platform. Of the twenty-odd defects that actually cost money and time, four can be put down to
the platform. The rest are errors in the design of the pipeline itself, and they would have
happened in exactly the same way on any other engine.

## How to read this document

The problems are arranged not by time but by nature, because each nature has its own cost and
its own way of being detected:

1. What the platform lacks. Detected at once, cured by a workaround, cheap after the first time.
2. Why runs failed. Detected loudly, but cured somewhere other than where you look.
3. Why nobody read the files that were written. Not detected at all until you start looking for
   it on purpose. The most expensive class.
4. How the intermediary lies — the agent through which the script learns everything about the
   outside world. Detected by odd numbers in a report.
5. Why the revision loop does not converge. Detected only by the token count.

After that — hooks (the only check an agent cannot get around), four independent records of a
run, an honest list of the problems of the approach itself, and conclusions.

## Glossary: six words needed below

A Dynamic Workflow is a JavaScript script that Claude Code executes itself, and inside which
there is a function `agent(prompt, options)`. Each call to it launches a subagent: a separate instance
of the model with its own context, its own set of tools and its own system instruction. The
script is the conductor: it decides whom to call, in what order, what to hand to whom and what to
do with the answer. It does not think or write texts itself.

A subagent is the performer of one narrow job. It is defined by a file in `.claude/agents/`: its
system instruction and the list of tools it is allowed. We have twelve: a source finder, an
analyst, a writer, two correctors, two critics, an intermediary for checks, a copier, a record
scribe and a brief writer.

A hook is a command that Claude Code runs by itself in response to an event: before a tool call,
after a subagent stops, and so on. Not an agent, not part of the script: an ordinary operating
system process that receives JSON about the event as input. Hooks get a section of their own,
because they turned out to be the most reliable source of truth in this design.

Three more words that come up often below.

A gate is a deterministic content check, a Python script. It measures the length of a text,
looks for forbidden phrases, checks the arithmetic of an example. It judges nothing by taste: it
returns numbers and a list of violations. The name stuck because the pipeline decides by its
answer whether to go on or redo.

An intermediary is a subagent with one job: run the command the script composed and return its
output. The script cannot run commands itself, so such an agent always stands between it and any
measurement. In our pipeline it is called gate-runner and is called more often than all the others.

A fan is the place in the script where, instead of one agent, several are launched in parallel:
one per aspect of the topic, one per file. The word matters because the width of the fan must be
known in advance, and this restriction comes back to bite in the third section.

## What went in and what came out

The task: from a one-sentence order, get a technical article or a technical design — with a
search for sources, analysis, writing under critics and acceptance. Not "generate a text", but
take a document through a pipeline where each step does a narrow job and leaves traces from which
one can later reconstruct what happened.

The design: a pipeline declaration in YAML is compiled into a Dynamic Workflow script and into
subagent definitions. The main rule — we generate, we do not execute. Agents are launched by
Claude Code with its runtime; we have no scheduler, no ledger, no recovery after a failure. The
previous version of the project had all of that, and all of it was killed deliberately: the
platform does execution better and changes faster than we could keep up with.

The actual state, and it has to be named right away, because otherwise the whole analysis that
follows reads wrongly. The compiler is half written, and not the right half. Generating agent
definitions works — 138 lines of Python. Generating the script does not exist at all: no
`emit_workflow.py`, no graph, no command. The pipeline scripts are written by hand, and all of
this week's edits went into them, not into the generator. A separate section below examines how
much of the machinery carries over between pipelines and what follows from that for the compiler.

Today's scale: the pipeline script is 2192 lines, twelve built agents, 28 in the library, 1241
lines of deterministic Python tools, 222 tests with no network and no calls to the model, 61
commits.

The last run of the article about the attention mechanism: 37 923 characters of prose, six
revision rounds, both critics approved, seven open remarks — all marked "optional". The previous
version of the same pipeline on the same topic: thirteen rounds, eight open, four of them
substantive, and the substance critic's verdict — "redo".

The difference is not in size — 37 812 characters against 37 923. The difference is that there
are now 92 quotations from sources against 45 at the same size: the same place in the text now
rests on a note about a specific work rather than on the model's memory.

The cost: three launches for this article, 4.66 million subagent tokens. This is expensive, and
part of that cost is direct payment for the defects examined below.

## 1. What the platform lacks

This section is about the limitations of Claude Code itself, not about our mistakes. All of them
are honest, all are described in the contract, and all shape the design more strongly than it
seems at first glance.

### The script has no filesystem and no shell

The script can neither open a file nor run a command. Agents read and write files; measurements
are made by Python launched by an agent with access to Bash. The script only passes paths and
gets structured answers back.

This is not a limitation one fights against — it is the axis of the whole design that follows.
Almost all the problems in the third and fourth sections grow from here: between what the script
knows and what lies on disk there always stands an agent.

### There is no clock and no randomness, and this has been checked

The claim: a script cannot call `Date.now()`, `new Date()` or `Math.random()`.

The check. I submitted for execution a script that calls these functions inside `try` and records
what came out. The answer came not from the script but instead of it:

```
Workflow scripts must be deterministic: Date.now()/Math.random()/new Date() are unavailable
(breaks resume). Stamp results after the workflow returns, or pass timestamps via args.
```

That is, the refusal happens at submission, before launch: the script did not begin executing at
all. My earlier wording "the runtime strips them out" was wrong — they are not stripped, a script
containing them is not accepted.

The second experiment: the same call, but only mentioned in a comment and inside a string
constant. Such a script was accepted and executed. So the check distinguishes a call from a
mention, that is, it parses the code rather than searching for a substring.

Why it is so. Resumption in Dynamic Workflows works by replay: when a script is restarted, the
longest unchanged initial run of `agent()` calls is not executed again but returns the saved
results. A match is determined by the call — by the prompt and the options. So the script must,
on the same input, build the same prompts in the same order; with the same script and the same
arguments the replay hits the cache completely. A clock and randomness break this: branching on
the current time gives a different order of calls and different prompts, the cache does not
match, and the replay quietly drifts apart from the original — part of the work is redone from
scratch, part is served with answers to a different question. It is cheaper to forbid
non-determinism at the entrance than to catch its consequences.

The practical consequence turned out larger than it sounds. The script cannot name the run
directory by the moment of start, so the name is minted outside and arrives as an argument. Before
this was in place, seven launches of one article went into one directory, where each one
dutifully picked up the material of the previous one — and there was nothing to compare these
runs with one another.

### No `import()`

Work with libraries lives inside the agents' tasks. The consequence is more unpleasant than it
seems. The pipeline is split into stages because the process does not survive a restart, but the
script cannot be cut into files: the shared hundred and twenty lines — configuration, answer
schemas, tool commands — would turn into two copies that start diverging after the first edit.
Hence one file for all stages, and it is big.

### No human in the middle of a run

You cannot ask the user anything during execution. A human's decision point is a stage boundary,
that is, a separate command. We gave up dialogue inside a run entirely and did not regret it: the
pipeline became a set of short launches, each of which leaves a result on disk.

### Small things, each of which cost a run once

The `meta` block in a script must be a pure literal: no variables, no calls, no template strings.

CRLF or a null byte in the script file — a launch refusal with a message about "control characters
that would be hidden in the approval dialog". On Windows `autocrlf` brings CRLF back on every
checkout, so the line ending had to be declared in `.gitattributes` and the bytes checked before
each launch. Now it is a test.

The least obvious: a new agent is not available in the same conversation turn in which it was
created. The list of agent types is taken once and held until the next human message. The file
is there, the generator has run, the stubbed run is green — and the live run fails instantly:
`agent type 'brief-writer' not found`, and the list of available ones shows the agent built a
turn earlier. The working order: build the agents, wait for the next message, launch.

## 2. Why runs failed

Three causes, and only one of them is a bug in the code.

### A run lives inside the CLI process, and the process restarts by itself

A process restart, or the session moving into a background task, kills the workflow halfway. In
one working day of the machine this was built on — five self-updates and one exit on idle. The
mechanism of resumption by run id saves you only within the same session; in a new one the cache
is empty.

One live run lost forty minutes of searching this way, and then it got worse: resumption started
from the very beginning, the brief writer invented new aspect slugs, and eleven source files
already found were left lying under the old names, handed to no one.

The conclusion from this is not "make resumption more reliable" but change the notion of a save
point. A save point is not the cache but the disk. Before spending, the script asks the disk what
is already done, and skips such stages with an explicit entry in the log.

This solution has a hard condition for stability: the brief must write the aspect slugs to a file.
An aspect slug is the name by which the source files are later named; if it lives only in the
process's memory, then after a restart there is nowhere to take it from, and the whole research
goes again. Critics' verdicts are the same story: each revision round is written as a separate
file, and the round limit becomes a property of the article rather than a property of the launch.
Without this, three crashes give six revision rounds where the order allowed two.

### A session limit looks like a broken agent

`You've hit your session limit` comes from three agents in a row, and the script sees only
`null`. The writer that died on the limit managed to write the file but not to answer: the
artifact exists, the result does not.

Hence the acceptance rule: look at the file, not at whether the agent came back.

### Bugs in the script itself

One was tellingly expensive: `SOURCE_PATHS is not defined` in the last `return` line — 468 thousand
tokens and twenty minutes of work to learn about a typo. An ordinary syntax check is useless here:
`node --check` parses a file with `export` as CommonJS and stays silent.

The cure is a stubbed run. The `agent()` function is replaced by a stub that answers according to
the call's schema (that is, produces a plausible object of the required shape), and the script's
real control flow is executed. Not in two modes, but in every branch the script has; ours has
nine: the full path, continuation from disk, research only, the pipeline without correctors, all
the failure branches, a busy directory, a mismatch between order and brief, an intermediary that
truncated its answer, and a loop already standing still. This took an evening and has caught
everything since.

## 3. Why nobody read the files that were written

This is the main part. All the losses found in one day had one and the same form: a file was
produced, and nobody read it. Not one looked like a failure at the moment it happened — the run
went on, the article came out, there were no errors. This is the most unpleasant property of this
class of defects.

### What exactly was lost

Twenty-five source notes written by the finders were handed to no one. A measured run: four
per-aspect summary files totalling 79 kilobytes reached the analyst, while 28 files totalling 260
lay on disk. That is, seventy percent of what was found was opened by nobody; from here on I call
such files orphans.

This is the most plausible explanation of why attribution errors survived eleven revision rounds.
The writer quoted the per-aspect summary while the note on the specific work lay next to it
unopened, and the verifier was given the same four summaries to check against — that is, it
checked the text against the same source it had been written from.

The whole directory of a failed finder: the aspect dropped out of the list, and nobody looked at
what was lying there.

The file `_index.json` with the URL and status of each source — written from the very beginning and
read for the first time a week later. The information about the material's provenance lay one
directory away from those who needed it.

Agents' scratch files in the run directory and in the repository root. In one day four turned up
in the root, and three got into a commit, because `git add -A`. Their mechanism is different: an
agent redirects a command's output into a file in order to read it back, instead of returning it.

### Why this happens

The script cannot read a directory. So the width of the fan — how many parallel agents to launch
and what to name their files — must be known in advance, before any one of them starts working.
Only the aspects from the brief are known in advance: their slugs become file names, and one
finder is launched per aspect.

But the finder, by its contract, also writes a file for each source it keeps, and those names the
script cannot know. Asking the agent where it put the file is not allowed — and this is a separate
project rule, not a precaution. The script invents the path. If a "path" field is added to the
answer schema, the agent gains a way to report on the work without doing it: saying where it
supposedly wrote is cheaper than writing, and from the answer the two cases cannot be told apart.

We confirmed this ban at a high price. A disk check once returned absolute paths with backslashes,
the script compared them with relative POSIX ones, nothing matched, and four finders and the
analyst worked again over material that was already done. Moreover, the previous run of the same
code returned relative paths and worked: a bug that fires every other time waits for an expensive
run. So results are matched by index — the order of commands was set by the script — and the
"path" field has been removed from the schemas entirely.

### What cures it

Enumeration. A separate tool returns the list of files in a directory, and from then on the analyst
and the verifier get all of them, while the writer still gets the summaries, so as not to pay for
260 kilobytes on every revision round. Enumeration is not the same as asking for a path: the script
still names everything it writes itself, and this is only a report of what exists.

And each finder has its own directory. In a common heap two finders working different aspects of
one topic inevitably reach the same well-known work and save it twice under different names:
`annotated-transformer-maskirovanie-kod.md` and `annotated-transformer-scaling-masking-code.md` are
one source saved by two agents. A directory per finder makes the collision impossible and allows
enumerating by aspect rather than sorting through one heap.

### How it is now checked that nothing was lost

The idea is simple: compare two lists. The first — what lies on disk. The second — what at least
one agent received as input. The difference between them is the losses.

The second list has to come from somewhere, and here is the important detail. The script keeps it,
and keeps it not as a separate action "and now write it to the log", but inside the very function
that composes the task text for the agent. It is built like this:

```js
const touched = new Set()          // every path handed to an agent goes here

function task({ inputs, output }) {
  for (const i of inputs) touched.add(i.path)   // <- accounting
  touched.add(output)                            // <- accounting
  return `INPUT\n${inputs.map((i) => `${i.port}: ${i.path}`).join('\n')}\n\n` +
         `OUTPUT\n${output}\n\n` + OUTPUT_RULE   // <- the task itself
}
```

`touched` is a set of strings to which every path that got into a task text is added. There is only
one way to hand a file to an agent: name the path in the task. And the task text is assembled only
by this function, and the same function makes the record in the same two lines. There is no
separate way in the script to pass a file bypassing the accounting — one would have to write a
second such function.

That is the whole trick. The accounting cannot be forgotten, because it is not a separate step but
part of the same action. The first version was built differently — the path was passed in one place
and recorded in another — and the two diverged within the very first week.

At the end of a stage the script asks for the whole run directory to be enumerated and subtracts
one from the other:

```
[audit] files in the directory 34, read by agents 34, read by nobody 0
[audit] no losses: everything produced has been read by someone
```

Files missing from the second list are printed by name, not counted. A number says that something
is missing; a name says what exactly, and without the name the report is useless — you would have
to search by hand anyway.

One exception had to be made explicit. The snapshot of each round's draft exists for a human: none of
the agents reads it, and none should. Such a file is entered into `touched` by a separate line right
in the code, with an explanation next to it. Otherwise it would end up among the losses every run,
and an audit that complains every time, rightly and wrongly mixed together, stops working as an
audit.

## 4. How the intermediary lies

The script can neither read files nor run commands. So any measurement reaches it through an
intermediary agent: that agent runs the command, reads the tool's output and returns it according
to the given schema. The carrier is a channel that has a budget and its own opinion about what in
the output matters.

The first case. The tool that reads the revision round records printed all the remarks of all rounds
verbatim: five rounds — about a hundred kilobytes of JSON. The carrier returned two rounds instead
of five. The script read this as "two done", started the loop from the third and ran four rounds
instead of one. A million and a half tokens for a silent truncation.

The conclusion: volume must be limited where it is produced, not left to the intermediary. The tool
got a "last round only" switch, and the symptom is now stated simply: any stage that reads through
an agent something that grows with the number of rounds or files is suspect.

The second case, in a purer form, happened yesterday. The tool printed 37 paths. The agent returned
one to the script — the run directory itself. The audit reported:

```
files on disk 1, read by agents 38, orphan: docs-runs/vnimanie-v-transformerah-...
```

The answer was wrong in its entirety, and it looked like an answer.

The cure is general and, it seems, the only one that works: the intermediary has to be checked by
itself. The answer schema now requires not only the list but also the number from the tool's
measurements. An agent that truncated the list truncates the number too, they diverge, and the audit
honestly says it was not carried out. The number is the one thing a truncating agent does not
shorten.

Hence a more general principle: if the only source of a fact is what an agent returned, you do not
have a fact. You need a second record, independent of its memory and its good faith.

## 5. Why the revision loop does not converge

This is what we did not expect at all, and what cost more than everything else put together.

The first design was the obvious one: a writer and two critics in a circle until the critics
approve. A live run ate six rounds and five million tokens, and the same five remarks came back
verbatim. The analysis showed several independent causes.

### The acceptance condition was impossible to meet

Requiring two independent judges to find nothing at the same time in a text of forty thousand
characters is a condition that simply is not met. Over eleven live rounds the critics approved in
turn, never together, and the total number of remarks sat on a plateau of 8–10. A hint to the
writer about which axis had already been approved did not change this: the problem was not the
writer.

So the loop got a second stopping condition besides approval. The script remembers the best
result — the smallest number of remarks achieved over all rounds. If two rounds in a row do not
beat this result, the loop stops: it has reached a plateau, and the next round will give the same.
The rest is decided by the author from the report on what remains open. Rounds 9–11 of one run cost
two and a half million tokens and did not beat the result of the eighth.

### A critic can only report, and a report costs a round

A critic that discovers `exp(2.887)` written as 17.940 instead of 17.939 spends a whole revision
round on it. So correctors were placed between the writer and the critics — agents that fix what is
decidable: they recompute the example's arithmetic in Python and check claims against the notes.

In the very first round with them a corrector found what six rounds of two Opus instances had not
seen: three discrepancies in the fourth digit and "8.34% at 12 heads" instead of 8.33%. By eye this
cannot be caught in principle.

The rule: everything a corrector can close must not become a remark.

### The writer silently lost remarks

Five items came back verbatim in two rounds in a row. The writer's contract had no place to write
what it did NOT do: the schema asked for a list of changes, that is, only what was done.

It is cured by a ledger of answers. Remarks are numbered in one list per round, the writer must
return a line for each number with the status "fixed" or "declined", the script checks the numbers
against the ones it issued, and whatever is uncovered or declined is carried into the next round and
into the report.

Yesterday a defect of the same kind turned up in this very ledger, coming in from the other side:
the substance critic numbers its list itself, and the ledger numbered it a second time. The round
record read "1. 1. …", and further on the two numbers diverged — the sixth item of the ledger turned
out to be the first style item. And the writer answers precisely by number.

### What was declined must reach the critics together with the reason

A critic that does not know why a remark was declined raises it again, the writer declines it again,
and the pair burns a round agreeing to disagree. Three rounds of a live run went exactly that way.

### An overrun in length must not be served as an item in the list

A round received "over by 616 characters" as item sixteen of sixteen and answered it with nine
thousand characters of well-reasoned material: each edit added a meaningful sentence, and the draft
grew instead of shrinking.

The ceiling is arithmetic, which the script knows. So it is the script that says how much to cut,
and forbids adding anything in that round. Served this way, the cut worked the first time: 41 877
characters became 37 829.

### And the same defect as with the round limit, only in the plateau detector

Yesterday's run gave 16, 12, 16, 12, 16 remarks per round. The plateau detector should have stopped
at the second twelve and did not, because rounds 1–2 were judged in the previous process, and their
count did not get into the new launch's memory. A property of the launch instead of a property of
the article — exactly what had already been cured for the round limit, and in another place it was
missed. Two rounds out of six turned out to be superfluous, on the order of a million tokens.

## 6. Hooks: the only check an agent cannot get around

A hook is a command that Claude Code launches by itself in response to an event, as a separate
process, receiving as input JSON describing the event. It is not an agent and not part of the
script, and precisely for this reason the hook turned out to be the most reliable source of truth in
the whole design.

We have one configured, on the subagent stop event:

```json
"hooks": { "SubagentStop": [ { "hooks": [
  { "type": "command", "command": "python -X utf8 tools/stop_audit.py" } ] } ] }
```

What it does. It opens the transcript of the agent that has just finished, extracts from it all of
the agent's own `Write` and `Edit` calls — that is, which files the agent wrote — and checks whether
those files are on disk now. It writes one line per agent: the agent type, how many files it wrote,
and the verdict: everything in place, wrote nothing, or wrote and did not leave it.

Why this is sturdier than everything else. The hook runs in Claude Code's own process, costs nothing
in tokens, and the agent cannot skip it — it does not even know about it. The hook looks at what
cannot be faked: not at the agent's words about its work, but at its actual tool calls from the
transcript. An agent that called `Write` and left nothing ends up in the log without anybody being
asked anything.

Over three calendar days the hook collected 351 records: 129 agents actually wrote files and all the
files turned out to be in place, 222 wrote nothing (a critic is not supposed to). And it recorded a
finder writing seven or eight files per call — those very orphans from the third section, long
before anyone noticed that nobody read them.

What the hook cannot do, and this was worth checking separately. It cannot block — for workflow
agents this has been measured: the hook fires, the data arrive in full, exit code 2 is ignored, and
the agent still finishes normally. So our hook is called an auditor, not a gate, and always returns
zero: a hook that fails must not take the run down with it.

The first version of this hook looked in the agent's structured answer for a "path" field and
checked whether a file lay there. Of fifty log lines forty-eight said "path not declared" — because
by that time the "path" field had been deliberately removed from the schemas, for the reason in the
third section. The hook became useful exactly when it stopped asking the agent and started looking
at its actions.

Two other uses of hooks in this design: isolation of the subagents' working directory is done by a
hook on the before-tool-call event, and secrets in the agents' environment by configuration, not
code. We wrote neither ourselves, and that is the right division of labour.

## 7. Four records of a run, three of which survive a process crash

A full answer to the question "was everything handed over correctly and was nothing lost" is
assembled from four independent sources. None of them is a memory of the model.

| record | what it says | who writes it | survives a crash |
|---|---|---|---|
| hook log | what the agent actually wrote and whether it is on disk | Claude Code | yes |
| tool log | what each deterministic check found | the tool itself | yes |
| directory audit | whether anything is left unread | the script, by subtraction | yes, files on disk |
| handoff record | what was meant to be handed to whom | the script composed it, an agent wrote it | no |

The last is the only one that accumulates in memory and is written at the end of the stage. That is
its honest limitation, and it is tolerable precisely because the first one covers it in substance:
the handoff record speaks of intention, the hook of an accomplished fact.

The tool log deserves a separate word, because it paid for itself fastest. Each tool leaves a
receipt: one line per call — arguments, verdict, measurements, problems, and never the content.

```
14:28:38  gate      ok=False {"chars": 27572, "prose_chars": 24387}
                    problems: max_prose 100 exceeded (got 24387)
16:05:16  gate      ok=True  round 4
16:14:52  listing   ok=True  {"files": 37}   audit: anything produced and never read
```

The tool writes, not the agent: the intermediary is forbidden to create files, and this ban has
already justified itself twice. A measurement leaves a receipt, and it is written by whoever
measured. Yesterday these lines turned up three defects out of eleven, including the one where the
intermediary delivered one path out of thirty-seven.

And one detail that at first seemed cosmetic. A log line carries a note of what the call was for.
Without it a clean run opens with eight "no file" lines, and that looks like eight failures — although
at the start of a run "no file" is the correct answer, that is exactly how the script decides what
needs building. The same words when checking an agent's result are a defect. The same words, the
opposite meaning; only the note on the call's purpose tells them apart.

## 8. Problems of the approach itself, with no attempt to defend it

The script is big and growing. 2192 lines, of which orchestration is almost all, because there are
no prompts in it at all. The absence of `import()` does not allow cutting it without producing two
diverging copies of the shared part. This is tolerable, but it is a wall you will hit.

The disk cannot be read, so the dimension of any fan must be known in advance. Every "how many of
them there will be, we'll find out along the way" turns into a separate enumeration stage through an
agent — that is, into one more channel with a budget and one more way to lie.

Every fact about the world costs an agent call. Checking that a file is in place — an agent.
Measuring length — an agent. Finding out how many rounds have been done — an agent. Cheap agents are
plentiful, but they are not free, and each can return the wrong thing. In the last run, of 43 agents
more than twenty were intermediaries — they composed nothing, they only ran commands and returned
the output.

A run does not survive the process, and the process restarts by itself. This is cured by stages and
the disk, but it means that "one command — one stage" becomes a discipline rather than a convenience,
and that nothing but files can be passed between stages.

A conversation turn is the unit of granularity of the agent registry. Generated an agent — you
cannot launch it until the next message. For automation that generates its own agents, this is a
mandatory pause in an awkward place.

A bug in the script costs a full run if it is not caught in advance. The script has no linter of its
own, the syntax check does not work, there are no types. A stubbed run covers this almost entirely,
but it had to be built, and before it existed we paid with several runs.

Against all this stands one argument, and it turned out stronger than the sum. In the previous
version of the project we had our own scheduler, our own ledger and our own recovery after a failure
— roughly half the code and almost the entire source of our own bugs. Of the ten rules that engine
enforced itself, two survived the move, and both concern not execution but the contract between the
script and the agent: input-output instructions are generated from the contract, and file
collections are created by the script, not by the agent.

## 9. Where we arrived

Principles that withstood the runs. Each has been paid for, and next to it is said with what.

We generate, we do not execute. No scheduler, ledger or recovery — the platform does that.

There is not a single prompt in the script. The script passes only what it knows itself: paths,
commands, round numbers, the list of aspects for the parallel launch. The input-output section of an
agent's instruction is generated from the contract and never written by hand. Before this rule the
analyst once sat between two descriptions of its own output — its instruction and the script's
requirement — and produced neither.

Paths are invented by the script, and they are not asked back. Results are matched by index,
because the order of commands was set by the script.

Everything that is decidable deterministically is decided by Python, not by the model. Length,
clichés, bold type, the example's arithmetic, the number of the last round, empty headings, whether
a directory is busy. Asked to judge by eye, two critics put the length at "10 500–11 500" where the
answer was 10 033.

Prohibitions and the profile of the author's manner are data, not code. The list of clichés lies one
regex per line next to the voice description, and a human edits it without opening the parser. A
missing pattern file is a problem, not an empty check: a gate that found no violations because it
had no patterns reads exactly like a gate that passed.

One launch — one stage, and nothing but files is passed between stages.

A new run — a new directory, and this is a rule, not a convention. The script refuses to begin
research where a result already lies until it is told explicitly what was meant: I am continuing an
interrupted run, or I am rebuilding here from scratch. Three intentions — three different actions,
and none is guessed on the caller's behalf, because a wrong guess is expensive in one direction and
invisible in the other.

The check is not in what the agent said but in what lies on disk. And that check is a subtraction,
not a promise.

No check has the right to stay silent. "Nobody looked" and "looked, all is well" coincide only for a
report nobody reads, so a skipped check goes into the open items as an explicit line.

## 10. Conclusions

The choice of orchestrator does not determine the quality of the document. The shape of the revision
round does. We compared Dynamic Workflows with our own Python engine and got nine defects in the
pipeline's design against four defects of the platform — and it was the former that burned the
tokens.

A defect that does not look like a failure lives until someone starts looking for it by subtraction.
All artifact losses had one form — "produced and not read" — and not one gave an error, a crash or
even a warning. The run went on, the article came out, and seventy percent of what was found lay
unopened.

A verdict that can be given without doing the work will be given. The checking agent gave "all in
order" to three pictures, two of which carried English labels in a Russian article. What helped was
not strengthening the wording in the instruction but a schema field that cannot be filled without
doing the work: "write out every label verbatim". After that both the labels and a substituted
multiplication sign were found. This seems to be the most transferable conclusion of the whole
story: demand not a verdict but evidence.

Everything that depends on the process must be treated as lost. The round limit, the best-result
count, critics' verdicts, sources found — in the first version all of this lived in the process's
memory, and each had to be moved to disk after the process died. Not because it is unreliable, but
because it restarts by itself, routinely, several times a day.

The agent is the least reliable element of the design, and its role must be assigned by that
measure. We seriously considered a "logger agent" that would write a full log of the run. The idea
was dropped precisely because an agent had already lied twice in that role: it truncated a tool's
output and returned paths in a different format. Logs are written by whoever measured — the tool
itself. And the most reliable check is not an agent at all but a hook: a separate process that looks
at actions, not at words.

And the last, the most uncomfortable. Recorded pitfalls do not help by themselves. "Two runs on one
directory corrupt the state" stood in the project instructions in black and white — and yesterday I
repeated it: the directory log was silent for six minutes, I read the silence as the end of the run
and launched a second one. The silent ones were the finders, which do not call tools at all. The
provenance of the resulting draft after that cannot be proven.

What helped was not "read more carefully" but making the question observable: a separate tool looks
at the age of the last log line, the script asks before the first spend, and on a live directory it
answers "busy". A rule that cannot be checked by a machine is not a rule but a wish.
