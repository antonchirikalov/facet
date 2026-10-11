// The technical design, from accepted requirements, for any type of solution.
//
// One pipeline, many designs: the type names the profile the design is written and judged to
// (`solution-design` for an ordinary product, `ai-solution` for one in which a model does part of
// the work). The script knows nothing about either: the profile holds the sections, the critic's
// checklist and the gate rules.
//
//   Start    the requirements are accepted; the profile exists
//   Design   solution-designer writes design.md to the profile, then in rounds:
//            gate (the profile's gate block, every cited id exists, every binding requirement is
//            cited) -> critics in parallel: the design critic on the profile's checklist, the rule
//            panel (one checker per top rule of the profile, a skeptic over their flags), the
//            domain checker on the design's numbers; every HIGH of the critic put to a vote
//   Report   remarks, unresolved items, the outcome
//
// Rounds stop on acceptance (gate clean, no HIGH, fewer than three MEDIUM, as the profiles say),
// on the round limit, on the same blocking items twice, or on a plateau: the blocking items not
// fewer than the best for two rounds in a row.
//
// The script has no filesystem and no shell: agents read and write, python tools measure through
// the gate-runner agent, results are matched to commands by index. Runtime rules: meta is a pure
// literal; no import(), no Date.now(), no Math.random().

export const meta = {
  name: 'design',
  description: 'Technical design from accepted requirements, written and judged to the profile of its type',
  phases: [
    { title: 'Start', detail: 'accepted requirements and the profile of the design type' },
    { title: 'Design', detail: 'designer, gate, critic with rule panel and domain checker, in rounds' },
    { title: 'Holdout', detail: 'the questions the client will ask, put to the design by a reader with nothing else' },
    { title: 'Report', detail: 'remarks, unresolved items, outcome' },
  ],
}

// --- Input ------------------------------------------------------------------------------------

const run = typeof args === 'string' ? args : args && args.runDir
if (!run) throw new Error('a run directory is required: args.runDir, the directory of an accepted requirements run')
const now = (args && args.now) || ''
const order = (args && args.order) || ''
const type = (args && args.type) || 'solution-design'
if (!/^[a-z-]+$/.test(type)) throw new Error(`args.type is a profile name such as "solution-design" or "ai-solution"; got ${type}`)
const cfg = (args && args.config) || {}
const client = (args && args.client) || ''
const CLIENT_BLOCK = client
  ? `CLIENT\nThe client is ${client}. These documents name them as ${client}; never replace the name with a ` +
    `placeholder. People of the client are named by role only.`
  : ''
if (cfg.continue && cfg.fresh) throw new Error('config.continue and config.fresh exclude each other')

// --- Paths ------------------------------------------------------------------------------------

const REQ_PATH = `${run}/requirements.md`
const REQ_OUTCOME = `${run}/outcome.md`
const DESIGN_PATH = `${run}/design.md`
const PROFILE = `.claude/skills/${type}-profile/SKILL.md`
const TOOLS_LOG = `${run}/tools.jsonl`
const ROUNDS_DIR = `${run}/rounds/design`
const OUTCOME_PATH = `${run}/design-outcome.md`
const REMARKS_PATH = `${run}/design-remarks.md`
const UNRESOLVED_PATH = `${run}/design-unresolved.md`
const NUMBER_CHECKS = `${run}/design-number-checks.md`
// The holdout questions requirements.js wrote before this design existed, and where this
// design's answers to them go. No writer or critic of the design is ever handed either.
const HOLDOUT_QUESTIONS = `${run}/holdout/questions.md`
const HOLDOUT_OUT = `${run}/holdout/design`
const HOLDOUT_PROFILE = '.claude/skills/holdout-questions-profile/SKILL.md'
// Two readers per batch: one reader moves between answered and acknowledged on the same text
// (one live run: 0.60 and 0.65 for one design); the lower of two outcomes stands, as in doubt.
const HOLDOUT_READERS = 2
const roundPathOf = (n) => `${ROUNDS_DIR}/round-${n}.md`
const draftPathOf = (n) => `${ROUNDS_DIR}/draft-${n}.md`
const editsPathOf = (n) => `${ROUNDS_DIR}/edits-${n}.json`

// --- Configuration ----------------------------------------------------------------------------

const MAX_ROUNDS = cfg.maxRounds || 3
const PLATEAU_ROUNDS = cfg.plateauRounds || 2
const MEDIUM_LIMIT = cfg.mediumLimit ?? 3
const VOTERS = cfg.voters ?? 3
// The rule panel by default for an AI design, whose profile is a set of decision rules.
const RULE_PANEL = cfg.rulePanel ?? type === 'ai-solution'
const MIN_ARTIFACT_CHARS = 1000
const MODELS = {
  design: 'opus',
  critic: 'opus',
  rules: 'sonnet',
  numbers: 'opus',
  vote: 'sonnet',
  gate: 'sonnet',
  record: 'sonnet',
  copy: 'sonnet',
  // Another model than the designer's: a reader who thinks like the writer finds what the writer meant.
  finder: 'sonnet',
  ...(cfg.models || {}),
}
const tool = (name) => `python -X utf8 tools/${name}.py`
const REQ_IDS = '\\b(?:FR|NFR|BR)-\\d{3}\\b'

