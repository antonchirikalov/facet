// Solution design from raw input documents: extract, build requirements, design under a critic.
//
// The second archetype, and it exists to answer a question about the first: how much of
// explainer-article.js is the article, and how much is machinery that any document pipeline
// needs? The answer is in this file. Everything between the I/O tail and the audit was copied
// from there with names changed and nothing else; the wiring — what is read, who is called, in
// what order — is new.
//
// One deliberate improvement over the original, forced by this pipeline rather than invented:
// the revision loop is a function here, because this archetype runs it twice (once for the
// requirements, once for the design). In the article script the same code sits inlined once. That
// is what a second archetype is for — it shows which parts are parameters and which are constants.
//
// What this pipeline does NOT do that the article one does: no web search (the sources are given,
// not found), no author's-voice critic (the slop critic judges generated-text tells instead, because
// these documents go to a client), no arithmetic corrector (there is no worked example to recompute). What it adds: a fan-out whose
// width comes off the disk rather than out of the brief, a two-model contest with a selector, and
// a discovery stage that produces the questions the design could not answer by itself.
//
// Runtime limits respected here, same as the article script: meta is a pure literal; no import();
// no Date.now and no Math.random; the script never touches the filesystem — every file is read and
// written by an agent, and every measurement is made by a python tool through an agent with Bash.

export const meta = {
  name: 'solution-design',
  description: 'Solution design from input documents: extract, requirements, design under a critic',
  phases: [
    { title: 'Resume', detail: 'what is already on disk, and is anybody else working here' },
    { title: 'Extract', detail: 'one agent per input document, in parallel' },
    { title: 'Voice', detail: 'the client in their own words: ranking, weights, vocabulary' },
    { title: 'Requirements', detail: 'writer, corrector, gate, critic, in rounds' },
    { title: 'Contest', detail: 'two models design in parallel, a selector picks one' },
    { title: 'Design', detail: 'the winner is refined against a critic, in rounds' },
    { title: 'Discovery', detail: 'what the design could not answer becomes questions' },
    { title: 'Client', detail: 'the editions the client reads, with the id map, gated' },
    { title: 'Lens', detail: 'the client lens: pain map and day story, in rounds' },
    { title: 'Proposal', detail: 'the proposal from the lens and the accepted documents, gated' },
    { title: 'Gate', detail: 'records, unresolved items, audit of the run directory' },
  ],
}

// --- Input -------------------------------------------------------------------------------

const run = typeof args === 'string' ? args : args && args.runDir
if (!run) {
  throw new Error('a run directory is required: args.runDir, e.g. docs-runs/reporting')
}
// Optional, and its absence is announced rather than assumed. Without a clock the script cannot
// ask how long this directory has been quiet, which is the only way it can tell that another run
// is working here. `Date.now()` is not available: a script that calls it is refused at submission,
// because resume replays cached agent() calls and a script that branches on time cannot replay.
const now = (args && args.now) || ''
// Free text about what is wanted, if there is any. Unlike the article pipeline this one does not
// require it: the input documents ARE the order here. When present it goes to the requirements
// writer as an extra port.
const order = (args && args.order) || ''
// Decisions the architect settled before the run, in the shape tech-proposal.js already uses:
// { id, title, mode: 'decided' | 'compare', brief }. Optional; checked here because a typo in a
// mode would otherwise turn a settled decision into an open one without anyone noticing.
const decisions = (args && args.decisions) || []
if (!Array.isArray(decisions)) {
  throw new Error('args.decisions must be a list: [{ id, title, mode: "decided"|"compare", brief }]')
}
for (const d of decisions) {
  if (!d || !d.id || !d.title || !['decided', 'compare'].includes(d.mode)) {
    throw new Error(`decision ${JSON.stringify(d)}: needs id, title and mode "decided" or "compare"`)
  }
}

const cfg = (args && args.config) || {}

// --- Paths: named here, by the script, and nowhere else --------------------------------------
//
// Agents receive paths and never report them back. A `path` field in a schema turns "say where it
// is" into a substitute for "put it there", and one live run had the disk check return absolute
// Windows paths where the script had passed relative posix ones — nothing matched, and five agents
// redid work that was already on disk. Results are matched to commands BY INDEX instead.
const INPUTS_DIR = `${run}/inputs`
const EXTRACTS_DIR = `${run}/extracts`
const REQ_PATH = `${run}/requirements.md`
const DESIGN_PATH = `${run}/design.md`
const DISCOVERY_PATH = `${run}/discovery-questions.md`
const UNRESOLVED_PATH = `${run}/UNRESOLVED.md`
const REQ_CLIENT_PATH = `${run}/requirements.client.md`
const DESIGN_CLIENT_PATH = `${run}/design.client.md`
const ID_MAP_PATH = `${run}/client-id-map.json`
const VOICE_PATH = `${run}/client-voice.md`
const PAIN_PATH = `${run}/pain-map.md`
const STORY_PATH = `${run}/day-story.md`
const PROP_PATH = `${run}/prop.md`
const CANDIDATES_DIR = `${run}/design-candidates`
const candidatePathOf = (n) => `${CANDIDATES_DIR}/candidate-${n}.md`
const extractPathOf = (stem) => `${EXTRACTS_DIR}/${stem}.md`
// One directory per loop, because there are two loops and their records must not mix. `rounds.py`
// counts what it finds in one directory, so two loops sharing one would each see the other's
// rounds and continue from the wrong number.
const roundsDirOf = (loop) => `${run}/rounds/${loop}`
const roundPathOf = (loop, n) => `${roundsDirOf(loop)}/round-${n}.md`
const draftPathOf = (loop, n) => `${roundsDirOf(loop)}/draft-${n}.md`
const TOOLS_LOG = `${run}/tools.jsonl`
const HANDOFF_PATH = `${run}/handoff.md`

// --- Configuration: everything a caller can change without editing this file -----------------

const STAGES = cfg.stages || ['requirements', 'design']
const RUN_REQUIREMENTS = STAGES.includes('requirements')
const RUN_DESIGN = STAGES.includes('design')
// Discovery — the questions to put in front of the client — runs after the design by default,
// and on its own when named as the only stage: it needs nothing but requirements.md.
const RUN_DISCOVERY = STAGES.includes('discovery') || (RUN_DESIGN && cfg.discovery !== false)
// The client edition runs alone, after a person has read the traceable versions: it is written
// from accepted documents, and a launch that also rewrote them would edit what it copies from.
const RUN_CLIENT = STAGES.includes('client')
if (RUN_CLIENT && STAGES.length > 1) {
  throw new Error(
    `config.stages=["client"] runs on its own, after requirements and design have been accepted; ` +
      `received: ${STAGES.join(', ')}`,
  )
}
// The client lens (pain map and day story) and the proposal are written from accepted
// requirements and design, so they run on their own: "lens", "proposal", or both in order.
const RUN_LENS = STAGES.includes('lens')
const RUN_PROPOSAL = STAGES.includes('proposal')
if ((RUN_LENS || RUN_PROPOSAL) && STAGES.some((st) => st !== 'lens' && st !== 'proposal')) {
  throw new Error(
    `config.stages "lens" and "proposal" run on their own, after requirements and design have been accepted; ` +
      `received: ${STAGES.join(', ')}`,
  )
}
if (!RUN_REQUIREMENTS && !RUN_DESIGN && !RUN_DISCOVERY && !RUN_CLIENT && !RUN_LENS && !RUN_PROPOSAL) {
  throw new Error(
    `config.stages must name "requirements", "design", "discovery", "client", "lens", "proposal" or a combination; got: ${STAGES.join(', ')}`,
  )
}
const MAX_ROUNDS = cfg.maxRounds || 3
const PLATEAU_ROUNDS = cfg.plateauRounds || 2
const MIN_ARTIFACT_CHARS = cfg.minArtifactChars || 200
// The shape of an extract, from the source-processor prompt: six tables, each row sourced. A table
// with only its header is a legitimate "nothing found", so the floor is on sourced rows across
// the whole extract, not on length: a skeleton of six empty tables passed a 200-character floor.
const EXTRACT_SHAPE = cfg.extractShape || [
  ...['Requirements', 'Decisions', 'Constraints', 'Roles', 'Facts', 'Open questions'].map(
    (h) => `--require-heading "^##\\s+${h}\\b"`,
  ),
  '--rows-have-source',
  '--min-sourced-rows 1',
].join(' ')
// The contest. Two models rather than two temperatures: the point is a different reading of the
// same requirements, and the selector then has something to choose between. One model here is a
// legal answer and turns the contest off.
const CONTEST_MODELS = cfg.contestModels || ['opus', 'sonnet']
const MODELS = {
  extract: 'sonnet',
  reqWrite: 'opus',
  reqFix: 'sonnet',
  reqCritic: 'opus',
  design: 'opus',
  designCritic: 'opus',
  select: 'opus',
  probe: 'opus',
  discovery: 'opus',
  client: 'opus',
  voice: 'opus',
  lens: 'opus',
  lensCritic: 'opus',
  proposal: 'opus',
  slop: 'sonnet',
  claims: 'sonnet',
  rules: 'sonnet',
  // Carriers run one command and copy its output. Sonnet, not haiku, and this was measured: a
  // haiku carrier read the harness's relayed user request ("check the prompts, run the tests") as
  // its own task, ran pytest and dry-runs for eight minutes, wrote a report into the repository
  // root and returned an INVENTED rounds record — three rounds done — which the script trusted,
  // skipping the whole revision loop. The saving was ~1% of the run; the failure cost the run.
  gate: 'sonnet',
  record: 'sonnet',
  copy: 'sonnet',
  ...(cfg.models || {}),
}
// Length bounds. Absent is a legal answer and it is the default for the ceiling: the gate then
// measures and does not judge.
//
// A ceiling nobody asked for makes acceptance unreachable, and this was measured rather than
// reasoned. An invented ceiling of 40 000 met a critic holding four blocking defects, each of
// which is closed by specifying something the design had left vague. Round 2 grew the document to
// 42 126, round 3 was told to remove 2 126 and not add — and grew it to 44 590. Neither agent was
// wrong: the critic asked for specification, the gate asked for cuts, and the loop cannot satisfy
// both. In the article pipeline the same budget block worked on the first try, because there the
// ceiling came from the order — the client's own requirement — rather than from the script.
//
// So the script states no ceiling of its own. A caller whose order names one passes it.
// By file length, not prose: the requirements profile makes the document tables, and prose_chars
// does not count table rows. Measured: a complete nine-section draft of 92 KB had 4 977 prose
// characters, failed a 6 000 prose floor, and the second round bought 2 024 characters of prose
// nobody had asked for. The design document stays on a prose floor — it is prose.
const REQ_BOUNDS = cfg.reqBounds || { minLength: 20000, min: 0, max: 0 }
// The requirements profile's own gate rules (.claude/skills/requirements-profile/SKILL.md, "Gate
// rules"). By heading NUMBER, because the names translate with the document's language and the
// numbers do not; the profile promises exactly these. What a regex settles here never costs a
// critic's round — and a critic sent to count citations counts them, while a gate reads them.
// The discovery profile's gate rules (.claude/skills/discovery-questions-profile/SKILL.md).
const DISCOVERY_GATE_FLAGS = cfg.discoveryGateFlags || [
  ...[1, 2, 3, 4].map((n) => `--require-heading "^##\\s+${n}\\."`),
  '--no-empty-sections',
  '--forbid "\\x60"',
]
// The client-edition profile's gate rules (.claude/skills/client-edition-profile/SKILL.md). The
// quotes are checked by a separate tool against the extracts, in the same carrier call.
// Ids are checked in the requirements edition only: there a row's first cell declares an id, in
// the design the same cell holds a reference (an NFR row quotes the requirement it meets).
const CLIENT_ID_PATTERN = cfg.clientIdPattern || '\\b(?:FR|NFR|BR|C|G|A)-\\d{3}\\b'
// Generated-text phrases no context makes informative, both languages: a pattern of the other
// language matches nothing. Narrow on purpose; what only reading settles is the slop critic's.
const SLOP_FLAGS = [
  '--forbid-file library/style/forbid/en-slop.txt',
  '--forbid-file library/style/forbid/ru-slop.txt',
]
// The slop critic sits in every revision loop of a client-facing document; off with false.
const SLOP_CRITIC = cfg.slopCritic !== false
// Two panels that can take a critic's seat in a revision round. Both are new and off until each
// has had one live call on real material; switch them on with config.claimCheck and
// config.rulePanel.
const CLAIM_CHECK = cfg.claimCheck === true
const RULE_PANEL = cfg.rulePanel === true
const CLAIM_BATCH = cfg.claimBatch || 12
const RULES_TOOL = cfg.rulesTool || 'python -X utf8 tools/rules.py'
const REQ_PROFILE = '.claude/skills/requirements-profile/SKILL.md'
const DESIGN_PROFILE = '.claude/skills/solution-design-profile/SKILL.md'
const CLIENT_GATE_FLAGS = cfg.clientGateFlags || [
  '--no-empty-sections',
  ...SLOP_FLAGS,
  '--figures-numbered',
  '--forbid-file library/style/forbid/client-meta.txt',
  '--forbid-file library/style/forbid/no-bold.txt',
  '--forbid "\\x60"',
]
const CLIENT_ID_FLAGS = [`--unique-ids "${CLIENT_ID_PATTERN}"`, `--sequential-ids "${CLIENT_ID_PATTERN}"`]
const QUOTES_TOOL = cfg.quotesTool || 'python -X utf8 tools/check_quotes.py'
const TRACE_TOOL = cfg.traceTool || 'python -X utf8 tools/trace_ids.py'
const VOCAB_TOOL = cfg.vocabTool || 'python -X utf8 tools/vocab.py'
// The client-voice profile's gate rules (.claude/skills/client-voice-profile/SKILL.md).
const VOICE_GATE_FLAGS = cfg.voiceGateFlags || [
  ...[1, 2, 3, 4, 5, 6].map((n) => `--require-heading "^##\\s+${n}\\."`),
  '--forbid "\\x60"',
]
// What a consumer of the voice sheet is told about it, next to the port.
const VOICE_NOTE =
  `CLIENT VOICE\nThe port client_voice is the client's own words, ranked by what mattered to them. ` +
  `Take each requirement's weight and frequency from its section 2 and the client's terms from its ` +
  `section 3. A weight the sheet gives and the document drops is a defect.`
// The design profile's gate rules (.claude/skills/solution-design-profile/SKILL.md, "Gate rules").
const DESIGN_GATE_FLAGS = cfg.designGateFlags || [
  ...[1, 2, 3, 4, 5, 6, 7].map((n) => `--require-heading "^##\\s+${n}\\."`),
  ...['1.1', '1.2', '1.3', '1.4'].map((n) => `--require-heading "^###\\s+${n.replace('.', '\\.')}"`),
  '--figures-numbered',
  ...SLOP_FLAGS,
  '--forbid-file library/style/forbid/no-bold.txt',
  '--forbid "\\x60"',
]
const REQ_GATE_FLAGS = cfg.reqGateFlags || [
  ...[1, 2, 3, 4, 5, 6, 7, 8, 9].map((n) => `--require-heading "^##\\s+${n}\\."`),
  ...['8.1', '8.2', '8.3'].map((n) => `--require-heading "^###\\s+${n.replace('.', '\\.')}"`),
  '--rows-have-source',
  '--unique-ids "\\b(?:FR|NFR|BR|C|G|A)-\\d{3}\\b"',
  // Weak words and escape clauses in the statement cell only (INCOSE R7–R9). Both languages
  // are passed: a pattern for the other language matches nothing and costs nothing, and the
  // script does not know the document's language.
  '--cell-forbid-file library/style/forbid/req-weak-ru.txt',
  '--cell-forbid-file library/style/forbid/req-weak-en.txt',
  ...SLOP_FLAGS,
  // No backticks: ids and names are plain text in a requirements document. \x60 is the
  // character, spelled as a regex escape so that no shell ever sees a real one.
  '--forbid "\\x60"',
]
const DESIGN_BOUNDS = cfg.designBounds || { min: 12000, max: 0 }
// No forbidden-pattern files by default. This is an internal engineering document, not an article
// in someone's voice, and the slop list is editorial policy for published prose. A caller who
// wants it passes paths.
const FORBID_FILES = cfg.forbidFiles || []

