// The client proposal, from accepted requirements and the client's pains.
//
// One question drives every step: does the client find their problem answered, in their words?
//
//   Start    the requirements are accepted, the pain map and the client voice sheet pass their
//            gates; without them the run refuses and names what to run first
//   content  proposal-writer -> gate (profile rules, quotes, client vocabulary, every pain and
//            worry answered in the client's words, the top pains early) -> proposal-reviewer,
//            each HIGH put to a vote of three checkers; only a confirmed HIGH sends it back
//   text     slop-critic -> the writer edits -> the same gate, so a wording fix cannot drop a pain
//   Report   remarks, unresolved items, the outcome of the stage
//
// One launch is one stage: content first, then a person reads the proposal, then text. The
// figures are the next launch: attn-figures.js on the accepted proposal.
//
// The script has no filesystem and no shell: agents read and write, python tools measure through
// the gate-runner agent, results are matched to commands by index. Runtime rules: meta is a pure
// literal; no import(), no Date.now(), no Math.random().

export const meta = {
  name: 'proposal',
  description: 'Client proposal from accepted requirements and the pain map: content under a reviewer, then wording under the slop critic',
  phases: [
    { title: 'Start', detail: 'accepted requirements, pain map and client voice on disk' },
    { title: 'Content', detail: 'writer, gate, reviewer with a vote on every HIGH, in rounds' },
    { title: 'Text', detail: 'slop critic, writer edits, gate, in rounds' },
    { title: 'Report', detail: 'remarks, unresolved items, outcome' },
  ],
}

// --- Input ------------------------------------------------------------------------------------

const run = typeof args === 'string' ? args : args && args.runDir
if (!run) {
  throw new Error('a run directory is required: args.runDir, the directory of an accepted requirements run')
}
const now = (args && args.now) || ''
const order = (args && args.order) || ''
// The design is optional: without it the proposal says only what the requirements fix about how
// it is built, and every other choice becomes a decision to take with the client.
const designPath = (args && args.design) || ''
const cfg = (args && args.config) || {}
// The client's name. Every document of these pipelines is written for the client, so it names
// them; without the name an agent may put a placeholder ("Client A") in its place, and on one
// live run that placeholder reached the proposal seventy-six times.
const client = (args && args.client) || ''
const CLIENT_BLOCK = client
  ? `CLIENT\nThe client is ${client}. These documents are written for the client and name them as ` +
    `${client}; never replace the name with a placeholder such as "Client A". People of the client ` +
    `are still named by role only.`
  : ''
const STAGES = cfg.stages || ['content']
if (STAGES.length !== 1 || !['content', 'text'].includes(STAGES[0])) {
  throw new Error(`config.stages is one stage, "content" or "text"; got: ${JSON.stringify(STAGES)}`)
}
const STAGE = STAGES[0]
if (cfg.continue && cfg.fresh) throw new Error('config.continue and config.fresh exclude each other')

// --- Paths ------------------------------------------------------------------------------------

const INPUTS_DIR = `${run}/inputs`
const EXTRACTS_DIR = `${run}/extracts`
const REQ_PATH = `${run}/requirements.md`
const REQ_OUTCOME = `${run}/outcome.md`
const PAINS_PATH = `${run}/pains.md`
const VOICE_PATH = `${run}/client-voice.md`
const PROP_PATH = `${run}/prop.md`
const TOOLS_LOG = `${run}/tools.jsonl`
const ROUNDS_DIR = `${run}/rounds/prop-${STAGE}`
// Not "report": the harness refuses a subagent a file of that name.
const OUTCOME_PATH = `${run}/prop-${STAGE}-outcome.md`
const REMARKS_PATH = `${run}/prop-${STAGE}-remarks.md`
const UNRESOLVED_PATH = `${run}/prop-${STAGE}-unresolved.md`
const CONTENT_OUTCOME = `${run}/prop-content-outcome.md`
const roundPathOf = (n) => `${ROUNDS_DIR}/round-${n}.md`
const draftPathOf = (n) => `${ROUNDS_DIR}/draft-${n}.md`
const editsPathOf = (n) => `${ROUNDS_DIR}/edits-${n}.json`

// --- Configuration ----------------------------------------------------------------------------

const MAX_ROUNDS = cfg.maxRounds || (STAGE === 'content' ? 3 : 2)
const MIN_ARTIFACT_CHARS = 200
const VOTERS = cfg.voters ?? 3
const MODELS = {
  write: 'opus',
  review: 'opus',
  slop: 'sonnet',
  vote: 'sonnet',
  gate: 'sonnet',
  record: 'sonnet',
  copy: 'sonnet',
  ...(cfg.models || {}),
}
const tool = (name) => `python -X utf8 tools/${name}.py`