// --- Records of the run -----------------------------------------------------------------------

const touched = new Set([TOOLS_LOG])
const handoff = []
let lastPorts = null
const warnings = []
const LOG_FLAG = `--log ${TOOLS_LOG}`
const noted = (purpose) => `${LOG_FLAG} --log-note "${purpose}"`
const commands = (list) => `COMMANDS\n` + list.map((c, i) => `${i + 1}. ${c}`).join('\n')
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
const ORDER_BLOCK = order
  ? `ORDER\n${order}\n\nThe order sets the scope and decisions of this run and is binding where it sets them.`
  : ''
function task({ inputs, output, extra, noFile }) {
  for (const i of inputs || []) touched.add(i.path)
  if (!noFile && output) touched.add(output)
  lastPorts = { inputs: (inputs || []).map((i) => `${i.port} -> ${i.path}`), output: noFile ? null : output }
  const ports = (inputs || []).map((i) => `${i.port}: ${i.path}`).join('\n')
  const lead = [CLIENT_BLOCK, ORDER_BLOCK].filter(Boolean).join('\n\n')
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
const LISTING = {
  type: 'object',
  required: ['files', 'count'],
  properties: {
    files: { type: 'array', items: { type: 'string' } },
    count: { type: 'integer', description: 'the files number from the report measures, verbatim' },
  },
}
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
const WROTE = { type: 'object', required: ['written'], properties: { written: { type: 'boolean' } } }
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
          status: { type: 'string', enum: ['fixed', 'needs_context', 'declined'] },
          note: { type: 'string', description: 'what you did, or why you deliberately did not' },
          missing: { type: 'string', description: 'needs_context only: the fact the inputs do not hold, in one line' },
          searched: { type: 'string', description: 'needs_context only: which inputs you searched for it' },
          owner: {
            type: 'string',
            enum: ['client', 'domain'],
            description: 'needs_context only: client when only the client can know it, domain when practice gives it',
          },
        },
      },
    },
  },
}
const VERDICT = {
  type: 'object',
  required: ['verdict', 'remarks'],
  properties: {
    verdict: { type: 'string', enum: ['approved', 'revise'], description: 'exactly approved or exactly revise' },
    remarks: { type: 'array', items: { type: 'string', description: '[HIGH|MEDIUM|LOW] section — what is wrong — evidence — fix' } },
  },
}
const RULES = {
  type: 'object',
  required: ['rules', 'count'],
  properties: {
    rules: {
      type: 'array',
      items: {
        type: 'object',
        required: ['id', 'severity', 'text'],
        properties: { id: { type: 'string' }, severity: { type: 'string' }, text: { type: 'string' } },
      },
    },
    count: { type: 'integer', description: 'the count number from the report measures, verbatim' },
  },
}
const FLAGS = {
  type: 'object',
  required: ['flags'],
  properties: {
    flags: {
      type: 'array',
      items: {
        type: 'object',
        required: ['where', 'quote', 'why'],
        properties: { where: { type: 'string' }, quote: { type: 'string' }, why: { type: 'string' } },
      },
    },
  },
}
const FOUND = {
  type: 'object',
  required: ['implausible'],
  properties: {
    implausible: {
      type: 'array',
      items: { type: 'string' },
      description: 'one line per implausible number: what the document says, what practice gives, a value that fits',
    },
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

// --- Missing input ----------------------------------------------------------------------------
//
// A remark the inputs hold no data for has a third answer besides fixed and declined. The designer
// reads the requirements, not the client's material, so what is missing is either a fact only the
// client knows, which goes on its own record of what to ask, or a fact of practice (a usual load, a
// typical duration), which the domain checker looks up in the same round and hands back. The
// critic may show where the inputs do hold it; the remark then comes back and cannot be answered so
// again.
const MISSING_ITEMS_RULE =
  `needs_context when the inputs hold no data to act on the remark: name in missing the fact that is ` +
  `absent, in searched which inputs you looked in, and in owner whose fact it is: client when only the ` +
  `client can know it (record it where the profile keeps assumptions to confirm or decisions to take ` +
  `with the client), domain when practice gives it (a usual figure, a typical duration; it is looked up ` +
  `and comes back to you). It is not an answer to a remark that is hard, or one you disagree with.`
function refusalOf(item, answer) {
  if (item.measured || item.kind === 'GATE') return 'a measurement is answered by a fix, not by missing input'
  if (item.contested) return 'the critic named where the inputs hold it'
  if (!String(answer.missing || '').trim()) return 'what is missing was not named'
  if (!String(answer.searched || '').trim()) return 'where it was looked for was not named'
  if (answer.owner !== 'client' && answer.owner !== 'domain') return 'whose fact it is was not named'
  if (answer.owner === 'domain' && item.practiceAsked) return 'practice was already looked up for it'
  return ''
}
const CONTESTED = /^\s*CONTESTED-(\d+)\s*[:.-]?\s*/
function contestedOf(text) {
  const m = CONTESTED.exec(String(text))
  return m ? { n: Number(m[1]), text: String(text).slice(m[0].length) } : null
}
function contextBlock(notes) {
  return notes.length
    ? `NO DATA IN THE INPUTS, the designer says, for these remarks of the last round; each left the rounds. ` +
        `If the inputs do hold what the designer names as missing, raise the remark again and open it with ` +
        `CONTESTED-<n>: followed by where the data is (the document and the place). Otherwise do not raise it again.\n` +
        notes.map((d, i) => `${i + 1}. ${d.text}\n    -> missing: ${d.missing}; searched: ${d.searched}`).join('\n')
    : ''
}

// =============================================================================================
// Start: the design rests on accepted requirements and on its profile
// =============================================================================================

phase('Start')
let present = false
{
  const required = [
    { what: 'the requirements', cmd: `${tool('gate')} --file "${REQ_PATH}" --min-length 1000 ${noted('start: requirements')}` },
    { what: `the profile ${PROFILE}`, cmd: `${tool('gate')} --file "${PROFILE}" --min-length 200 ${noted('start: design profile')}` },
    ...(cfg.accepted
      ? []
      : [
          {
            what: 'the acceptance of the requirements (outcome.md, line 1: Accepted: yes)',
            cmd: `${tool('gate')} --file "${REQ_OUTCOME}" --require-line "^\\s*1\\. Accepted: yes" ${noted('start: requirements accepted')}`,
          },
        ]),
  ]
  const list = [
    ...(now ? [`${tool('busy')} --file ${TOOLS_LOG} --now ${now} --idle-seconds ${cfg.idleSeconds || 600} ${noted('is another run working here')}`] : []),
    `${tool('gate')} --file "${DESIGN_PATH}" --min-length ${MIN_ARTIFACT_CHARS} ${noted('start: design already on disk')}`,
    ...required.map((r) => r.cmd),
  ]
  const started = await call(commands(list), { agentType: 'gate-runner', model: MODELS.gate, label: 'start', phase: 'Start', schema: CHECKS })
  const checks = (started && started.checks) || []
  if (checks.length !== list.length) throw new Error(`the start check returned ${checks.length} reports for ${list.length} commands`)
  const offset = now ? 1 : 0
  if (now && checks[0].busy && !cfg.ignoreBusy) {
    throw new Error(`another run seems to be working in ${run}: ${(checks[0].problems || []).join('; ')}; config.ignoreBusy=true if it is dead`)
  }
  if (!now) warnings.push('args.now was not passed: whether another run works in this directory was not checked')
  present = checks[offset].ok
  const failed = required.filter((r, i) => !checks[offset + 1 + i].ok)
  if (failed.length) {
    throw new Error(
      `the design rests on what is not there yet: ` +
        failed.map((r) => `${r.what} (${checks[offset + 1 + required.indexOf(r)].problems.join('; ')})`).join('; ') +
        `. Run requirements.js in ${run} first; if you accepted the requirements yourself, config.accepted=true.`,
    )
  }
  if (cfg.accepted) warnings.push('accepted by the person who launched the run (config.accepted), not by an outcome on disk')
  for (const x of [REQ_PATH, REQ_OUTCOME, PROFILE]) touched.add(x)
  if (present && !cfg.continue && !cfg.fresh) {
    throw new Error(`${DESIGN_PATH} already exists. config.continue=true to continue, config.fresh=true to write it again.`)
  }
  if (cfg.fresh) present = false
  log(`[start] type=${type} design on disk=${present} rule panel=${RULE_PANEL}`)
}

const evidence = [{ port: 'evidence:requirements', path: REQ_PATH }]
const checksOf = (round) => [
  `${tool('gate')} --file "${DESIGN_PATH}" --profile ${PROFILE} --min-length ${MIN_ARTIFACT_CHARS} ${noted(`design round ${round}`)}`,
  `${tool('trace_ids')} --file "${DESIGN_PATH}" --against "${REQ_PATH}" --ids "${REQ_IDS}" ${noted(`requirement ids the design cites, round ${round}`)}`,
  `${tool('must_covered')} --requirements "${REQ_PATH}" --file "${DESIGN_PATH}" ${noted(`binding requirements cited, round ${round}`)}`,
]
const severityOf = (text) => {
  const m = /^\s*(?:\d{1,2}[.)]\s+)?\[(HIGH|MEDIUM|LOW|CRITICAL|MAJOR|MINOR)\]/.exec(text)
  const s = m ? m[1] : 'MEDIUM'
  return s === 'CRITICAL' ? 'HIGH' : s === 'MAJOR' ? 'MEDIUM' : s === 'MINOR' ? 'LOW' : s
}
const plain = (r) => String(r).replace(/^\s*\d{1,2}[.)]\s+/, '').replace(/^\[(?:HIGH|MEDIUM|LOW|CRITICAL|MAJOR|MINOR)\]\s*/, '')
const CRITIC_EXTRA =
  `THE PROFILE of this design is ${PROFILE}: judge against it. THE FIGURES are drawn later; do not report ` +
  `missing image files. THE REMARKS are defects only: what you checked and found right is not a remark.`

