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
          status: { type: 'string', enum: ['fixed', 'declined'] },
          note: { type: 'string', description: 'what you did, or why you deliberately did not' },
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
  const kept = await call(
    task({
      inputs: [{ port: 'draft', path: DESIGN_PATH }, ...evidence],
      noFile: true,
      extra: `FLAGS\n` + lines.map((l, i) => `${i + 1}. ${l}`).join('\n') + `\n\n${CRITIC_EXTRA}`,
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
let accepted = false
let rounds = 0
let previousSignature = null
let numbersChecked = false
let best = Infinity
let sinceBest = 0
let lastMust = {}
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
      `\n\nHOW TO ANSWER. One entry per number from 1 to ${pending.length}: fixed or declined with the reason.` +
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
    pending.forEach((it, i) => {
      const a = answers.get(i + 1)
      if (it.entry) it.entry.answer = a ? `${a.status}: ${a.note}` : 'not answered'
      if (!a) carried.push(it.text)
      else if (a.status === 'declined') declinedNotes.push(`${it.text}\n    -> declined: ${a.note}`)
    })
    const unapplied = (report.problems || []).map((p) => `EDIT NOT APPLIED, quote the draft exactly: ${p}`)
    log(`[design/${round}] answered ${answers.size} of ${pending.length}; edits not applied ${unapplied.length}`)
    pending = [...carried, ...unapplied].map((text) => ({ kind: 'CARRIED', text }))
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

  // --- The critics, in parallel
  const extra = [
    CRITIC_EXTRA,
    declinedNotes.length
      ? `DECLINED LAST ROUND, with the reason. Raise one again only if the reason is wrong, and say why.\n` +
        declinedNotes.map((d, i) => `${i + 1}. ${d}`).join('\n')
      : '',
  ]
    .filter(Boolean)
    .join('\n\n')
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
      call(task({ inputs: [{ port: 'draft', path: DESIGN_PATH }], output: NUMBER_CHECKS }), {
        agentType: 'domain-checker',
        model: MODELS.numbers,
        label: `design:numbers:${round}`,
        phase: 'Design',
        schema: FOUND,
      }),
  ])
  const criticRemarks = criticSaid
    ? (criticSaid.remarks || []).map((r) => ({ severity: severityOf(r), text: `[DESIGN] ${plain(r)}` }))
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
const mine = (f) => f === DESIGN_PATH || f.startsWith(`${ROUNDS_DIR}/`) || f.startsWith(`${run}/design-`)
const orphans = onDisk.filter((f) => mine(f) && !touched.has(f) && f !== OUTCOME_PATH)
if (!onDisk.length) warnings.push('the directory audit was not done: the listing did not come back')
const missingMust = Array.isArray(lastMust.missing) ? lastMust.missing : []
const outcome = [
  `Design accepted: ${accepted ? 'yes' : 'no'}; rounds: ${rounds} (this launch at most ${MAX_ROUNDS})`,
  `Type: ${type}; profile: ${PROFILE}`,
  `Binding requirements cited: ${lastMust.cited ?? '?'} of ${lastMust.binding ?? '?'}` + (missingMust.length ? `; not cited: ${missingMust.join(', ')}` : ''),
  ...perRound,
  `Open items: ${open.length}; all remarks: ${REMARKS_PATH}`,
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
  remarks: ledger.length ? REMARKS_PATH : null,
  number_checks: numbersChecked ? NUMBER_CHECKS : null,
  outcome: OUTCOME_PATH,
  orphans,
  warnings,
}