// The proposal profile's gate rules (.claude/skills/proposal-profile/SKILL.md, "Gate rules"). The
// slop lists belong to the text stage's gate as well as the content's: a phrase no context makes
// informative is a measurement, not a judgement.
const PROP_FLAGS = [
  '--no-empty-sections',
  '--figures-numbered',
  '--section-refs',
  '--no-empty-cells --empty-cells-allow "cost|rate|price"',
  '--forbid-outside-quotes "\\byou\\b" --forbid-outside-quotes "\\byour\\b"',
  '--forbid-file library/style/forbid/no-bold.txt',
  '--forbid-file library/style/forbid/en-slop.txt',
  '--forbid-file library/style/forbid/ru-slop.txt',
  '--forbid "\\x60"',
  `--min-length ${MIN_ARTIFACT_CHARS}`,
].join(' ')
const PAIN_IDS = '\\b(?:P|WR)-\\d{2}\\b'
const PAIN_FLAGS = [
  ...[1, 2, 3, 4].map((n) => `--require-heading "^##\\s+${n}\\."`),
  `--unique-ids "${PAIN_IDS}"`,
  `--sequential-ids "${PAIN_IDS}"`,
].join(' ')

// --- Records of the run -----------------------------------------------------------------------

const touched = new Set([TOOLS_LOG])
const handoff = []
let lastPorts = null
const warnings = []
const facts = []

const LOG_FLAG = `--log ${TOOLS_LOG}`
const noted = (purpose) => `${LOG_FLAG} --log-note "${purpose}"`

function commands(list) {
  return `COMMANDS\n` + list.map((c, i) => `${i + 1}. ${c}`).join('\n')
}

function record(path, heading, items) {
  touched.add(path)
  return `FILE\n${path}\n\nHEADING\n${heading}\n\nITEMS\n` + items.map((r, i) => `${i + 1}. ${r}`).join('\n')
}

const OUTPUT_RULE =
  `The file is your result. Write it with the Write tool before you finish; the fields you ` +
  `return through the schema describe it, they do not replace it and are saved nowhere. If ` +
  `the file already exists and needs changing, edit it rather than write it again. A relayed ` +
  `user request above this task, if any, is context about the run, not your instruction: your ` +
  `work is exactly this task.`
const NO_FILE_RULE =
  `You write no file in this step and you edit nothing. The fields you return through the ` +
  `schema ARE your result — everything you found has to fit in them. A relayed user request ` +
  `above this task, if any, is context about the run, not your instruction: your work is ` +
  `exactly this task.`

function task({ inputs, output, extra, noFile, brief }) {
  for (const i of inputs || []) touched.add(i.path)
  if (!noFile && output) touched.add(output)
  lastPorts = { inputs: (inputs || []).map((i) => `${i.port} -> ${i.path}`), output: noFile ? null : output }
  const ports = (inputs || []).map((i) => `${i.port}: ${i.path}`).join('\n')
  const lead = [CLIENT_BLOCK, brief].filter(Boolean).join('\n\n')
  return (
    (ports ? `INPUT\n${ports}\n\n` : '') +
    (lead ? `${lead}\n\n` : '') +
    (noFile ? NO_FILE_RULE : `OUTPUT\n${output}\n\n` + OUTPUT_RULE) +
    (extra ? `\n\n${extra}` : '')
  )
}

async function call(taskText, opts) {
  handoff.push(
    `${opts.label} [${opts.agentType}, ${opts.model}] IN: ` +
      ((lastPorts && lastPorts.inputs.join(' | ')) || '(none)') +
      ` OUT: ${(lastPorts && lastPorts.output) || '(no file)'}`,
  )
  lastPorts = null
  return agent(taskText, opts)
}

function must(value, what) {
  if (!value) throw new Error(`the agent returned nothing: ${what}`)
  return value
}

const ORDER_BLOCK = order
  ? `ORDER\n${order}\n\nThe order sets the scope and audience of this run and is binding where it sets them. ` +
    `Facts still come only from the sources.`
  : ''

// A file name without its folder and suffix, ASCII only: the port name of a collection member.
const stemOf = (path) =>
  String(path)
    .replace(/\\/g, '/')
    .split('/')
    .pop()
    .replace(/\.[^.]+$/, '')
    .replace(/[^A-Za-z0-9._-]+/g, '-')
    .replace(/^-+|-+$/g, '') || 'doc'

// --- Schemas ----------------------------------------------------------------------------------