// A HIGH of the design critic sends the design back, so independent checkers vote on it first.
async function voteOnHigh(round, remarks) {
  const high = remarks.filter((r) => r.severity === 'HIGH')
  if (!high.length || VOTERS < 2) return 0
  const claims =
    `CLAIMS TO CHECK\nEach claim is a reviewer's remark about the draft. It holds when the draft really ` +
    `has the defect the remark names and the evidence confirms what the remark says.\n` +
    high.map((r, i) => `V${i + 1}: "${r.text}"`).join('\n')
  const ballots = await parallel(
    Array.from({ length: VOTERS }, (_, k) => () =>
      call(task({ inputs: [{ port: 'draft', path: DESIGN_PATH }, ...evidence], noFile: true, extra: claims }), {
        agentType: 'claim-checker',
        model: MODELS.vote,
        label: `design:vote:${round}:${k + 1}`,
        phase: 'Design',
        schema: CHECKED,
      }),
    ),
  )
  const majority = Math.floor(VOTERS / 2) + 1
  let refuted = 0
  high.forEach((r, i) => {
    const said = ballots.map((b) => b && (b.results || []).find((x) => x.id === `V${i + 1}`)).filter(Boolean)
    const against = said.filter((x) => !x.holds)
    if (against.length >= majority) {
      r.severity = 'MEDIUM'
      r.text = `${r.text} [not confirmed by ${against.length} of ${VOTERS} checkers: ${against[0].problem || 'no reason given'}]`
      refuted += 1
    }
  })
  return refuted
}

