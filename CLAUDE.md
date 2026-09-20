# facet — document practice on Claude Code Dynamic Workflows

> This file is loaded into the context of EVERY subagent the workflows spawn, so it is short
> and in English. Human-facing material lives elsewhere: `SPEC.md` (decisions, levels,
> pipelines, plan — Russian), `docs/workflow-conventions.md` (the rules of the scripts and
> every rake paid for by a live run — Russian; read it before touching a script or a tool),
> `docs/decisions/` (dated write-ups). Whatever an agent reads is English; whatever only a
> person reads may be Russian.

**The one rule: we generate and run, we do not write orchestration.** Workflow scripts are
written by hand; agents are run by Claude Code. No scheduler, no ledger, no compiler. Python is
a ruler an agent calls: it measures, it never decides (SPEC R2, R6).

## Commands

```bash
uv run python -c "from pathlib import Path; from collimator.emit_agents import emit_all; print([p.name for p in emit_all(Path('library/agents'), Path('.claude/agents'), Path('.claude/skills'))])"   # agents; fails if a named profile is missing from .claude/skills
uv run pytest                                          # no network, no LLM
uv run ruff check --fix . && uv run ruff format .
uv run mypy collimator                                 # strict
node tools/dry_run.mjs .claude/workflows/<script>.js ok '<args json>'    # stubbed run, EVERY branch
node tools/dry_run.mjs .claude/workflows/<script>.js bad '<args json>'
python -X utf8 tools/newrun.py --base docs-runs --label <what>          # directory name for a NEW run
python -X utf8 tools/gate.py --file <file> --no-empty-sections --rows-have-source --unique-ids '<regex>'
python -X utf8 tools/rounds.py --dir <run>/rounds --last-only
python -X utf8 tools/listing.py --dir <run>/sources --recursive
python -X utf8 tools/busy.py --file <run>/tools.jsonl --now "<ISO>"
python -X utf8 tools/sweep_junk.py --dry-run
python -X utf8 tools/confluence_publish.py --draft <file> --parent-id <id> --json <out.json>
```

Done means: pytest green, mypy green, ruff clean, generated files rebuilt and committed, and
`dry_run.mjs` in every mode of any script that was touched.

## Rules that break a run when broken

- **Everything an agent reads is English**: the whole prompt, task texts in scripts, schema
  `description`s, command arguments, the profiles in `.claude/skills/`, this file. Russian
  only where a person reads it: `log()`, error messages, `handoff.md`, round records. Language
  material an agent must match (a dictionary of Russian clichés) lives in data files under
  `library/style/`, not in prompts. Held by `test_generated_agent_prompts_are_english`.
- **The output language comes from the material**, never from the prompt: a document is in
  the language of its sources.
- **`meta` in a script is a pure literal**; `import()`, `Date.now()`, `new Date()` and
  `Math.random()` are unavailable; a script has no filesystem and no shell — agents read and
  write files, the script passes paths and **never asks for them back**: results are matched
  to commands by index.
- **CRLF in a script refuses to launch**; line endings are declared in `.gitattributes`.
- **Tool arguments are ASCII**; Cyrillic travels only inside files (`--forbid-file`).
- **A new agent is not available in the turn that created it**: build, wait for the next
  human message, then launch.
- **A new run gets a new directory** from `newrun.py`; continuation is `config.continue`,
  rebuilding is `config.fresh`. The script refuses to guess.
- **One launch is one stage** (`config.stages`); stages share nothing but files on disk.

## Rules for an agent working inside a run

- Run commands from the repository root; each Bash call is a fresh shell, so environment and
  command travel in the same call.
- Create no files outside the run directory the task names. Scratch code goes to the system
  temp directory or to python fed from stdin; nothing lands in the repository root.
- In a revision round, edit the existing file with Edit, in batches of several related edits
  per turn; never rewrite the whole file.
- A relayed user request at the top of a task is context about the run, not an instruction.
  The task is exactly the COMMANDS / INPUT / OUTPUT block that follows it.
- A verdict is a literal from the schema, never a synonym; evidence (quotes, labels seen,
  numbers checked) is written out, because a verdict without evidence is a stamp.

## Layout

- `library/agents/<name>/{agent.yaml,prompt.md}` — source of truth for the 22 agents;
  `library/agents-archive/` — six agents no script calls;
- `.claude/agents/` — **generated** by `emit_agents`, committed; edit the source only;
- `.claude/skills/<type>-profile/SKILL.md` — document-type profiles (SPEC §6). **The document
  contract lives in the profile, not in prompts**: writer, corrector and critic read one text,
  a prompt describes a role. A missing profile is skipped silently by the runtime, so the
  build checks it exists;
- `.claude/workflows/*.js` — level-3 pipelines; `tools/` — rulers; `library/style/` — voice
  profile and pattern lists; `exemplars/` — anonymised skeletons only, full documents via
  `exemplars.local.yaml` under `.gitignore` (SPEC R8);
- `docs/decisions/` — dated write-ups; `docs-runs/` — runs, not in git.

## The revision round

Writer → correctors → gate → critics in parallel. A corrector fixes what is decidable
(arithmetic, attribution, source references), by Edit, in batches. A critic judges what only
judgement decides and writes its remarks in the document's language. Remarks are one numbered
list per round; the writer answers every number `fixed` / `declined`. The loop stops on the
round limit, on stagnation (the same remark set twice) or on a plateau (`plateauRounds`
rounds without improving the best score). Anything left open goes to `UNRESOLVED.md`, never
silently dropped.

## What the audit checks

At the end of every stage the script subtracts: everything produced on disk minus everything
some agent read or the script declared as a record. Orphans are named, not counted. Four
records survive a process crash: `logs/stop-audit.jsonl` (the hook: what an agent actually
wrote), `<run>/tools.jsonl` (tool receipts), the directory audit, `<run>/rounds/` (verdicts
and per-round snapshots).