const REPORT = {
  type: 'object',
  required: ['ok', 'problems', 'measures'],
  properties: { ok: { type: 'boolean' }, problems: { type: 'array', items: { type: 'string' } }, measures: { type: 'object' } },
}
const GATE = { type: 'object', required: ['report', 'stdout'], properties: { report: REPORT, stdout: { type: 'string' } } }
const CHECKS = {
  type: 'object',
  required: ['checks'],
  properties: {
    checks: {
      type: 'array',
      items: {
        type: 'object',
        required: ['ok', 'problems', 'measures'],
        properties: {
          ok: { type: 'boolean' },
          problems: { type: 'array', items: { type: 'string' } },
          measures: { type: 'object', description: 'the measures object of the report, verbatim' },
          busy: { type: 'boolean', description: 'the busy field of the report, verbatim; only busy.py has it' },
        },
      },
    },
  },
}
// One listing per command, in order.
const LISTINGS = {
  type: 'object',
  required: ['listings'],
  properties: {
    listings: {
      type: 'array',
      items: {
        type: 'object',
        required: ['ok', 'files'],
        properties: { ok: { type: 'boolean' }, files: { type: 'array', items: { type: 'string' } } },
      },
    },
  },
}
const LISTING = {
  type: 'object',
  required: ['files', 'count'],
  properties: {
    files: { type: 'array', items: { type: 'string' } },
    count: { type: 'integer', description: 'the files number from the report measures, verbatim' },
  },
}
const WROTE = { type: 'object', required: ['written'], properties: { written: { type: 'boolean' } } }
const ROUNDS = {
  type: 'object',
  required: ['report', 'rounds'],
  properties: {
    report: REPORT,
    rounds: {
      type: 'array',
      items: {
        type: 'object',
        required: ['round', 'verdict', 'remarks', 'gate'],
        properties: {
          round: { type: 'number' },
          verdict: { type: 'string', description: 'the verdict of the round, verbatim' },
          remarks: { type: 'array', items: { type: 'string' } },
          gate: { type: 'array', items: { type: 'string' } },
        },
      },
    },
  },
}
const DRAFT = {
  type: 'object',
  required: ['changes', 'addressed'],
  properties: {
    changes: { type: 'array', items: { type: 'string' }, description: 'what you changed beyond the numbered remarks' },
    addressed: {
      type: 'array',
      description: 'one entry per numbered remark; empty on the first draft',
      items: {
        type: 'object',
        required: ['item', 'status', 'note'],
        properties: {
          item: { type: 'number', description: 'the number of the remark, as given' },
          status: { type: 'string', enum: ['fixed', 'declined'] },
          note: { type: 'string', description: 'what you did, or why you deliberately did not' },
        },
      },
    },
  },
}
// The reviewer's and the slop critic's verdict: remarks as strings opening with their severity.
const VERDICT = {
  type: 'object',
  required: ['verdict', 'remarks'],
  properties: {
    verdict: { type: 'string', enum: ['approved', 'revise'], description: 'exactly approved or exactly revise' },
    remarks: { type: 'array', items: { type: 'string', description: '[HIGH|MEDIUM|LOW] place — what is wrong — evidence — fix' } },
  },
}
const CHECKED = {
  type: 'object',
  required: ['results'],
  properties: {
    results: {
      type: 'array',
      items: {
        type: 'object',
        required: ['id', 'holds', 'problem'],
        properties: {
          id: { type: 'string' },
          holds: { type: 'boolean' },
          problem: { type: 'string', description: 'what the draft and the evidence say instead, quoted; empty when the remark holds' },
        },
      },
    },
  },
}

// =============================================================================================
// Start: nothing is written for the client until what it rests on is accepted
// =============================================================================================

