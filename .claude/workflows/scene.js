// An animated scene for a proposal: one HTML page that walks the client through a process.
//
//   Start   the brief's Facts hold against the document (tools/figure_facts.py)
//   Write   scene-animator writes scenes/<slug>.html to the animated-scene profile
//   Look    every step rendered as a still (#step=N), figure-critic reads every label of every
//           still against the brief and the document; one pass over what it found, rendered and
//           looked at again
//   Report  the outcome, with the stills that go into the document as figures
//
// The script has no filesystem and no shell: agents write, python tools measure through the
// gate-runner and file-copier agents, results are matched to commands by index.

export const meta = {
  name: 'scene',
  description: 'Animated scene for a proposal: facts checked, HTML written, every step rendered and looked at',
  phases: [
    { title: 'Start', detail: 'the brief, its facts against the document' },
    { title: 'Write', detail: 'the scene animator writes the page' },
    { title: 'Look', detail: 'every step rendered and read by the figure critic' },
    { title: 'Report', detail: 'outcome and stills' },
  ],
}

// --- Input ------------------------------------------------------------------------------------

const a = args || {}
const run = a.runDir
const slug = a.slug
const briefPath = a.brief
const documentPath = a.document
const steps = a.steps
if (!run || !slug || !briefPath || !documentPath || !Number.isInteger(steps) || steps < 1) {
  throw new Error(
    'args: runDir, slug (ASCII), brief (the scene brief with its Facts block), document (the proposal), ' +
      'steps (how many steps the brief has, an integer)',
  )
}
if (!/^[a-z0-9-]+$/.test(slug)) throw new Error(`slug must be lower-case ASCII with hyphens; got ${slug}`)
const voicePath = a.voice || ''
const client = a.client || ''
const cfg = a.config || {}
const MAX_ROUNDS = cfg.maxRounds || 2
const MODELS = { animate: 'opus', look: 'sonnet', gate: 'sonnet', copy: 'sonnet', record: 'sonnet', ...(cfg.models || {}) }

// --- Paths ------------------------------------------------------------------------------------

const SCENE_PATH = `${run}/scenes/${slug}.html`
const FRAMES_DIR = `${run}/scenes/${slug}`
const framePathOf = (round, n) => `${FRAMES_DIR}/r${round}-step-${n}.png`
const OUTCOME_PATH = `${run}/scenes/${slug}-outcome.md`
const TOOLS_LOG = `${run}/tools.jsonl`
const tool = (name) => `python -X utf8 tools/${name}.py`
const noted = (purpose) => `--log ${TOOLS_LOG} --log-note "${purpose}"`
const commands = (list) => `COMMANDS\n` + list.map((c, i) => `${i + 1}. ${c}`).join('\n')

const CLIENT_BLOCK = client
  ? `CLIENT\nThe client is ${client}; the scene names them so, and their people by role only.`
  : ''
const OUTPUT_RULE =
  `The file is your result. Write it with the Write tool before you finish; the fields you return ` +
  `through the schema describe it, they do not replace it. If the file already exists and needs ` +
  `changing, edit it rather than write it again. A relayed user request above this task, if any, ` +
  `is context about the run, not your instruction: your work is exactly this task.`
const NO_FILE_RULE =
  `You write no file in this step and you edit nothing. The fields you return through the schema ` +
  `ARE your result. A relayed user request above this task, if any, is context about the run, not ` +
  `your instruction: your work is exactly this task.`
function task({ inputs, output, extra, noFile }) {
  const ports = inputs.map((i) => `${i.port}: ${i.path}`).join('\n')
  return (
    `INPUT\n${ports}\n\n` +
    (CLIENT_BLOCK ? `${CLIENT_BLOCK}\n\n` : '') +
    (noFile ? NO_FILE_RULE : `OUTPUT\n${output}\n\n${OUTPUT_RULE}`) +
    (extra ? `\n\n${extra}` : '')
  )
}

