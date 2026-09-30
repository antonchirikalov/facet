// Review a client proposal before its author sees it: map every client ask onto the document,
// run the deterministic gates, let an independent reviewer read it with the sources and the
// figures, and let an editor answer the remarks, round after round.
//
// Why this exists. The Vista proposal went to its author after the writer was done, and the
// author then found, one question at a time, what a reviewer with the transcript would have
// found in one pass: how the app reaches the installers, that technicians need training, an
// addressed reader, bold lead-ins, empty table cells, a disclaimer worded differently from the
// client's, a screen needed in week 10 but built in week 14. Five independent reviews were run by
// hand, each after the author had already read the draft, and each found new HIGH items. This
// script runs that review first and hands the author a document the review has passed, plus a
// file naming what it could not close.
//
// The contract is .claude/skills/proposal-profile/SKILL.md, preloaded into all three agents.
// The script only names paths and branches on what the gates measure; agents read and write.
//
// Every string an agent reads is English. The proposal is in the language of its sources.

export const meta = {
  name: 'proposal-review',
  description: 'Coverage map, gates and an independent review of a client proposal, with edit rounds',
  phases: [
    { title: 'Coverage', detail: 'every client ask, worry and question mapped onto the document' },
    { title: 'Gate', detail: 'voice, tables, references, figures, quotes, coverage' },
    { title: 'Review', detail: 'an independent reader with the sources and the figures' },
    { title: 'Edit', detail: 'the editor answers every remark, fixed or declined' },
    { title: 'Record', detail: 'rounds and unresolved items on disk' },
  ],
}

const run = args && args.runDir
if (!run) throw new Error('a run directory is required: args.runDir')
const DOC = args && args.document
if (!DOC) throw new Error('the proposal is required: args.document, a markdown file')
const SOURCES = (args && args.sources) || []
if (!SOURCES.length) {
  throw new Error('the client sources are required: args.sources, the transcript and their documents')
}
const cfg = (args && args.config) || {}
const FIGURES_DIR = cfg.figuresDir || `${DOC.replace(/\/[^/]*$/, '')}/figures`
const MAX_ROUNDS = cfg.maxRounds || 3
const PLATEAU_ROUNDS = cfg.plateauRounds || 2
// Columns a manager fills in by hand (a cost, a rate) may stay empty in a delivered table.
const EMPTY_ALLOW = cfg.emptyCellsAllow || 'cost|rate|price'

const MAP_PATH = `${run}/coverage-map.md`
const ROUNDS_DIR = `${run}/rounds/proposal`
const UNRESOLVED_PATH = `${run}/UNRESOLVED.md`
const LOG = `--log ${run}/tools.jsonl`
const roundPath = (n) => `${ROUNDS_DIR}/round-${n}.md`
const answersPath = (n) => `${ROUNDS_DIR}/answers-${n}.md`
const draftPath = (n) => `${ROUNDS_DIR}/draft-${n}.md`

const OUTPUT_RULE =
  `The file is your result. Write it with the Write tool, or edit it with the Edit tool if it ` +
  `exists, before you finish; the fields you return describe it, they do not replace it.`
const NO_FILE_RULE =
  `You write no file in this step and you edit nothing. The fields you return ARE your result.`

function task(inputs, output, brief) {
  const ports = inputs.map(([port, path]) => `${port}: ${path}`).join('\n')
  return (
    `INPUT\n${ports}\n\n` +
    (brief ? `${brief}\n\n` : '') +
    (output ? `OUTPUT\n${output}\n\n${OUTPUT_RULE}` : NO_FILE_RULE)
  )
}

const sourceInputs = SOURCES.map((s, i) => [`source_${i + 1}`, s])
// The client-voice sheet of solution-design.js, when the proposal has one: their ranking, weights
// and vocabulary. Optional, and named by the caller, because a script cannot look for a file.
const VOICE = (args && args.voice) || ''
const voiceInputs = VOICE ? [['client_voice', VOICE]] : []
const sourceFlags = SOURCES.map((s) => `--source ${s}`).join(' ')

