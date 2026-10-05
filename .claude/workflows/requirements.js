// Traceable requirements from the client's material.
//
// One question drives every step: did anything the client said get lost on the way?
//
//   Start         is another run working here; what is already on disk
//   Intake        what is in inputs/ and what will be read (duplicates, formats, images, our notes)
//   Extract       per document: extractor -> gate -> independent auditor -> one pass over what it
//                 found -> gate. The auditor's count before the pass is the measure of extraction.
//   Voice         the client voice sheet: what mattered to them, with weights, in their words
//   Requirements  writer -> fact-checker -> gate (shape, every extract row traced, quotes) ->
//                 critic, in rounds. Only a CRITICAL remark sends the document back.
//   Pains         once the requirements are accepted: the client's pains, numbered, each tied to
//                 the requirements that answer it or set aside as not answered yet. The
//                 proposal pipeline reads this as its spine.
//   Report        critic-remarks.md, UNRESOLVED.md, the directory audit, outcome.md
//
// The script has no filesystem and no shell: agents read and write, python tools measure through
// the gate-runner agent, results are matched to commands by index. Runtime rules: meta is a pure
// literal; no import(), no Date.now(), no Math.random().

export const meta = {
  name: 'requirements',
  description: 'Traceable requirements from input documents: extract and audit, client voice, requirements under a critic',
  phases: [
    { title: 'Start', detail: 'is anybody working here, what is already on disk' },
    { title: 'Intake', detail: 'what is in the input folder and what will be read' },
    { title: 'Extract', detail: 'extractor, gate, independent auditor, one pass over what it found' },
    { title: 'Voice', detail: 'the client in their own words: ranking, weights, vocabulary' },
    { title: 'Requirements', detail: 'writer, fact-checker, gate, critic, in rounds' },
    { title: 'Pains', detail: 'the client pains, each tied to the requirements that answer it' },
    { title: 'Report', detail: 'remarks, unresolved items, audit, report' },
  ],
}

// --- Input ------------------------------------------------------------------------------------

const run = typeof args === 'string' ? args : args && args.runDir
if (!run) {
  throw new Error(
    'a run directory is required: args.runDir. A new one: python -X utf8 tools/newrun.py --base <dir> --label <what>',
  )
}
// The script has no clock; without the time it cannot tell whether another run is working here.
const now = (args && args.now) || ''
// Free text about the run. Optional: the input documents are the order.
const order = (args && args.order) || ''
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
if (cfg.continue && cfg.fresh) throw new Error('config.continue and config.fresh exclude each other')

// --- Paths: named here and nowhere else -------------------------------------------------------

const INPUTS_DIR = `${run}/inputs`
const EXTRACTS_DIR = `${run}/extracts`
const VOICE_PATH = `${run}/client-voice.md`
const REQ_PATH = `${run}/requirements.md`
const ROUNDS_DIR = `${run}/rounds/req`
const REMARKS_PATH = `${run}/critic-remarks.md`
const UNRESOLVED_PATH = `${run}/UNRESOLVED.md`
// Not report.md: the harness refuses a subagent a file of that name, and on one live run the
// writer was refused and still answered that it had written it.
const REPORT_PATH = `${run}/outcome.md`
const PAINS_PATH = `${run}/pains.md`
// Its own record: a continued run that only writes the pain map must not overwrite the
// requirements rounds' record with an empty one.
const PAIN_REMARKS_PATH = `${run}/pains-remarks.md`
const TOOLS_LOG = `${run}/tools.jsonl`
const extractPathOf = (stem) => `${EXTRACTS_DIR}/${stem}.md`
const roundPathOf = (n) => `${ROUNDS_DIR}/round-${n}.md`
const draftPathOf = (n) => `${ROUNDS_DIR}/draft-${n}.md`
const editsPathOf = (n) => `${ROUNDS_DIR}/edits-${n}.json`

// --- Configuration ----------------------------------------------------------------------------

const MAX_ROUNDS = cfg.maxRounds || 3
const MIN_ARTIFACT_CHARS = 200
// A floor that says "a real document was written", not a target: the accepted requirements of one
// small live project were 16 KB.
const REQ_MIN_LENGTH = cfg.reqMinLength || 5000
const MODELS = {
  extract: 'sonnet',
  // A different model from the extractor's, so the second reading is not the first one repeated.
  audit: 'opus',
  voice: 'opus',
  write: 'opus',
  fix: 'sonnet',
  critic: 'opus',
  // The checkers that vote on a CRITICAL remark: several fresh readings, each cheap.
  vote: 'sonnet',
  pains: 'opus',
  // Carriers stay on sonnet: a haiku carrier once read the relayed user request as its own task
  // and returned an invented report the script trusted.
  gate: 'sonnet',
  record: 'sonnet',
  copy: 'sonnet',
  ...(cfg.models || {}),
}
const tool = (name) => `python -X utf8 tools/${name}.py`

// A document type's gate rules live in its profile (the ```gate block); the script names the
// profile and adds only what is its own, such as a length floor from the run's config.
const profileFlags = (type) => `--profile .claude/skills/${type}-profile/SKILL.md`
const EXTRACT_FLAGS = profileFlags('extract')
const REQ_FLAGS = `${profileFlags('requirements')} --min-length ${REQ_MIN_LENGTH}`
const PAIN_FLAGS = profileFlags('pain-map')
const VOICE_FLAGS = profileFlags('client-voice')

// --- Records of the run -----------------------------------------------------------------------

// Every path an agent was handed or the script declared as a record. The audit subtracts this
// from what is on disk: every loss this project has had was a file produced and never read.
const touched = new Set([TOOLS_LOG])
// Who was handed what; written into the report.
const handoff = []
let lastPorts = null
// What did not stop the run but changes how its result must be read.
const warnings = []
// What went into the report as it happened.
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

// agent() yields null when a subagent dies after its retries.
function must(value, what) {
  if (!value) throw new Error(`the agent returned nothing: ${what}`)
  return value
}

// A stem is the path inside inputs/ with folders joined by "__": two transcript.md files in two
// subfolders must not write one extract. Tool arguments are ASCII, so other characters are
// dropped and a short hash of the original name keeps two such names apart.
const hashOf = (text) => {
  let h = 5381
  for (const ch of String(text)) h = ((h * 33) ^ ch.codePointAt(0)) >>> 0
  return h.toString(36)
}
const stemOf = (path) => {
  const raw = String(path)
    .replace(/\\/g, '/')
    .replace(`${INPUTS_DIR}/`, '')
    .split('/')
    .join('__')
    .replace(/\.[^.]+$/, '')
    .replace(/ +/g, '-')
  const safe = raw.replace(/[^A-Za-z0-9._-]+/g, '').replace(/^-+|-+$/g, '')
  return safe === raw ? raw : `${safe || 'doc'}-${hashOf(raw)}`
}