phase('Start')
let propPresent = false
let sourcePorts = []
let extractPorts = []
{
  const required = [
    { what: 'the requirements', cmd: `${tool('gate')} --file "${REQ_PATH}" --min-length 1000 ${noted('start: requirements')}` },
    ...(cfg.accepted
      ? []
      : [
          {
            what: 'the acceptance of the requirements (outcome.md, line 1: Accepted: yes)',
            cmd: `${tool('gate')} --file "${REQ_OUTCOME}" --require-line "^\\s*1\\. Accepted: yes" ${noted('start: requirements accepted')}`,
          },
        ]),
    { what: 'the pain map', cmd: `${tool('gate')} --file "${PAINS_PATH}" --min-length ${MIN_ARTIFACT_CHARS} ${PAIN_FLAGS} ${noted('start: pain map')}` },
    { what: 'the client voice sheet', cmd: `${tool('gate')} --file "${VOICE_PATH}" --min-length ${MIN_ARTIFACT_CHARS} ${noted('start: client voice')}` },
    ...(designPath
      ? [{ what: `the design ${designPath}`, cmd: `${tool('gate')} --file "${designPath}" --min-length 1000 ${noted('start: design')}` }]
      : []),
    ...(STAGE === 'text' && !cfg.accepted
      ? [
          {
            what: 'the accepted content of the proposal (prop-content-outcome.md, line 1: Content accepted: yes)',
            cmd: `${tool('gate')} --file "${CONTENT_OUTCOME}" --require-line "^\\s*1\\. Content accepted: yes" ${noted('start: content accepted')}`,
          },
        ]
      : []),
  ]
  const list = [
    ...(now ? [`${tool('busy')} --file ${TOOLS_LOG} --now ${now} --idle-seconds ${cfg.idleSeconds || 600} ${noted('is another run working here')}`] : []),
    `${tool('gate')} --file "${PROP_PATH}" --min-length ${MIN_ARTIFACT_CHARS} ${noted('start: proposal already on disk')}`,
    ...required.map((r) => r.cmd),
  ]
  const started = await call(commands(list), { agentType: 'gate-runner', model: MODELS.gate, label: 'start', phase: 'Start', schema: CHECKS })
  const checks = (started && started.checks) || []
  if (checks.length !== list.length) {
    throw new Error(`the start check returned ${checks.length} reports for ${list.length} commands: nothing can be verified, the run stops`)
  }
  const offset = now ? 1 : 0
  if (now && checks[0].busy && !cfg.ignoreBusy) {
    throw new Error(`another run seems to be working in ${run}: ${(checks[0].problems || []).join('; ')}; config.ignoreBusy=true if it is dead`)
  }
  if (!now) warnings.push('args.now was not passed: whether another run works in this directory was not checked')
  propPresent = checks[offset].ok
  const failed = required.filter((r, i) => !checks[offset + 1 + i].ok)
  if (failed.length) {
    throw new Error(
      `the proposal rests on what is not there yet: ` +
        failed.map((r) => `${r.what} (${checks[offset + 1 + required.indexOf(r)].problems.join('; ')})`).join('; ') +
        `. Run requirements.js in ${run} first (config.continue=true writes the pain map for accepted requirements); ` +
        `if you accepted the requirements yourself, config.accepted=true.`,
    )
  }
  if (cfg.accepted) warnings.push('accepted by the person who launched the run (config.accepted), not by an outcome on disk')
  for (const p of [REQ_PATH, REQ_OUTCOME, PAINS_PATH, VOICE_PATH, CONTENT_OUTCOME]) touched.add(p)
  if (designPath) touched.add(designPath)

  if (STAGE === 'content' && propPresent && !cfg.continue && !cfg.fresh) {
    throw new Error(
      `${PROP_PATH} already exists. To continue an interrupted run, config.continue=true; to write it again, config.fresh=true.`,
    )
  }
  if (STAGE === 'text' && !propPresent) throw new Error(`${PROP_PATH} is missing: the text stage edits an accepted proposal`)
  if (cfg.fresh && STAGE === 'content') propPresent = false

  // What the reviewer and the writer read: the extracts and the client's own text documents.
  const listed = await call(
    commands([
      `${tool('listing')} --dir ${EXTRACTS_DIR} --ext .md ${noted('extracts')}`,
      `${tool('listing')} --dir ${INPUTS_DIR} --ext "" --recursive ${noted('client documents')}`,
    ]),
    { agentType: 'gate-runner', model: MODELS.gate, label: 'start:listing', phase: 'Start', schema: LISTINGS },
  )
  const listings = (listed && listed.listings) || []
  const extracts = (listings[0] && listings[0].files) || []
  const inputs = (listings[1] && listings[1].files) || []
  extractPorts = extracts.map((f) => ({ port: `extract:${stemOf(f)}`, path: f }))
  // Text the reviewer can read: markdown and plain text, the converted twin of an office file.
  sourcePorts = inputs.filter((f) => /\.(md|txt)$/i.test(f)).map((f) => ({ port: `source:${stemOf(f)}`, path: f }))
  if (!extractPorts.length) throw new Error(`no extracts in ${EXTRACTS_DIR}: the proposal's quotes are copied from them`)
  if (!sourcePorts.length) warnings.push(`no text documents in ${INPUTS_DIR}: the reviewer checks quotes against the extracts only`)
  log(`[start] stage=${STAGE} proposal on disk=${propPresent} extracts=${extractPorts.length} client documents=${sourcePorts.length}`)
}

const basePorts = [
  { port: 'requirements', path: REQ_PATH },
  { port: 'pain_map', path: PAINS_PATH },
  { port: 'client_voice', path: VOICE_PATH },
  ...(designPath ? [{ port: 'design', path: designPath }] : []),
  ...extractPorts,
]
const checksOf = (round) => [
  `${tool('gate')} --file "${PROP_PATH}" ${PROP_FLAGS} ${noted(`proposal ${STAGE} round ${round}`)}`,
  `${tool('check_quotes')} --file "${PROP_PATH}" --source ${INPUTS_DIR} --source ${EXTRACTS_DIR} ${noted(`proposal quotes round ${round}`)}`,
  `${tool('vocab')} --file "${PROP_PATH}" --voice "${VOICE_PATH}" ${noted(`client vocabulary round ${round}`)}`,
  `${tool('pain_coverage')} --pains "${PAINS_PATH}" --file "${PROP_PATH}" ${noted(`pains answered round ${round}`)}`,
]