const REPORT = {
  type: 'object',
  required: ['ok', 'problems', 'measures'],
  properties: {
    ok: { type: 'boolean' },
    problems: { type: 'array', items: { type: 'string' } },
    measures: { type: 'object' },
  },
}
const CHECKS = {
  type: 'object',
  required: ['checks', 'stdout'],
  properties: { checks: { type: 'array', items: REPORT }, stdout: { type: 'string' } },
}
const MAPPED = {
  type: 'object',
  required: ['rows', 'not_answered'],
  properties: {
    rows: { type: 'number', description: 'rows written into the map' },
    not_answered: { type: 'number', description: 'rows marked not answered' },
  },
}
const VERDICT = {
  type: 'object',
  required: ['verdict', 'remarks'],
  properties: {
    verdict: {
      type: 'string',
      enum: ['approved', 'revise'],
      description: 'exactly `approved` or exactly `revise`; no synonyms',
    },
    remarks: {
      type: 'array',
      description: 'one numbered remark each, severity in brackets first: [HIGH], [MEDIUM] or [LOW]',
      items: { type: 'string' },
    },
  },
}
const ANSWERED = {
  type: 'object',
  required: ['fixed', 'declined', 'figures_to_update'],
  properties: {
    fixed: { type: 'array', items: { type: 'number' }, description: 'remark numbers fixed' },
    declined: {
      type: 'array',
      items: {
        type: 'object',
        required: ['n', 'reason'],
        properties: { n: { type: 'number' }, reason: { type: 'string' } },
      },
    },
    figures_to_update: { type: 'array', items: { type: 'string' }, description: 'slug: new value' },
  },
}
const WROTE = {
  type: 'object',
  required: ['written'],
  properties: { written: { type: 'boolean' } },
}

function gateCommands() {
  return (
    `COMMANDS\n` +
    [
      `python -X utf8 tools/gate.py --file ${DOC} --no-empty-sections --figures-numbered --section-refs ` +
        `--no-empty-cells --empty-cells-allow "${EMPTY_ALLOW}" ` +
        `--forbid-outside-quotes "\\byou\\b" --forbid-outside-quotes "\\byour\\b" ` +
        `--forbid-file library/style/forbid/no-bold.txt ${LOG} --log-note "proposal gates"`,
      `python -X utf8 tools/check_quotes.py --file ${DOC} ${sourceFlags} ${LOG} --log-note "proposal quotes"`,
      `python -X utf8 tools/coverage.py --map ${MAP_PATH} --file ${DOC} ${sourceFlags} ${LOG} --log-note "coverage"`,
    ]
      .map((c, i) => `${i + 1}. ${c}`)
      .join('\n')
  )
}

// The score the plateau detector compares: HIGH counts five, MEDIUM two, LOW nothing; a gate
// problem counts as a HIGH, because it is mechanical and there is no reason to leave it.
function scoreOf(remarks, gateProblems) {
  let score = gateProblems.length * 5
  for (const r of remarks) {
    if (/^\s*\[HIGH\]/i.test(r)) score += 5
    else if (/^\s*\[MEDIUM\]/i.test(r)) score += 2
  }
  return score
}

// The reviewer numbers its remarks itself ("1. [HIGH] ..."); the number is dropped so the
// severity is the first thing on the line, for the score and for the round record alike.
function bare(remark) {
  return String(remark).replace(/^\s*\d+[.)]\s*/, '')
}

function record(path, heading, items) {
  return `FILE\n${path}\n\nHEADING\n${heading}\n\nITEMS\n` + items.map((r, i) => `${i + 1}. ${r}`).join('\n')
}

log(`[start] run=${run} document=${DOC} sources=${SOURCES.length} rounds<=${MAX_ROUNDS}`)

// --- Coverage: every ask of the client, with the place that answers it ------------------------

phase('Coverage')
const mapped = await agent(
  task(
    [['document', DOC], ...voiceInputs, ...sourceInputs],
    MAP_PATH,
    `Write the coverage map of this proposal from the client's sources, as your instructions and ` +
      `the proposal profile describe.`,
  ),
  { agentType: 'coverage-mapper', model: 'sonnet', label: 'coverage', phase: 'Coverage', schema: MAPPED },
)
if (!mapped) throw new Error('the coverage mapper returned nothing')
log(`[coverage] rows=${mapped.rows} not_answered=${mapped.not_answered} → ${MAP_PATH}`)

// --- Rounds: gate, review, edit ---------------------------------------------------------------

let best = null
let sinceBest = 0
let previous = ''
let accepted = false
let open = []
let rounds = 0
// Every answers file the editor wrote: read by the next reviewer, returned for the person.
const answerFiles = []