// The rule panel: one checker per top rule of the profile, a skeptic over their flags. The rules
// are read from the profile by tools/rules.py, once.
let rules = null
async function rulePanel(round) {
  if (rules === null) {
    const got = await call(
      commands([`${tool('rules')} --profile ${PROFILE} --top ${noted(`top rules of ${PROFILE}`)}`]) +
        `\n\nReturn the rules from measures.rules and the number from measures.count, unchanged.`,
      { agentType: 'gate-runner', model: MODELS.gate, label: 'design:rules', phase: 'Design', schema: RULES },
    )
    rules = got && Array.isArray(got.rules) && got.rules.length === got.count ? got.rules : []
    if (!rules.length) warnings.push(`rule panel skipped: the rules of ${PROFILE} did not arrive whole`)
  }
  if (!rules.length) return []
  const flagged = await parallel(
    rules.map((r) => () =>
      call(
        task({ inputs: [{ port: 'draft', path: DESIGN_PATH }, ...evidence], noFile: true, extra: `THE RULE\n${r.id}. [${r.severity}] ${r.text}` }),
        { agentType: 'rule-checker', model: MODELS.rules, label: `design:rule-${r.id}:${round}`, phase: 'Design', schema: FLAGS },
      ),
    ),
  )
  const lines = []
  rules.forEach((r, i) => {
    const got = flagged[i]
    if (!got) {
      lines.push(`rule ${r.id} [${r.severity}]: its checker returned nothing, so the rule was not checked`)
      return
    }
    for (const f of got.flags || []) lines.push(`rule ${r.id} [${r.severity}] — ${f.where} — "${f.quote}" — ${f.why}`)
  })
  if (!lines.length) return []
  // A gap the designer declared for want of data is not a defect while the design records it: a
  // checker that flags it again every round would hold the loop on a remark nobody can close.
  const gaps = contextNotes.length
    ? `\n\nGAPS THE DESIGNER DECLARED, no data in the inputs. A flag that only says one of these is missing ` +
      `is not a defect while the design records the gap as an assumption to confirm or a decision to take; drop it.\n` +
      contextNotes.map((d, i) => `${i + 1}. ${d.text} -> missing: ${d.missing}`).join('\n')
    : ''
  const kept = await call(
    task({
      inputs: [{ port: 'draft', path: DESIGN_PATH }, ...evidence],
      noFile: true,
      extra: `FLAGS\n` + lines.map((l, i) => `${i + 1}. ${l}`).join('\n') + `\n\n${CRITIC_EXTRA}` + gaps,
    }),
    { agentType: 'rule-skeptic', model: MODELS.rules, label: `design:skeptic:${round}`, phase: 'Design', schema: VERDICT },
  )
  if (!kept) return [{ severity: 'HIGH', text: '[RULES] the rule skeptic returned nothing: the flags were not judged' }]
  return (kept.remarks || []).map((r) => ({ severity: severityOf(r), text: `[RULES] ${plain(r)}` }))
}

// =============================================================================================
// The rounds
// =============================================================================================

phase('Design')
const ledger = []
let pending = []
let declinedNotes = []
// The remarks answered needs_context and accepted as the client's facts, for the record.
const missingInput = []
// Those of the last round, shown to the critic so it can contest them and to the rule skeptic.
let contextNotes = []
// Facts of practice the designer asked for this round: the domain checker looks them up.
let practiceAsked = []
let accepted = false
let rounds = 0
let previousSignature = null
let numbersChecked = false
let best = Infinity
let sinceBest = 0
let lastMust = {}
// Whether the last round found a design on disk: the holdout reader needs one to read.
let designOnDisk = false
const perRound = []