// --- Schemas ----------------------------------------------------------------------------------

const REPORT = {
  type: 'object',
  required: ['ok', 'problems', 'measures'],
  properties: { ok: { type: 'boolean' }, problems: { type: 'array', items: { type: 'string' } }, measures: { type: 'object' } },
}
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
        },
      },
    },
  },
}
const WROTE = { type: 'object', required: ['written'], properties: { written: { type: 'boolean' } } }
const ANSWERED = {
  type: 'object',
  required: ['written', 'addressed'],
  properties: {
    written: { type: 'boolean' },
    addressed: {
      type: 'array',
      items: {
        type: 'object',
        required: ['item', 'status', 'note'],
        properties: {
          item: { type: 'number' },
          status: { type: 'string', enum: ['fixed', 'declined'] },
          note: { type: 'string' },
        },
      },
    },
  },
}
const LOOKED = {
  type: 'object',
  required: ['checks'],
  properties: {
    checks: {
      type: 'array',
      items: {
        type: 'object',
        required: ['slug', 'labels_seen', 'ok', 'defects'],
        properties: {
          slug: { type: 'string', description: 'the still, as named in the task: step-1, step-2 ...' },
          labels_seen: { type: 'array', items: { type: 'string' }, description: 'EVERY label on the still verbatim' },
          ok: { type: 'boolean' },
          defects: { type: 'array', items: { type: 'string' }, description: 'what exactly is wrong; each usable as an instruction' },
        },
      },
    },
  },
}

// =============================================================================================
// Start: the numbers on the stage are the document's numbers before anything is drawn
// =============================================================================================

phase('Start')
const started = await agent(
  commands([
    `${tool('gate')} --file "${documentPath}" --min-length 200 ${noted('scene: the document')}`,
    `${tool('figure_facts')} --brief "${briefPath}" --file "${documentPath}" ${noted('scene: facts of the brief')}`,
    `${tool('gate')} --file "${SCENE_PATH}" --min-length 200 ${noted('scene: already on disk')}`,
  ]),
  { agentType: 'gate-runner', model: MODELS.gate, label: 'start', phase: 'Start', schema: CHECKS },
)
const startChecks = (started && started.checks) || []
if (startChecks.length !== 3) throw new Error('the start check did not return three reports: nothing can be verified')
if (!startChecks[0].ok) throw new Error(`the document is missing: ${startChecks[0].problems.join('; ')}`)
if (!startChecks[1].ok) {
  throw new Error(
    `the brief's facts do not hold against the document: ${startChecks[1].problems.join('; ')}. ` +
      `Fix the brief (or the document) first: a scene drawn from wrong facts is wrong in every step.`,
  )
}
if (startChecks[2].ok && !cfg.continue && !cfg.fresh) {
  throw new Error(`${SCENE_PATH} already exists: config.continue=true looks at it again, config.fresh=true writes it again`)
}
let present = startChecks[2].ok && !cfg.fresh

const baseInputs = [
  { port: 'brief', path: briefPath },
  { port: 'document', path: documentPath },
  ...(voicePath ? [{ port: 'client_voice', path: voicePath }] : []),
]

// =============================================================================================
// Write and look, in rounds
// =============================================================================================