for (let round = 1; round <= MAX_ROUNDS; round++) {
  rounds = round
  phase('Gate')
  const gate = await agent(
    gateCommands() + `\n\nRun every command and return one report per command, in order, and the raw output.`,
    { agentType: 'gate-runner', model: 'haiku', label: `gate:${round}`, phase: 'Gate', schema: CHECKS },
  )
  const gateProblems = ((gate && gate.checks) || []).flatMap((c) => c.problems || [])
  if (!gate || (gate.checks || []).length !== 3) gateProblems.push('the gates did not all report')
  log(`[gate/${round}] problems=${gateProblems.length}`)
  for (const p of gateProblems) log(`[gate/${round}] ${p}`)

  phase('Review')
  const verdict =
    (await agent(
      task(
        [
          ['draft', DOC],
          ['coverage', MAP_PATH],
          ['figures', FIGURES_DIR],
          ...(round > 1 ? [['answers', answersPath(round - 1)]] : []),
          ...voiceInputs,
          ...sourceInputs,
        ],
        null,
        `Review this proposal as your instructions and the proposal profile describe. Open every ` +
          `figure the proposal references in ${FIGURES_DIR}.` +
          (round > 1
            ? ` The answers file is the editor's reply to your previous remarks: a remark declined ` +
              `with a reason is raised again only if the reason does not hold, and then say why.`
            : '') +
          (gateProblems.length
            ? `\n\nThe gates already found these; do not repeat them as remarks:\n` +
              gateProblems.map((p) => `- ${p}`).join('\n')
            : ''),
      ),
      { agentType: 'proposal-reviewer', model: 'opus', label: `review:${round}`, phase: 'Review', schema: VERDICT },
    )) || { verdict: 'revise', remarks: ['[HIGH] the reviewer returned no verdict: an open item, not agreement'] }
  const remarks = (verdict.remarks || []).map(bare)
  const score = scoreOf(remarks, gateProblems)
  log(`[review/${round}] verdict=${verdict.verdict} remarks=${remarks.length} score=${score}`)

  await agent(record(roundPath(round), `Round ${round}: ${verdict.verdict}, score ${score}`, [...gateProblems.map((p) => `[GATE] ${p}`), ...remarks]), {
    agentType: 'verbatim-writer',
    model: 'haiku',
    label: `record:${round}`,
    phase: 'Record',
    schema: WROTE,
  })
  await agent(`COMMANDS\n1. cp ${DOC} ${draftPath(round)}`, {
    agentType: 'file-copier',
    model: 'haiku',
    label: `snapshot:${round}`,
    phase: 'Record',
    schema: CHECKS,
  })

  open = [...gateProblems.map((p) => `[GATE] ${p}`), ...remarks]
  if (verdict.verdict === 'approved' && !gateProblems.length) {
    accepted = true
    open = remarks
    log(`[round/${round}] accepted`)
    break
  }
  const signature = JSON.stringify([...open].sort())
  if (signature === previous) {
    log(`[round/${round}] stagnation: the same remarks as the round before`)
    break
  }
  previous = signature
  if (best === null || score < best) {
    best = score
    sinceBest = 0
  } else if (++sinceBest >= PLATEAU_ROUNDS) {
    log(`[round/${round}] plateau: ${PLATEAU_ROUNDS} rounds without beating score ${best}`)
    break
  }
  if (round === MAX_ROUNDS) break

  phase('Edit')
  const answered = await agent(
    task(
      [['draft', DOC], ['remarks', roundPath(round)], ['coverage', MAP_PATH], ...sourceInputs],
      answersPath(round),
      `Edit the proposal ${DOC} in place to answer every numbered item of ${roundPath(round)}; ` +
        `[GATE] items are mechanical and are always fixed. Where a fix answers a coverage row, ` +
        `update its "Answered in" cell in ${MAP_PATH}. Then write the answers file.`,
    ),
    { agentType: 'proposal-editor', model: 'opus', label: `edit:${round}`, phase: 'Edit', schema: ANSWERED },
  )
  answerFiles.push(answersPath(round))
  if (answered) {
    log(`[edit/${round}] fixed=${answered.fixed.length} declined=${answered.declined.length}`)
    for (const d of answered.declined) log(`[edit/${round}] declined ${d.n}: ${d.reason}`)
    for (const f of answered.figures_to_update) log(`[edit/${round}] figure to update: ${f}`)
  } else {
    log(`[edit/${round}] the editor returned nothing`)
  }
}

phase('Record')
if (open.length) {
  await agent(
    record(
      UNRESOLVED_PATH,
      accepted ? 'The proposal was accepted; these remarks were left open' : 'The rounds ended with these items open',
      open,
    ),
    { agentType: 'verbatim-writer', model: 'haiku', label: 'unresolved', phase: 'Record', schema: WROTE },
  )
  log(`[unresolved] ${open.length} → ${UNRESOLVED_PATH}`)
}
log(`[summary] rounds=${rounds} accepted=${accepted} open=${open.length}`)

return {
  document: DOC,
  coverage: MAP_PATH,
  rounds,
  accepted,
  open: open.length,
  unresolved: open.length ? UNRESOLVED_PATH : null,
  answers: answerFiles,
}