let startRound = 1
if (cfg.continue) {
  const recorded = await call(
    commands([`${tool('rounds')} --dir ${ROUNDS_DIR} --last-only ${noted('continue: rounds already judged')}`]),
    { agentType: 'gate-runner', model: MODELS.gate, label: 'design:continue', phase: 'Design', schema: ROUNDS },
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
        .filter((r) => !/^\[LOW\]/.test(r) && !/^Gate: /.test(r))
        .map((r) => ({ kind: severityOf(r), text: plain(r).replace(/^Carried: /, '') })),
    ]
    log(`[design/continue] rounds judged ${recorded.report.measures.rounds}, continuing from ${startRound} with ${pending.length} items`)
  }
}

for (let round = startRound; round < startRound + MAX_ROUNDS; round++) {
  rounds = round
  phase('Design')
  const writerInputs = [
    { port: 'requirements', path: REQ_PATH },
    { port: 'profile', path: PROFILE },
    ...(numbersChecked ? [{ port: 'number_checks', path: NUMBER_CHECKS }] : []),
  ]

  // --- The designer: the first draft, or one edits file answering the numbered items
  if (!present) {
    must(
      await call(task({ inputs: writerInputs, output: DESIGN_PATH }), {
        agentType: 'solution-designer',
        model: MODELS.design,
        label: `design:write:${round}`,
        phase: 'Design',
        schema: DRAFT,
      }),
      `design:write:${round}`,
    )
    present = true
  } else if (pending.length) {
    const editsPath = editsPathOf(round)
    const remarks =
      `REMARKS ON THE PREVIOUS DRAFT. GATE items are measurements and are not open to argument; everything ` +
      `else you may decline with a reason.\n\n` +
      pending.map((it, i) => `${i + 1}. [${it.kind}] ${it.text}`).join('\n') +
      `\n\nHOW TO ANSWER. One entry per number from 1 to ${pending.length}: fixed, declined with the reason, or ` +
      `${MISSING_ITEMS_RULE}` +
      `\n\nHOW TO DELIVER THIS ROUND. Do not edit ${DESIGN_PATH} yourself. Write your changes as a JSON array to ` +
      `${editsPath}: [{"old": "<text copied verbatim from the draft, occurring exactly once>", "new": "<the ` +
      `replacement>"}]. To delete, new is empty. A tool applies the list and reports every pair whose old text ` +
      `was not found once.`
    const drafted = must(
      await call(task({ inputs: [{ port: 'draft', path: DESIGN_PATH }, ...writerInputs], output: editsPath, extra: remarks }), {
        agentType: 'solution-designer',
        model: MODELS.design,
        label: `design:write:${round}`,
        phase: 'Design',
        schema: DRAFT,
      }),
      `design:write:${round}`,
    )
    const applied = await call(
      commands([`${tool('apply_edits')} --file ${DESIGN_PATH} --edits ${editsPath} ${noted(`apply round ${round} edits`)}`]),
      { agentType: 'file-copier', model: MODELS.copy, label: `design:apply:${round}`, phase: 'Design', schema: GATE },
    )
    const report = (applied && applied.report) || { ok: false, problems: ['the edits were not applied: no report'], measures: {} }
    const answers = new Map()
    for (const a of drafted.addressed || []) if (a.item >= 1 && a.item <= pending.length) answers.set(a.item, a)
    const carried = []
    declinedNotes = []
    contextNotes = []
    practiceAsked = []
    pending.forEach((it, i) => {
      const a = answers.get(i + 1)
      if (it.entry) it.entry.answer = a ? `${a.status}: ${a.note}` : 'not answered'
      if (!a) carried.push(it)
      else if (a.status === 'declined') declinedNotes.push(`${it.text}\n    -> declined: ${a.note}`)
      else if (a.status === 'needs_context') {
        const refused = refusalOf(it, a)
        if (it.entry) {
          it.entry.answer += refused ? ` [needs_context refused: ${refused}]` : ` [${a.owner} fact missing: ${a.missing}; searched: ${a.searched}]`
        }
        const note = { round, text: it.text, missing: a.missing, searched: a.searched }
        if (refused) {
          log(`[design/${round}/needs_context] refused for ${i + 1}: ${refused}`)
          carried.push({ ...it, text: `${it.text} [answered needs_context, refused: ${refused}]` })
        } else if (a.owner === 'domain') {
          practiceAsked.push(note)
        } else {
          missingInput.push(note)
          contextNotes.push(note)
        }
      }
    })
    const unapplied = (report.problems || []).map((p) => `EDIT NOT APPLIED, quote the draft exactly: ${p}`)
    log(
      `[design/${round}] answered ${answers.size} of ${pending.length}; client facts missing ${contextNotes.length}; ` +
        `practice to look up ${practiceAsked.length}; edits not applied ${unapplied.length}`,
    )
    pending = [
      ...carried.map((it) => ({
        kind: 'CARRIED',
        text: it.text,
        measured: it.measured || it.kind === 'GATE',
        contested: it.contested,
        practiceAsked: it.practiceAsked,
      })),
      ...unapplied.map((text) => ({ kind: 'CARRIED', text, measured: true })),
    ]
  } else {
    log(`[design/${round}] the design on disk has not been judged: straight to the checks`)
  }

  // --- The gate
  const list = checksOf(round)
  const gated = await call(commands(list), { agentType: 'gate-runner', model: MODELS.gate, label: `design:gate:${round}`, phase: 'Design', schema: CHECKS })
  const checks = (gated && gated.checks) || []
  const gateProblems =
    checks.length === list.length ? checks.flatMap((c) => c.problems || []) : ['the gate did not return one report per command']
  const sized = (checks[0] && checks[0].measures) || {}
  const exists = typeof sized.chars === 'number' && sized.chars >= MIN_ARTIFACT_CHARS
  lastMust = (checks[2] && checks[2].measures) || {}
  designOnDisk = exists

  // --- The critics, in parallel
  const extra = [
    CRITIC_EXTRA,
    declinedNotes.length
      ? `DECLINED LAST ROUND, with the reason. Raise one again only if the reason is wrong, and say why.\n` +
        declinedNotes.map((d, i) => `${i + 1}. ${d}`).join('\n')
      : '',
    contextBlock(contextNotes),
  ]
    .filter(Boolean)
    .join('\n\n')
  // What the designer could not answer without practice is looked up by the checker of numbers,
  // in the same file and the same way, and goes back to the designer next round.
  const practice = practiceAsked.length
    ? `QUESTIONS OF PRACTICE the designer could not answer from the requirements. Answer each in the same ` +
      `file and the same way, one section per question, with sources:\n` +
      practiceAsked.map((d, i) => `P${i + 1}. ${d.missing} (for the remark: ${d.text})`).join('\n')
    : undefined
  const [criticSaid, ruleRemarks, numbers] = await parallel([
    () =>
      call(
        task({
          inputs: [{ port: 'draft', path: DESIGN_PATH }, { port: 'requirements', path: REQ_PATH }, { port: 'profile', path: PROFILE }],
          noFile: true,
          extra,
        }),
        { agentType: 'solution-design-critic', model: MODELS.critic, label: `design:critic:${round}`, phase: 'Design', schema: VERDICT },
      ),
    () => (RULE_PANEL ? rulePanel(round) : Promise.resolve([])),
    () =>
      call(task({ inputs: [{ port: 'draft', path: DESIGN_PATH }], output: NUMBER_CHECKS, extra: practice }), {
        agentType: 'domain-checker',
        model: MODELS.numbers,
        label: `design:numbers:${round}`,
        phase: 'Design',
        schema: FOUND,
      }),
  ])
  const criticRemarks = criticSaid
    ? (criticSaid.remarks || []).map((r) => {
        // CONTESTED-<n> says the inputs do hold what the designer called missing: the item leaves the
        // missing-input record and comes back, never to be answered so again.
        const c = contestedOf(plain(r))
        const note = c && contextNotes[c.n - 1]
        if (!note) return { severity: severityOf(r), text: `[DESIGN] ${plain(r)}` }
        if (missingInput.includes(note)) missingInput.splice(missingInput.indexOf(note), 1)
        log(`[design/${round}/critic] contested ${c.n}: ${note.text}`)
        return { severity: severityOf(r), text: `[DESIGN] ${c.text} [contested: the critic says the inputs hold it]`, contested: true }
      })
    : [{ severity: 'HIGH', text: '[DESIGN] the design critic returned nothing: that is an open item, not agreement' }]
  const refuted = criticSaid ? await voteOnHigh(round, criticRemarks) : 0
  if (numbers) numbersChecked = true
  const numberRemarks = ((numbers && numbers.implausible) || []).map((x) => ({
    severity: 'MEDIUM',
    text: `[NUMBERS] ${x} (what practice gives, with sources: ${NUMBER_CHECKS})`,
  }))
  const remarks = [...criticRemarks, ...(ruleRemarks || []), ...numberRemarks]
  const count = (s) => remarks.filter((r) => r.severity === s).length
  perRound.push(
    `Round ${round}: HIGH ${count('HIGH')}, MEDIUM ${count('MEDIUM')}, LOW ${count('LOW')}, ` +
      `HIGH refuted by the vote ${refuted}, gate problems ${gateProblems.length}`,
  )
  log(`[design/${round}] ${perRound[perRound.length - 1]}`)

  // --- On the record; what goes back
  const sendBack = []
  for (const p of gateProblems) {
    const entry = { round, kind: 'GATE', text: p, answer: null }
    ledger.push(entry)
    sendBack.push({ kind: 'GATE', text: p, entry })
  }
  for (const r of remarks) {
    const low = r.severity === 'LOW'
    const entry = { round, kind: r.severity, text: r.text, answer: low ? 'recorded, not sent back' : null }
    ledger.push(entry)
    if (!low) sendBack.push({ kind: r.severity, text: r.text, entry, contested: r.contested })
  }
  // The facts of practice come back to the designer with what the checker found for them.
  for (const d of practiceAsked) {
    const text = numbers
      ? `${d.text} — practice for "${d.missing}" is in ${NUMBER_CHECKS}`
      : `${d.text} — practice for "${d.missing}" was not looked up: the domain checker returned nothing`
    const entry = { round, kind: 'PRACTICE', text, answer: null }
    ledger.push(entry)
    sendBack.push({ kind: 'PRACTICE', text, entry, practiceAsked: true })
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
      ...sendBack.filter((it) => it.kind === 'PRACTICE').map((it) => `Carried: ${it.text}`),
    ]),
    { agentType: 'verbatim-writer', model: MODELS.record, label: `design:record:${round}`, phase: 'Design', schema: WROTE },
  )
  if (!(wrote && wrote.written)) warnings.push(`round ${round} was not recorded`)
  touched.add(draftPathOf(round))
  await call(
    commands([`${tool('snapshot')} --file ${DESIGN_PATH} --to ${draftPathOf(round)} ${noted(`design snapshot round ${round}`)}`]),
    { agentType: 'file-copier', model: MODELS.copy, label: `design:snapshot:${round}`, phase: 'Design', schema: GATE },
  )
  pending = [...pending, ...sendBack]

  if (!exists) warnings.push(`round ${round}: the design did not reach the disk`)
  if (passed) {
    accepted = true
    log(`[design/${round}] ACCEPTED`)
    break
  }
  const signature = JSON.stringify(blocking.slice().sort())
  if (signature === previousSignature) {
    log(`[design/${round}] STUCK: the same blocking items as the previous round`)
    break
  }
  previousSignature = signature
  // A plateau: the critics keep finding about as much as they did; more rounds buy text, not quality.
  if (blocking.length < best) {
    best = blocking.length
    sinceBest = 0
  } else {
    sinceBest += 1
    if (sinceBest >= PLATEAU_ROUNDS) {
      log(`[design/${round}] PLATEAU: ${sinceBest} rounds without fewer blocking items than ${best}; the rest is for a person`)
      break
    }
  }
}