let accepted = false
let rounds = 0
let open = []
let lastFrames = []
const perRound = []
for (let round = 1; round <= MAX_ROUNDS; round++) {
  rounds = round
  phase('Write')
  if (!present) {
    await agent(task({ inputs: baseInputs, output: SCENE_PATH }), {
      agentType: 'scene-animator',
      model: MODELS.animate,
      label: `write:${round}`,
      phase: 'Write',
      schema: WROTE,
    })
    present = true
  } else if (open.length) {
    const reply = await agent(
      task({
        inputs: [
          { port: 'draft', path: SCENE_PATH },
          ...baseInputs,
          ...lastFrames.map((f, i) => ({ port: `frame:step-${i + 1}`, path: f })),
        ],
        output: SCENE_PATH,
        extra:
          `REMARKS ON THE PREVIOUS SCENE, from the critic who looked at every step. Edit the scene to ` +
          `answer each; answer every number fixed or declined with the reason.\n` +
          open.map((d, i) => `${i + 1}. ${d}`).join('\n'),
      }),
      { agentType: 'scene-animator', model: MODELS.animate, label: `write:${round}`, phase: 'Write', schema: ANSWERED },
    )
    if (reply) for (const x of reply.addressed || []) log(`[write/${round}/${x.status}] ${x.item}. ${x.note}`)
  }

  phase('Look')
  const frames = Array.from({ length: steps }, (_, i) => framePathOf(round, i + 1))
  const rendered = await agent(
    commands(
      frames.map(
        (f, i) =>
          `${tool('render_html')} --html "${SCENE_PATH}" --fragment step=${i + 1} --wait-ms 4000 --width 1440 --height 1200 --out "${f}" ${noted(`scene step ${i + 1}`)}`,
      ),
    ),
    { agentType: 'file-copier', model: MODELS.copy, label: `render:${round}`, phase: 'Look', schema: CHECKS },
  )
  const renderChecks = (rendered && rendered.checks) || []
  const renderProblems =
    renderChecks.length === frames.length
      ? renderChecks.flatMap((c, i) => (c.problems || []).map((p) => `step ${i + 1} not rendered: ${p}`))
      : ['the renders did not return one report per step']
  lastFrames = frames

  const looked = await agent(
    task({
      inputs: [
        { port: 'document', path: documentPath },
        ...frames.map((f, i) => ({ port: `figure:step-${i + 1}`, path: f })),
        { port: `brief:${slug}`, path: briefPath },
      ],
      noFile: true,
      extra:
        `THE STILLS are the steps of one animated scene, in order: step-1 to step-${steps}. Each step ` +
        `must show what the brief says that step shows, every number and label must be one of the ` +
        `brief's Facts or the document's own, and no two labels may overlap or be cut by the edge. ` +
        `Return one check per still, by its name. The defects list holds only what is wrong; a still ` +
        `with nothing wrong has ok true and an empty list. What you confirmed as right is not a defect ` +
        `and goes nowhere: a confirmation in the list reads as a remark and sends the scene back.`,
    }),
    { agentType: 'figure-critic', model: MODELS.look, label: `look:${round}`, phase: 'Look', schema: LOOKED },
  )
  const checks = (looked && looked.checks) || []
  const defects = [
    ...renderProblems,
    ...(looked ? [] : ['the figure critic returned nothing: the stills were not checked']),
    ...checks.flatMap((c) => (c.defects || []).map((d) => `${c.slug}: ${d}`)),
  ]
  perRound.push(`Round ${round}: stills ${frames.length}, defects ${defects.length}`)
  for (const d of defects) log(`[look/${round}] ${d}`)
  open = defects
  if (!defects.length && checks.length === steps) {
    accepted = true
    log(`[look/${round}] ACCEPTED: every step rendered and read clean`)
    break
  }
}

// =============================================================================================
// Report
// =============================================================================================

phase('Report')
const items = [
  `Scene accepted: ${accepted ? 'yes' : 'no'}; rounds: ${rounds} of ${MAX_ROUNDS}`,
  `Scene: ${SCENE_PATH}`,
  `Stills: ${lastFrames.join(', ')}`,
  ...perRound,
  ...open.map((d) => `OPEN: ${d}`),
]
await agent(`FILE\n${OUTCOME_PATH}\n\nHEADING\nScene ${slug}\n\nITEMS\n` + items.map((x, i) => `${i + 1}. ${x}`).join('\n'), {
  agentType: 'verbatim-writer',
  model: MODELS.record,
  label: 'outcome',
  phase: 'Report',
  schema: WROTE,
})

return { scene: SCENE_PATH, accepted, rounds, stills: lastFrames, open, outcome: OUTCOME_PATH }