const ORDER_BLOCK = order
  ? `ORDER\n${order}\n\nThe order sets the scope and audience of this run and is binding where it sets them. ` +
    `Facts still come only from the sources.`
  : ''

// --- Schemas: only what the script cannot know on its own --------------------------------------

const REPORT = {
  type: 'object',
  required: ['ok', 'problems', 'measures'],
  properties: { ok: { type: 'boolean' }, problems: { type: 'array', items: { type: 'string' } }, measures: { type: 'object' } },
}
const GATE = { type: 'object', required: ['report', 'stdout'], properties: { report: REPORT, stdout: { type: 'string' } } }
// One entry per command, in order.
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
const INTAKE = {
  type: 'object',
  required: ['files', 'count'],
  properties: {
    files: {
      type: 'array',
      items: {
        type: 'object',
        required: ['path', 'kind'],
        properties: {
          path: { type: 'string' },
          kind: { type: 'string', enum: ['client', 'ours', 'media', 'unknown'] },
          duplicate_of: { type: 'string', description: 'present only when the report has it' },
        },
      },
    },
    count: { type: 'integer', description: 'the files number from the report measures, verbatim' },
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
const CHANGES = {
  type: 'object',
  required: ['changes'],
  properties: { changes: { type: 'array', items: { type: 'string' }, description: 'what you corrected; empty is a fine answer' } },
}
const TABLES = ['Requirements', 'Decisions', 'Constraints', 'Roles', 'Facts', 'Open questions']
const GAPS = {
  type: 'object',
  required: ['missing', 'distorted'],
  properties: {
    missing: {
      type: 'array',
      description: 'what the document states and no extract row carries; empty when nothing is missing',
      items: {
        type: 'object',
        required: ['table', 'locator', 'quote', 'why'],
        properties: {
          table: { type: 'string', enum: TABLES },
          locator: { type: 'string', description: 'section, page, or time and speaker' },
          quote: { type: 'string', description: 'short, verbatim from the document' },
          why: { type: 'string', description: 'one line: why a requirements writer needs it' },
        },
      },
    },
    distorted: {
      type: 'array',
      description: 'extract rows whose meaning, figure or weight differs from the document; empty when none',
      items: {
        type: 'object',
        required: ['row', 'document_says', 'why'],
        properties: {
          row: { type: 'string', description: 'the extract row id, e.g. R-04' },
          document_says: { type: 'string', description: 'locator and verbatim quote' },
          why: { type: 'string' },
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
// The lens critic's verdict: remarks as strings that open with [HIGH], [MEDIUM] or [LOW].
const LENS_VERDICT = {
  type: 'object',
  required: ['verdict', 'remarks'],
  properties: {
    verdict: { type: 'string', enum: ['approved', 'revise'], description: 'exactly approved or exactly revise' },
    remarks: { type: 'array', items: { type: 'string', description: '[HIGH|MEDIUM|LOW] place — what is wrong — what would fix it' } },
  },
}
const VERDICT = {
  type: 'object',
  required: ['verdict', 'remarks'],
  properties: {
    verdict: { type: 'string', enum: ['approved', 'revise'], description: 'exactly approved or exactly revise' },
    remarks: {
      type: 'array',
      items: {
        type: 'object',
        required: ['severity', 'text'],
        properties: {
          severity: { type: 'string', enum: ['MINOR', 'MAJOR', 'CRITICAL'], description: 'by the profile checklist' },
          text: { type: 'string', description: 'row id, what it says, what the source says, what to do' },
        },
      },
    },
  },
}

// =============================================================================================
// Start: is anybody working here, and what is already on disk
// =============================================================================================

phase('Start')
let reqPresent = false
let voicePresent = false
{
  const list = [
    ...(now
      ? [`${tool('busy')} --file ${TOOLS_LOG} --now ${now} --idle-seconds ${cfg.idleSeconds || 600} ${noted('is another run working here')}`]
      : []),
    `${tool('gate')} --file "${REQ_PATH}" --min-length ${MIN_ARTIFACT_CHARS} ${noted('start: requirements already on disk')}`,
    `${tool('gate')} --file "${VOICE_PATH}" --min-length ${MIN_ARTIFACT_CHARS} ${noted('start: client voice already on disk')}`,
  ]
  const started = await call(commands(list), { agentType: 'gate-runner', model: MODELS.gate, label: 'start', phase: 'Start', schema: CHECKS })
  const checks = (started && started.checks) || []
  if (checks.length !== list.length) {
    warnings.push('the start check did not return one report per command: occupancy and earlier results unknown')
    log(`[start] ${checks.length} reports for ${list.length} commands — nothing on disk is reused`)
  } else {
    const busy = now ? checks[0] : null
    const [req, voice] = now ? checks.slice(1) : checks
    if (busy && busy.busy && !cfg.ignoreBusy) {
      throw new Error(
        `another run seems to be working in ${run}: ${(busy.problems || []).join('; ')}. A new run gets a new ` +
          `directory (tools/newrun.py); if that run is certainly dead, config.ignoreBusy=true.`,
      )
    }
    reqPresent = req.ok
    voicePresent = voice.ok
  }
  if (!now) warnings.push('args.now was not passed: whether another run works in this directory was not checked')
  if (reqPresent && !cfg.continue && !cfg.fresh) {
    throw new Error(
      `${REQ_PATH} already exists. A new run gets a new directory (tools/newrun.py); to continue an ` +
        `interrupted run, config.continue=true; to rebuild here, config.fresh=true.`,
    )
  }
  if (cfg.fresh) {
    reqPresent = false
    voicePresent = false
  }
  log(`[start] requirements on disk=${reqPresent} client voice on disk=${voicePresent} continue=${!!cfg.continue}`)
}

// =============================================================================================
// Intake: one inventory of the whole tree is the list of what gets read
// =============================================================================================

phase('Intake')
const sources = []
const ourNotes = []
const imagesOf = new Map()
// Every input file that is not read, with the reason; the report lists them.
const skipped = []
{
  const inventory = await call(
    commands([`${tool('intake')} --dir ${INPUTS_DIR} ${noted('inventory of the whole input tree')}`]),
    { agentType: 'gate-runner', model: MODELS.gate, label: 'intake', phase: 'Intake', schema: INTAKE },
  )
  const files = (inventory && inventory.files) || []
  if (inventory && typeof inventory.count === 'number' && inventory.count !== files.length) {
    throw new Error(
      `the inventory counted ${inventory.count} files in ${INPUTS_DIR}, but ${files.length} arrived through the ` +
        `agent. A lost document is a requirement nobody can notice is missing; the run stops here.`,
    )
  }
  if (!files.length) throw new Error(`${INPUTS_DIR} holds no input documents: put the client's material there.`)

  const IMAGE = /\.(png|jpe?g|gif|webp)$/i
  const AUDIO_VIDEO = /\.(mp4|mov|mkv|avi|webm|mp3|wav|m4a|ogg)$/i
  const OFFICE = /\.(docx|pptx|xlsx|odt|rtf|epub)$/i
  const dirOf = (rel) => (rel.includes('/') ? rel.slice(0, rel.lastIndexOf('/')) : '')
  const skip = (rel, why) => {
    skipped.push(`${rel}: ${why}`)
    touched.add(`${INPUTS_DIR}/${rel}`)
    log(`[intake/skip] ${rel}: ${why}`)
  }
  const listed = new Set(files.map((f) => f.path))
  const kindOf = new Map(files.map((f) => [f.path, f.kind]))

  // A byte-identical copy names another file of the inventory; it is read once.
  const unique = files.filter((f) => {
    if (!f.duplicate_of || f.duplicate_of === f.path || !listed.has(f.duplicate_of)) return true
    skip(f.path, `duplicate of ${f.duplicate_of}`)
    return false
  })
  for (const f of unique.filter((f) => AUDIO_VIDEO.test(f.path))) {
    skip(f.path, 'audio or video; a transcript next to it would be read')
    warnings.push(`not read: ${f.path} is audio or video`)
  }
  let docs = unique
    .map((f) => f.path)
    .filter((rel) => !IMAGE.test(rel) && !AUDIO_VIDEO.test(rel))
    .filter((rel) => {
      if (!(OFFICE.test(rel) && listed.has(`${rel}.md`))) return true
      touched.add(`${INPUTS_DIR}/${rel}`)
      return false
    })

  // Office documents become markdown first: the extractor reads with Read, and Read refuses a
  // .docx. The tool writes <name>.docx.md next to each, so the script knows the names.
  const office = docs.filter((rel) => OFFICE.test(rel))
  if (office.length) {
    const converted = await call(
      commands([`${tool('to_text')} --dir ${INPUTS_DIR} --recursive ${noted('office documents to markdown')}`]),
      { agentType: 'file-copier', model: MODELS.copy, label: 'intake:to-text', phase: 'Intake', schema: GATE },
    )
    const report = (converted && converted.report) || { ok: false, problems: ['the conversion did not report'] }
    const problems = report.problems || []
    const perFile = problems.every((pr) => office.some((o) => pr.startsWith(`${o}:`)))
    const allFailed = !converted || (!report.ok && !perFile)
    docs = docs.map((rel) => {
      if (!office.includes(rel)) return rel
      touched.add(`${INPUTS_DIR}/${rel}`)
      if (allFailed || problems.some((pr) => pr.startsWith(`${rel}:`))) {
        warnings.push(`not converted to text, the extractor gets the original: ${rel}`)
        return rel
      }
      kindOf.set(`${rel}.md`, kindOf.get(rel))
      return `${rel}.md`
    })
  }

  // One document saved in several formats side by side is read once, in the best format.
  const FORMAT_RANK = ['.md', '.txt', '.docx.md', '.pptx.md', '.xlsx.md', '.odt.md', '.rtf.md', '.pdf', '.html', '.htm']
  const formatOf = (rel) => FORMAT_RANK.find((ext) => rel.toLowerCase().endsWith(ext)) || rel.slice(rel.lastIndexOf('.'))
  const baseOf = (rel) => rel.slice(0, rel.length - formatOf(rel).length)
  const rankOf = (rel) => {
    const r = FORMAT_RANK.indexOf(formatOf(rel))
    return r < 0 ? FORMAT_RANK.length : r
  }
  const chosen = new Map()
  for (const rel of docs) {
    const held = chosen.get(baseOf(rel))
    if (!held || rankOf(rel) < rankOf(held)) chosen.set(baseOf(rel), rel)
  }
  for (const rel of docs) if (chosen.get(baseOf(rel)) !== rel) skip(rel, `another format of ${chosen.get(baseOf(rel))}`)
  docs = docs.filter((rel) => chosen.get(baseOf(rel)) === rel)

  // Images travel with the document in their folder or the folder above (a call folder with its
  // transcript and frames/), the client's document first. Only inside a subfolder: the top level
  // holds unrelated documents. An image with no document near it is read on its own.
  const images = unique.map((f) => f.path).filter((rel) => IMAGE.test(rel))
  const near = (folder) => {
    const here = docs.filter((rel) => dirOf(rel) === folder)
    return here.find((rel) => kindOf.get(rel) === 'client') || here[0]
  }
  const attached = new Map()
  for (const dir of [...new Set(images.map(dirOf))]) {
    const companion = !dir ? undefined : near(dir) || (dirOf(dir) ? near(dirOf(dir)) : undefined)
    const inDir = images.filter((r) => dirOf(r) === dir)
    if (companion) {
      attached.set(companion, [...(attached.get(companion) || []), `${INPUTS_DIR}/${dir}`])
      for (const rel of inDir) touched.add(`${INPUTS_DIR}/${rel}`)
      log(`[intake/images] ${dir} goes with ${companion}`)
    } else {
      docs.push(...inDir)
    }
  }
  if (!docs.length) throw new Error(`${INPUTS_DIR} holds no readable document: only duplicates, audio or video.`)

  for (const rel of docs) {
    const path = `${INPUTS_DIR}/${rel}`
    sources.push(path)
    imagesOf.set(path, attached.get(rel) || [])
    if (kindOf.get(rel) === 'ours') ourNotes.push(path)
    log(`[intake/read] ${rel}${kindOf.get(rel) === 'ours' ? ' (our note)' : ''}`)
  }
  facts.push(`Input files: ${files.length}; read: ${sources.length}; not read: ${skipped.length}`)
  for (const s of skipped) facts.push(`Not read: ${s}`)
  for (const n of ourNotes) facts.push(`Our note, not the client's words: ${n}`)
}

// =============================================================================================
// Extract: extractor, gate, independent auditor, one pass over what it found, gate
// =============================================================================================

phase('Extract')
const TEXT = /\.(md|txt)$/i
const ASCII = /^[\x20-\x7e]*$/
const OUR_NOTE =
  `OUR NOTE\nThis document is our own note, not the client's words. Set trust_level to low and say so ` +
  `in the header; a row that only this note supports is our reading.`

// The gate of one extract: its shape, and its quotes against its own document where that document
// is text. Returns what the script needs and nothing else.
async function checkExtract(source, label, purpose) {
  const out = extractPathOf(stemOf(source))
  // The language and quote checks need the source on the command line, which must be ASCII.
  const text = TEXT.test(source) && ASCII.test(source)
  const list = [
    `${tool('gate')} --file "${out}" --min-length ${MIN_ARTIFACT_CHARS} ${EXTRACT_FLAGS}` +
      (text ? ` --language-of "${source}"` : '') +
      ` ${noted(purpose)}`,
    ...(text ? [`${tool('check_quotes')} --file "${out}" --source "${source}" ${noted(`${purpose}: quotes`)}`] : []),
  ]
  const res = await call(commands(list), { agentType: 'gate-runner', model: MODELS.gate, label, phase: 'Extract', schema: CHECKS })
  const checks = (res && res.checks) || []
  if (checks.length !== list.length) {
    return { exists: false, ok: false, rows: null, problems: ['the extract check did not return one report per command'] }
  }
  const m = checks[0].measures || {}
  const problems = checks.flatMap((c) => c.problems || [])
  return {
    exists: typeof m.chars === 'number' && m.chars >= MIN_ARTIFACT_CHARS,
    ok: !problems.length,
    rows: typeof m.sourced_rows === 'number' ? m.sourced_rows : null,
    problems,
  }
}

async function extractOne(source) {
  const stem = stemOf(source)
  const out = extractPathOf(stem)
  const inputs = [{ port: 'source', path: source }, ...imagesOf.get(source).map((d) => ({ port: 'images', path: d }))]
  const sourceBlock = `SOURCE ID\n${stem}` + (ourNotes.includes(source) ? `\n\n${OUR_NOTE}` : '')
  await call(task({ inputs, output: out, extra: sourceBlock }), {
    agentType: 'source-processor',
    model: MODELS.extract,
    label: `extract:${stem}`,
    phase: 'Extract',
    schema: WROTE,
  })
  const first = await checkExtract(source, `extract:gate:${stem}`, 'extract written')
  if (!first.exists) return { source, stem, first, final: first, audited: false, missing: 0, distorted: 0 }

  // A second reader in a fresh context. Its count before the pass is the measure of extraction.
  const gaps = await call(task({ inputs: [...inputs, { port: 'extract', path: out }], noFile: true }), {
    agentType: 'extract-auditor',
    model: MODELS.audit,
    label: `extract:audit:${stem}`,
    phase: 'Extract',
    schema: GAPS,
  })
  if (!gaps) warnings.push(`the auditor did not answer for ${source}: its extract was not checked for omissions`)
  const missing = (gaps && gaps.missing) || []
  const distorted = (gaps && gaps.distorted) || []
  const items = [
    ...missing.map((g) => `MISSING [${g.table}] ${g.locator} — “${g.quote}” — ${g.why}`),
    ...distorted.map((g) => `DISTORTED ${g.row}: the document says ${g.document_says} — ${g.why}`),
    ...first.problems.map((p) => `GATE ${p}`),
  ]
  for (const it of items) log(`[extract/${stem}/found] ${it}`)
  let final = first
  if (items.length) {
    await call(
      task({ inputs, output: out, extra: `${sourceBlock}\n\nMISSING ITEMS\n` + items.map((t, i) => `${i + 1}. ${t}`).join('\n') }),
      { agentType: 'source-processor', model: MODELS.extract, label: `extract:fix:${stem}`, phase: 'Extract', schema: WROTE },
    )
    final = await checkExtract(source, `extract:regate:${stem}`, 'extract after the second pass')
  }
  return { source, stem, first, final, audited: !!gaps, missing: missing.length, distorted: distorted.length }
}

let extractPorts = []
{
  // Continuing: an extract already on disk that passes its gate is kept, and not audited again.
  let todo = sources
  if (cfg.continue) {
    const list = sources.map(
      (s) => `${tool('gate')} --file "${extractPathOf(stemOf(s))}" --min-length ${MIN_ARTIFACT_CHARS} ${EXTRACT_FLAGS} ${noted('continue: extract on disk')}`,
    )
    const found = await call(commands(list), { agentType: 'gate-runner', model: MODELS.gate, label: 'extract:continue', phase: 'Extract', schema: CHECKS })
    const checks = (found && found.checks) || []
    if (checks.length === sources.length) {
      todo = sources.filter((s, i) => !checks[i].ok)
      // A kept extract is its source, read by an earlier launch: both are accounted for.
      for (const [i, s] of sources.entries()) {
        if (!checks[i].ok) continue
        touched.add(extractPathOf(stemOf(s)))
        touched.add(s)
        for (const d of imagesOf.get(s) || []) touched.add(d)
      }
      log(`[extract] kept from the earlier run: ${sources.length - todo.length} of ${sources.length}`)
    }
  }
  const done = await pipeline(todo, (source) => extractOne(source))
  const redone = new Set(todo)
  for (const s of sources) {
    const d = done.find((x) => x && x.source === s)
    if (!redone.has(s)) {
      extractPorts.push({ port: `extract:${stemOf(s)}`, path: extractPathOf(stemOf(s)) })
      facts.push(`Extract ${stemOf(s)}: kept from the earlier run, not audited again`)
      continue
    }
    if (!d || !d.final.exists) {
      warnings.push(`no extract for ${s}: its content did not reach the requirements`)
      facts.push(`Extract ${stemOf(s)}: NOT WRITTEN`)
      continue
    }
    extractPorts.push({ port: `extract:${d.stem}`, path: extractPathOf(d.stem) })
    facts.push(
      `Extract ${d.stem}: rows ${d.first.rows ?? '?'} -> ${d.final.rows ?? '?'}; ` +
        (d.audited ? `auditor found missing ${d.missing}, distorted ${d.distorted}` : 'NOT AUDITED') +
        `; gate ${d.final.ok ? 'clean' : 'open: ' + d.final.problems.join('; ')}`,
    )
    if (!d.final.ok) warnings.push(`extract ${d.stem} still fails its gate: ${d.final.problems.join('; ')}`)
  }
  log(`[extract] extracts on disk: ${extractPorts.length} of ${sources.length}`)
  if (!extractPorts.length) {
    throw new Error(
      `not one extract from ${sources.length} documents: the writer has nothing to read. If the agents were ` +
        `built in this same turn, the registry sees them only from the next human message.`,
    )
  }
}

// =============================================================================================
// Voice: the client in their own words, before the requirements take their weights from it
// =============================================================================================

phase('Voice')
let voicePort = []
{
  const voiceChecks = [
    `${tool('gate')} --file "${VOICE_PATH}" --min-length ${MIN_ARTIFACT_CHARS} ${VOICE_FLAGS} ${noted('client voice gate')}`,
    `${tool('check_quotes')} --file "${VOICE_PATH}" --source ${INPUTS_DIR} --source ${EXTRACTS_DIR} ${noted('client voice quotes')}`,
  ]
  // config.redoVoice writes the sheet again on a continued run, when its profile changed since.
  if (voicePresent && cfg.continue && !cfg.redoVoice) {
    log('[voice] the sheet is already on disk, kept')
  } else {
    await call(
      task({
        inputs: [...sources.map((s) => ({ port: `source:${stemOf(s)}`, path: s })), ...extractPorts],
        output: VOICE_PATH,
        brief: ORDER_BLOCK,
        extra: ourNotes.length ? `OUR NOTES, NOT THE CLIENT'S WORDS\n${ourNotes.map((n) => `- ${n}`).join('\n')}` : '',
      }),
      { agentType: 'client-voice', model: MODELS.voice, label: 'voice', phase: 'Voice', schema: WROTE },
    )
  }
  const res = await call(commands(voiceChecks), { agentType: 'gate-runner', model: MODELS.gate, label: 'voice:gate', phase: 'Voice', schema: CHECKS })
  const checks = (res && res.checks) || []
  const m = (checks[0] && checks[0].measures) || {}
  if (checks.length === voiceChecks.length && typeof m.chars === 'number' && m.chars >= MIN_ARTIFACT_CHARS) {
    voicePort = [{ port: 'client_voice', path: VOICE_PATH }]
    touched.add(VOICE_PATH)
    const problems = checks.flatMap((c) => c.problems || [])
    for (const p of problems) warnings.push(`client voice: ${p}`)
    facts.push(`Client voice: written; gate ${problems.length ? 'open: ' + problems.join('; ') : 'clean'}`)
  } else {
    warnings.push('the client voice sheet is missing: requirement weights come from the extracts only')
    facts.push('Client voice: NOT WRITTEN')
  }
}

// =============================================================================================
// Requirements: writer, fact-checker, gate, critic — until no CRITICAL remark is left
// =============================================================================================

phase('Requirements')
const notesBlock = ourNotes.length
  ? `OUR NOTES, NOT THE CLIENT'S WORDS\nThese extracts come from our own notes: ` +
    ourNotes.map((n) => `extract:${stemOf(n)}`).join(', ') +
    `. A row that rests on them alone is our interpretation: an assumption in 8.3, never a client statement.`
  : ''
const VOICE_NOTE =
  `CLIENT VOICE\nThe port client_voice is the client's own words, ranked by what mattered to them. Take each ` +
  `requirement's weight and frequency from its section 2 and the client's terms from its section 3.`
const writerBrief = [ORDER_BLOCK, voicePort.length ? VOICE_NOTE : '', notesBlock].filter(Boolean).join('\n\n')
const factBrief = [ORDER_BLOCK, notesBlock].filter(Boolean).join('\n\n')
const reqChecks = (round) => [
  `${tool('gate')} --file "${REQ_PATH}" ${REQ_FLAGS} ${noted(`requirements round ${round}`)}`,
  `${tool('extract_trace')} --file "${REQ_PATH}" --extracts ${EXTRACTS_DIR} ${noted(`trace round ${round}`)}`,
  `${tool('check_quotes')} --file "${REQ_PATH}" --source ${INPUTS_DIR} --source ${EXTRACTS_DIR} ${noted(`quotes round ${round}`)}`,
]

// Every remark of every round, with the writer's answer: critic-remarks.md at the end.
const ledger = []
// What goes to the writer next round: { kind, text, entry }.
let pending = []
let declinedNotes = []
let startRound = 1
let rounds = 0
let accepted = false
let previousSignature = null
let lastTrace = {}
let lastQuotes = {}
const perRound = []

// Continuing: the rounds already judged are read back, so the limit counts per document.
if (cfg.continue && reqPresent) {
  const recorded = await call(
    commands([`${tool('rounds')} --dir ${ROUNDS_DIR} --last-only ${noted('continue: rounds already judged')}`]),
    { agentType: 'gate-runner', model: MODELS.gate, label: 'req:continue', phase: 'Requirements', schema: ROUNDS },
  )
  // --last-only lists the newest round alone and counts every round in the measures, so the
  // list is matched to the report by that round's number. Comparing the list's length with the
  // count rejected every history of two rounds or more, and a continued run judged its accepted
  // document again from round 1.
  const shaped =
    recorded && recorded.report && recorded.report.measures && Array.isArray(recorded.rounds) &&
    recorded.rounds.length === 1 && recorded.rounds[0].round === recorded.report.measures.last_round
  if (shaped && recorded.rounds.length) {
    const last = recorded.rounds[recorded.rounds.length - 1]
    startRound = last.round + 1
    for (let n = 1; n < startRound; n++) [roundPathOf(n), draftPathOf(n), editsPathOf(n)].forEach((p) => touched.add(p))
    touched.add(REMARKS_PATH)
    const sent = (last.remarks || []).filter((r) => !r.startsWith('[MINOR]'))
    pending = [...(last.gate || []).map((text) => ({ kind: 'GATE', text })), ...sent.map((text) => ({ kind: 'CARRIED', text }))]
    if (last.verdict === 'approved') {
      accepted = true
      rounds = last.round
      log(`[req/continue] round ${last.round} accepted the requirements: no more rounds`)
    }
    warnings.push(`continued after round ${last.round}: the remarks of earlier rounds are in ${ROUNDS_DIR}, not in critic-remarks.md`)
    log(`[req/continue] rounds judged ${recorded.report.measures.rounds}, continuing from ${startRound} with ${pending.length} items`)
  } else {
    log('[req/continue] no usable round records: the draft on disk is judged as round 1')
  }
}

// A CRITICAL remark sends the document back, so before it does, independent checkers vote on it.
// One critic is one reading, and on live runs a single reader's blocking remark was as often a
// misreading as a defect. Each checker gets the draft, the evidence and the CRITICAL remarks as
// claims; a remark that a majority refutes is downgraded to MAJOR with the reason, one that the
// checkers could not judge stays CRITICAL: an unverified remark is not a refuted one.
const VOTERS = cfg.voters ?? 3
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
async function voteOnCritical(round, remarks) {
  const critical = remarks.filter((r) => r.severity === 'CRITICAL')
  if (!critical.length || VOTERS < 2) return 0
  const evidence = [
    ...extractPorts.map((e) => ({ port: e.port.replace(/^extract:/, 'evidence:'), path: e.path })),
    ...voicePort.map((v) => ({ port: 'evidence:client-voice', path: v.path })),
  ]
  const claims =
    `CLAIMS TO CHECK\nEach claim is a reviewer's remark about the draft. It holds when the draft really ` +
    `has the defect the remark names and the evidence confirms what the remark says the source says.\n` +
    critical.map((r, i) => `V${i + 1}: "${r.text}"`).join('\n')
  const ballots = await parallel(
    Array.from({ length: VOTERS }, (_, k) => () =>
      call(task({ inputs: [{ port: 'draft', path: REQ_PATH }, ...evidence], noFile: true, extra: claims }), {
        agentType: 'claim-checker',
        model: MODELS.vote,
        label: `req:vote:${round}:${k + 1}`,
        phase: 'Requirements',
        schema: CHECKED,
      }),
    ),
  )
  const majority = Math.floor(VOTERS / 2) + 1
  let refutedCount = 0
  critical.forEach((r, i) => {
    const said = ballots.map((b) => b && (b.results || []).find((x) => x.id === `V${i + 1}`)).filter(Boolean)
    const against = said.filter((x) => !x.holds)
    log(`[req/${round}/vote] V${i + 1}: holds ${said.length - against.length}, refuted ${against.length}, not judged ${VOTERS - said.length}`)
    if (against.length >= majority) {
      r.severity = 'MAJOR'
      r.text = `${r.text} [not confirmed by ${against.length} of ${VOTERS} checkers: ${against[0].problem || 'no reason given'}]`
      refutedCount += 1
    }
  })
  return refutedCount
}

// An accepted document found on disk is measured once, so the outcome carries its trace; a
// person may have edited it since, and the gate is how that edit is checked.
if (accepted) {
  touched.add(REQ_PATH)
  const list = reqChecks('recheck')
  const res = await call(commands(list), { agentType: 'gate-runner', model: MODELS.gate, label: 'req:recheck', phase: 'Requirements', schema: CHECKS })
  const checks = (res && res.checks) || []
  lastTrace = (checks[1] && checks[1].measures) || {}
  lastQuotes = (checks[2] && checks[2].measures) || {}
  const problems = checks.length === list.length ? checks.flatMap((c) => c.problems || []) : ['the recheck did not return one report per command']
  for (const pr of problems) warnings.push(`accepted requirements on disk: ${pr}`)
}

for (let round = startRound; round <= MAX_ROUNDS && !accepted; round++) {
  rounds = round
  phase('Requirements')

  // --- The writer: a first draft, or one edits file answering the numbered items
  if (!reqPresent) {
    must(
      await call(task({ inputs: [...extractPorts, ...voicePort], output: REQ_PATH, brief: writerBrief }), {
        agentType: 'requirements-writer',
        model: MODELS.write,
        label: `req:write:${round}`,
        phase: 'Requirements',
        schema: DRAFT,
      }),
      `req:write:${round}`,
    )
    reqPresent = true
  } else if (pending.length) {
    const editsPath = editsPathOf(round)
    const remarks =
      `REMARKS ON THE PREVIOUS DRAFT. GATE items are measurements and are not open to argument; everything ` +
      `else you may decline with a reason.\n\n` +
      pending.map((it, i) => `${i + 1}. [${it.kind}] ${it.text}`).join('\n') +
      `\n\nHOW TO ANSWER. One entry per number from 1 to ${pending.length}: fixed when the draft now satisfies ` +
      `it, declined with the reason in one sentence when you deliberately did not act.` +
      `\n\nHOW TO DELIVER THIS ROUND. Do not edit ${REQ_PATH} yourself. Write your changes as a JSON array to ` +
      `${editsPath}: [{"old": "<text copied verbatim from the draft, occurring exactly once>", "new": "<the ` +
      `replacement>"}]. To add a row, old is the row before it and new is that row plus the new one; to delete, ` +
      `new is empty. A tool applies the list and reports every pair whose old text was not found once.`
    const drafted = must(
      await call(
        task({ inputs: [{ port: 'draft', path: REQ_PATH }, ...extractPorts, ...voicePort], output: editsPath, extra: remarks, brief: writerBrief }),
        { agentType: 'requirements-writer', model: MODELS.write, label: `req:write:${round}`, phase: 'Requirements', schema: DRAFT },
      ),
      `req:write:${round}`,
    )
    const applied = await call(
      commands([`${tool('apply_edits')} --file ${REQ_PATH} --edits ${editsPath} ${noted(`apply round ${round} edits`)}`]),
      { agentType: 'file-copier', model: MODELS.copy, label: `req:apply:${round}`, phase: 'Requirements', schema: GATE },
    )
    const report = (applied && applied.report) || { ok: false, problems: ['the edits were not applied: no report'], measures: {} }
    // The ledger, checked against the numbers the script handed over.
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
    log(`[req/${round}] answered ${answers.size} of ${pending.length}; edits not applied ${unapplied.length}`)
    pending = [...carried, ...unapplied].map((text) => ({ kind: 'CARRIED', text }))
  } else {
    log(`[req/${round}] the draft on disk has not been judged: straight to the checks`)
    pending = []
  }

  // --- The fact-checker settles what is decidable before anyone judges
  const fixed = await call(
    task({ inputs: [{ port: 'draft', path: REQ_PATH }, ...extractPorts], output: REQ_PATH, brief: factBrief }),
    { agentType: 'requirements-fact-checker', model: MODELS.fix, label: `req:factcheck:${round}`, phase: 'Requirements', schema: CHANGES },
  )
  if (!fixed) warnings.push(`the fact-checker did not run in round ${round}`)
  for (const c of (fixed && fixed.changes) || []) log(`[req/${round}/factcheck] ${c}`)

  // --- The gate: the profile's shape, every extract row traced, every quote verbatim
  const list = reqChecks(round)
  const gated = await call(commands(list), { agentType: 'gate-runner', model: MODELS.gate, label: `req:gate:${round}`, phase: 'Requirements', schema: CHECKS })
  const checks = (gated && gated.checks) || []
  const gateProblems =
    checks.length === list.length
      ? checks.flatMap((c) => c.problems || [])
      : ['the gate did not return one report per command: the draft was not measured']
  const sized = (checks[0] && checks[0].measures) || {}
  const exists = typeof sized.chars === 'number' && sized.chars >= MIN_ARTIFACT_CHARS
  lastTrace = (checks[1] && checks[1].measures) || {}
  lastQuotes = (checks[2] && checks[2].measures) || {}
  log(`[req/${round}/gate] problems ${gateProblems.length}${gateProblems.length ? ': ' + gateProblems.join('; ') : ''}`)

  // --- The critic judges what only judgement decides
  const criticSaid = await call(
    task({
      inputs: [{ port: 'draft', path: REQ_PATH }, ...extractPorts, ...voicePort],
      noFile: true,
      brief: writerBrief,
      extra: declinedNotes.length
        ? `DECLINED LAST ROUND, with the reason. Raise one again only if the reason is wrong, and say why.\n` +
          declinedNotes.map((d, i) => `${i + 1}. ${d}`).join('\n')
        : undefined,
    }),
    { agentType: 'requirements-critic', model: MODELS.critic, label: `req:critic:${round}`, phase: 'Requirements', schema: VERDICT },
  )
  // A dead critic is an open item, not agreement; it is not put to the vote.
  const verdict = criticSaid || {
    verdict: 'revise',
    remarks: [{ severity: 'CRITICAL', text: 'the critic returned no verdict: that is an open item, not agreement' }],
  }
  const remarks = (verdict.remarks || []).map((r) => ({ severity: r.severity, text: String(r.text).replace(/^\s*\d{1,2}[.)]\s+/, '') }))
  const refuted = criticSaid ? await voteOnCritical(round, remarks) : 0
  const count = (s) => remarks.filter((r) => r.severity === s).length
  perRound.push(
    `Round ${round}: CRITICAL ${count('CRITICAL')}, MAJOR ${count('MAJOR')}, MINOR ${count('MINOR')}, ` +
      `CRITICAL refuted by the vote ${refuted}, gate problems ${gateProblems.length}`,
  )
  log(`[req/${round}/critic] ${perRound[perRound.length - 1]}`)
  for (const r of remarks) log(`[req/${round}/critic] [${r.severity}] ${r.text}`)
  if ((verdict.verdict === 'approved') !== (count('CRITICAL') === 0)) {
    log(`[req/${round}/critic] the verdict "${verdict.verdict}" disagrees with the severities; the severities decide`)
  }

  // --- On the record before anything decides what to do with it
  // What the next round gets: measurements, CRITICAL and MAJOR remarks; MINOR is only recorded.
  const sendBack = []
  for (const p of gateProblems) {
    const entry = { round, kind: 'GATE', text: p, answer: null }
    ledger.push(entry)
    sendBack.push({ kind: 'GATE', text: p, entry })
  }
  for (const r of remarks) {
    const minor = r.severity === 'MINOR'
    const entry = { round, kind: r.severity, text: r.text, answer: minor ? 'recorded, not sent back' : null }
    ledger.push(entry)
    if (!minor) sendBack.push({ kind: r.severity, text: r.text, entry })
  }
  const blocking = [...gateProblems, ...remarks.filter((r) => r.severity === 'CRITICAL').map((r) => r.text)]
  const passed = exists && blocking.length === 0
  const recordItems = [
    ...remarks.map((r) => `[${r.severity}] ${r.text}`),
    ...gateProblems.map((p) => `Gate: ${p}`),
    ...pending.map((it) => `Carried: ${it.text}`),
  ]
  const wrote = await call(
    record(roundPathOf(round), `Round ${round} — verdict=${passed ? 'approved' : 'revise'} style=approved`, recordItems),
    { agentType: 'verbatim-writer', model: MODELS.record, label: `req:record:${round}`, phase: 'Requirements', schema: WROTE },
  )
  if (!(wrote && wrote.written)) warnings.push(`round ${round} was not recorded: a restart will judge it again`)
  touched.add(draftPathOf(round))
  await call(
    commands([`${tool('snapshot')} --file ${REQ_PATH} --to ${draftPathOf(round)} ${noted(`draft snapshot round ${round}`)}`]),
    { agentType: 'file-copier', model: MODELS.copy, label: `req:snapshot:${round}`, phase: 'Requirements', schema: GATE },
  )

  pending = [...pending, ...sendBack]

  if (!exists) warnings.push(`round ${round}: the requirements did not reach the disk`)
  if (passed) {
    accepted = true
    log(`[req/${round}] ACCEPTED: the gate is clean and no CRITICAL remark is left`)
    break
  }
  const signature = JSON.stringify(blocking.slice().sort())
  if (signature === previousSignature) {
    log(`[req/${round}] STUCK: the same blocking items as the previous round; more rounds will not help`)
    break
  }
  previousSignature = signature
}

// =============================================================================================
// Pains: the client's pains, each tied to the requirements that answer it
// =============================================================================================

// Written from accepted requirements only: a pain tied to a requirement that the next round
// renumbers or drops is a trace to nothing. One writing, one gate, one critic, one pass over what
// they found; what stays open goes to the unresolved list with the rest.
let painsWritten = false
const painOpen = []
const painLedger = []
if (!accepted && !cfg.acceptOpen) {
  log('[pains] the requirements were not accepted: no pain map (config.acceptOpen=true writes it anyway)')
  facts.push('Pains: not written, the requirements were not accepted')
} else if (!voicePort.length) {
  warnings.push('no pain map: it ranks the pains by the client voice sheet, and the sheet is missing')
  facts.push('Pains: not written, no client voice sheet')
} else {
  phase('Pains')
  const painInputs = [
    { port: 'client_voice', path: VOICE_PATH },
    { port: 'requirements', path: REQ_PATH },
    ...extractPorts,
  ]
  const painChecks = [
    `${tool('gate')} --file "${PAINS_PATH}" --min-length ${MIN_ARTIFACT_CHARS} ${PAIN_FLAGS} ${noted('pain map gate')}`,
    `${tool('check_quotes')} --file "${PAINS_PATH}" --source ${INPUTS_DIR} --source ${EXTRACTS_DIR} ${noted('pain map quotes')}`,
    `${tool('trace_ids')} --file "${PAINS_PATH}" --against "${REQ_PATH}" --ids "\\b(?:FR|NFR|BR)-\\d{3}\\b" ${noted('requirement ids the pain map cites')}`,
    `${tool('vocab')} --file "${PAINS_PATH}" --voice "${VOICE_PATH}" ${noted('client vocabulary in the pain map')}`,
  ]
  const checkPains = async (label) => {
    const res = await call(commands(painChecks), { agentType: 'gate-runner', model: MODELS.gate, label, phase: 'Pains', schema: CHECKS })
    const checks = (res && res.checks) || []
    const m = (checks[0] && checks[0].measures) || {}
    return {
      exists: typeof m.chars === 'number' && m.chars >= MIN_ARTIFACT_CHARS,
      problems:
        checks.length === painChecks.length
          ? checks.flatMap((c) => c.problems || [])
          : ['the pain map check did not return one report per command'],
    }
  }
  const painsOnDisk = cfg.continue ? await checkPains('pains:continue') : { exists: false, problems: [] }
  if (painsOnDisk.exists && !painsOnDisk.problems.length) {
    touched.add(PAINS_PATH)
    painsWritten = true
    log('[pains] the pain map on disk passes its gate, kept')
    facts.push('Pains: kept from the earlier run, gate clean')
  } else {
    await call(task({ inputs: painInputs, output: PAINS_PATH, brief: notesBlock || undefined }), {
      agentType: 'pain-mapper',
      model: MODELS.pains,
      label: 'pains:write',
      phase: 'Pains',
      schema: WROTE,
    })
    const first = await checkPains('pains:gate')
    const judged = first.exists
      ? await call(
          task({
            inputs: [{ port: 'draft', path: PAINS_PATH }, { port: 'client_voice', path: VOICE_PATH }, { port: 'requirements', path: REQ_PATH }, ...extractPorts],
            noFile: true,
          }),
          { agentType: 'lens-critic', model: MODELS.critic, label: 'pains:critic', phase: 'Pains', schema: LENS_VERDICT },
        )
      : null
    const remarks = ((judged && judged.remarks) || []).map((r) => String(r).replace(/^\s*\d{1,2}[.)]\s+/, ''))
    const high = remarks.filter((r) => /^\[HIGH\]/.test(r))
    for (const r of remarks) {
      painLedger.push({ kind: 'LENS', text: r, answer: /^\[HIGH\]/.test(r) ? null : 'recorded, not sent back' })
    }
    if (first.exists && !judged) warnings.push('the pain map critic returned nothing: the map was not judged')
    let final = first
    const items = [...first.problems.map((p) => `[GATE] ${p}`), ...high]
    if (first.exists && items.length) {
      await call(
        task({
          inputs: [{ port: 'draft', path: PAINS_PATH }, ...painInputs],
          output: PAINS_PATH,
          brief: notesBlock || undefined,
          extra:
            `REMARKS ON THE PAIN MAP. GATE items are measurements; a HIGH remark you may decline in the ` +
            `map's open rows if the sources do not support it.\n` +
            items.map((it, i) => `${i + 1}. ${it}`).join('\n'),
        }),
        { agentType: 'pain-mapper', model: MODELS.pains, label: 'pains:fix', phase: 'Pains', schema: WROTE },
      )
      final = await checkPains('pains:regate')
      for (const e of painLedger) if (!e.answer) e.answer = 'sent to the pain mapper once'
    }
    painsWritten = final.exists
    for (const pr of final.problems) painOpen.push(`[PAINS GATE] ${pr}`)
    if (!final.exists) warnings.push('the pain map did not reach the disk')
    facts.push(
      `Pains: ${final.exists ? 'written' : 'NOT WRITTEN'}; critic HIGH ${high.length}, other ${remarks.length - high.length}; ` +
        `gate ${final.problems.length ? 'open: ' + final.problems.join('; ') : 'clean'}`,
    )
  }
}

// =============================================================================================
// Report: remarks, unresolved items, audit, report
// =============================================================================================

phase('Report')
const open = [...pending.map((it) => `[${it.kind}] ${it.text}`), ...painOpen]
// A continued launch writes the list even when nothing is open: a list an earlier launch left
// would otherwise stay on disk and read as open items.
const writeOpen = open.length > 0 || !!cfg.continue
if (writeOpen) {
  await call(
    record(
      UNRESOLVED_PATH,
      accepted ? 'The requirements were accepted; these items were left open' : 'The rounds ran out; these items are still open',
      open.length ? open : ['Nothing is open'],
    ),
    { agentType: 'verbatim-writer', model: MODELS.record, label: 'unresolved', phase: 'Report', schema: WROTE },
  )
}
if (ledger.length) {
  await call(
    record(
      REMARKS_PATH,
      'Every remark of every round, its severity and what the writer did with it',
      ledger.map((e) => `Round ${e.round} [${e.kind}] ${e.text} -> ${e.answer || 'open'}`),
    ),
    { agentType: 'verbatim-writer', model: MODELS.record, label: 'remarks', phase: 'Report', schema: WROTE },
  )
}

if (painLedger.length) {
  await call(
    record(PAIN_REMARKS_PATH, 'Remarks on the pain map and what was done with them', painLedger.map((e) => `[${e.kind}] ${e.text} -> ${e.answer || 'open'}`)),
    { agentType: 'verbatim-writer', model: MODELS.record, label: 'pains:remarks', phase: 'Report', schema: WROTE },
  )
}
// A continued run that judged no round keeps the earlier record; it is declared, not lost.
if (!ledger.length) touched.add(REMARKS_PATH)

const audit = await call(
  commands([`${tool('listing')} --dir ${run} --ext "" --recursive --log-release ${noted('audit: anything produced and never read')}`]),
  { agentType: 'gate-runner', model: MODELS.gate, label: 'audit', phase: 'Report', schema: LISTING },
)
let orphans = []
const onDisk = (audit && audit.files) || []
if (!onDisk.length || (typeof audit.count === 'number' && audit.count !== onDisk.length)) {
  warnings.push('the directory audit was not done: the listing did not arrive whole')
} else {
  orphans = onDisk.filter((f) => !touched.has(f) && f !== REPORT_PATH)
  for (const f of orphans) log(`[audit/orphan] ${f}`)
}

const trace = lastTrace || {}
const lost = Array.isArray(trace.lost) ? trace.lost : []
const reportItems = [
  `Accepted: ${accepted ? 'yes' : 'no'}; rounds: ${rounds} of ${MAX_ROUNDS}`,
  ...facts,
  `Trace: extract rows ${trace.declared ?? '?'}, carried ${trace.carried ?? '?'}, set aside ${trace.not_carried ?? '?'}, lost ${lost.length}` +
    (lost.length ? ` (${lost.join(', ')})` : ''),
  `Quotes in the requirements: checked ${lastQuotes.quotes ?? '?'}, not found ${lastQuotes.not_found ?? '?'}`,
  ...perRound,
  `Open items: ${open.length}${open.length ? ` (${UNRESOLVED_PATH})` : ''}; all remarks: ${REMARKS_PATH}`,
  `Audit: files on disk ${onDisk.length}, read by nobody ${orphans.length}` + (orphans.length ? ` (${orphans.join(', ')})` : ''),
  ...warnings.map((w) => `WARNING: ${w}`),
  ...handoff.map((h) => `Call: ${h}`),
]
await call(record(REPORT_PATH, `Requirements run: ${run}`, reportItems), {
  agentType: 'verbatim-writer',
  model: MODELS.record,
  label: 'report',
  phase: 'Report',
  schema: WROTE,
})

// A writer's "written" is a claim; the disk is the answer. The records are checked by the gate.
const records = [
  REPORT_PATH,
  ...(ledger.length ? [REMARKS_PATH] : []),
  ...(painLedger.length ? [PAIN_REMARKS_PATH] : []),
  ...(writeOpen ? [UNRESOLVED_PATH] : []),
]
const recordList = records.map((r) => `${tool('gate')} --file "${r}" --min-length 50 ${noted('record on disk')}`)
const recorded = await call(commands(recordList), {
  agentType: 'gate-runner',
  model: MODELS.gate,
  label: 'records',
  phase: 'Report',
  schema: CHECKS,
})
const recordChecks = (recorded && recorded.checks) || []
const missingRecords =
  recordChecks.length === records.length ? records.filter((r, i) => !recordChecks[i].ok) : records
for (const r of missingRecords) log(`[report] RECORD NOT ON DISK: ${r}`)

return {
  inputs: sources,
  extracts: extractPorts.map((e) => e.path),
  client_voice: voicePort.length ? VOICE_PATH : null,
  requirements: REQ_PATH,
  accepted,
  rounds,
  lost_rows: lost,
  open_items: open.length,
  unresolved: open.length ? UNRESOLVED_PATH : null,
  remarks: ledger.length ? REMARKS_PATH : null,
  pains: painsWritten ? PAINS_PATH : null,
  report: REPORT_PATH,
  records_missing: missingRecords,
  orphans,
  warnings,
}