// Which directories belong to which stage, so the audit can tell a loss from somebody else's
// business. A launch that only designs never opens `inputs/` or `extracts/`, and never should.
const STAGE_OWNED = [
  { prefix: `${INPUTS_DIR}/`, mine: RUN_REQUIREMENTS },
  { prefix: `${EXTRACTS_DIR}/`, mine: RUN_REQUIREMENTS },
  { prefix: `${roundsDirOf('req')}/`, mine: RUN_REQUIREMENTS },
  { prefix: `${CANDIDATES_DIR}/`, mine: RUN_DESIGN },
  { prefix: `${roundsDirOf('design')}/`, mine: RUN_DESIGN },
  { prefix: `${run}/probe-questions.md`, mine: RUN_DISCOVERY },
  { prefix: DISCOVERY_PATH, mine: RUN_DISCOVERY },
  { prefix: UNRESOLVED_PATH, mine: !RUN_CLIENT },
  { prefix: VOICE_PATH, mine: RUN_REQUIREMENTS },
  { prefix: REQ_CLIENT_PATH, mine: RUN_CLIENT },
  { prefix: DESIGN_CLIENT_PATH, mine: RUN_CLIENT },
  { prefix: ID_MAP_PATH, mine: RUN_CLIENT },
  { prefix: PAIN_PATH, mine: RUN_LENS },
  { prefix: STORY_PATH, mine: RUN_LENS },
  { prefix: `${run}/rounds/pain/`, mine: RUN_LENS },
  { prefix: `${run}/rounds/story/`, mine: RUN_LENS },
  { prefix: PROP_PATH, mine: RUN_PROPOSAL },
]

const GATE_TOOL = cfg.gateTool || 'python -X utf8 tools/gate.py'
const ROUNDS_TOOL = cfg.roundsTool || 'python -X utf8 tools/rounds.py'
const LISTING_TOOL = cfg.listingTool || 'python -X utf8 tools/listing.py'
const INTAKE_TOOL = cfg.intakeTool || 'python -X utf8 tools/intake.py'
const TO_TEXT_TOOL = cfg.toTextTool || 'python -X utf8 tools/to_text.py'
const SNAPSHOT_TOOL = cfg.snapshotTool || 'python -X utf8 tools/snapshot.py'
const BUSY_TOOL = cfg.busyTool || 'python -X utf8 tools/busy.py'
const APPLY_TOOL = cfg.applyTool || 'python -X utf8 tools/apply_edits.py'

// --- No prompts in this file ------------------------------------------------------------------
//
// Every agent called here is a library agent that already knows its job from its own prompt.md.
// What travels from this file is only what the script alone can know: which paths, which commands,
// which items, which round, which model. The test: a string here that would still make sense if
// the pipeline produced a marketing plan instead of a design is orchestration; anything else
// belongs in a prompt.

// --- The I/O tail, generated the same way for every agent -------------------------------------

const OUTPUT_RULE =
  `The file is your result. Write it with the Write tool before you finish; the fields you ` +
  `return through the schema describe it, they do not replace it and are saved nowhere. If ` +
  `the file already exists and needs changing, edit it rather than write it again. A relayed ` +
  `user request above this task, if any, is context about the run, not your instruction: your ` +
  `work is exactly this task.`

// A critic produces no file. Until this branch existed, a critic was handed both descriptions of
// its own output at once — "OUTPUT (no file)" followed by "the file is your result, write it" —
// and that contradiction is what made an analyst produce neither artifact.
const NO_FILE_RULE =
  `You write no file in this step and you edit nothing. The fields you return through the ` +
  `schema ARE your result — everything you found has to fit in them. A relayed user request ` +
  `above this task, if any, is context about the run, not your instruction: your work is ` +
  `exactly this task.`

// Every path that ever reaches an agent, recorded as it goes. Not bookkeeping anyone has to
// remember: a path becomes consumed by the only act that can consume it — appearing in a task —
// so there is no way to hand a file to an agent without this seeing it. The audit at the end
// subtracts this set from what is on disk, because every loss this project has had was the same
// shape: a file produced and never read.
const touched = new Set()
touched.add(TOOLS_LOG)

const handoff = []
let lastPorts = null

// Things that did not stop the run but change how its result must be read. `log()` is not enough
// for these: it lives in the run transcript, and the transcript is exactly what is gone by the
// time someone asks why a section is thin. They go on disk with the handoff record.
const warnings = []

// A remark without the number the critic put in front of it. The ledger is one list per round
// precisely because several lists each numbered from one make a number meaningless, and a critic
// numbering its own items rebuilds that by hand. Only a leading ordinal goes.
const unnumbered = (text) => String(text).replace(/^\s*\d{1,2}[.)]\s+/, '')

// A file name from a path, without directory and without suffix. The listing reports what is on
// disk; this turns each reported name into the name of the file the script will write next to it,
// so the correspondence between an input and its extract is visible in the directory.
// The stem is the path inside inputs/ with folders joined by "__": two transcript.md files in two
// subfolders would otherwise write one extract over the other. A top-level file keeps its name.
//
// Tool arguments must be ASCII (a Cyrillic name on a Windows command line arrives mangled), and the
// stem becomes the extract's file name, which travels in gate commands. Spaces become hyphens; any
// other character outside [A-Za-z0-9._-] is dropped and a short hash of the original name is
// appended, so two names that differ only in those characters still get two extracts.
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

async function call(taskText, opts) {
  handoff.push({
    label: opts.label,
    agent: opts.agentType || '(built-in)',
    model: opts.model,
    inputs: (lastPorts && lastPorts.inputs) || [],
    output: (lastPorts && lastPorts.output) || null,
  })
  lastPorts = null
  return agent(taskText, opts)
}

function task({ inputs, output, extra, noFile, brief }) {
  for (const i of inputs || []) touched.add(i.path)
  if (!noFile && output) touched.add(output)
  lastPorts = {
    inputs: (inputs || []).map((i) => `${i.port} → ${i.path}`),
    output: noFile ? null : output,
  }
  const ports = (inputs || []).map((i) => `${i.port}: ${i.path}`).join('\n')
  return (
    (ports ? `INPUT\n${ports}\n\n` : '') +
    (brief ? `${brief}\n\n` : '') +
    (noFile ? NO_FILE_RULE : `OUTPUT\n${output}\n\n` + OUTPUT_RULE) +
    (extra ? `\n\n${extra}` : '')
  )
}

// --- What the person who launched the run decided before it started --------------------------
//
// The order used to travel as a port whose path was the inputs directory: a script has no
// filesystem, so the text was never on disk and no agent ever saw it. One live run paid for that
// twice — frames the order asked for were never embedded, and the stack, the hosting and the MVP
// bounds the architect had already settled were chosen again by the designer, differently. Both
// now travel as text inside the task, the only channel a script has.
const ORDER_BLOCK = order
  ? `ORDER\n${order}\n\nThe order sets the scope, audience, format and decisions of this run and is ` +
    `binding where it sets them. Facts still come only from the sources.`
  : ''
const DECISIONS_BLOCK = decisions.length
  ? `DECISIONS\n` +
    decisions
      .map((d) => `- ${d.id} ${d.title} [${d.mode === 'compare' ? 'compare' : 'decided'}]: ${d.brief || ''}`)
      .join('\n') +
    `\n\nA decided item is taken as given: design on it and justify it from the requirements. A ` +
    `compare item is presented as the options with their trade-offs, and the choice is left as an ` +
    `open question. Neither is reopened by the design.`
  : ''
const DESIGN_BRIEF = [ORDER_BLOCK, DECISIONS_BLOCK].filter(Boolean).join('\n\n')

// agent() yields null when a subagent dies on a terminal error after retries, or when the person
// running this skips it. The most expensive of those assumptions used to sit in the last quarter
// of a script, reached only after both writing rounds had been paid for.
function must(value, what) {
  if (!value) throw new Error(`the agent returned nothing: ${what}`)
  return value
}

// A critic that died is not a critic that approved. Silent passes are the failure this pipeline
// exists to prevent, so a missing verdict becomes `revise` plus an open item.
function noVerdict(who) {
  return {
    verdict: 'revise',
    remarks: [`${who} returned no verdict — that is an open item, not silent agreement`],
  }
}

// --- Schemas: only what the script cannot know on its own -------------------------------------

const REPORT = {
  type: 'object',
  required: ['ok', 'problems', 'measures'],
  properties: {
    ok: { type: 'boolean' },
    problems: { type: 'array', items: { type: 'string' } },
    measures: { type: 'object' },
  },
}

const GATE = {
  type: 'object',
  required: ['report', 'stdout'],
  properties: { report: REPORT, stdout: { type: 'string' } },
}

const LISTING = {
  type: 'object',
  required: ['files', 'count'],
  properties: {
    files: { type: 'array', items: { type: 'string' } },
    // Required so the carrier can be checked against itself: a live audit had the tool print 37
    // paths and the agent return one. A carrier that drops the list also drops the count, and
    // then the two disagree and say so. Carrying a number is the one thing a summarising agent
    // does not shorten.
    count: { type: 'integer', description: 'the files number from the report measures, verbatim' },
  },
}

// One live run listed the top of input/ and missed input/call-<date>/ with the call digest,
// a cleaner transcript and sixteen frames; our own notes sat among the client's words unmarked.
// The inventory walks the whole tree and the script names what the listing will not process.
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

const EXISTENCE = {
  type: 'object',
  required: ['checks'],
  properties: {
    checks: {
      type: 'array',
      items: {
        type: 'object',
        required: ['ok', 'problems'],
        properties: {
          ok: { type: 'boolean' },
          problems: { type: 'array', items: { type: 'string' } },
        },
      },
    },
  },
}

const BUSY = {
  type: 'object',
  required: ['checks'],
  properties: {
    checks: {
      type: 'array',
      items: {
        type: 'object',
        required: ['busy', 'problems'],
        properties: {
          busy: { type: 'boolean', description: 'the busy field of the report, verbatim' },
          problems: { type: 'array', items: { type: 'string' } },
        },
      },
    },
  },
}

// Startup: the busy.py report (which carries `busy`) and then gate.py existence reports.
const STARTUP = {
  type: 'object',
  required: ['checks'],
  properties: {
    checks: {
      type: 'array',
      items: {
        type: 'object',
        required: ['ok', 'problems'],
        properties: {
          ok: { type: 'boolean' },
          problems: { type: 'array', items: { type: 'string' } },
          busy: { type: 'boolean', description: 'the busy field of the report, verbatim; only the busy.py report has it' },
        },
      },
    },
  },
}

const ROUNDS = {
  type: 'object',
  required: ['report', 'rounds', 'counts'],
  properties: {
    // Asked for by name rather than left inside the free-form `measures`, because a free-form
    // object is precisely what a summarising carrier trims. One number per round, for every
    // round: the plateau detector needs the whole history, and `rounds` carries only the newest.
    counts: {
      type: 'array',
      description: 'the counts array from the report measures, verbatim, one entry per round',
      items: {
        type: 'object',
        required: ['round', 'items'],
        properties: { round: { type: 'number' }, items: { type: 'number' } },
      },
    },
    report: REPORT,
    rounds: {
      type: 'array',
      items: {
        type: 'object',
        required: ['round', 'verdict', 'style_verdict', 'remarks', 'style', 'gate'],
        properties: {
          round: { type: 'number' },
          verdict: { type: 'string' },
          style_verdict: { type: 'string' },
          remarks: { type: 'array', items: { type: 'string' } },
          style: { type: 'array', items: { type: 'string' } },
          gate: { type: 'array', items: { type: 'string' } },
        },
      },
    },
  },
}

const WROTE = {
  type: 'object',
  required: ['written'],
  properties: { written: { type: 'boolean' } },
}

const EXTRACT = {
  type: 'object',
  required: ['facts', 'open_questions'],
  properties: {
    facts: {
      type: 'array',
      items: { type: 'string' },
      description: 'what this document establishes, in its own terms',
    },
    open_questions: {
      type: 'array',
      items: { type: 'string' },
      description: 'what it raises and does not answer',
    },
  },
}

// The writer of either document answers the ledger. `changes` is what it did beyond the numbered
// remarks; `addressed` is one entry per number it was given, and its absence is what let five
// remarks come back word for word in two consecutive rounds of a live run.
const DRAFT = {
  type: 'object',
  required: ['changes', 'addressed'],
  properties: {
    changes: {
      type: 'array',
      items: { type: 'string' },
      description: 'what you changed beyond the numbered remarks; empty is a fine answer',
    },
    addressed: {
      type: 'array',
      items: {
        type: 'object',
        required: ['item', 'status', 'note'],
        properties: {
          item: { type: 'number', description: 'the number of the remark, as it was given' },
          status: { type: 'string', enum: ['fixed', 'declined'] },
          note: {
            type: 'string',
            description: 'what you did, or — for declined — why you deliberately did not',
          },
        },
      },
      description: 'one entry per numbered remark; empty only on the first round, which has none',
    },
  },
}

// The verdict literal is `approved`, quoted from the critics' own instructions rather than chosen
// here. A prompt that says `approved` against a schema that allows only `ok` leaves the agent
// between two descriptions of its own output: at best that costs a retry, at worst the model
// picks `revise` and a round is spent for nothing.
const VERDICT = {
  type: 'object',
  required: ['verdict', 'remarks'],
  properties: {
    verdict: {
      type: 'string',
      enum: ['approved', 'revise'],
      description: 'exactly `approved` or exactly `revise`; no synonyms',
    },
    remarks: { type: 'array', items: { type: 'string' } },
  },
}

// The selector returns which candidate won, by number, and never a path. The script named the
// candidates and knows where they are; what it cannot know is which one is better.
const SELECTION = {
  type: 'object',
  required: ['winner', 'reason'],
  properties: {
    winner: {
      type: 'integer',
      description: 'the number of the winning candidate, as given in the task',
    },
    reason: { type: 'string', description: 'why this one and not the others, in a few sentences' },
    borrow: {
      type: 'array',
      items: { type: 'string' },
      description: 'what the losing candidates did better and the winner should take from them',
    },
  },
}

const PROBE = {
  type: 'object',
  required: ['questions'],
  properties: {
    questions: {
      type: 'array',
      items: { type: 'string' },
      description: 'the discovery questions you produced, one per entry',
    },
  },
}

// --- Measurement: python counts, an agent carries, the script decides -------------------------