// =============================================================================================
// Holdout: the client's questions put to the design by a reader holding nothing else
// =============================================================================================

// After the rounds and outside them: the score goes to the outcome for a person, never to the
// designer, and it does not decide acceptance. A score fed back as remarks would hand the writer
// the questions, and the next score would measure them, not the design.
const holdoutOutcome = []
const holdoutAnswers = []
let holdoutScore = null
if (cfg.holdout === false) {
  holdoutOutcome.push('Holdout: not scored (config.holdout=false)')
} else if (!designOnDisk) {
  holdoutOutcome.push('Holdout: not scored, the design is not on disk')
} else {
  phase('Holdout')
  const checked = await call(
    commands([`${tool('holdout')} --check --final --file "${HOLDOUT_QUESTIONS}" --profile ${HOLDOUT_PROFILE} ${noted('holdout questions for the design')}`]),
    { agentType: 'gate-runner', model: MODELS.gate, label: 'holdout:questions', phase: 'Holdout', schema: CHECKS },
  )
  const ready = checked && checked.checks && checked.checks.length === 1 && checked.checks[0].ok
  if (!ready) {
    holdoutOutcome.push(`Holdout: not scored, no usable questions in ${HOLDOUT_QUESTIONS} (requirements.js writes them)`)
  } else {
    touched.add(HOLDOUT_QUESTIONS)
    const blinded = await call(
      commands([`${tool('holdout')} --blind --file "${HOLDOUT_QUESTIONS}" --for design --out-dir "${HOLDOUT_OUT}" --profile ${HOLDOUT_PROFILE} ${noted('holdout batches for the design')}`]),
      { agentType: 'file-copier', model: MODELS.copy, label: 'holdout:blind', phase: 'Holdout', schema: GATE },
    )
    const batches = Number((blinded && blinded.report && blinded.report.measures && blinded.report.measures.batches) || 0)
    const answers = await parallel(
      Array.from({ length: Math.min(batches, 10) * HOLDOUT_READERS }, (_, i) => () => {
        const batch = Math.floor(i / HOLDOUT_READERS) + 1
        const out = `${HOLDOUT_OUT}/answers-${batch}-${(i % HOLDOUT_READERS) + 1}.json`
        holdoutAnswers.push(out)
        return call(task({ inputs: [{ port: 'draft', path: DESIGN_PATH }, { port: 'references', path: REQ_PATH }, { port: 'questions', path: `${HOLDOUT_OUT}/blind-${batch}.md` }], output: out }), {
          agentType: 'answer-finder',
          model: MODELS.finder,
          label: `holdout:find:${batch}:${(i % HOLDOUT_READERS) + 1}`,
          phase: 'Holdout',
          schema: WROTE,
        })
      }),
    )
    const dead = answers.filter((a) => !a).length
    if (dead) warnings.push(`holdout: ${dead} of ${answers.length} readers returned nothing; the other reader of their batch stands alone`)
    const SCORE = `${HOLDOUT_OUT}/score.md`
    const scored = await call(
      commands([
        `${tool('holdout')} --score --file "${HOLDOUT_QUESTIONS}" --for design --document "${DESIGN_PATH}" --answers-dir "${HOLDOUT_OUT}" --out "${SCORE}" ${noted('holdout score of the design')}`,
      ]),
      { agentType: 'file-copier', model: MODELS.copy, label: 'holdout:score', phase: 'Holdout', schema: GATE },
    )
    const m = (scored && scored.report && scored.report.measures) || {}
    touched.add(SCORE)
    touched.add(SCORE.replace(/\.md$/, '.json'))
    if (typeof m.score === 'number') {
      holdoutScore = m.score
      const list = (x) => (Array.isArray(x) && x.length ? x.join(', ') : 'none')
      holdoutOutcome.push(
        `Holdout: score ${m.score}; met ${m.met} of ${m.expected}; blocking not met: ${list(m.absent_blocking)}; ` +
          `answers whose quote is not in the design: ${list(m.downgraded_quote_not_found)}; readers disagreed, the lower stands: ${list(m.readers_disagreed)} (${SCORE})`,
      )
    } else {
      warnings.push('holdout: the score did not come back')
    }
  }
}

