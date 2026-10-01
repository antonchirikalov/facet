# Pipeline economics and quality: measurements of 19–20 September 2026

Three full requirements runs on one demo input (five documents of a fictional chain of veterinary
clinics), one design run with illustrations. Everything was measured from the subagent
transcripts, not from impressions.

## Where the tokens go (requirements run v2, 27 agents)

| item | tokens | note |
|---|---|---|
| new input into the cache | 4.0 M | an agent's starting context ~25 K, of which ~16 K is CLAUDE.md |
| cache reads | 11.0 M | 6.0 M is one writer: 26 Edit changes, one per turn |
| output | 254 K | 49 K is a corrector that rewrote 92 KB for the sake of a few edits |

Three conclusions and three fixes:

1. **Every subagent read CLAUDE.md.** The platform puts the whole CLAUDE.md hierarchy into a
   subagent's context as an `instructions` block. The agent's role is in the prompt, the document
   is in the profile, the inputs and outputs are in the task; CLAUDE.md added only tokens. The
   generator sets `omitClaudeMd: true` (Claude Code ≥ 2.1.271). A carrier's starting context:
   25 → 11 → 4–8 K tokens.
2. **Editing via Edit one call per turn is more expensive than rewriting.** 72 edits in round 3 of
   v3 read 10.3 M cached tokens. The instruction "in batches" does not work: every tool call is a
   turn. The solution is an edits file `{old, new}` and the ruler `tools/apply_edits.py`.
3. **The corrector rewrote the document.** The rule "Edit, not Write" is kept for correctors:
   they have few edits (9 and 3), the loop does not run away.

## What did not work and why

- **Carriers on haiku.** Savings of ~1% of a run. The platform hands every subagent the human's
  last chat message as "a request that outranks the task"; haiku carried it out literally
  (pytest, dry-run, a report in the repository root) and returned a made-up record of three
  completed rounds; the script believed it and skipped the loop. Sonnet ignores the same block.
  Carriers are on sonnet; the prompts and the tail of the task call the relayed request context;
  the script trusts reports about rounds and the gate only in the form the tool prints.
- **Merging carriers.** The gate and the disk check sit at different points of the round with
  different schemas; after the context reduction a carrier costs ~8 K tokens, and the rework does
  not pay off.

## The carriers' share (SPEC §12)

31 of 84 calls on the article (37 %), 12 of 27–32 on the requirements (38–44 %). The 50 %
threshold is not reached; by tokens, after the context reduction, the carriers are a few percent.

## Requirements quality over three runs

| | v1 (no profile) | v2 (profile) | v3 (profile + gates) |
|---|---|---|---|
| form | 86 items in prose | 9 sections, 189 table rows | 9 sections, all gates |
| "one doctor in every clinic" | "every doctor" | "some of the doctors" | verbatim |
| roles | — | people | roles, people in the description |
| language | the critic's remarks in English | English scraps in the roles | clean |
| rounds to acceptance | 2 (not accepted by the substance critic) | 2 | 3 (corrector skipped on continuation) |
| tokens, new input / cache reads | — | 4.0 / 11.0 M | 3.1 / 17.5 M |

Every improvement of the form came from a concrete trap in the demo documents, not from general
considerations.

## Design and illustrations

- Design: the candidate on opus won (99 KB against 42 for sonnet), three rounds, the critic did
  not accept, the best round was the first. Growth 24 → 28 → 34 K characters of prose at 8 → 10 →
  9 remarks: every remark was closed with a paragraph. For three rounds the critic demanded
  figures that by construction do not exist yet. Both defects are closed by the
  `solution-design` profile (IGNORE for placeholders; a preference for remarks closed by cutting).
- Illustrations: five figures in 3 h 17 min and 794 K tokens; four were accepted, the component
  diagram after 24 iterations and two redraws was left with three exact defects (no API →
  PostgreSQL connection, an invented bucket → PostgreSQL arrow, a one-way SPA → API arrow). The
  looking agent named them correctly. The Kimi K3 quota ran out on the second figure, after that
  sonnet judged — just as on the article. The time is the price of drawing with a critic inside
  figgybanana: up to 24 iterations per diagram.

## What next, in decreasing order of payoff

1. A design run through the edits file: the expectation is minus 6–8 M cache reads per round.
2. Limit figgybanana iterations per figure (now up to 24) and hand a failed diagram to a human
   after the second redraw: three hours for five figures is more expensive than the design.
3. A v2 mode for requirements: the previous document as input, the client's new answers as a
   delta, CHANGED/NEW labels — this is how the reference document lives at the RFP stage.
4. `tools/trace.py`: coverage of MUST requirements by the design, by id — a ruler instead of the
   critic's manual check.
5. Extracting long documents in chunks, when one source is larger than the window of one agent.