// A HIGH remark sends the proposal back, so before it does, independent checkers vote on it; one
// that a majority refutes is downgraded to MEDIUM with the reason. One the checkers could not
// judge stays HIGH: an unverified remark is not a refuted one.
async function voteOnHigh(round, remarks) {
  const high = remarks.filter((r) => r.severity === 'HIGH')
  if (!high.length || VOTERS < 2) return 0
  const evidence = [
    ...sourcePorts.map((s) => ({ port: s.port.replace(/^source:/, 'evidence:'), path: s.path })),
    { port: 'evidence:pains', path: PAINS_PATH },
    { port: 'evidence:requirements', path: REQ_PATH },
    { port: 'evidence:client-voice', path: VOICE_PATH },
  ]
  const claims =
    `CLAIMS TO CHECK\nEach claim is a reviewer's remark about the draft. It holds when the draft really ` +
    `has the defect the remark names and the evidence confirms what the remark says.\n` +
    high.map((r, i) => `V${i + 1}: "${r.text}"`).join('\n')
  const ballots = await parallel(
    Array.from({ length: VOTERS }, (_, k) => () =>
      call(task({ inputs: [{ port: 'draft', path: PROP_PATH }, ...evidence], noFile: true, extra: claims }), {
        agentType: 'claim-checker',
        model: MODELS.vote,
        label: `prop:vote:${round}:${k + 1}`,
        phase: 'Content',
        schema: CHECKED,
      }),
    ),
  )
  const majority = Math.floor(VOTERS / 2) + 1
  let refuted = 0
  high.forEach((r, i) => {
    const said = ballots.map((b) => b && (b.results || []).find((x) => x.id === `V${i + 1}`)).filter(Boolean)
    const against = said.filter((x) => !x.holds)
    log(`[prop/${round}/vote] V${i + 1}: holds ${said.length - against.length}, refuted ${against.length}, not judged ${VOTERS - said.length}`)
    if (against.length >= majority) {
      r.severity = 'MEDIUM'
      r.text = `${r.text} [not confirmed by ${against.length} of ${VOTERS} checkers: ${against[0].problem || 'no reason given'}]`
      refuted += 1
    }
  })
  return refuted
}

const severityOf = (text) => {
  const m = /^\s*(?:\d{1,2}[.)]\s+)?\[(HIGH|MEDIUM|LOW)\]/.exec(text)
  return m ? m[1] : 'MEDIUM'
}
const critics = {
  content: () => ({
    agentType: 'proposal-reviewer',
    model: MODELS.review,
    inputs: [{ port: 'draft', path: PROP_PATH }, { port: 'pain_map', path: PAINS_PATH }, ...sourcePorts, { port: 'client_voice', path: VOICE_PATH }],
    vote: true,
  }),
  text: () => ({
    agentType: 'slop-critic',
    model: MODELS.slop,
    inputs: [{ port: 'draft', path: PROP_PATH }, { port: 'client_voice', path: VOICE_PATH }],
    vote: false,
  }),
}

// =============================================================================================
// The rounds: one loop for both stages, only the critic differs
// =============================================================================================

const PHASE = STAGE === 'content' ? 'Content' : 'Text'
phase(PHASE)
const critic = critics[STAGE]()
const ledger = []
let pending = []
let declinedNotes = []
let accepted = false
let rounds = 0
let previousSignature = null
let lastCoverage = {}
const perRound = []
// The proposal profile's verdict rule: any HIGH, or three MEDIUM, send the draft back. A client
// document accepted with seven MEDIUM remarks left a worked example without numbers and the
// owner's main question deferred, which is what the comparison with the sent proposal found.
// In the text stage every remark is a wording fix the writer makes in one edits file, so any
// MEDIUM sends it back and LOW remarks travel with it: one live text stage accepted a draft
// with two MEDIUM and three LOW remarks and changed nothing.
const MEDIUM_LIMIT = cfg.mediumLimit ?? (STAGE === 'text' ? 1 : 3)
const SEND_LOW = STAGE === 'text'

