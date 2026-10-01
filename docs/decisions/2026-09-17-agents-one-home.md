# One home for the agents: reconciling library/agents with refract

Date: 2026-09-17. Step 1 of the plan (`SPEC.md` §10).

## What was compared

`library/agents` in facet (28 packages) against `library/agents` in `../refract` (13 packages;
refract is frozen, last commit 2026-07-28). The comparison used `--strip-trailing-cr`: the refract
working copy has CRLF, and without it every file "differed".

## Result

Seven packages match byte for byte. Six diverge, and in all six facet is newer:

| package | what changed after the divergence |
|---|---|
| `confluence_publisher` | publishing via `tools/confluence_publish.py`, not by MCP conversion |
| `illustrator` | the figgybanana CLI instead of the paperbanana MCP; the `article` port, not `design_doc` |
| `requirements_writer` | source references on every requirement; the language of the result comes from the sources |
| `requirements_fact_checker` | fixes source references in place |
| `requirements_critic` | checks the references instead of counting them; the conclusion goes into "Assumptions" |
| `source_finder` | `mcp:pdf-reader` — a finder without PDF declared an aspect uncovered |

There is nothing to take from refract; the source of truth for agents is `library/agents` in
facet. `refract/claude-agents/` is empty.

## The generated files

`emit_all` into a clean directory produces byte for byte the same 28 files that are in
`.claude/agents`: there are no manual edits in the generated files. That is the readiness
criterion for the step.

## Profiles through `skills:`

The `skills:` field in an agent's frontmatter loads `.claude/skills/<name>/SKILL.md` into the
context at launch. Two properties of the runtime determined the shape:

- **a non-existent profile is skipped silently** — a warning only in the debug log, and the agent
  starts without a contract. So `emit_agents` checks every named profile on disk and fails if it
  is missing; `tests/test_workflows.py` checks the same on the generated files;
- **a profile with `disable-model-invocation: true` is not loaded.** The profiles do not have
  this field, and a test holds that. `user-invocable: false` does not prevent loading and removes
  the profile from the list of slash commands.

The names are `<type>-profile`, not `<type>` as recorded in SPEC §6 before this step: the saved
workflows `.claude/workflows/<name>.js` already occupy the skill names `solution-design`,
`explainer-article`, `attn-figures`, and `requirements.js` from step 5 would take `requirements`.
A project skill overrides one with the same name, and the profile would replace the pipeline's
launch point.

Declared: `requirements-profile` on the requirements writer, corrector and critic;
`solution-design-profile` on the designer and its critic. The content of the profiles is a
skeleton of the mandatory sections of §6; the contract stays in the prompts until step 3.