const LOG_FLAG = `--log ${TOOLS_LOG}`
// The same command means different things at different points, and the log has to say which.
// `output missing` while asking what already exists is the expected answer on a fresh run; the
// same words while checking that an agent left its file behind are a defect. English, because the
// note travels through argv to a python tool via whichever shell the carrying agent picked, and
// Cyrillic through argv on Windows depends on the codepage.
const noted = (purpose) => `${LOG_FLAG} --log-note "${purpose}"`

function gateCommand(path, bounds, purpose, flags = []) {
  const parts = [...flags]
  if (bounds && bounds.minLength) parts.push(`--min-length ${bounds.minLength}`)
  if (bounds && bounds.min) parts.push(`--min-prose ${bounds.min}`)
  if (bounds && bounds.max) parts.push(`--max-prose ${bounds.max}`)
  for (const file of FORBID_FILES) parts.push(`--forbid-file ${file}`)
  // Every structured document gets this check. A floor on length answers "did the agent write
  // anything" and misses what actually happens: the agent writes the SHAPE of the document —
  // every heading the contract asks for, in order — and fills it pass by pass. Caught live at
  // 1 748 bytes of headings alone, and again at 68 KB with three of six sections still hollow.
  parts.push('--no-empty-sections')
  return `${GATE_TOOL} --file "${path}" ${parts.join(' ')} ${noted(purpose)}`.trim()
}

function commands(list) {
  return `COMMANDS\n` + list.map((c, i) => `${i + 1}. ${c}`).join('\n')
}

// A file that exists but holds 200 characters is a file an agent created and abandoned, which is
// why existence is measured rather than tested: `--min-length` turns "is it there" and "is there
// anything in it" into one number the script can branch on.
function existenceCommands(paths, purpose = 'file is where it should be', flagsOf = () => '') {
  return commands(
    paths.map(
      (p) => `${GATE_TOOL} --file "${p}" --min-length ${MIN_ARTIFACT_CHARS} ${flagsOf(p)} ${noted(purpose)}`.replace(/ {2,}/g, ' '),
    ),
  )
}

function record(path, heading, items) {
  touched.add(path)
  return (
    `FILE\n${path}\n\nHEADING\n${heading}\n\nITEMS\n` +
    items.map((r, i) => `${i + 1}. ${r}`).join('\n')
  )
}

async function recordHandoff() {
  const lines = handoff.map((h) => {
    const ins = h.inputs.length ? h.inputs.join(' | ') : '(no inputs)'
    const out = h.output || '(no file, schema only)'
    return `${h.label} [${h.agent}, ${h.model}] IN: ${ins} OUT: ${out}`
  })
  for (const w of warnings) lines.push(`WARNING: ${w}`)
  touched.add(HANDOFF_PATH)
  const wrote = await call(record(HANDOFF_PATH, `Handoffs between agents, calls: ${lines.length}`, lines), {
    agentType: 'verbatim-writer',
    model: MODELS.record,
    label: 'handoff',
    phase: 'Gate',
    schema: WROTE,
  })
  log(
    wrote && wrote.written
      ? `[handoff] handoffs written: ${lines.length} → ${HANDOFF_PATH}`
      : `[handoff] NOT WRITTEN — what was handed to whom survives only in the run log`,
  )
}

// What no round managed to close, on disk. A function rather than a block at the end, because
// this pipeline has two exits — a launch that only builds the requirements returns early — and the
// first version wrote the record on one of them. A live run then ended with eight open remarks and
// no file naming them: exactly the silent pass this project treats as its worst failure mode.
//
// Written even when the document was accepted. A critic that says `approved` and attaches remarks
// has accepted the document and left work behind; those remarks are for a person, not for the next
// round, and a report nobody wrote is a report nobody reads.
async function recordUnresolved(items, accepted) {
  if (!items.length) {
    log('[unresolved] no open remarks')
    return
  }
  const wrote = await call(
    record(
      UNRESOLVED_PATH,
      accepted
        ? 'The document was accepted, but these remarks were left open'
        : 'The revision rounds ran out; these remarks are still open',
      items,
    ),
    { agentType: 'verbatim-writer', model: MODELS.record, label: 'unresolved', phase: 'Gate', schema: WROTE },
  )
  log(
    wrote && wrote.written
      ? `[unresolved] open items: ${items.length} → ${UNRESOLVED_PATH}`
      : `[unresolved] FILE NOT WRITTEN, and ${items.length} items are open`,
  )
  if (!(wrote && wrote.written)) {
    warnings.push(`open remarks (${items.length}) were not written to a file`)
  }
  for (const item of items) log(`[unresolved/item] ${item}`)
}

async function auditRun() {
  const audit = await call(
    commands([`${LISTING_TOOL} --dir ${run} --ext "" --recursive --log-release ${noted('audit: anything produced and never read')}`]),
    { agentType: 'gate-runner', model: MODELS.gate, label: 'audit', phase: 'Gate', schema: LISTING },
  )
  const onDisk = (audit && audit.files) || []
  if (!onDisk.length) {
    log('[audit] could not list the run directory — no audit was done')
    warnings.push('directory audit not done: the listing did not come back')
    return { onDisk, orphans: [] }
  }
  // The carrier checked against itself. Subtraction only means anything on the whole list: paths
  // that did not arrive look exactly like files that were never read.
  const counted = audit && typeof audit.count === 'number' ? audit.count : null
  if (counted !== null && counted !== onDisk.length) {
    log(
      `[audit] the tool counted ${counted} files, ${onDisk.length} arrived — ` +
        `audit NOT done: on an incomplete list the subtraction is wrong in both directions`,
    )
    warnings.push(
      `audit not done: the listing counted ${counted} files, but only ${onDisk.length} arrived through the agent`,
    )
    return { onDisk, orphans: [] }
  }
  const unread = onDisk.filter((f) => !touched.has(f))
  // Files a stage this launch did not run produced and consumed. A design-only launch never opens
  // the input documents or the extracts, and it is right not to — the requirements document is
  // what it reads. Counting them as losses is how the audit cries wolf: a live design run reported
  // six orphans, every one of them correct and none of them a loss, which is exactly the thing
  // that teaches a reader to skip the audit line.
  //
  // Named by prefix rather than by listing them, because this launch has no reason to know what is
  // in a directory it does not use, and asking would cost an agent call to learn nothing.
  const elsewhere = STAGE_OWNED.filter((p) => !p.mine).map((p) => p.prefix)
  const foreign = unread.filter((f) => elsewhere.some((prefix) => f.startsWith(prefix)))
  const orphans = unread.filter((f) => !foreign.includes(f))
  log(
    `[audit] files in the directory ${onDisk.length}, read by agents ${touched.size}, ` +
      `from another stage ${foreign.length}, read by nobody ${orphans.length}`,
  )
  for (const f of foreign) log(`[audit/other-stage] ${f}`)
  for (const f of orphans) log(`[audit/orphan] ${f}`)
  if (!orphans.length) log('[audit] nothing lost: everything this launch produced was read by someone')
  return { onDisk, orphans, foreign }
}

// --- Is anybody else working here ------------------------------------------------------------
//
// Asked before anything is spent, and asked of the disk rather than of memory. Two runs pointed
// at one directory is the most expensive mistake this project has made: one rewrote the other's
// analysis while the first's writer was reading it, and which version reached the document can no
// longer be established. A quiet tool log looks exactly like a finished one, so the question has
// to be measured, not judged.
// --- Resume: the artifacts on disk are the checkpoint ----------------------------------------
//
// A dynamic workflow lives inside the CLI process, and that process restarts routinely. The cache
// that makes `resumeFromRunId` work does not outlive the session, so the checkpoint is the disk:
// before spending anything, the script asks what is already there.
const present = new Set()
{
  phase('Resume')
  const resumePaths = [REQ_PATH, DESIGN_PATH, VOICE_PATH, PAIN_PATH, STORY_PATH, DISCOVERY_PATH]
  // One carrier call for both questions, matched by index: the occupancy check first (when the
  // time is known), then one existence check per path.
  const busyCommand = now
    ? [`${BUSY_TOOL} --file ${TOOLS_LOG} --now ${now} --idle-seconds ${cfg.idleSeconds || 600} ${noted('is another run working here')}`]
    : []
  const existence = existenceCommands(resumePaths, 'resume: what is already on disk').replace(/^COMMANDS\n/, '')
  const startup = await call(
    commands([...busyCommand, ...existence.split('\n').map((line) => line.replace(/^\d+\.\s/, ''))]),
    { agentType: 'gate-runner', model: MODELS.gate, label: 'resume', phase: 'Resume', schema: STARTUP },
  )
  const all = (startup && startup.checks) || []
  const verdict = now ? all[0] : null
  const checks = now ? all.slice(1) : all
  if (!now) {
    warnings.push(
      'not checked whether another run is using this directory: args.now was not passed — ' +
        'two runs in one directory make the provenance of the document unprovable',
    )
    log('[busy] args.now was not passed — directory occupancy was NOT checked')
  } else if (!verdict) {
    log('[busy] the check did not come back — directory occupancy is unknown')
    warnings.push('the directory occupancy check did not come back: the answer is unknown')
  } else if (verdict.busy && !cfg.ignoreBusy) {
    throw new Error(
      `another run seems to be using ${run}: ${(verdict.problems || []).join('; ')}. ` +
        `A new run gets a new directory: python -X utf8 tools/newrun.py --base docs-runs --label <what>. ` +
        `If that run is certainly dead, config.ignoreBusy=true.`,
    )
  } else if (verdict.busy) {
    log(`[busy] the directory is busy, but config.ignoreBusy is set — continuing: ${(verdict.problems || []).join('; ')}`)
    warnings.push('the directory was busy; the run was started over it under config.ignoreBusy')
  } else {
    log('[busy] the directory is free')
  }
  if (checks.length !== resumePaths.length) {
    // One result per command is the contract. A different count means the results cannot be
    // matched to paths at all, and guessing which is which would reuse the wrong file.
    log(
      `[resume] ${checks.length} checks for ${resumePaths.length} paths — ` +
        `they cannot be matched, nothing is reused`,
    )
  } else {
    resumePaths.forEach((path, i) => {
      if (checks[i].ok) present.add(path)
    })
  }
  log(
    `[resume] already done: requirements=${present.has(REQ_PATH)} design=${present.has(DESIGN_PATH)}`,
  )

  // Starting the requirements over on top of somebody's finished run is the one ambiguous act
  // here, and it used to pass silently. Three intents, three different acts, none of them guessed
  // on the caller's behalf: the wrong guess is expensive in one direction and invisible in the
  // other.
  if (RUN_REQUIREMENTS && present.has(REQ_PATH) && !cfg.continue && !cfg.fresh) {
    throw new Error(
      `${run} already holds ${REQ_PATH} from an earlier run. ` +
        `A new run gets a new directory: python -X utf8 tools/newrun.py --base docs-runs --label <what>. ` +
        `To continue an interrupted run, config.continue=true. To rebuild here from scratch, config.fresh=true.`,
    )
  }
  // Rebuilding means rebuilding. Found by the wiring check: with `fresh` the old requirements.md
  // still counted as an unjudged draft, the first round skipped the writer, and "from scratch"
  // reviewed the previous document. Only this launch's own artifacts are forgotten: a design-only
  // rebuild still stands on the requirements it was given.
  if (cfg.fresh) {
    if (RUN_REQUIREMENTS) present.delete(REQ_PATH)
    if (RUN_REQUIREMENTS) present.delete(VOICE_PATH)
    if (RUN_DESIGN) present.delete(DESIGN_PATH)
    if (RUN_LENS) present.delete(PAIN_PATH)
    if (RUN_LENS) present.delete(STORY_PATH)
  }
}

// --- Panels: many fresh readers in one critic seat ------------------------------------------
//
// One reader checking fifty claims checks the first thirty and skims the rest, and one critic
// holding a fifteen-item checklist reads its first items closely. Both panels split the work so
// that every reader holds little: the claim panel lists every checkable claim once and hands them
// to fresh checkers in batches; the rule panel gives every top-tier rule of the profile its own
// checker in a clean context and lets a skeptic drop the false positives. Each panel returns a
// verdict like a critic, so the loop treats it as one.
const CLAIMS = {
  type: 'object',
  required: ['claims'],
  properties: {
    claims: {
      type: 'array',
      items: {
        type: 'object',
        required: ['id', 'where', 'text', 'cited'],
        properties: {
          id: { type: 'string', description: 'C1, C2, ... in document order' },
          where: { type: 'string', description: 'the row id or the section' },
          text: { type: 'string', description: 'the claim in the document\'s exact words' },
          cited: { type: 'string', description: 'the source the document cites, or "none cited"' },
        },
      },
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
          problem: { type: 'string', description: 'what the evidence says instead, quoted; empty when the claim holds' },
        },
      },
    },
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

// Evidence travels under one port name whatever it is: extracts, input documents, requirements.
const asEvidence = (ports) => ports.map((e) => ({ port: `evidence:${e.port.split(':').pop()}`, path: e.path }))

function claimPanel({ tag, artifact, evidence, brief }) {
  return {
    tag,
    agentType: 'claim-checker',
    run: async (loop, round, phaseName) => {
      const listed = await call(task({ inputs: [{ port: 'draft', path: artifact }], noFile: true, brief }), {
        agentType: 'claim-lister',
        model: MODELS.claims,
        label: `${loop}:${tag}:list:${round}`,
        phase: phaseName,
        schema: CLAIMS,
      })
      if (!listed) return noVerdict(`${tag} (claim-lister)`)
      const claims = listed.claims || []
      const batches = []
      for (let i = 0; i < claims.length; i += CLAIM_BATCH) batches.push(claims.slice(i, i + CLAIM_BATCH))
      log(`[${loop}/${round}/${tag}] claims=${claims.length} batches=${batches.length}`)
      const checked = await parallel(
        batches.map((batch, k) => () =>
          call(
            task({
              inputs: [{ port: 'draft', path: artifact }, ...evidence],
              noFile: true,
              brief,
              extra:
                `CLAIMS TO CHECK\n` +
                batch.map((c) => `${c.id} (${c.where}): "${c.text}" (cited: ${c.cited})`).join('\n'),
            }),
            {
              agentType: 'claim-checker',
              model: MODELS.claims,
              label: `${loop}:${tag}:check:${round}:${k + 1}`,
              phase: phaseName,
              schema: CHECKED,
            },
          ),
        ),
      )
      const remarks = []
      batches.forEach((batch, k) => {
        const got = checked[k]
        if (!got) {
          remarks.push(`[HIGH] claims ${batch[0].id} to ${batch[batch.length - 1].id} were not checked: the checker returned nothing`)
          return
        }
        const byId = new Map((got.results || []).map((r) => [r.id, r]))
        for (const c of batch) {
          const r = byId.get(c.id)
          if (!r) remarks.push(`[HIGH] ${c.where} — "${c.text}" — not checked: no result for ${c.id}`)
          else if (!r.holds) remarks.push(`[HIGH] ${c.where} — "${c.text}" — ${r.problem || 'does not hold against the evidence'}`)
        }
      })
      log(`[${loop}/${round}/${tag}] claims that do not hold or were not checked: ${remarks.length}`)
      return { verdict: remarks.length ? 'revise' : 'approved', remarks }
    },
  }
}