// Continuing: the rounds already judged are read back, so a continued launch numbers its rounds
// after them instead of writing over round 1 of the earlier launch.
let startRound = 1
if (cfg.continue) {
  const recorded = await call(
    commands([`${tool('rounds')} --dir ${ROUNDS_DIR} --last-only ${noted('continue: rounds already judged')}`]),
    { agentType: 'gate-runner', model: MODELS.gate, label: 'prop:continue', phase: PHASE, schema: ROUNDS },
  )
  const shaped =
    recorded && recorded.report && recorded.report.measures && Array.isArray(recorded.rounds) &&
    recorded.rounds.length === 1 && recorded.rounds[0].round === recorded.report.measures.last_round
  if (shaped) {
    const last = recorded.rounds[0]
    startRound = last.round + 1
    for (let n = 1; n < startRound; n++) [roundPathOf(n), draftPathOf(n), editsPathOf(n)].forEach((x) => touched.add(x))
    pending = [
      ...(last.gate || []).map((text) => ({ kind: 'GATE', text })),
      ...(last.remarks || [])
        .filter((r) => (SEND_LOW || !/^\[LOW\]/.test(r)) && !/^Gate: /.test(r))
        .map((r) => ({ kind: /^\[(HIGH|MEDIUM|LOW)\]/.test(r) ? r.slice(1, r.indexOf(']')) : 'CARRIED', text: r.replace(/^\[(HIGH|MEDIUM|LOW)\]\s*/, '').replace(/^Carried: /, '') })),
    ]
    log(`[prop/continue] rounds judged ${recorded.report.measures.rounds}, continuing from ${startRound} with ${pending.length} items`)
  } else {
    log('[prop/continue] no usable round records: the proposal on disk is judged as round 1')
  }
}