// =============================================================================================
// Report
// =============================================================================================

phase('Report')
const open = pending.map((it) => `[${it.kind}] ${it.text}`)
const writeOpen = open.length > 0 || !!cfg.continue
if (writeOpen) {
  await call(
    record(UNRESOLVED_PATH, accepted ? 'The design was accepted; these items were left open' : 'These items are still open', open.length ? open : ['Nothing is open']),
    { agentType: 'verbatim-writer', model: MODELS.record, label: 'unresolved', phase: 'Report', schema: WROTE },
  )
}
// The client's facts the requirements did not hold, on their own record: they are for the client,
// not for another round. A continued launch names its own file and never writes over an earlier one.
const MISSING_INPUT_PATH =
  startRound > 1 ? `${run}/design-missing-input-from-round-${startRound}.md` : `${run}/design-missing-input.md`
if (startRound > 1) touched.add(`${run}/design-missing-input.md`)
if (missingInput.length) {
  await call(
    record(
      MISSING_INPUT_PATH,
      'Remarks the requirements hold no data for: what to ask the client',
      missingInput.map((d) => `Round ${d.round}: ${d.text} — missing: ${d.missing} — searched: ${d.searched}`),
    ),
    { agentType: 'verbatim-writer', model: MODELS.record, label: 'missing-input', phase: 'Report', schema: WROTE },
  )
}
if (ledger.length) {
  await call(
    record(REMARKS_PATH, 'Every remark of every round, its severity and what the designer did with it', ledger.map((e) => `Round ${e.round} [${e.kind}] ${e.text} -> ${e.answer || 'open'}`)),
    { agentType: 'verbatim-writer', model: MODELS.record, label: 'remarks', phase: 'Report', schema: WROTE },
  )
}
const audit = await call(
  commands([`${tool('listing')} --dir ${run} --ext "" --recursive --log-release ${noted('audit: anything produced and never read')}`]),
  { agentType: 'gate-runner', model: MODELS.gate, label: 'audit', phase: 'Report', schema: LISTING },
)
const onDisk = (audit && audit.files) || []
const mine = (f) =>
  f === DESIGN_PATH || f.startsWith(`${ROUNDS_DIR}/`) || f.startsWith(`${run}/design-`) || f.startsWith(`${HOLDOUT_OUT}/`)