function rulePanel({ tag, profile, artifact, evidence, brief }) {
  let rules = null
  return {
    tag,
    agentType: 'rule-skeptic',
    run: async (loop, round, phaseName) => {
      if (rules === null) {
        const got = await call(
          commands([`${RULES_TOOL} --profile ${profile} --top ${noted(`top rules of ${profile}`)}`]) +
            `\n\nReturn the rules from measures.rules and the number from measures.count, unchanged.`,
          { agentType: 'gate-runner', model: MODELS.gate, label: `${loop}:${tag}:rules`, phase: phaseName, schema: RULES },
        )
        rules = got && Array.isArray(got.rules) && got.rules.length === got.count ? got.rules : []
        if (!rules.length) {
          log(`[${loop}/${tag}] the rules of ${profile} did not arrive whole: the rule panel is skipped`)
          warnings.push(`rule panel ${tag} skipped: the rules of ${profile} did not arrive whole`)
        }
      }
      if (!rules.length) return { verdict: 'approved', remarks: [] }
      const flagged = await parallel(
        rules.map((r) => () =>
          call(
            task({
              inputs: [{ port: 'draft', path: artifact }, ...evidence],
              noFile: true,
              brief,
              extra: `THE RULE\n${r.id}. [${r.severity}] ${r.text}`,
            }),
            {
              agentType: 'rule-checker',
              model: MODELS.rules,
              label: `${loop}:${tag}:rule-${r.id}:${round}`,
              phase: phaseName,
              schema: FLAGS,
            },
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
      log(`[${loop}/${round}/${tag}] rules=${rules.length} flags=${lines.length}`)
      if (!lines.length) return { verdict: 'approved', remarks: [] }
      const kept = await call(
        task({
          inputs: [{ port: 'draft', path: artifact }, ...evidence],
          noFile: true,
          brief,
          extra: `FLAGS\n` + lines.map((l, i) => `${i + 1}. ${l}`).join('\n'),
        }),
        { agentType: 'rule-skeptic', model: MODELS.rules, label: `${loop}:${tag}:skeptic:${round}`, phase: phaseName, schema: VERDICT },
      )
      return kept || noVerdict(`${tag} (rule-skeptic)`)
    },
  }
}

// --- The revision loop, as a function --------------------------------------------------------
//
// The whole shape of a revision round, parameterised. In the article pipeline this sits inlined
// once; here it runs twice, on two different documents with two different critics, and writing it
// twice would have meant two copies drifting apart after the first fix.
//
// What varies between the two uses is exactly the argument list: which file, which writer, which
// correctors, which critics, which bounds, which records directory. What does NOT vary is
// everything the loop was expensive to learn:
//
//   the ledger — one numbered list per round, one answer per number, verified against the numbers
//     the script handed over, because a writer with no place to say "I did not do this" silently
//     drops remarks and they come back word for word;
//   the length budget as arithmetic — a round told "you are 616 over" as item sixteen of sixteen
//     answered with nine thousand characters of good material, so the script says how much to
//     remove and forbids adding;
//   declined items travelling to the critics with the reason — a critic that does not know why a
//     remark was declined raises it again and the pair burns a round agreeing to disagree;
//   the stall detector — a round whose item set equals the previous round's will produce it again;
//   the plateau detector — two rounds that fail to beat the best result end the loop, and the best
//     result is recovered from disk so it is a property of the document, not of the launch.
async function reviseLoop({
  loop,
  artifact,
  bounds,
  gateFlags = [],
  phaseName,
  writer,
  correctors = [],
  critics,
  maxRounds = MAX_ROUNDS,
  // Commands run beside gate.py in the same round (quotes, ids, vocabulary): their problems join
  // the gate's, so the writer gets them in the same numbered list.
  extraChecks = [],
}) {
  const roundsDir = roundsDirOf(loop)

  let startRound = 1
  let carried = []
  let declinedNotes = []
  let previousItems = null
  let bestOpen = Infinity
  let bestRound = 0
  let sinceBest = 0
  // Per-critic state, in the order the critics were declared. A round's verdicts are what the
  // next round's item list is built from, so they have to survive a restart — and they do,
  // because each round is written to disk and read back here.
  let verdicts = critics.map((c) => null)
  let gateProblems = []
  let measured = 0
  // What the document measured when the previous round judged it. A revision loop with no ceiling
  // is a growth loop: every remark a critic raises is closed by specifying something, specifying
  // adds text, and nothing pushes back. Measured on a live design with the ceiling removed —
  // 37 595, then 50 633, then 73 978 characters of prose across three rounds, while the item count
  // went 11, 12, 8. Round 2 bought thirteen thousand characters and one extra remark.
  //
  // The script does not judge this, because it cannot: a specification that grew because it was
  // vague grew correctly. It measures and says so, in the log and in the round record, where a
  // person deciding whether to buy another round can see the price of the last one.
  let previousMeasured = 0

  // The rounds already judged, recovered from disk rather than from the process cache, for the
  // same reason as everything else here: the cache does not outlive the process. Without this,
  // `maxRounds` is a limit per launch instead of per document, and three restarts give nine
  // rounds where the caller allowed three.
  // A fresh rebuild starts at round 1 whatever the records say; the new records overwrite them.
  const recorded = cfg.fresh
    ? null
    : await call(
        commands([`${ROUNDS_TOOL} --dir ${roundsDir} --last-only ${noted(`how many ${loop} rounds are already done`)}`]),
        { agentType: 'gate-runner', model: MODELS.gate, label: `${loop}:resume-rounds`, phase: phaseName, schema: ROUNDS },
      )
  // Trusted only when it has the shape rounds.py prints: the report's own `rounds` count equals
  // the number of rounds returned AND the number of counts. A carrier that answered something else
  // — one invented a repository health report here — fails this and is announced, not believed.
  const roundsShape =
    recorded &&
    recorded.report &&
    recorded.report.measures &&
    typeof recorded.report.measures.rounds === 'number' &&
    Array.isArray(recorded.rounds) &&
    Array.isArray(recorded.counts) &&
    // --last-only lists the newest round alone; matched by its number, not by the list's length.
    recorded.rounds.length === 1 &&
    recorded.rounds[0].round === recorded.report.measures.last_round &&
    recorded.counts.length === recorded.report.measures.rounds
  if (recorded && recorded.report && !recorded.report.ok) {
    // A record that does not parse is not trusted into the loop: continuing from a guessed round
    // number would skip a revision the caller paid for.
    for (const problem of recorded.report.problems) {
      log(`[${loop}/resume] ROUND RECORDS ARE CORRUPT, not trusted: ${problem}`)
    }
    warnings.push(`round records of ${loop} are corrupt: ${recorded.report.problems.join('; ')}`)
  } else if (recorded && !roundsShape) {
    log(`[${loop}/resume] THE CARRIER'S ANSWER DOES NOT LOOK LIKE rounds.py OUTPUT — not trusted, counting 0 rounds`)
    warnings.push(`the carrier did not return a rounds.py report for ${loop}; rounds restarted from the first`)
  } else if (recorded && recorded.rounds && recorded.rounds.length) {
    const last = recorded.rounds[recorded.rounds.length - 1]
    startRound = last.round + 1
    // A critic that numbers its own list is not wrong to; the ledger is what must stay single.
    // A live round recorded `1. 1. …` and from the first item of the second critic the two
    // numbers disagreed — while the writer answers by number.
    verdicts = critics.map((c, i) =>
      i === 0
        ? { verdict: last.verdict, remarks: (last.remarks || []).map(unnumbered) }
        : { verdict: last.style_verdict, remarks: (last.style || []).map(unnumbered) },
    )
    gateProblems = last.gate || []
    carried = [...(last.remarks || []), ...(last.style || [])].map(unnumbered)
    log(
      `[${loop}/resume] rounds done ${recorded.rounds.length}, continuing from ${startRound}: ` +
        `verdicts=${verdicts.map((v) => (v && v.verdict) || 'unknown').join('/')}`,
    )

    // Records and snapshots of rounds a previous launch judged: declared as writing, the same
    // exception the audit makes for a draft snapshot. They were written for a person, this launch
    // does not open them, and without the declaration a resumed run reports correct files as
    // losses. An audit that cries wolf is an audit nobody reads.
    for (let n = 1; n < startRound; n++) {
      touched.add(roundPathOf(loop, n))
      touched.add(draftPathOf(loop, n))
    }

    // The plateau counts from the document, not from the launch. Measured live as 16, 12, 16, 12,
    // 16 where the detector should have stopped at the second 12: the first two rounds had been
    // judged in a previous process and their counts never reached the new one.
    for (const c of recorded.counts || []) {
      if (c.items < bestOpen) {
        bestOpen = c.items
        bestRound = c.round
        sinceBest = 0
      } else {
        sinceBest += 1
      }
    }
    if ((recorded.counts || []).length) {
      log(
        `[${loop}/resume] best result ${bestOpen} items in round ${bestRound}, ` +
          `rounds in a row without improvement: ${sinceBest}`,
      )
    }
  } else {
    log(`[${loop}/resume] no round records, starting from the first`)
  }

  // Measure a draft a previous launch left behind. Otherwise the first round of a resumed run
  // builds its revision block with no measurement — the gate of the round before it died with
  // that process — and the length budget goes missing exactly when the run is being continued
  // because the length was wrong.
  if (present.has(artifact) && startRound > 1) {
    const sized = await call(
      commands([gateCommand(artifact, bounds, `resume: size of the ${loop} draft found`, gateFlags)]),
      { agentType: 'gate-runner', model: MODELS.gate, label: `${loop}:resume-size`, phase: phaseName, schema: GATE },
    )
    if (sized && sized.report) {
      measured = (sized.report.measures && sized.report.measures.prose_chars) || 0
      gateProblems = sized.report.problems || []
      log(`[${loop}/resume] draft on disk: ${measured} prose characters, ${gateProblems.length} problems`)
    }
  }

  if (startRound > maxRounds) {
    log(`[${loop}] rounds used up by earlier launches (${startRound - 1} of ${maxRounds})`)
  }
  // A run that comes back onto a plateau should not buy one more round to rediscover it. The
  // detector inside the loop fires only after a round has been paid for; here the same verdict is
  // available before anything is spent, because the counts came off disk.
  const plateauAlready = startRound > 1 && sinceBest >= PLATEAU_ROUNDS
  if (plateauAlready) {
    log(
      `[${loop}] PLATEAU already reached by earlier launches: best result ${bestOpen} items ` +
        `in round ${bestRound}. No more rounds are bought.`,
    )
  }

  let rounds = startRound - 1
  let accepted = false

  for (let round = plateauAlready ? maxRounds + 1 : startRound; round <= maxRounds; round++) {
    rounds = round
    phase(phaseName)

    // Order of the revision block is the order of authority: the length budget, then what a regex
    // measured, then the critics. A writer that runs out of attention runs out of it on the last
    // section, so what cannot be argued with goes first.
    const overBy = bounds.max && measured ? measured - bounds.max : 0
    const underBy = bounds.min && measured ? bounds.min - measured : 0
    const budget =
      overBy > 0
        ? `LENGTH BUDGET. The draft measures ${measured} characters of readable prose against a ` +
          `ceiling of ${bounds.max}: it is ${overBy} over. This round must END SHORTER than it ` +
          `started — remove at least ${overBy} characters. Every other item below has to be ` +
          `satisfied by cutting, or by replacing text with something no longer. Adding a section ` +
          `is not available this round; if a remark cannot be honoured inside the budget, leave ` +
          `it and say which one.\n\n`
        : underBy > 0
          ? `LENGTH BUDGET. The draft measures ${measured} characters of readable prose against a ` +
            `floor of ${bounds.min}: it is ${underBy} short. Close the gap with substance the ` +
            `sources carry, not by restating what the document already says.\n\n`
          : ''

    const isFirstPass = round === 1 && startRound === 1
    const items = isFirstPass
      ? []
      : [
          ...carried.map((text) => ({ source: 'CARRIED', text })),
          ...gateProblems.map((text) => ({ source: 'GATE', text })),
          ...critics.flatMap((c, i) =>
            ((verdicts[i] && verdicts[i].remarks) || []).map((text) => ({ source: c.tag, text })),
          ),
        ]

    const ledgerRule = items.length
      ? `\n\nHOW TO ANSWER. Return one entry per numbered item above, and account for every ` +
        `number from 1 to ${items.length}. Status \`fixed\` when the draft now satisfies it, ` +
        `\`declined\` when you deliberately did not act — and then the note says why, in one ` +
        `sentence. Do not answer an item you did not act on with \`fixed\`: the next round is ` +
        `given whatever you leave open, and the run reports it.`
      : ''

    const approved = critics.filter((c, i) => verdicts[i] && verdicts[i].verdict === 'approved')
    const approvedBlock = approved.length
      ? `ALREADY APPROVED, and it has to stay approved: ${approved.map((c) => c.tag).join(' and ')}. ` +
        `Whatever you change now must leave it passing — make the smallest edit that answers the ` +
        `items below, and where a fix would disturb an approved axis, prefer the version that ` +
        `does not.\n\n`
      : ''

    const declinedBlock = declinedNotes.length
      ? `\n\nDECLINED LAST ROUND, with the reason given. Do not raise these again unless the ` +
        `reason is wrong; if it is wrong, say why.\n` +
        declinedNotes.map((d, i) => `${i + 1}. ${d}`).join('\n')
      : ''

    const revision = !items.length
      ? null
      : budget +
        approvedBlock +
        `REMARKS ON THE PREVIOUS DRAFT. GATE items are arithmetic and are not open to argument; ` +
        `everything else is a judgement you may decline with a reason.\n\n` +
        items.map((it, i) => `${i + 1}. [${it.source}] ${it.text}`).join('\n') +
        ledgerRule

    // A draft already on disk is a draft nobody has judged yet, and rewriting it from scratch
    // throws away the most expensive agent in the run. So the first round skips the writer and
    // goes straight to the gate and the critics.
    const skipWriter = isFirstPass && present.has(artifact)
    // Two ways to get a draft: from scratch the writer writes the file; in a revision round it
    // does NOT touch the draft but writes ONE edits file — a JSON list of {old, new} pairs, old
    // copied verbatim from the draft — and a ruler applies them. Measured before this existed: 72
    // single Edit calls in one round read 10 million cached tokens, more than rewriting the whole
    // document would have cost; one Write of the whole document re-types 90 KB to change 3 and
    // nothing checks what else moved. The ruler is deterministic and names every edit that did
    // not land, so nothing is applied on a guess and nothing is lost silently.
    const editsPath = `${roundsDir}/edits-${round}.json`
    const editsRule =
      `\n\nHOW TO DELIVER THIS ROUND. Do not edit ${artifact} yourself. Write your changes as a ` +
      `JSON array to ${editsPath}: [{"old": "<text copied verbatim from the draft, enough of it ` +
      `to occur exactly once>", "new": "<the replacement>"}, ...]. One object per change. To add ` +
      `a row, make old the row it goes after and new that row followed by the new one; to delete, ` +
      `make new an empty string. Keep old short but unique — a whole table row is usually right. ` +
      `A tool applies the list in order and reports every object whose old text was not found or ` +
      `was found more than once; those come back to you next round, so quote exactly.`
    let drafted = null
    let unapplied = []
    if (skipWriter) {
      log(`[${loop}/1] the draft is already on disk, the writer is not launched — straight to the gate and critics`)
    } else if (revision) {
      drafted = must(
        await call(
          task({
            inputs: [{ port: 'draft', path: artifact }, ...writer.inputs],
            output: editsPath,
            extra: revision + editsRule,
            brief: writer.brief,
          }),
          {
            agentType: writer.agentType,
            model: writer.model,
            label: `${loop}:write:${round}`,
            phase: phaseName,
            schema: DRAFT,
          },
        ),
        `${loop}:write:${round} — without an edits file the round is empty`,
      )
      const applied = await call(
        commands([`${APPLY_TOOL} --file ${artifact} --edits ${editsPath} ${noted(`apply the writer's round ${round} edits`)}`]),
        { agentType: 'file-copier', model: MODELS.copy, label: `${loop}:apply:${round}`, phase: phaseName, schema: GATE },
      )
      const appliedReport = (applied && applied.report) || {
        ok: false,
        problems: ['the edits were not applied — the tool did not answer'],
        measures: {},
      }
      const m = appliedReport.measures || {}
      log(
        `[${loop}/${round}/apply] applied=${m.applied ?? '?'} unmatched=${m.unmatched ?? '?'}` +
          (appliedReport.problems.length ? ` | ${appliedReport.problems.join('; ')}` : ''),
      )
      // An edit that did not land is a remark the writer has not honoured: carried, by name.
      unapplied = appliedReport.problems.map((pr) => `EDIT NOT APPLIED — quote the draft exactly: ${pr}`)
      if (!appliedReport.ok) {
        warnings.push(`round ${round} (${loop}): edits not applied — ${appliedReport.problems.length}`)
      }
    } else {
      drafted = must(
        await call(task({ inputs: writer.inputs, output: artifact, extra: revision, brief: writer.brief }), {
          agentType: writer.agentType,
          model: writer.model,
          label: `${loop}:write:${round}`,
          phase: phaseName,
          schema: DRAFT,
        }),
        `${loop}:write:${round} — without a draft the round is empty`,
      )
    }
    if (drafted) {
      log(`[${loop}/${round}] changes=${drafted.changes.length}`)
      for (const c of drafted.changes) log(`[${loop}/${round}/change] ${c}`)

      // The ledger, checked against the numbers the script itself handed over.
      const answered = new Map()
      for (const a of drafted.addressed || []) {
        if (a.item >= 1 && a.item <= items.length) answered.set(a.item, a)
      }
      const declined = []
      const unanswered = []
      for (let n = 1; n <= items.length; n++) {
        const entry = answered.get(n)
        if (!entry) {
          unanswered.push(items[n - 1])
          continue
        }
        log(`[${loop}/${round}/${entry.status}] ${n}. [${items[n - 1].source}] ${entry.note}`)
        if (entry.status === 'declined') declined.push(items[n - 1])
      }
      if (unanswered.length) {
        log(
          `[${loop}/${round}] UNANSWERED ${unanswered.length} of ${items.length} remarks — ` +
            `they go to the next round and to the report`,
        )
        for (const it of unanswered) log(`[${loop}/${round}/unanswered] [${it.source}] ${it.text}`)
      }
      declinedNotes = declined.map((it) => {
        const entry = [...answered.values()].find((a) => items[a.item - 1] === it)
        return `[${it.source}] ${it.text}\n    → declined: ${entry ? entry.note : '(no reason given)'}`
      })
      carried = [...unanswered, ...declined].map((it) => it.text).concat(unapplied)
    }

    // Correctors: a chain, not a fan-out. They edit the same file in turn, and turn is what makes
    // it safe — two agents writing one document concurrently already produced a draft whose
    // provenance could not be established. They run before the gate, so the measurement the
    // critics are told about is the measurement of the text that exists. They also run on a
    // draft found on disk: the launch that wrote it died before they could (writer at 16:58,
    // process gone at 17:00, nothing in between), and an unchecked draft judged by a critic
    // spends the critic's round on what a corrector settles.
    {
      for (const corrector of correctors) {
        const fixed = await call(task({ inputs: corrector.inputs, output: artifact, brief: corrector.brief }), {
          agentType: corrector.agentType,
          model: corrector.model,
          label: `${loop}:${corrector.tag}:${round}`,
          phase: phaseName,
          schema: corrector.schema || DRAFT,
        })
        log(
          fixed
            ? `[${loop}/${round}/${corrector.tag}] edits: ${(fixed.changes || []).length}`
            : `[${loop}/${round}/${corrector.tag}] DID NOT RUN — this layer of checking was skipped`,
        )
        if (!fixed) warnings.push(`${corrector.tag} did not run in round ${round} (${loop})`)
        for (const c of (fixed && fixed.changes) || []) {
          log(`[${loop}/${round}/${corrector.tag}/edit] ${c}`)
        }
      }
    }

    // The gate before the critics, always. What a regex settles must never cost a critic's round,
    // and the critics have to be judging the text that is actually on disk.
    const gated = await call(commands([gateCommand(artifact, bounds, `${loop} round ${round}`, gateFlags)]), {
      agentType: 'gate-runner',
      model: MODELS.gate,
      label: `${loop}:gate:${round}`,
      phase: phaseName,
      schema: GATE,
    })
    let gateReport = (gated && gated.report) || {
      ok: false,
      problems: ['the gate returned nothing — the draft was not measured'],
      measures: {},
    }
    // gate.py always prints `chars` for a file it found and `output missing` for one it did not.
    // A report with neither is not gate.py's, whatever it says about `ok`.
    const measuredShape =
      (gateReport.measures && typeof gateReport.measures.chars === 'number') ||
      (gateReport.problems || []).some((p) => String(p).startsWith('output missing'))
    if (!measuredShape) {
      gateReport = {
        ok: false,
        problems: ['the gate report carries no measurement — not trusted as a pass'],
        measures: {},
      }
    }
    previousMeasured = measured
    measured = (gateReport.measures && gateReport.measures.prose_chars) || 0
    gateProblems = gateReport.problems || []
    if (extraChecks.length) {
      const more = await call(commands(extraChecks), {
        agentType: 'gate-runner',
        model: MODELS.gate,
        label: `${loop}:checks:${round}`,
        phase: phaseName,
        schema: EXISTENCE,
      })
      const got = (more && more.checks) || []
      if (got.length !== extraChecks.length) gateProblems = [...gateProblems, 'the extra checks did not all report']
      gateProblems = [...gateProblems, ...got.flatMap((c) => c.problems || [])]
    }
    const grew = previousMeasured ? measured - previousMeasured : 0
    log(
      `[${loop}/${round}/gate] ok=${gateReport.ok} prose characters=${measured}` +
        (grew ? ` (${grew > 0 ? '+' : ''}${grew} against the previous round)` : '') +
        (gateProblems.length ? ` | ${gateProblems.join('; ')}` : ''),
    )

    // Acceptance looks at the file, not at whether an agent came back. A writer that died on the
    // session limit had written the file and not answered: the artifact exists, the result does
    // not.
    // The gate measured the file, so it also answers whether it is there: gate.py prints `chars`
    // for a file it read and `output missing` for one it did not. A separate existence call asked
    // the same question twice.
    const exists =
      typeof (gateReport.measures && gateReport.measures.chars) === 'number' &&
      gateReport.measures.chars >= MIN_ARTIFACT_CHARS
    if (!exists) {
      log(`[${loop}/${round}] NO DRAFT ON DISK — the round cannot be counted`)
      warnings.push(`in round ${round} (${loop}) the draft did not reach the disk`)
    }

    // The critics in parallel: neither reads the other's output, and a round costs the slower of
    // them instead of their sum.
    const judged = await parallel(
      critics.map((c) => () =>
        c.run
          ? c.run(loop, round, phaseName)
          : call(task({ inputs: c.inputs, noFile: true, extra: declinedBlock || undefined, brief: c.brief }), {
          agentType: c.agentType,
          model: c.model,
          label: `${loop}:${c.tag}:${round}`,
          phase: phaseName,
          schema: VERDICT,
        }),
      ),
    )
    verdicts = critics.map((c, i) => {
      const v = judged[i] || noVerdict(`${c.tag} (${c.agentType})`)
      v.remarks = (v.remarks || []).map(unnumbered)
      log(`[${loop}/${round}/${c.tag}] verdict=${v.verdict} remarks=${v.remarks.length}`)
      for (const r of v.remarks) log(`[${loop}/${round}/${c.tag}/remark] ${r}`)
      return v
    })

    // The round goes on the record before anything decides what to do with it. Written here
    // rather than at the end of the run on purpose: the point is to survive a process that dies
    // mid-loop, and a record written after the loop would die with it.
    //
    // The first critic's remarks go in the plain numbered list and the rest under `Style:`,
    // because that is the shape `rounds.py` reads back. Two buckets, not because these are
    // stylistic, but because the reader of the record needs to know which critic said what.
    const roundItems = [
      ...(verdicts[0] ? verdicts[0].remarks : []),
      ...critics.slice(1).flatMap((c, i) =>
        ((verdicts[i + 1] && verdicts[i + 1].remarks) || []).map((r) => `Style: ${r}`),
      ),
      ...gateProblems.map((p) => `Gate: ${p}`),
      ...carried.map((c) => `Carried: ${c}`),
    ]
    const secondVerdict = critics.length > 1 && verdicts[1] ? verdicts[1].verdict : 'approved'
    // The size and what it cost, in the heading, because the record is what outlives the run. The
    // question a person asks before buying another round is "what did the last one buy me", and
    // both halves of the answer — items closed, characters added — have to be in one line.
    const priceTag = grew ? ` prose=${measured} (${grew > 0 ? '+' : ''}${grew})` : ` prose=${measured}`
    const wroteRound = await call(
      record(
        roundPathOf(loop, round),
        `Round ${round} — verdict=${verdicts[0] ? verdicts[0].verdict : 'unknown'} style=${secondVerdict}${priceTag}`,
        roundItems,
      ),
      { agentType: 'verbatim-writer', model: MODELS.record, label: `${loop}:record:${round}`, phase: phaseName, schema: WROTE },
    )
    log(
      wroteRound && wroteRound.written
        ? `[${loop}/${round}] round recorded: ${roundPathOf(loop, round)} items=${roundItems.length}`
        : `[${loop}/${round}] ROUND NOT RECORDED — a restart will judge the document again`,
    )

    // The draft as it stood when this round judged it. The record keeps what the critics said;
    // this keeps what they said it about. Without it, "what actually changed between round 2 and
    // round 3" — the question worth asking when a loop stops converging — has no answer.
    touched.add(draftPathOf(loop, round))
    const copied = await call(
      commands([`${SNAPSHOT_TOOL} --file ${artifact} --to ${draftPathOf(loop, round)} ${noted(`draft snapshot of ${loop} round ${round}`)}`]),
      { agentType: 'file-copier', model: MODELS.copy, label: `${loop}:snapshot:${round}`, phase: phaseName, schema: GATE },
    )
    if (!(copied && copied.report && copied.report.ok)) {
      log(`[${loop}/${round}] no snapshot of the draft was taken — there will be nothing to compare rounds with`)
    }

    // Counted before the acceptance check, not after. With the accounting below the break, the
    // accepted round never became the best one, and `best_round` is exactly what a person reads
    // to find the draft snapshot worth keeping.
    if (roundItems.length < bestOpen) {
      bestOpen = roundItems.length
      bestRound = round
      sinceBest = 0
    } else {
      sinceBest += 1
      log(
        `[${loop}/${round}] no better than the best so far: ${roundItems.length} items against ` +
          `${bestOpen} in round ${bestRound} (rounds in a row without improvement: ${sinceBest})`,
      )
    }

    // All conditions at once. A document every critic likes but that overruns its budget, and one
    // inside its budget that a critic rejects, are equally unfinished.
    const allApproved = verdicts.every((v) => v && v.verdict === 'approved')
    if (allApproved && gateReport.ok && exists) {
      accepted = true
      log(`[${loop}/${round}] ACCEPTED: all critics approved, the gate is clean, the file is on disk`)
      break
    }

    if (sinceBest >= PLATEAU_ROUNDS) {
      log(
        `[${loop}/${round}] PLATEAU: ${sinceBest} rounds in a row did not improve the result. The loop has ` +
          `done its part — the rest is for the author to decide, and it is in the report.`,
      )
      break
    }

    const signature = JSON.stringify(roundItems.slice().sort())
    if (previousItems === signature) {
      log(
        `[${loop}/${round}] THE LOOP IS STUCK: the remark set matches the previous round ` +
          `(${roundItems.length} items). More rounds will not help.`,
      )
      break
    }
    previousItems = signature
  }

  const open = [
    ...(verdicts[0] ? verdicts[0].remarks : []),
    ...critics.slice(1).flatMap((c, i) => (verdicts[i + 1] && verdicts[i + 1].remarks) || []),
    ...gateProblems,
    ...carried,
  ]
  log(
    `[${loop}] rounds done ${rounds}, accepted=${accepted}, ` +
      `best round ${bestRound} with ${bestOpen === Infinity ? '?' : bestOpen} items, open ${open.length}`,
  )
  return { rounds, accepted, open, bestRound, bestOpen: bestOpen === Infinity ? null : bestOpen, measured, verdicts }
}

// --- Extract: the fan-out width comes off the disk -------------------------------------------
//
// The archetype's first real difference from the article pipeline. There, the fan-out width was
// known before anything ran, because the aspects came out of the brief. Here the sources are files
// somebody put in a directory, and the script cannot read a directory — so the first thing that
// happens is a listing, and everything downstream is shaped by its answer.
//
// This is also why the listing carries a count: the width of everything below depends on a list
// that arrives through an agent, and a carrier that silently returns three of five documents would
// cost two extracts nobody notices are missing.
let sources = []
// Inputs the inventory marked as our own notes: never quoted as the client.
const ourNotes = []
let extractPorts = []
let requirements = null

if (RUN_REQUIREMENTS) {
  phase('Extract')
  // One inventory of the whole tree is the list of what gets read. A subfolder is part of the
  // input: a call folder with its transcript and screen frames was once listed by name in a
  // warning and never read, because only the top level went to the extractors.
  const inventory = await call(
    commands([`${INTAKE_TOOL} --dir ${INPUTS_DIR} ${noted('inventory of the whole input tree')}`]),
    { agentType: 'gate-runner', model: MODELS.gate, label: 'inputs:intake', phase: 'Extract', schema: INTAKE },
  )
  const files = (inventory && inventory.files) || []
  if (inventory && typeof inventory.count === 'number' && inventory.count !== files.length) {
    throw new Error(
      `the inventory of ${INPUTS_DIR} counted ${inventory.count} files, but only ${files.length} arrived through ` +
        `the agent. The pipeline must not be built on an incomplete list: a lost document is a requirement ` +
        `that will be missing from the result, and nobody can notice it later.`,
    )
  }
  if (!files.length) {
    throw new Error(
      `${INPUTS_DIR} holds no input documents. This pipeline has nothing to extract from — ` +
        `put in the request, the transcript, the correspondence or the RFP, and launch again.`,
    )
  }
  const IMAGE = /\.(png|jpe?g|gif|webp)$/i
  const AUDIO_VIDEO = /\.(mp4|mov|mkv|avi|webm|mp3|wav|m4a|ogg)$/i
  const OFFICE = /\.(docx|pptx|odt|rtf|epub)$/i
  const dirOf = (rel) => (rel.includes('/') ? rel.slice(0, rel.lastIndexOf('/')) : '')
  const listedPaths = new Set(files.map((f) => f.path))
  const kindOf = new Map(files.map((f) => [f.path, f.kind]))
  const unique = files.filter((f) => {
    // A file cannot repeat itself; a duplicate names another file of the inventory.
    if (!f.duplicate_of || f.duplicate_of === f.path || !listedPaths.has(f.duplicate_of)) return true
    log(`[extract/inventory] duplicate, not read twice: ${f.path} = ${f.duplicate_of}`)
    // Accounted for: the audit counts a file the inventory chose not to read as read, not as lost.
    touched.add(`${INPUTS_DIR}/${f.path}`)
    return false
  })
  for (const f of unique.filter((f) => AUDIO_VIDEO.test(f.path))) {
    log(`[extract/inventory] audio or video cannot be read: ${f.path} — put its transcript next to it`)
    warnings.push(`not read: ${f.path} is audio or video; a transcript next to it would be read`)
    touched.add(`${INPUTS_DIR}/${f.path}`)
  }
  // A Word file that already has its markdown twin is read through the twin.
  let docs = unique
    .map((f) => f.path)
    .filter((rel) => !IMAGE.test(rel) && !AUDIO_VIDEO.test(rel))
    .filter((rel) => !(OFFICE.test(rel) && listedPaths.has(`${rel}.md`)))

  // Office documents become markdown before anyone reads them: the extracting agent reads with
  // Read, and Read refuses a .docx. The tool takes the folder, never a file name, and writes
  // <name>.docx.md next to each; the script knows those names without asking for them.
  const office = docs.filter((rel) => OFFICE.test(rel))
  if (office.length) {
    const converted = await call(
      commands([`${TO_TEXT_TOOL} --dir ${INPUTS_DIR} --recursive ${noted('office documents to markdown')}`]),
      { agentType: 'file-copier', model: MODELS.copy, label: 'inputs:to-text', phase: 'Extract', schema: GATE },
    )
    const report = (converted && converted.report) || { ok: false, problems: ['the conversion did not report'] }
    for (const pr of report.problems || []) {
      log(`[extract/word] ${pr}`)
      warnings.push(`an input document was not converted to text: ${pr}`)
    }
    // A problem that names a file fails that file; any other (pandoc missing, no report) fails all,
    // so no agent is ever handed a .md that was never written.
    const problems = report.problems || []
    const perFile = problems.every((pr) => office.some((o) => pr.startsWith(`${o}:`)))
    const allFailed = !converted || (!report.ok && !perFile)
    docs = docs.map((rel) => {
      if (!office.includes(rel)) return rel
      touched.add(`${INPUTS_DIR}/${rel}`)
      if (allFailed || problems.some((pr) => pr.startsWith(`${rel}:`))) return rel
      kindOf.set(`${rel}.md`, kindOf.get(rel))
      log(`[extract/word] ${rel} → ${rel}.md`)
      return `${rel}.md`
    })
  }

  // One document is often saved in several formats (transcript.html, .md and .txt side by side).
  // They are not byte-identical, so the duplicate check misses them, and three extracts of one
  // transcript would bring every requirement in three times. Files with the same name in the same
  // folder are versions of one document; one is read, by this preference.
  const FORMAT_RANK = ['.md', '.txt', '.docx.md', '.pptx.md', '.odt.md', '.rtf.md', '.pdf', '.html', '.htm']
  const formatOf = (rel) => FORMAT_RANK.find((ext) => rel.toLowerCase().endsWith(ext)) || rel.slice(rel.lastIndexOf('.'))
  const baseOf = (rel) => rel.slice(0, rel.length - formatOf(rel).length)
  const rankOf = (rel) => {
    const r = FORMAT_RANK.indexOf(formatOf(rel))
    return r < 0 ? FORMAT_RANK.length : r
  }
  const chosen = new Map()
  for (const rel of docs) {
    const key = baseOf(rel)
    const held = chosen.get(key)
    if (!held || rankOf(rel) < rankOf(held)) chosen.set(key, rel)
  }
  for (const rel of docs) {
    if (chosen.get(baseOf(rel)) !== rel) {
      log(`[extract/inventory] another format of ${chosen.get(baseOf(rel))}, not read twice: ${rel}`)
      touched.add(`${INPUTS_DIR}/${rel}`)
    }
  }
  docs = docs.filter((rel) => chosen.get(baseOf(rel)) === rel)

  // Images travel with the document they belong to: a folder of screen frames goes, as one
  // folder, to the extractor of the document in the same folder, or in the folder above it (a
  // call folder holding transcript.md and frames/). An image with no document near it is read on
  // its own.
  const imageDirsOf = new Map()
  const images = unique.map((f) => f.path).filter((rel) => IMAGE.test(rel))
  for (const dir of [...new Set(images.map(dirOf))]) {
    // Only inside a subfolder: the top level holds unrelated documents, and an image there, or a
    // folder of images whose parent is the top level, does not belong to any one of them.
    // The client's document first: frames of a call belong to its transcript, not to our digest.
    const near = (folder) => {
      const here = docs.filter((rel) => dirOf(rel) === folder)
      return here.find((rel) => kindOf.get(rel) === 'client') || here[0]
    }
    const companion = !dir ? undefined : near(dir) || (dirOf(dir) ? near(dirOf(dir)) : undefined)
    if (companion) {
      const folder = dir ? `${INPUTS_DIR}/${dir}` : INPUTS_DIR
      imageDirsOf.set(companion, [...(imageDirsOf.get(companion) || []), folder])
      // The extractor reads the folder, so its images are read through it.
      for (const rel of images.filter((r) => dirOf(r) === dir)) touched.add(`${INPUTS_DIR}/${rel}`)
      log(`[extract/images] ${dir || '(top level)'} goes with ${companion}`)
    } else {
      for (const rel of images.filter((r) => dirOf(r) === dir)) docs.push(rel)
      log(`[extract/images] ${dir || '(top level)'}: no document beside it, each image is read on its own`)
    }
  }
  if (!docs.length) {
    throw new Error(`${INPUTS_DIR} holds no readable document: only duplicates, audio or video.`)
  }

  sources = docs.map((rel) => `${INPUTS_DIR}/${rel}`)
  const imagesOf = new Map(docs.map((rel) => [`${INPUTS_DIR}/${rel}`, imageDirsOf.get(rel) || []]))
  for (const rel of docs) {
    if (kindOf.get(rel) === 'ours') {
      ourNotes.push(`${INPUTS_DIR}/${rel}`)
      log(`[extract/inventory] our own note, not the client's words: ${rel}`)
    }
    if (kindOf.get(rel) === 'unknown') log(`[extract/inventory] unclear whose document this is: ${rel}`)
  }
  log(`[extract] input documents: ${sources.length}`)
  for (const src of sources) log(`[extract/input] ${src}`)

  // Matched by index, never by a path the agent chose how to spell.
  const extractPaths = sources.map((s) => extractPathOf(stemOf(s)))
  // Two more rules per extract, both paid for: every row of its tables has a Source cell (the
  // writer cannot cite what the extract did not locate), and it is written in the script of its
  // source — a Russian chat extracted in English put English role descriptions into a Russian
  // stakeholder table, and the critic found it, not the gate.
  const extractFlags = (extractPath) => {
    const i = extractPaths.indexOf(extractPath)
    // Extracts are written by the one agent that reads the client's raw material; injected
    // instructions carried into an extract would reach every agent downstream.
    // The language check needs the source's path on the command line; a name outside ASCII cannot
    // travel there, so that one extract is checked without it and the log says so.
    const ascii = /^[\x20-\x7e]*$/.test(sources[i])
    if (!ascii) log(`[extract] language not checked for ${sources[i]}: the file name is not ASCII`)
    const language = ascii ? `--language-of "${sources[i]}"` : ''
    return `${EXTRACT_SHAPE} ${language} --forbid-file library/style/forbid/injection.txt`
  }

  // What is already extracted is not extracted again. The disk is the checkpoint here as
  // everywhere: a launch that resumed after the writer re-extracted all five documents although
  // every extract was on disk and had passed this same gate. `fresh` is the one way to redo them.
  let todo = sources
  if (!cfg.fresh) {
    const already = await call(
      existenceCommands(extractPaths, 'resume: which extracts are already on disk', extractFlags),
      { agentType: 'gate-runner', model: MODELS.gate, label: 'extract:resume', phase: 'Extract', schema: EXISTENCE },
    )
    const found = (already && already.checks) || []
    if (found.length === extractPaths.length) {
      todo = sources.filter((s, i) => !found[i].ok)
      const kept = sources.length - todo.length
      if (kept) log(`[extract] ${kept} of ${sources.length} extracts are already on disk, only the missing ones are redone`)
      for (const [i, s] of sources.entries()) if (found[i].ok) touched.add(extractPaths[i])
    } else {
      log(`[extract] ${found.length} checks for ${extractPaths.length} paths — they cannot be matched, extracting everything`)
    }
  }

  // One agent per document, in parallel, each writing one extract. `pipeline` rather than
  // `parallel` because there is nothing to synchronise: a document that finishes early has no
  // reason to wait for the slowest one.
  const extracted = await pipeline(todo, (source) => {
    const stem = stemOf(source)
    return call(
      task({
        inputs: [{ port: 'source', path: source }, ...(imagesOf.get(source) || []).map((d) => ({ port: 'images', path: d }))],
        output: extractPathOf(stem),
        extra: ourNotes.includes(source)
          ? `OUR NOTE\nThis document is our own note, not the client's words. Set trust_level to low and ` +
            `say so in the header; a row that only this note supports is our reading.`
          : undefined,
      }),
      {
        agentType: 'source-processor',
        model: MODELS.extract,
        label: `extract:${stem}`,
        phase: 'Extract',
        schema: EXTRACT,
      },
    ).then((res) => ({ stem, source, res }))
  })

  const checks = await call(existenceCommands(extractPaths, 'was the extract actually written', extractFlags), {
    agentType: 'gate-runner',
    model: MODELS.gate,
    label: 'extract:verify',
    phase: 'Extract',
    schema: EXISTENCE,
  })
  const results = (checks && checks.checks) || []
  if (results.length !== extractPaths.length) {
    log(`[extract] ${results.length} checks for ${extractPaths.length} paths — they cannot be matched`)
    warnings.push('extracts not checked against the disk: the number of checks did not match the number of paths')
    extractPorts = extractPaths.map((p, i) => ({ port: `extract:${stemOf(sources[i])}`, path: p }))
  } else {
    extractPorts = []
    extractPaths.forEach((p, i) => {
      if (results[i].ok) {
        extractPorts.push({ port: `extract:${stemOf(sources[i])}`, path: p })
      } else {
        // A document whose extract never appeared is a document that will not be in the
        // requirements, and that has to be visible while the run is watched rather than
        // discovered in the result. The run continues: one lost extract out of five is worth
        // less than throwing away the four that worked.
        log(`[extract] NO EXTRACT for ${sources[i]}: ${results[i].problems.join('; ')}`)
        warnings.push(`document ${sources[i]} produced no extract — its content did not reach the requirements`)
      }
    })
  }
  for (const e of extracted) {
    if (!e || !e.res) continue
    log(`[extract/${e.stem}] facts=${(e.res.facts || []).length} questions=${(e.res.open_questions || []).length}`)
  }
  log(`[extract] extracts on disk: ${extractPorts.length} of ${sources.length}`)

  // One extract lost out of five is worth less than throwing away the four that worked. All of
  // them lost is a different thing: the writer would be handed no material at all, and it would
  // either invent a requirements document or die — and in a live run it died three stages later,
  // after the run had already paid for the resume, the listing and two rounds of setup.
  //
  // The likely cause is named because it recurs and looks like nothing else: the registry of agent
  // types is snapshotted once per human turn, so an agent generated in the same turn as the launch
  // is not callable yet, however correct its file is.
  if (!extractPorts.length) {
    const died = extracted.filter((e) => !e || !e.res).length
    throw new Error(
      `not one extract from ${sources.length} input documents — the requirements writer ` +
        `has nothing to read, there is no point going on. Agents that did not answer: ${died}. ` +
        `If the agents were built in this same turn, the registry sees them only from the next ` +
        `human message: build, wait for the next message, launch.`,
    )
  }

  // --- The client's voice: what they said, how much it weighed, the words they use ---------------
  //
  // Before the requirements, because the weight of a requirement comes from here. On one live run
  // "losing the connection is rare" reached the design without "rare", and the design built an
  // offline store; the drafts said "appointment" where the client said "visit". Warnings, not a stop: the requirements
  // can still be written from the extracts, only without the sheet.
  phase('Voice')
  const voiced = await call(
    task({
      inputs: [...sources.map((s) => ({ port: `source:${stemOf(s)}`, path: s })), ...extractPorts],
      output: VOICE_PATH,
      brief: ORDER_BLOCK,
      extra: ourNotes.length
        ? `OUR NOTES, NOT THE CLIENT'S WORDS\n${ourNotes.map((n) => `- ${n}`).join('\n')}`
        : '',
    }),
    { agentType: 'client-voice', model: MODELS.voice, label: 'voice', phase: 'Voice', schema: WROTE },
  )
  let voicePort = []
  if (!voiced || !voiced.written) {
    warnings.push('the client voice sheet was not written: requirement weights come from the extracts only')
    log('[voice] the sheet was not written — the requirements are written without it')
  } else {
    const vgate = await call(
      commands([
        gateCommand(VOICE_PATH, null, 'client voice gate', VOICE_GATE_FLAGS),
        `${QUOTES_TOOL} --file ${VOICE_PATH} --source ${EXTRACTS_DIR} --source ${INPUTS_DIR} ${noted('client voice quotes')}`,
      ]),
      { agentType: 'gate-runner', model: MODELS.gate, label: 'voice:gate', phase: 'Voice', schema: EXISTENCE },
    )
    const vchecks = (vgate && vgate.checks) || []
    const vproblems = vchecks.flatMap((c) => c.problems || [])
    if (vchecks.length !== 2) vproblems.push('the check of the client voice sheet did not return two reports')
    log(`[voice/gate] ok=${!vproblems.length}${vproblems.length ? ' | ' + vproblems.join('; ') : ''}`)
    for (const pr of vproblems) warnings.push(`client voice sheet: ${pr}`)
    voicePort = [{ port: 'client_voice', path: VOICE_PATH }]
    present.add(VOICE_PATH)
  }
  // Our notes reach the extracts marked; the requirements loop is told which extracts they are.
  const noteStems = ourNotes.map((n) => stemOf(n))
  const notesBlock = noteStems.length
    ? `OUR NOTES, NOT THE CLIENT'S WORDS\nThese extracts come from our own notes: ` +
      noteStems.map((st) => `extract:${st}`).join(', ') +
      `. A row that rests on them alone is our interpretation: an assumption in 8.3, never a client statement.`
    : ''
  const voiceBrief = [ORDER_BLOCK, voicePort.length ? VOICE_NOTE : '', notesBlock].filter(Boolean).join('\n\n')
  const factBrief = [ORDER_BLOCK, notesBlock].filter(Boolean).join('\n\n')

  // --- Requirements: the first revision loop -------------------------------------------------
  requirements = await reviseLoop({
    loop: 'req',
    artifact: REQ_PATH,
    bounds: REQ_BOUNDS,
    gateFlags: REQ_GATE_FLAGS,
    phaseName: 'Requirements',
    writer: {
      agentType: 'requirements-writer',
      model: MODELS.reqWrite,
      inputs: [...extractPorts, ...voicePort],
      brief: voiceBrief,
    },
    correctors: [
      {
        // Between the writer and the critic, so a figure that drifted from its source is fixed
        // before the critic ever judges the draft. Anything a corrector can settle should never
        // become a remark: a critic can only report it, and reporting costs a round.
        tag: 'factcheck',
        agentType: 'requirements-fact-checker',
        model: MODELS.reqFix,
        inputs: [{ port: 'draft', path: REQ_PATH }, ...extractPorts],
        brief: factBrief,
      },
    ],
    critics: [
      {
        tag: 'REQUIREMENTS',
        agentType: 'requirements-critic',
        model: MODELS.reqCritic,
        inputs: [{ port: 'draft', path: REQ_PATH }, ...extractPorts, ...voicePort],
        brief: voiceBrief,
      },
      // No slop critic here: the requirements are an internal document, judged on completeness,
      // traceability and weight. Wording is judged where the client reads, after the proposal.
      ...(CLAIM_CHECK ? [claimPanel({ tag: 'CLAIMS', artifact: REQ_PATH, evidence: asEvidence(extractPorts), brief: voiceBrief })] : []),
      ...(RULE_PANEL
        ? [rulePanel({ tag: 'RULES', profile: REQ_PROFILE, artifact: REQ_PATH, evidence: asEvidence(extractPorts), brief: voiceBrief })]
        : []),
    ],
  })

  if (!RUN_DESIGN && !RUN_DISCOVERY) {
    // Before the handoff record, so the record carries the warning if the file was not written.
    await recordUnresolved(
      requirements.open.map((o) => `Requirements: ${o}`),
      requirements.accepted,
    )
  }
  await recordHandoff()
  const { orphans: reqOrphans, foreign: reqForeign } = await auditRun()
  if (!RUN_DESIGN && !RUN_DISCOVERY) {
    log(`[summary/requirements] next: the same directory with config.stages=["design"] or ["discovery"]`)
    return {
      stages: STAGES,
      inputs: sources,
      extracts: extractPorts.map((e) => e.path),
      requirements: REQ_PATH,
      client_voice: voicePort.length ? VOICE_PATH : null,
      rounds: requirements.rounds,
      accepted: requirements.accepted,
      open_items: requirements.open.length,
      unresolved: requirements.open.length ? UNRESOLVED_PATH : null,
      orphans: reqOrphans,
      other_stage: reqForeign,
      warnings,
    }
  }
}

// --- Client edition: the documents the client reads -------------------------------------------
//
// The traceable versions are the record: a Source cell on every row, tags, notes on how our own
// materials were weighed. One live run published those, and they were rewritten by hand into
// editions a quarter and two fifths of the length, with ids renumbered through a map. This stage
// is that rewrite: requirements first, because the design edition applies the map it leaves.
if (RUN_CLIENT) {
  phase('Client')
  const needed = [REQ_PATH, DESIGN_PATH].filter((p) => !present.has(p))
  if (needed.length) {
    throw new Error(
      `the client edition needs accepted ${needed.join(' and ')}, and they are missing. First ` +
        `config.stages=["requirements","design"] in this same directory, then read the result, then client.`,
    )
  }
  const EDITION = {
    type: 'object',
    required: ['written', 'unplaced'],
    properties: {
      written: { type: 'boolean' },
      unplaced: {
        type: 'array',
        items: { type: 'string' },
        description: 'traceable ids that have no place in the edition or the id map; empty when complete',
      },
    },
  }
  const reqEdition = await call(
    task({
      inputs: [
        { port: 'traceable', path: REQ_PATH },
        { port: 'extracts', path: EXTRACTS_DIR },
        ...(present.has(VOICE_PATH) ? [{ port: 'client_voice', path: VOICE_PATH }] : []),
      ],
      output: REQ_CLIENT_PATH,
      brief: ORDER_BLOCK,
      extra:
        `ID MAP\nAlso write ${ID_MAP_PATH}: one JSON object from every traceable id to its client id, ` +
        `as the profile's Numbering section says.`,
    }),
    { agentType: 'client-editor', model: MODELS.client, label: 'client:requirements', phase: 'Client', schema: EDITION },
  )
  touched.add(ID_MAP_PATH)
  if (!reqEdition || !reqEdition.written) {
    throw new Error(
      `the client edition of the requirements was not written — the design edition cannot be made without the id map: ` +
        `its references to requirements would drift apart. Launch the client stage again.`,
    )
  }
  const designEdition = await call(
    task({
      inputs: [
        { port: 'traceable', path: DESIGN_PATH },
        { port: 'requirements_edition', path: REQ_CLIENT_PATH },
        { port: 'id_map', path: ID_MAP_PATH },
        { port: 'extracts', path: EXTRACTS_DIR },
        ...(present.has(VOICE_PATH) ? [{ port: 'client_voice', path: VOICE_PATH }] : []),
      ],
      output: DESIGN_CLIENT_PATH,
      brief: DESIGN_BRIEF,
    }),
    { agentType: 'client-editor', model: MODELS.client, label: 'client:design', phase: 'Client', schema: EDITION },
  )
  const editions = [
    { path: REQ_CLIENT_PATH, what: 'requirements', result: reqEdition, ids: CLIENT_ID_FLAGS },
    { path: DESIGN_CLIENT_PATH, what: 'design', result: designEdition, ids: [] },
  ]
  for (const e of editions) {
    for (const id of (e.result && e.result.unplaced) || []) warnings.push(`client edition (${e.what}): ${id} lost`)
  }
  // One slop check per edition and, where it says revise, one correction pass by the same editor.
  // No loop: the traceable versions already went through rounds; what is left is wording.
  if (SLOP_CRITIC) {
    const voiceIn = present.has(VOICE_PATH) ? [{ port: 'client_voice', path: VOICE_PATH }] : []
    const judged = await parallel(
      editions.map((e) => () =>
        call(task({ inputs: [{ port: 'draft', path: e.path }, ...voiceIn], noFile: true, brief: ORDER_BLOCK }), {
          agentType: 'slop-critic',
          model: MODELS.slop,
          label: `client:slop:${e.what}`,
          phase: 'Client',
          schema: VERDICT,
        }),
      ),
    )
    for (const [i, e] of editions.entries()) {
      const v = judged[i]
      if (!v) {
        warnings.push(`client edition (${e.what}): the generated-text (slop) check did not come back`)
        continue
      }
      log(`[client/slop] ${e.what}: verdict=${v.verdict} remarks=${(v.remarks || []).length}`)
      if (v.verdict !== 'revise' || !(v.remarks || []).length) continue
      const fixed = await call(
        task({
          inputs: [{ port: 'draft', path: e.path }, { port: 'extracts', path: EXTRACTS_DIR }, ...voiceIn],
          output: e.path,
          extra:
            `SLOP REMARKS\nFix each numbered remark in ${e.path} by Edit, in batches. Change wording only: ` +
            `no requirement, number, quote or id moves.\n\n` +
            v.remarks.map((r, n) => `${n + 1}. ${r}`).join('\n'),
        }),
        { agentType: 'client-editor', model: MODELS.client, label: `client:slop-fix:${e.what}`, phase: 'Client', schema: EDITION },
      )
      if (!fixed) warnings.push(`client edition (${e.what}): the slop remarks were not fixed`)
    }
  }
  // Two commands per edition, matched by index: the gate, then the quotes against the extracts.
  const gated = await call(
    commands(
      editions.flatMap((e) => [
        gateCommand(e.path, null, `client edition gate: ${e.what}`, [...CLIENT_GATE_FLAGS, ...e.ids]),
        `${QUOTES_TOOL} --file ${e.path} --source ${EXTRACTS_DIR} ${noted(`client edition quotes: ${e.what}`)}`,
      ]),
    ),
    { agentType: 'gate-runner', model: MODELS.gate, label: 'client:gate', phase: 'Client', schema: EXISTENCE },
  )
  const checks = (gated && gated.checks) || []
  editions.forEach((e, i) => {
    const pair = [checks[2 * i], checks[2 * i + 1]]
    if (pair.some((c) => !c)) {
      warnings.push(`client edition (${e.what}): the check did not come back`)
      return
    }
    const problems = pair.flatMap((c) => c.problems || [])
    log(`[client/gate] ${e.what}: ok=${pair.every((c) => c.ok)}${problems.length ? ' | ' + problems.join('; ') : ''}`)
    for (const pr of problems) warnings.push(`client edition (${e.what}): ${pr}`)
  })
  await recordHandoff()
  const { onDisk: cOnDisk, orphans: cOrphans, foreign: cForeign } = await auditRun()
  log(`[summary/client] ${REQ_CLIENT_PATH}, ${DESIGN_CLIENT_PATH}; warnings: ${warnings.length}`)
  return {
    stages: STAGES,
    requirements_client: REQ_CLIENT_PATH,
    design_client: designEdition && designEdition.written ? DESIGN_CLIENT_PATH : null,
    id_map: ID_MAP_PATH,
    files_on_disk: cOnDisk.length,
    files_read_by_agents: touched.size,
    orphans: cOrphans,
    other_stage: cForeign,
    warnings,
  }
}

// --- Client lens and proposal: the documents that speak to the client ----------------------
//
// One proposal read as being about the client's business because of its order, not its
// technology: their own words first, then a day of the person who will use the product, then the
// one mechanism their trust depended on, and only then how it is built. That was done by hand
// over sixteen revisions. The lens stage writes the two documents it rested on (a pain map: does
// the solution remove what hurts; a day story: the product through the main user's eyes), and the
// proposal stage writes the proposal from them. proposal-review.js then reviews it in rounds.
if (RUN_LENS || RUN_PROPOSAL) {
  phase('Lens')
  const needed = [REQ_PATH, DESIGN_PATH].filter((pth) => !present.has(pth))
  if (needed.length) {
    throw new Error(
      `the lens and proposal stages need accepted ${needed.join(' and ')}, and they are missing. First ` +
        `config.stages=["requirements","design"] in this same directory, read the result, then lens.`,
    )
  }
  touched.add(REQ_PATH)
  touched.add(DESIGN_PATH)
  const docs = [
    { port: 'requirements', path: REQ_PATH },
    { port: 'design', path: DESIGN_PATH },
  ]
  const extractsIn = [{ port: 'extracts', path: EXTRACTS_DIR }]

  // The voice sheet comes from the requirements stage; a run that predates it writes it here,
  // from the input folder and the extracts on disk.
  if (!present.has(VOICE_PATH)) {
    const voiced = await call(
      task({
        inputs: [{ port: 'sources', path: INPUTS_DIR }, ...extractsIn],
        output: VOICE_PATH,
        brief: ORDER_BLOCK,
      }),
      { agentType: 'client-voice', model: MODELS.voice, label: 'lens:voice', phase: 'Lens', schema: WROTE },
    )
    const vgate = await call(
      commands([
        gateCommand(VOICE_PATH, null, 'client voice gate', VOICE_GATE_FLAGS),
        `${QUOTES_TOOL} --file "${VOICE_PATH}" --source "${EXTRACTS_DIR}" --source "${INPUTS_DIR}" ${noted('client voice quotes')}`,
      ]),
      { agentType: 'gate-runner', model: MODELS.gate, label: 'lens:voice-gate', phase: 'Lens', schema: EXISTENCE },
    )
    const vchecks = (vgate && vgate.checks) || []
    for (const pr of vchecks.flatMap((c) => c.problems || [])) warnings.push(`client voice: ${pr}`)
    if (voiced && voiced.written && vchecks[0] && vchecks[0].ok) present.add(VOICE_PATH)
  }
  if (!present.has(VOICE_PATH)) {
    throw new Error(
      `the lens stage needs ${VOICE_PATH}, and it could not be written or did not pass its gate. ` +
        `Read the log above, then launch the stage again.`,
    )
  }
  touched.add(VOICE_PATH)
  const voiceIn = [{ port: 'client_voice', path: VOICE_PATH }]
  const lensBrief = [ORDER_BLOCK, VOICE_NOTE].filter(Boolean).join('\n\n')
  const lensGate = (n) => [
    ...Array.from({ length: n }, (_, i) => `--require-heading "^##\\s+${i + 1}\\."`),
    ...SLOP_FLAGS,
    '--forbid-file library/style/forbid/no-bold.txt',
    '--forbid "\\x60"',
  ]
  const traceCheck = (pth) =>
    `${TRACE_TOOL} --file "${pth}" --against "${REQ_PATH}" --against "${DESIGN_PATH}" ${noted(`ids cited by ${pth}`)}`
  const vocabCheck = (pth) => `${VOCAB_TOOL} --file "${pth}" --voice "${VOICE_PATH}" ${noted(`client vocabulary in ${pth}`)}`
  const lensCritics = (pth) => [
    {
      tag: 'LENS',
      agentType: 'lens-critic',
      model: MODELS.lensCritic,
      inputs: [{ port: 'draft', path: pth }, ...voiceIn, ...docs, ...extractsIn],
      brief: lensBrief,
    },
    ...(SLOP_CRITIC
      ? [{ tag: 'SLOP', agentType: 'slop-critic', model: MODELS.slop, inputs: [{ port: 'draft', path: pth }, ...voiceIn], brief: lensBrief }]
      : []),
  ]

  let pain = null
  let story = null
  if (RUN_LENS) {
    pain = await reviseLoop({
      loop: 'pain',
      artifact: PAIN_PATH,
      bounds: { minLength: 1500 },
      gateFlags: lensGate(4),
      phaseName: 'Lens',
      writer: { agentType: 'pain-mapper', model: MODELS.lens, inputs: [...voiceIn, ...docs, ...extractsIn], brief: lensBrief },
      critics: lensCritics(PAIN_PATH),
      extraChecks: [
        `${QUOTES_TOOL} --file "${PAIN_PATH}" --source "${EXTRACTS_DIR}" --source "${INPUTS_DIR}" ${noted('pain map quotes')}`,
        traceCheck(PAIN_PATH),
        vocabCheck(PAIN_PATH),
      ],
    })
    present.add(PAIN_PATH)
    story = await reviseLoop({
      loop: 'story',
      artifact: STORY_PATH,
      bounds: { minLength: 2500 },
      gateFlags: lensGate(4),
      phaseName: 'Lens',
      writer: {
        agentType: 'story-writer',
        model: MODELS.lens,
        inputs: [...voiceIn, { port: 'pain_map', path: PAIN_PATH }, ...docs],
        brief: lensBrief,
      },
      critics: lensCritics(STORY_PATH),
      extraChecks: [traceCheck(STORY_PATH), vocabCheck(STORY_PATH)],
    })
    present.add(STORY_PATH)
  }

  let proposalReport = null
  if (RUN_PROPOSAL) {
    phase('Proposal')
    const missing = [PAIN_PATH, STORY_PATH].filter((pth) => !present.has(pth))
    if (missing.length) {
      throw new Error(`the proposal needs ${missing.join(' and ')}: run config.stages=["lens"] first.`)
    }
    touched.add(PAIN_PATH)
    touched.add(STORY_PATH)
    const wrote = await call(
      task({
        inputs: [
          ...docs,
          ...voiceIn,
          { port: 'pain_map', path: PAIN_PATH },
          { port: 'day_story', path: STORY_PATH },
          ...(present.has(DISCOVERY_PATH) ? [{ port: 'discovery', path: DISCOVERY_PATH }] : []),
          ...extractsIn,
        ],
        output: PROP_PATH,
        brief: DESIGN_BRIEF,
      }),
      { agentType: 'proposal-writer', model: MODELS.proposal, label: 'proposal:write', phase: 'Proposal', schema: WROTE },
    )
    if (!wrote) warnings.push('the proposal writer returned nothing')
    // The proposal profile's mechanical rules; the reviewing rounds are proposal-review.js.
    const gated = await call(
      commands([
        gateCommand(PROP_PATH, null, 'proposal gate', [
          ...Array.from({ length: 9 }, (_, i) => `--require-heading "^##\\s+${i + 1}\\."`),
          '--figures-numbered',
          '--section-refs',
          '--no-empty-cells --empty-cells-allow "cost|rate|price"',
          '--forbid-outside-quotes "\\byou\\b" --forbid-outside-quotes "\\byour\\b"',
          '--forbid-file library/style/forbid/no-bold.txt',
          ...SLOP_FLAGS,
        ]),
        `${QUOTES_TOOL} --file "${PROP_PATH}" --source "${EXTRACTS_DIR}" --source "${INPUTS_DIR}" ${noted('proposal quotes')}`,
        vocabCheck(PROP_PATH),
      ]),
      { agentType: 'gate-runner', model: MODELS.gate, label: 'proposal:gate', phase: 'Proposal', schema: EXISTENCE },
    )
    const checks = (gated && gated.checks) || []
    const problems = checks.flatMap((c) => c.problems || [])
    if (checks.length !== 3) problems.push('the proposal gates did not all report')
    proposalReport = { ok: !problems.length, problems }
    log(`[proposal/gate] ok=${!problems.length}${problems.length ? ' | ' + problems.join('; ') : ''}`)
    for (const pr of problems) warnings.push(`proposal: ${pr}`)
    log(
      `[proposal] next: proposal-review.js with document=${PROP_PATH}, sources=["${INPUTS_DIR}"], ` +
        `voice=${VOICE_PATH}, to review it in rounds before the author reads it`,
    )
  }

  const open = [
    ...(pain ? pain.open.map((o) => `Pain map: ${o}`) : []),
    ...(story ? story.open.map((o) => `Day story: ${o}`) : []),
  ]
  await recordUnresolved(open, Boolean((pain ? pain.accepted : true) && (story ? story.accepted : true)))
  await recordHandoff()
  const { onDisk: lOnDisk, orphans: lOrphans, foreign: lForeign } = await auditRun()
  return {
    stages: STAGES,
    client_voice: VOICE_PATH,
    pain_map: pain ? PAIN_PATH : present.has(PAIN_PATH) ? PAIN_PATH : null,
    day_story: story ? STORY_PATH : present.has(STORY_PATH) ? STORY_PATH : null,
    proposal: RUN_PROPOSAL ? PROP_PATH : null,
    proposal_gate_ok: proposalReport ? proposalReport.ok : null,
    rounds: { pain: pain ? pain.rounds : null, story: story ? story.rounds : null },
    unresolved: open.length ? UNRESOLVED_PATH : null,
    files_on_disk: lOnDisk.length,
    orphans: lOrphans,
    other_stage: lForeign,
    warnings,
  }
}

// --- The requirements exist, whoever produced them --------------------------------------------
//
// A launch that runs only the design stage never saw the loop above, so it asks the disk instead
// of assuming. Same rule as everywhere: acceptance looks at the file.
if (!RUN_REQUIREMENTS) {
  // The startup check already measured requirements.md; asking the disk again cost a carrier call.
  if (!present.has(REQ_PATH)) {
    throw new Error(
      `the design stage needs ${REQ_PATH}, and it is missing. First run config.stages=["requirements"] ` +
        `in the same directory.`,
    )
  }
  touched.add(REQ_PATH)
  log('[design] requirements found on disk')
}

// --- Discovery: the questions the requirements leave open --------------------------------------
//
// Two agents: one mines the requirements for gaps, contradictions and unstated trade-offs, the
// second cuts what is generic or already answered and writes the list a client can be asked.
// Needs nothing but requirements.md, so it runs after the design by default and on its own as
// `config.stages: ["discovery"]` — a requirements document straight from a client workshop can
// be turned into the next workshop's agenda without a design in between.
async function runDiscovery() {
  phase('Discovery')
  const probed = await call(
    task({ inputs: [{ port: 'requirements', path: REQ_PATH }], output: `${run}/probe-questions.md` }),
    { agentType: 'arch-probe', model: MODELS.probe, label: 'discovery:probe', phase: 'Discovery', schema: PROBE },
  )
  if (!probed) {
    log('[discovery] the probe did not run — there will be no questions for the client')
    warnings.push('the discovery stage produced no questions: the probe did not run')
    return null
  }
  log(`[discovery] candidate questions: ${(probed.questions || []).length}`)
  const curated = await call(
    task({
      inputs: [
        { port: 'draft', path: `${run}/probe-questions.md` },
        { port: 'requirements', path: REQ_PATH },
      ],
      output: DISCOVERY_PATH,
    }),
    { agentType: 'arch-critic', model: MODELS.discovery, label: 'discovery:curate', phase: 'Discovery', schema: PROBE },
  )
  log(
    curated
      ? `[discovery] questions after curation: ${(curated.questions || []).length} → ${DISCOVERY_PATH}`
      : `[discovery] curation did not run — only the candidates remain`,
  )
  if (!curated) {
    warnings.push('questions for the client were not curated: the curating agent did not run')
    return null
  }

  // The same deterministic check the other two documents get. No revision loop here: the
  // curator IS the critic of this document, and a second judge over a question list would
  // argue about taste. What a regex settles is settled here and named in the log.
  const gated = await call(
    commands([gateCommand(DISCOVERY_PATH, null, 'discovery questions', DISCOVERY_GATE_FLAGS)]),
    { agentType: 'gate-runner', model: MODELS.gate, label: 'discovery:gate', phase: 'Discovery', schema: GATE },
  )
  const report = (gated && gated.report) || { ok: false, problems: ['the gate returned nothing'], measures: {} }
  log(`[discovery/gate] ok=${report.ok}${report.problems.length ? ' | ' + report.problems.join('; ') : ''}`)
  for (const pr of report.problems) warnings.push(`questions for the client: ${pr}`)
  return curated
}

// Discovery alone: the requirements are on disk (checked just above), no design is asked for.
if (!RUN_DESIGN) {
  const found = await runDiscovery()
  await recordUnresolved([], true)
  await recordHandoff()
  const { onDisk: dOnDisk, orphans: dOrphans, foreign: dForeign } = await auditRun()
  log(`[summary/discovery] questions for the client: ${found ? (found.questions || []).length : 0}`)
  return {
    stages: STAGES,
    requirements: REQ_PATH,
    discovery: found ? DISCOVERY_PATH : null,
    questions: found ? (found.questions || []).length : 0,
    files_on_disk: dOnDisk.length,
    files_read_by_agents: touched.size,
    orphans: dOrphans,
    other_stage: dForeign,
    warnings,
  }
}

// --- Contest: two models design the same requirements ----------------------------------------
//
// The archetype's second difference. One design from one model is one reading of the requirements,
// and there is no way to tell a strong reading from a weak one without a second to compare it to.
// So both are produced, a selector picks, and what the losers did better travels to the winner
// rather than being thrown away.
phase('Contest')
const candidates = await parallel(
  CONTEST_MODELS.map((model, i) => () =>
    call(task({ inputs: [{ port: 'requirements', path: REQ_PATH }], output: candidatePathOf(i + 1), brief: DESIGN_BRIEF }), {
      agentType: 'solution-designer',
      model,
      label: `design:candidate:${i + 1}`,
      phase: 'Contest',
      schema: DRAFT,
    }),
  ),
)
const candidatePaths = CONTEST_MODELS.map((m, i) => candidatePathOf(i + 1))
const candidateChecks = await call(
  existenceCommands(candidatePaths, 'was the candidate design written'),
  { agentType: 'gate-runner', model: MODELS.gate, label: 'design:candidates-verify', phase: 'Contest', schema: EXISTENCE },
)
const candidateResults = (candidateChecks && candidateChecks.checks) || []
const alive = []
if (candidateResults.length !== candidatePaths.length) {
  log(`[contest] ${candidateResults.length} checks for ${candidatePaths.length} paths — they cannot be matched`)
  warnings.push('candidates not checked against the disk: the number of checks did not match the number of paths')
  candidatePaths.forEach((p, i) => alive.push({ n: i + 1, path: p, model: CONTEST_MODELS[i] }))
} else {
  candidatePaths.forEach((p, i) => {
    if (candidateResults[i].ok) {
      alive.push({ n: i + 1, path: p, model: CONTEST_MODELS[i] })
    } else {
      log(`[contest] candidate ${i + 1} (${CONTEST_MODELS[i]}) not written: ${candidateResults[i].problems.join('; ')}`)
      warnings.push(`candidate ${i + 1} from model ${CONTEST_MODELS[i]} did not reach the disk`)
    }
  })
}
log(`[contest] candidates on disk: ${alive.length} of ${CONTEST_MODELS.length}`)
if (!alive.length) {
  throw new Error('no candidate was written — there is nothing to choose from, this run produced no design')
}

// --- Choose: by number, never by path --------------------------------------------------------
let winner = alive[0]
let borrow = []
if (alive.length === 1) {
  log(`[choose] only one candidate (${winner.model}) — no choice needed`)
} else {
  const choice = await call(
    task({
      inputs: alive.map((c) => ({ port: `candidate:${c.n}`, path: c.path })),
      noFile: true,
      brief: DESIGN_BRIEF,
      extra:
        `The candidates are numbered as their ports are: ${alive.map((c) => c.n).join(', ')}. ` +
        `Return the number of the one to carry forward.`,
    }),
    {
      agentType: 'solution-design-selector',
      model: MODELS.select,
      label: 'design:select',
      phase: 'Contest',
      schema: SELECTION,
    },
  )
  const picked = choice && alive.find((c) => c.n === choice.winner)
  if (!picked) {
    // The fallback the template asks for. A selector that returns a number nobody offered has not
    // chosen, and taking the first candidate is the honest default — with a warning, because
    // "nobody chose" and "the first one won" must not read the same afterwards.
    log(`[choose] no choice returned or the number is out of range — taking the first (${winner.model})`)
    warnings.push('the agent chose no winner: the first candidate was taken by the fallback rule')
  } else {
    winner = picked
    borrow = choice.borrow || []
    log(`[choose] candidate ${winner.n} (${winner.model}) won: ${choice.reason}`)
    for (const b of borrow) log(`[choose/borrow-from-losers] ${b}`)
  }
}

// The winner becomes the design draft, copied by a tool rather than by an agent rewriting it.
// Both paths were named by the script, so this is a copy and not a question; and a rewrite here
// would mean the refinement loop starts from something no critic has seen.
const copiedWinner = await call(
  commands([`${SNAPSHOT_TOOL} --file ${winner.path} --to ${DESIGN_PATH} ${noted('the winning candidate becomes the draft')}`]),
  { agentType: 'file-copier', model: MODELS.copy, label: 'design:promote', phase: 'Contest', schema: GATE },
)
if (!(copiedWinner && copiedWinner.report && copiedWinner.report.ok)) {
  throw new Error(
    `could not copy the winner ${winner.path} to ${DESIGN_PATH}: ` +
      `${copiedWinner && copiedWinner.report ? copiedWinner.report.problems.join('; ') : 'the tool did not answer'}`,
  )
}
touched.add(DESIGN_PATH)
present.add(DESIGN_PATH)
log(`[design] the design draft is ready from candidate ${winner.n}`)

// --- Design: the second revision loop, same machinery ----------------------------------------
const borrowBlock = borrow.length
  ? `WHAT THE OTHER CANDIDATES DID BETTER. The selector kept this design and named these as the ` +
    `losing candidates' advantages. Take what applies:\n` +
    borrow.map((b, i) => `${i + 1}. ${b}`).join('\n')
  : ''

const design = await reviseLoop({
  loop: 'design',
  artifact: DESIGN_PATH,
  bounds: DESIGN_BOUNDS,
  gateFlags: DESIGN_GATE_FLAGS,
  phaseName: 'Design',
  writer: {
    agentType: 'solution-designer',
    model: MODELS.design,
    inputs: [
      { port: 'requirements', path: REQ_PATH },
      { port: 'draft', path: DESIGN_PATH },
    ],
    brief: DESIGN_BRIEF,
  },
  critics: [
    {
      tag: 'DESIGN',
      agentType: 'solution-design-critic',
      model: MODELS.designCritic,
      inputs: [
        { port: 'draft', path: DESIGN_PATH },
        { port: 'requirements', path: REQ_PATH },
      ],
      brief: DESIGN_BRIEF,
    },
    ...(SLOP_CRITIC
      ? [
          {
            tag: 'SLOP',
            agentType: 'slop-critic',
            model: MODELS.slop,
            inputs: [
              { port: 'draft', path: DESIGN_PATH },
              ...(present.has(VOICE_PATH) ? [{ port: 'client_voice', path: VOICE_PATH }] : []),
            ],
            brief: DESIGN_BRIEF,
          },
        ]
      : []),
    ...(CLAIM_CHECK
      ? [claimPanel({ tag: 'CLAIMS', artifact: DESIGN_PATH, evidence: asEvidence([{ port: 'requirements', path: REQ_PATH }]), brief: DESIGN_BRIEF })]
      : []),
    ...(RULE_PANEL
      ? [rulePanel({ tag: 'RULES', profile: DESIGN_PROFILE, artifact: DESIGN_PATH, evidence: asEvidence([{ port: 'requirements', path: REQ_PATH }]), brief: DESIGN_BRIEF })]
      : []),
  ],
})

if (borrowBlock) log(`[design] items borrowed from the losing candidates: ${borrow.length}`)

// --- Discovery: what the design could not answer ----------------------------------------------
//
// Not a fix for anything — the archetype's own output. A design built from an internal discussion
// always rests on things nobody stated, and the useful form of that is a list of questions to put
// in front of the client rather than an assumption buried in a section. Two agents: one mines the
// requirements for gaps, the second cuts what is generic or already answered.
let discovery = null
if (RUN_DISCOVERY) discovery = await runDiscovery()

// --- Gate: the record of what stayed open -----------------------------------------------------
phase('Gate')
const openItems = [
  ...(requirements ? requirements.open.map((o) => `Requirements: ${o}`) : []),
  ...design.open.map((o) => `Design: ${o}`),
]
await recordUnresolved(openItems, design.accepted)

await recordHandoff()
const { onDisk, orphans, foreign } = await auditRun()

log(
  `[summary] requirements=${Boolean(requirements || present.has(REQ_PATH))} design=${design.accepted ? 'accepted' : 'with remarks'} ` +
    `design rounds=${design.rounds} open=${openItems.length} warnings=${warnings.length}`,
)

return {
  stages: STAGES,
  inputs: sources,
  extracts: extractPorts.map((e) => e.path),
  requirements: REQ_PATH,
  client_voice: present.has(VOICE_PATH) ? VOICE_PATH : null,
  requirements_rounds: requirements ? requirements.rounds : null,
  requirements_accepted: requirements ? requirements.accepted : null,
  contest_models: CONTEST_MODELS,
  candidates: candidatePaths,
  winner: { candidate: winner.n, model: winner.model },
  design: DESIGN_PATH,
  design_rounds: design.rounds,
  design_accepted: design.accepted,
  design_best_round: design.bestRound,
  design_prose_chars: design.measured,
  discovery: discovery ? DISCOVERY_PATH : null,
  unresolved: openItems.length ? UNRESOLVED_PATH : null,
  open_items: openItems.length,
  files_on_disk: onDisk.length,
  files_read_by_agents: touched.size,
  orphans,
  other_stage: foreign,
  warnings,
}