for (let round = startRound; round < startRound + MAX_ROUNDS; round++) {
  rounds = round
  phase(PHASE)

  // --- The writer: the first draft, or one edits file that answers the numbered items
  if (!propPresent) {
    must(
      await call(task({ inputs: basePorts, output: PROP_PATH, brief: ORDER_BLOCK || undefined }), {
        agentType: 'proposal-writer',
        model: MODELS.write,
        label: `prop:write:${round}`,
        phase: PHASE,
        schema: DRAFT,
      }),
      `prop:write:${round}`,
    )
    propPresent = true
  } else if (pending.length) {
    const editsPath = editsPathOf(round)
    const remarks =
      `REMARKS ON THE PREVIOUS DRAFT. GATE items are measurements and are not open to argument; everything ` +
      `else you may decline with a reason.\n\n` +
      pending.map((it, i) => `${i + 1}. [${it.kind}] ${it.text}`).join('\n') +
      `\n\nHOW TO ANSWER. One entry per number from 1 to ${pending.length}: fixed when the draft now satisfies ` +
      `it, declined with the reason in one sentence when you deliberately did not act.` +
      `\n\nHOW TO DELIVER THIS ROUND. Do not edit ${PROP_PATH} yourself. Write your changes as a JSON array to ` +
      `${editsPath}: [{"old": "<text copied verbatim from the draft, occurring exactly once>", "new": "<the ` +
      `replacement>"}]. To delete, new is empty. A tool applies the list and reports every pair whose old text ` +
      `was not found once.`
    const drafted = must(
      await call(
        task({ inputs: [{ port: 'draft', path: PROP_PATH }, ...basePorts], output: editsPath, extra: remarks, brief: ORDER_BLOCK || undefined }),
        { agentType: 'proposal-writer', model: MODELS.write, label: `prop:write:${round}`, phase: PHASE, schema: DRAFT },
      ),
      `prop:write:${round}`,
    )
    const applied = await call(
      commands([`${tool('apply_edits')} --file ${PROP_PATH} --edits ${editsPath} ${noted(`apply round ${round} edits`)}`]),
      { agentType: 'file-copier', model: MODELS.copy, label: `prop:apply:${round}`, phase: PHASE, schema: GATE },
    )
    const report = (applied && applied.report) || { ok: false, problems: ['the edits were not applied: no report'], measures: {} }
    const answers = new Map()
    for (const a of drafted.addressed || []) if (a.item >= 1 && a.item <= pending.length) answers.set(a.item, a)
    const carried = []
    declinedNotes = []
    pending.forEach((it, i) => {
      const a = answers.get(i + 1)
      if (it.entry) it.entry.answer = a ? `${a.status}: ${a.note}` : 'not answered'
      if (!a) carried.push(it.text)
      else if (a.status === 'declined') declinedNotes.push(`${it.text}\n    -> declined: ${a.note}`)
    })
    const unapplied = (report.problems || []).map((p) => `EDIT NOT APPLIED, quote the draft exactly: ${p}`)
    log(`[prop/${round}] answered ${answers.size} of ${pending.length}; edits not applied ${unapplied.length}`)
    pending = [...carried, ...unapplied].map((text) => ({ kind: 'CARRIED', text }))
  } else {
    log(`[prop/${round}] the proposal on disk has not been judged in this stage: straight to the checks`)
  }

  // --- The gate: the profile's rules, the quotes, the client's words, every pain answered early
  const list = checksOf(round)
  const gated = await call(commands(list), { agentType: 'gate-runner', model: MODELS.gate, label: `prop:gate:${round}`, phase: PHASE, schema: CHECKS })
  const checks = (gated && gated.checks) || []
  const gateProblems =
    checks.length === list.length
      ? checks.flatMap((c) => c.problems || [])
      : ['the gate did not return one report per command: the draft was not measured']
  const sized = (checks[0] && checks[0].measures) || {}
  const exists = typeof sized.chars === 'number' && sized.chars >= MIN_ARTIFACT_CHARS
  lastCoverage = (checks[3] && checks[3].measures) || {}
  log(`[prop/${round}/gate] problems ${gateProblems.length}${gateProblems.length ? ': ' + gateProblems.join('; ') : ''}`)

  // --- The critic of the stage
  const said = await call(
    task({
      inputs: critic.inputs,
      noFile: true,
      brief: ORDER_BLOCK || undefined,
      extra: declinedNotes.length
        ? `DECLINED LAST ROUND, with the reason. Raise one again only if the reason is wrong, and say why.\n` +
          declinedNotes.map((d, i) => `${i + 1}. ${d}`).join('\n')
        : undefined,
    }),
    { agentType: critic.agentType, model: critic.model, label: `prop:${STAGE}:critic:${round}`, phase: PHASE, schema: VERDICT },
  )
  const remarks = said
    ? (said.remarks || []).map((r) => ({
        severity: severityOf(r),
        // The severity travels in its own field; left in the text it was printed twice.
        text: String(r).replace(/^\s*\d{1,2}[.)]\s+/, '').replace(/^\[(?:HIGH|MEDIUM|LOW)\]\s*/, ''),
      }))
    : [{ severity: 'HIGH', text: `the ${critic.agentType} returned no verdict: that is an open item, not agreement` }]
  const refuted = said && critic.vote ? await voteOnHigh(round, remarks) : 0
  const count = (s) => remarks.filter((r) => r.severity === s).length
  perRound.push(
    `Round ${round}: HIGH ${count('HIGH')}, MEDIUM ${count('MEDIUM')}, LOW ${count('LOW')}, ` +
      `HIGH refuted by the vote ${refuted}, gate problems ${gateProblems.length}`,
  )
  log(`[prop/${round}/critic] ${perRound[perRound.length - 1]}`)
  for (const r of remarks) log(`[prop/${round}/critic] ${r.text}`)

  // --- On the record; what goes back: gate, HIGH and MEDIUM; LOW is only recorded
  const sendBack = []
  for (const p of gateProblems) {
    const entry = { round, kind: 'GATE', text: p, answer: null }
    ledger.push(entry)
    sendBack.push({ kind: 'GATE', text: p, entry })
  }
  for (const r of remarks) {
    const low = r.severity === 'LOW' && !SEND_LOW
    const entry = { round, kind: r.severity, text: r.text, answer: low ? 'recorded, not sent back' : null }
    ledger.push(entry)
    if (!low) sendBack.push({ kind: r.severity, text: r.text, entry })
  }
  const mediums = remarks.filter((r) => r.severity === 'MEDIUM')
  const blocking = [
    ...gateProblems,
    ...remarks.filter((r) => r.severity === 'HIGH').map((r) => r.text),
    ...(mediums.length >= MEDIUM_LIMIT ? mediums.map((r) => r.text) : []),
  ]
  const passed = exists && blocking.length === 0
  const wrote = await call(
    record(roundPathOf(round), `Round ${round} — verdict=${passed ? 'approved' : 'revise'} style=approved`, [
      ...remarks.map((r) => `[${r.severity}] ${r.text}`),
      ...gateProblems.map((p) => `Gate: ${p}`),
      ...pending.map((it) => `Carried: ${it.text}`),
    ]),
    { agentType: 'verbatim-writer', model: MODELS.record, label: `prop:record:${round}`, phase: PHASE, schema: WROTE },
  )
  if (!(wrote && wrote.written)) warnings.push(`round ${round} was not recorded`)
  touched.add(draftPathOf(round))
  await call(
    commands([`${tool('snapshot')} --file ${PROP_PATH} --to ${draftPathOf(round)} ${noted(`proposal snapshot round ${round}`)}`]),
    { agentType: 'file-copier', model: MODELS.copy, label: `prop:snapshot:${round}`, phase: PHASE, schema: GATE },
  )
  pending = [...pending, ...sendBack]

  if (!exists) warnings.push(`round ${round}: the proposal did not reach the disk`)
  if (passed) {
    accepted = true
    log(`[prop/${round}] ACCEPTED: the gate is clean, no HIGH remark and fewer than ${MEDIUM_LIMIT} MEDIUM`)
    break
  }
  const signature = JSON.stringify(blocking.slice().sort())
  if (signature === previousSignature) {
    log(`[prop/${round}] STUCK: the same blocking items as the previous round; more rounds will not help`)
    break
  }
  previousSignature = signature
}