const orphans = onDisk.filter((f) => mine(f) && !touched.has(f) && f !== OUTCOME_PATH)
if (!onDisk.length) warnings.push('the directory audit was not done: the listing did not come back')
const missingMust = Array.isArray(lastMust.missing) ? lastMust.missing : []
const outcome = [
  `Design accepted: ${accepted ? 'yes' : 'no'}; rounds: ${rounds} (this launch at most ${MAX_ROUNDS})`,
  `Type: ${type}; profile: ${PROFILE}`,
  `Binding requirements cited: ${lastMust.cited ?? '?'} of ${lastMust.binding ?? '?'}` + (missingMust.length ? `; not cited: ${missingMust.join(', ')}` : ''),
  ...perRound,
  ...holdoutOutcome,
  `Open items: ${open.length}; all remarks: ${REMARKS_PATH}`,
  `No data in the requirements, the client's to give: ${missingInput.length}${missingInput.length ? ` (${MISSING_INPUT_PATH})` : ''}`,
  `Audit of this stage: read by nobody ${orphans.length}` + (orphans.length ? ` (${orphans.join(', ')})` : ''),
  ...warnings.map((w) => `WARNING: ${w}`),
  ...handoff.map((h) => `Call: ${h}`),
]
await call(record(OUTCOME_PATH, `Design (${type}): ${run}`, outcome), {
  agentType: 'verbatim-writer',
  model: MODELS.record,
  label: 'outcome',
  phase: 'Report',
  schema: WROTE,
})

return {
  type,
  design: DESIGN_PATH,
  accepted,
  rounds,
  binding_not_cited: missingMust,
  open_items: open.length,
  unresolved: writeOpen ? UNRESOLVED_PATH : null,
  missing_input: missingInput.length ? MISSING_INPUT_PATH : null,
  remarks: ledger.length ? REMARKS_PATH : null,
  number_checks: numbersChecked ? NUMBER_CHECKS : null,
  holdout: { score: holdoutScore, answers: holdoutAnswers },
  outcome: OUTCOME_PATH,
  orphans,
  warnings,
}