// =============================================================================================
// Report
// =============================================================================================

phase('Report')
const open = pending.map((it) => `[${it.kind}] ${it.text}`)
if (open.length) {
  await call(
    record(UNRESOLVED_PATH, accepted ? `The ${STAGE} was accepted; these items were left open` : 'The rounds ran out; these items are still open', open),
    { agentType: 'verbatim-writer', model: MODELS.record, label: 'unresolved', phase: 'Report', schema: WROTE },
  )
}
if (ledger.length) {
  await call(
    record(REMARKS_PATH, 'Every remark of every round, its severity and what the writer did with it', ledger.map((e) => `Round ${e.round} [${e.kind}] ${e.text} -> ${e.answer || 'open'}`)),
    { agentType: 'verbatim-writer', model: MODELS.record, label: 'remarks', phase: 'Report', schema: WROTE },
  )
}

// Only this stage's files are audited: the run directory also holds the requirements run.
const audit = await call(
  commands([`${tool('listing')} --dir ${run} --ext "" --recursive --log-release ${noted('audit: anything produced and never read')}`]),
  { agentType: 'gate-runner', model: MODELS.gate, label: 'audit', phase: 'Report', schema: LISTING },
)
const onDisk = (audit && audit.files) || []
const mine = (f) => f === PROP_PATH || f.startsWith(`${ROUNDS_DIR}/`) || f.startsWith(`${run}/prop-${STAGE}-`)
const orphans = onDisk.filter((f) => mine(f) && !touched.has(f) && f !== OUTCOME_PATH)
for (const f of orphans) log(`[audit/orphan] ${f}`)
if (!onDisk.length) warnings.push('the directory audit was not done: the listing did not come back')

const missing = Array.isArray(lastCoverage.missing) ? lastCoverage.missing : []
const late = Array.isArray(lastCoverage.late) ? lastCoverage.late : []
const outcome = [
  `${STAGE === 'content' ? 'Content' : 'Text'} accepted: ${accepted ? 'yes' : 'no'}; rounds: ${rounds} (this launch at most ${MAX_ROUNDS})`,
  `Pains answered in the client's words: ${lastCoverage.answered ?? '?'} of ${(lastCoverage.pains ?? 0) + (lastCoverage.worries ?? 0) || '?'}` +
    (missing.length ? `; not answered: ${missing.join(', ')}` : '') +
    (late.length ? `; top pains answered late: ${late.join(', ')}` : ''),
  `Design: ${designPath || 'none; how it is built rests on the requirements alone'}`,
  ...facts,
  ...perRound,
  `Open items: ${open.length}${open.length ? ` (${UNRESOLVED_PATH})` : ''}; all remarks: ${REMARKS_PATH}`,
  `Audit of this stage: read by nobody ${orphans.length}` + (orphans.length ? ` (${orphans.join(', ')})` : ''),
  ...warnings.map((w) => `WARNING: ${w}`),
  ...handoff.map((h) => `Call: ${h}`),
]
await call(record(OUTCOME_PATH, `Proposal ${STAGE}: ${run}`, outcome), {
  agentType: 'verbatim-writer',
  model: MODELS.record,
  label: 'outcome',
  phase: 'Report',
  schema: WROTE,
})
const records = [OUTCOME_PATH, ...(ledger.length ? [REMARKS_PATH] : []), ...(open.length ? [UNRESOLVED_PATH] : [])]
const recordList = records.map((r) => `${tool('gate')} --file "${r}" --min-length 50 ${noted('record on disk')}`)
const recorded = await call(commands(recordList), { agentType: 'gate-runner', model: MODELS.gate, label: 'records', phase: 'Report', schema: CHECKS })
const recordChecks = (recorded && recorded.checks) || []
const missingRecords = recordChecks.length === records.length ? records.filter((r, i) => !recordChecks[i].ok) : records
for (const r of missingRecords) log(`[report] RECORD NOT ON DISK: ${r}`)

return {
  stage: STAGE,
  proposal: PROP_PATH,
  accepted,
  rounds,
  pains_not_answered: missing,
  top_pains_late: late,
  open_items: open.length,
  unresolved: open.length ? UNRESOLVED_PATH : null,
  remarks: ledger.length ? REMARKS_PATH : null,
  outcome: OUTCOME_PATH,
  records_missing: missingRecords,
  orphans,
  warnings,
  next: accepted && STAGE === 'content' ? 'read prop.md, then config.stages=["text"]' : accepted ? 'figures: attn-figures.js on prop.md' : 'read the open items',
}
