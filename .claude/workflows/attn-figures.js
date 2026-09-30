// Illustrate an article that is already written: plan the figures it needs, render them with
// the figgybanana CLI, look at what came out, redraw what failed.
//
// The drawing itself is not ours. figgybanana runs its own five-agent pipeline per figure
// (retriever, planner, stylist, visualizer, vision critic), and this script only commissions
// it and judges the result. Two model slots are set explicitly on every call:
//
//   --vlm-provider claude_code --vlm-model sonnet      planner and stylist
//   --critic-vlm-provider kimi --critic-vlm-model k3   the vision critic only
//
// Kimi K3 sits in the critic slot on purpose. It is the slot that looks at the rendered image,
// which is what its vision is wanted for, and the Kimi-for-Coding quota is small — spending it
// on the critic alone stretches it about three times further than putting Kimi on every agent.
// Whether Kimi answers is checked once before the first render (tools/preflight.py); if it does
// not, the run goes without the two critic flags. If its quota runs out later, figgybanana
// switches the critic to claude_code sonnet itself and prints who judged each image.
//
// Images go through ss_gateway and nowhere else. A 401 from the gateway means its bridge has no
// token in the Windows keychain (fix: open "SS AI Setup", press Apply) — it is not a reason to
// reach for a public image key, and silently switching providers is how a run stops testing
// what it was built to test.
//
// Every string in this file is English, including the ones only a person reads. The machinery
// is English; the document is in whatever language its sources were, and a script that mixes the
// two gives a model one more reason to switch language halfway through a run.
//
// The language of the labels is NOT a constant here. It used to be — the script said "the article
// is Russian" in three places, because the first three documents it drew for were. Then it drew
// an English client-facing page and produced Russian labels, one of them rendered as noise. The
// plan step now reports the document's language and every later task is told it.

export const meta = {
  name: 'attn-figures',
  description: 'Figures for a finished article through figgybanana, with a separate vision critic',
  phases: [
    { title: 'Preflight', detail: 'which critic answers; the temp directory in long form' },
    { title: 'Plan', detail: 'which figures the article needs, placeholders into the text' },
    { title: 'Draw', detail: 'figgybanana, one run per figure' },
    { title: 'Look', detail: 'read the PNGs with our own eyes against the captions' },
    { title: 'Redraw', detail: 'redraw what failed, with the defects attached' },
    { title: 'Gate', detail: 'deterministic file count' },
  ],
}

const run = typeof args === 'string' ? args : args && args.runDir
if (!run) {
  throw new Error('a run directory is required: args.runDir, e.g. probe-runs/figures')
}
// The article to illustrate comes from a previous run; nothing here writes to it. Required
// rather than defaulted: the default used to name one particular old run, so a caller who
// forgot the argument got figures drawn for somebody else's article and no error to say so.
// A missing path is a question, and the script asks it instead of guessing.
const source = args && args.articlePath
if (!source) {
  throw new Error('нужен путь к статье: args.articlePath — тот файл, к которому рисуем')
}
// A count, not a path: this one is a policy default and belongs here.
const wanted = (args && args.figures) || 3
const MAX_REDRAWS = 2
// The width of the copy that ships with the article. The render itself is 4K and stays in the
// tool's run directory for redraws; a page gets this.
const FIGURE_WIDTH = (args && args.figureWidth) || 2000

// The vision critic is a parameter, not a sentence in a prompt: `args.critic` is
// { provider, model } or the string 'none' (the CLI then judges with claude_code sonnet).
// Kimi K3 by default, for the reasons in the header — but only after the Preflight phase has seen
// it answer one image. On the Vista run both keys were dead (401, then 429) and every figure went
// out "Critic satisfied" unreviewed. Now: no answer in preflight, no Kimi flags at all; an answer
// in preflight and a quota that runs out later, and figgybanana itself switches to claude_code for
// the rest of the run and prints who judged each image.
const critic = (args && args.critic) || { provider: 'kimi', model: 'k3' }
let CRITIC_FLAGS =
  critic === 'none' ? '' : `  --critic-vlm-provider ${critic.provider} --critic-vlm-model ${critic.model} \\\n`
let CRITIC_NAME = critic === 'none' ? 'claude_code sonnet (no separate critic)' : `${critic.provider} ${critic.model}`
// Several candidates per render, and a choice by our own check. One render per figure, repaired
// by continue-run, was the most expensive habit of the Vista run: 80 renders for 9 figures,
// because continuing regenerates the whole picture from text and breaks what was already right.
// Fresh runs with three candidates were what converged.
const CANDIDATES = (args && args.candidates) || 3
// One look for every figure of a document. Passed into every brief, so figures drawn in
// different runs still look like one set.
const STYLE =
  (args && args.style) ||
  'Clean flat vector style: white rounded cards with a soft shadow, one consistent line-icon set, ' +
    'soft pastel accents (blue, teal, amber, coral, violet), generous spacing, one sans-serif font, ' +
    'crisp legible labels, no logos, no people, no decorative background.'

// Every path is named by the script. `run_dir` is the one exception the agents report back,
// because the CLI stamps it with a timestamp the script has no way to know.
// In place when the document lives directly in the run directory, whatever it is called —
// article.md from the article pipeline, design.md from the design pipeline. The writer already
// put the placeholders into the text, so the figures belong next to it; drawing into a side
// directory left the original with five dangling figures/ links, patched by hand with a
// junction once. In place, the plan step writes nothing at all.
const IN_PLACE = source.startsWith(`${run}/`) && !source.slice(run.length + 1).includes('/')
const ARTICLE_PATH = IN_PLACE ? source : `${run}/article.md`
const FIGURES_DIR = `${run}/figures`
const WORK_DIR = `${run}/figures-work`
const MANIFEST_PATH = `${FIGURES_DIR}/manifest.json`
// Both paths are absolute and both are needed. figgybanana resolves `guidelines_path` and
// `reference_set_path` relative to the current directory, and we run its CLI from this
// repository, not from its own — so the defaults `data/guidelines` and `data/reference_sets`
// point at directories that do not exist here. The guidelines being missing is visible (a
// thin stylist prompt); the reference set being missing is not: the retriever simply returns
// `retrieved_examples: []` and the pipeline proceeds ungrounded. The first run drew all three
// figures that way.
//
// The blog pair, not the conference one: `reference_sets_blog` holds the two etalon diagrams
// the blog style guide was synthesised from, and pairing the guide with a different corpus
// would pull the stylist and the retriever in two directions.
//
// Where figgybanana lives is not written here. A workflow script has no access to the
// environment, so the shell resolves it: `$FIGGYBANANA_HOME` if set, otherwise derived from
// `$PAPERBANANA_BIN`, which already points inside that repository
// (`…/figgybanana/.venv/Scripts/paperbanana.exe`). Hardcoding an absolute path would tie the
// script to one machine and put a home directory into a public repository.
const GUIDELINES = '$FIGGY/data/guidelines/blog'
const REFERENCE_SET = '$FIGGY/data/reference_sets_blog'

const PLAN = {
  type: 'object',
  required: ['figures', 'language'],
  properties: {
    // Named in English (Russian, English, German), read off the document itself. Every worded
    // label on every figure is in this language, and so is the brief the illustrator writes.
    language: {
      type: 'string',
      description: 'the language the document is written in, named in English: Russian, English, …',
    },
    figures: {
      type: 'array',
      minItems: 1,
      items: {
        type: 'object',
        required: ['slug', 'caption', 'why', 'section', 'kind'],
        properties: {
          kind: {
            type: 'string',
            enum: ['exact', 'screen', 'illustration'],
            description:
              'exact: its value is which box connects to which, in what order or on which week ' +
              '(sequence, component, deployment, state, flow, timeline); screen: a product screen ' +
              'or panel whose numbers, counts and words the text relies on (items on a plan, a ' +
              'price list, a banner, a disclaimer); illustration: a scene or a hero picture whose ' +
              'value is the look',
          },
          slug: { type: 'string', description: 'latin, hyphenated, the filename without .png' },
          caption: { type: 'string', description: 'the caption from the placeholder, verbatim' },
          why: { type: 'string', description: 'what the figure explains better than a paragraph' },
          section: { type: 'string', description: 'the heading of the section it stands after' },
        },
      },
    },
  },
}

const DRAWN = {
  type: 'object',
  required: ['done', 'failed', 'gateway_ok'],
  properties: {
    done: {
      type: 'array',
      items: {
        type: 'object',
        required: ['slug', 'critic_provider', 'run_dir', 'iterations'],
        properties: {
          slug: { type: 'string' },
          critic_provider: { type: 'string', description: 'kimi or claude_code — who judged it' },
          run_dir: { type: 'string', description: 'the CLI run directory, which the CLI named' },
          iterations: { type: 'number' },
        },
      },
    },
    failed: {
      type: 'array',
      items: {
        type: 'object',
        required: ['slug', 'reason'],
        properties: { slug: { type: 'string' }, reason: { type: 'string' } },
      },
    },
    gateway_ok: {
      type: 'boolean',
      description: 'did the image gateway answer; false on a 401 or a missing token',
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
        // `labels_seen` is not decoration: the first run returned ok with zero defects for
        // three figures, two of which carried English prose in a Russian article. A verdict
        // is cheap to rubber-stamp; an enumeration of every label on the image is not, and it
        // forces the reading that the verdict was supposed to rest on.
        required: ['slug', 'labels_seen', 'ok', 'defects'],
        properties: {
          slug: { type: 'string' },
          labels_seen: {
            type: 'array',
            items: { type: 'string' },
            description: 'EVERY label on the image verbatim, including small and sub-figure ones',
          },
          ok: { type: 'boolean', description: 'is the figure fit for the article as it stands' },
          defects: {
            type: 'array',
            items: { type: 'string' },
            description: 'what exactly is wrong; each one usable as an instruction to redraw',
          },
        },
      },
    },
  },
}

const PREFLIGHT = {
  type: 'object',
  required: ['report', 'stdout'],
  properties: {
    report: {
      type: 'object',
      required: ['ok', 'problems', 'measures', 'critic'],
      properties: {
        ok: { type: 'boolean' },
        problems: { type: 'array', items: { type: 'string' } },
        measures: { type: 'object' },
        critic: { type: 'string', enum: ['kimi', 'claude_code'] },
      },
    },
    stdout: { type: 'string' },
  },
}

const GATE = {
  type: 'object',
  required: ['report', 'stdout'],
  properties: {
    report: {
      type: 'object',
      required: ['ok', 'problems', 'measures'],
      properties: {
        ok: { type: 'boolean' },
        problems: { type: 'array', items: { type: 'string' } },
        measures: { type: 'object' },
      },
    },
    stdout: { type: 'string' },
  },
}

// The environment block every CLI call needs, spelled out once. Every line here was paid for
// with a failed live run.
//
// `pwd -W`, not `$PWD`. In Git Bash `$PWD` is the POSIX form `/c/Users/...`, and a TEMP in
// that form is a path Windows cannot resolve. PowerShell then fails to start, and the gateway
// bridge reads its tokens through PowerShell — so all eight come back empty, the bridge builds
// 3 headers instead of 11, and the gateway answers 401. The whole thing reads exactly like
// expired credentials and is not: it is one wrong-shaped path. Cost: an hour and a wrong
// diagnosis handed to the user.
//
// The temp dir must also sit inside the working directory, or the vision critic cannot read
// the image it is meant to judge and reviews the description instead; and it must be in long
// form, because a segment like `ACHIRI~1` is refused as a "suspicious Windows path pattern"
// and the critic again declares itself satisfied having seen nothing.
//
// KIMI_BASE_URL is exported because the CLI reads figgybanana's own .env relative to the
// current directory, and we are not running in that directory.
const ENV_BLOCK =
  `mkdir -p ${WORK_DIR}/tmp ${FIGURES_DIR}\n` +
  `export WINROOT="$(pwd -W)"   # Windows form; the POSIX form breaks PowerShell\n` +
  // Three statements, not one: bash expands every word of an `export` BEFORE it assigns any of
  // them, so `export TMPDIR=x TEMP="$TMPDIR"` hands TEMP the OLD value of TMPDIR — empty in a
  // fresh shell. Measured on the smoke run: it printed `TEMP=` and the gateway bridge failed
  // three times in a row, which is exactly the 401 this block exists to prevent.
  `export TMPDIR="$WINROOT/${WORK_DIR}/tmp"\n` +
  `export TEMP="$TMPDIR"\n` +
  `export TMP="$TMPDIR"\n` +
  `export KIMI_BASE_URL="\${KIMI_BASE_URL:-https://api.kimi.com/coding/v1}"\n` +
  // The key from the user environment, not the session's copy: a session keeps the environment it
  // started with, and on 28.09 it still carried a replaced key that answered 401 while the one in
  // the registry worked. Never printed.
  `UKEY="$(powershell.exe -NoProfile -Command "[Environment]::GetEnvironmentVariable('MOONSHOT_API_KEY','User')" 2>/dev/null | tr -d '\\r')"\n` +
  `[ -n "$UKEY" ] && export MOONSHOT_API_KEY="$UKEY"; unset UKEY\n` +
  `FIGGY="\${FIGGYBANANA_HOME:-$(echo "$PAPERBANANA_BIN" | tr '\\\\\\\\' '/' | ` +
  `sed 's#/[.]venv/Scripts/paperbanana.exe$##')}"\n` +
  `test -d "$FIGGY/data" || { echo "figgybanana directory not found: $FIGGY"; exit 1; }\n` +
  `export GUIDELINES_PATH="${GUIDELINES}"\n` +
  `export REFERENCE_SET_PATH="${REFERENCE_SET}"\n` +
  `echo "TEMP=$TEMP FIGGY=$FIGGY"   # TEMP must start with C:/ — if it starts with /c/, fix it`

const TOOL_RULES =
  `\n\nTHE TOOL. Resolve the executable in this order and stop at the first one that answers:\n` +
  `1. the variable $PAPERBANANA_BIN — check it FIRST, before any search; the tool lives in its ` +
  `own virtualenv, and that is the normal case, not the exception;\n` +
  `2. paperbanana on PATH — only if the variable is empty.\n` +
  `While $PAPERBANANA_BIN is set, "not on PATH" is neither a finding nor a reason to stop: ` +
  `paperbanana, figgybanana, npm and pip will not be found there by construction.\n\n` +
  `THE ENVIRONMENT. The exports are already written into the command below. Run them and the ` +
  `tool call in ONE Bash invocation: every Bash call of yours is a fresh shell, variables from ` +
  `the previous one are dead in it, and without TEMP the gateway bridge cannot read its tokens ` +
  `and answers 401. Do not split this across two calls.\n\n` +
  `PROVIDERS. Images go through ss_gateway and nothing else. If the gateway answers 401 or ` +
  `"missing bearer token", stop, set gateway_ok=false and explain; do NOT fall back to ` +
  `openai_imagen, google_imagen or any other image provider — that is not your decision.\n` +
  `The critic is ${CRITIC_NAME}. If it fails mid-run the tool switches to claude_code by itself ` +
  `and prints "Critic satisfied (<provider>)" per image: report that provider per figure. A ` +
  `line "Critic unavailable: image NOT reviewed" means no critic looked at it: report the ` +
  `critic as none. Either way you accept a figure only by your own check, never on the ` +
  `critic's word: on the last run it called defective images satisfied again and again.\n` +
  `NEVER use --continue-run: it regenerates the whole figure from text and breaks what was right.`

// The environment and the command go into ONE Bash call, never two. Each Bash invocation is a
// fresh shell, so exports from a previous call are gone — and when TEMP is gone the gateway
// bridge cannot read its tokens and answers 401. That is exactly how the first redraw round
// died after the first draw round had worked: same script, same agent, different call
// boundary.
function drawCommand(slug, caption, tag = '') {
  return (
    `${ENV_BLOCK}\n` +
    `mkdir -p ${WORK_DIR}/logs\n` +
    `<bin> generate \\\n` +
    `  --input ${WORK_DIR}/brief-${slug}.txt \\\n` +
    `  --caption "${caption}" \\\n` +
    `  --output-dir ${WORK_DIR} \\\n` +
    `  --auto --max-iterations 3 --num-candidates ${CANDIDATES} \\\n` +
    `  --vlm-provider claude_code --vlm-model sonnet \\\n` +
    CRITIC_FLAGS +
    `  --image-provider ss_gateway \\\n` +
    `  --aspect-ratio 16:9 --save-prompts \\\n` +
    `  2>&1 | tee ${WORK_DIR}/logs/${slug}${tag}.log`
  )
}

// Who judged a figure is read from its render log, never taken from the illustrator's word. On
// the Vista run Kimi began answering 403 halfway through, the tool switched to Claude on its own,
// and the illustrator reported "critic: Kimi K3" for figures Kimi never saw.
function criticCommand(logs) {
  return (
    `python -X utf8 tools/critic_used.py ` +
    logs.map((l) => `--log-file ${l}`).join(' ') +
    ` --log ${WORK_DIR}/tools.jsonl --log-note "who judged the figures"`
  )
}

// A screen is not generated: its numbers and words are the point, and a generator does not keep
// them. The illustrator writes an HTML mockup in the look of the accepted figures, its brief ends
// with a Facts block that tools/figure_facts.py checks against the document, and headless Chrome
// renders it. The Vista drawing screen took thirty generated candidates and still needed its
// text fixed by hand; its brief had asked for five piers where the spacing called for seven.
function screenCommands(slug) {
  return (
    `python -X utf8 tools/figure_facts.py --brief ${WORK_DIR}/brief-${slug}.txt --file ${ARTICLE_PATH} ` +
    `--log ${WORK_DIR}/tools.jsonl --log-note "facts of ${slug}"\n` +
    `python -X utf8 tools/render_html.py --html ${WORK_DIR}/mockup-${slug}.html ` +
    `--out ${WORK_DIR}/render-${slug}.png --width 1600 --height 900 ` +
    `--log ${WORK_DIR}/tools.jsonl --log-note "render of ${slug}"`
  )
}

// The web copy. Pillow lives in figgybanana's virtualenv, so the interpreter is derived from
// $PAPERBANANA_BIN the way $FIGGY is — this command has to work in a Bash call of its own.
function shrinkCommand(chosen, slug) {
  return (
    `"$(echo "$PAPERBANANA_BIN" | sed 's#paperbanana.exe$#python.exe#')" -X utf8 ` +
    `tools/shrink_png.py --file ${chosen} --to ${FIGURES_DIR}/${slug}.png ` +
    `--max-width ${FIGURE_WIDTH} --log ${WORK_DIR}/tools.jsonl --log-note "web copy of ${slug}"`
  )
}

log(`[start] dir=${run} article=${source} figures=${wanted}`)

// --- Preflight: which critic answers, and is the temp directory one the critic can read ------

phase('Preflight')
if (critic !== 'none' && critic.provider === 'kimi') {
  const pre = await agent(
    `Run exactly this, from the repository root, in ONE Bash invocation, and return the parsed ` +
      `JSON report in the report field and the raw output in stdout. Correct nothing.\n\n` +
      `${ENV_BLOCK}\n` +
      `python -X utf8 tools/preflight.py --kimi --log ${WORK_DIR}/tools.jsonl --log-note "which critic answers"`,
    { agentType: 'gate-runner', model: 'haiku', label: 'preflight', phase: 'Preflight', schema: PREFLIGHT },
  )
  const verdict = pre && pre.report && pre.report.critic
  if (verdict === 'kimi') {
    log(`[preflight] Kimi answered; critic = ${CRITIC_NAME}`)
  } else {
    const why = (pre && pre.report && pre.report.measures && pre.report.measures.kimi && pre.report.measures.kimi.reason) || 'no answer'
    CRITIC_FLAGS = ''
    CRITIC_NAME = 'claude_code sonnet (Kimi unavailable at preflight)'
    log(`[preflight] Kimi did not answer (${why}); the critic for this run is claude_code sonnet`)
  }
  // After the exports the temp directory is in long form, so a problem here means the environment
  // block itself went wrong. Said loudly; the figures are still drawn, because the Look step
  // judges every image with its own eyes whatever the critic managed to see.
  for (const problem of (pre && pre.report && pre.report.problems) || []) {
    log(`[preflight] PROBLEM: ${problem}`)
  }
}

// --- Plan: the writer declares the figures, which is what its contract says it does ---------

phase('Plan')
const plan = await agent(
  `The article is already written and lives at ${source}. It must not be changed.\n\n` +
    `Read it and decide which ${wanted} figures explain the mechanism better than a paragraph ` +
    `of prose does. A figure must carry what prose carries badly: a structure, a flow, a ` +
    `correspondence between parts. Do not illustrate what one sentence already makes clear.\n\n` +
    `FIRST check whether the article already carries placeholders of the form ` +
    `![caption](figures/<slug>.png). If it does, they ARE the plan: the writer declared them ` +
    `while writing, with the reader in front of them. ` +
    (IN_PLACE
      ? `Write nothing — the article stays exactly where and as it is. `
      : `Copy the article to ${ARTICLE_PATH} unchanged, add none, remove none. `) +
    `Return every placeholder you found — however many there are, the count ${wanted} does ` +
    `not apply.\n\n` +
    (IN_PLACE
      ? `If the article has no placeholders at all, stop and say so in the result: in place, ` +
        `the source is never edited, and the figures then have to be planned in a separate run ` +
        `directory.\n\n`
      : `Only if the article has no placeholders at all: copy the article to ${ARTICLE_PATH} and ` +
        `insert into the copy exactly ${wanted} `) +
    `placeholders of the form ![caption](figures/<slug>.png), each one directly after the ` +
    `paragraph it belongs to. The caption is in the article's language and says what the ` +
    `figure communicates. The slug is latin and hyphenated. Change nothing else in the text: ` +
    `not a word, not the order of the sections.\n\n` +
    `Return the list of figures: slug, caption verbatim, the section it stands after, what it ` +
    `is good for, and its kind: exact when its value is which box connects to which, in what ` +
    `order or on which week (sequence, component, deployment, state, flow, timeline), ` +
    `screen when it is a product screen whose numbers, counts or words the text relies on ` +
    `(items placed on a plan, a price list, a banner, a disclaimer), illustration when its ` +
    `value is the look (a scene, a hero picture). ` +
    `Return also the language the document is written in, named in English — every worded ` +
    `label on every figure will be in that language.\n\n` +
    (IN_PLACE
      ? `OUTPUT (no file). Your result is the list of placeholders in the schema; the article ` +
        `is not yours to write.`
      : `OUTPUT. Your result is the FILE ${ARTICLE_PATH}: the copy of the article with the ` +
        `placeholders. Write it with the Write tool. The schema fields describe it, they are ` +
        `not it.`),
  { agentType: 'article-writer', model: 'sonnet', label: 'plan', phase: 'Plan', schema: PLAN },
)
const LANG = (plan.language || '').trim() || 'the language of the document'
log(`[plan] figures planned=${plan.figures.length} language=${LANG}`)
for (const f of plan.figures) {
  log(`[plan/${f.slug}] «${f.caption}» — after «${f.section}»`)
  log(`[plan/${f.slug}/why] ${f.why}`)
}

// --- Draw: one CLI run per figure; the tool owns the drawing, we own the brief --------------

phase('Draw')
let drawn = await agent(
  `You have ${plan.figures.length} figures to draw for the article ${ARTICLE_PATH}.\n\n` +
    `The placeholders in the article:\n` +
    plan.figures.map((f, i) => `${i + 1}. ${f.slug} [${f.kind}] — «${f.caption}» (section «${f.section}»)`).join('\n') +
    `\n\nFor each figure:\n` +
    `1. Read the section of the article it belongs to and write a brief into ` +
    `${WORK_DIR}/brief-<slug>.txt: the entities, what connects to what, the labels that must ` +
    `appear verbatim, and what must NOT be on the picture. In prose, not in fragments. Take ` +
    `the notation from the article: if the text calls a matrix Q, it is Q on the figure.\n` +
    `   The style line for every brief, verbatim: ${STYLE}\n` +
    `   For an EXACT figure the brief ends with two lists the check will be run against: ` +
    `"Boxes:" — every box or participant with its exact label; "Connections:" — every arrow as ` +
    `"FROM -> TO: label", in order, and for a timeline every bar as "label: weeks A–B". Nothing ` +
    `outside these lists may appear. For an ILLUSTRATION the brief ends with "Text on the ` +
    `image:" — every word that must be legible — and reference images, if any, are passed for ` +
    `style only: say so in the brief, because a reference drawing's own details (stairs, labels) ` +
    `otherwise leak into the picture.\n` +
    `   EVERY NUMBER that has to appear on the figure is written in the brief, copied from the ` +
    `article: weights, sizes, counts — and for a panel that compares two variants, BOTH sets of ` +
    `numbers, not just the headline one. A number the brief does not name is a number the ` +
    `generator invents: one comparison panel shipped with the scaled weights repeated on the ` +
    `unscaled side because the brief named only the peak.\n` +
    `   The document is written in ${LANG}, so every worded label on the figure is in ${LANG}, ` +
    `and you write the brief in ${LANG}. Copy the wording from the document itself rather than ` +
    `translating it. Notation, formulas, product names and identifiers (X, Q, K, V, FR-012, ` +
    `PostgreSQL) stay exactly as the text writes them — they have no language. Keep the worded ` +
    `labels few and short: an image generator draws a non-Latin script worse than Latin, and a ` +
    `long phrase is likelier to come out mangled than a short one.\n` +
    `   For a SCREEN the brief ends with a Facts block, one line each: "- text: <words the ` +
    `screen shows, copied from the document>" for every banner, disclaimer, label and price line ` +
    `the text also has, and "- check: <arithmetic that must hold>" for every count the screen ` +
    `derives, written with the document's numbers (for piers on a wall: ceil((wall - 2 * corner) ` +
    `/ spacing) + 1 == piers). A screen is NOT drawn with the tool: write it as one self-contained ` +
    `HTML file ${WORK_DIR}/mockup-<slug>.html (inline CSS, no external files, the style line above, ` +
    `every text from the brief verbatim, every counted item drawn exactly that many times), then ` +
    `run these two commands and ship render-<slug>.png through the same web-copy command as below. ` +
    `A false check or a text not in the document is fixed in the brief and the HTML before ` +
    `rendering, never waved through:\n\n` +
    screenCommands('<slug>') +
    `\n\n2. For every other figure run the tool once with this command, substituting your bin, ` +
    `the slug and the caption:\n\n` +
    drawCommand('<slug>', '<caption>') +
    `\n\n3. The tool names its own run directory and renders ${CANDIDATES} candidates into ` +
    `<run directory>/candidates/cand_<n>/ (with one candidate: final_output.png in the run ` +
    `directory itself). Open every candidate's final image AND its diagram_iter_*.png with the ` +
    `Read tool at full size and check it against the lists at the end of its brief, item by ` +
    `item: every box present and spelled exactly, every connection from the right box to the ` +
    `right box in the right direction, every bar on its weeks, every text item legible, nothing ` +
    `outside the lists. Choose the clean one; an earlier iteration of a candidate may be cleaner ` +
    `than its final output, and it counts. The render is 4K and over ten megabytes — it stays ` +
    `there. What ships is a web-sized copy of the chosen file under the name from the ` +
    `placeholder, made by this command (one Bash call, it resolves its own interpreter):\n\n` +
    shrinkCommand('<the chosen png>', '<slug>') +
    `\n\n   Use the run that just finished, not the newest one at a guess. Check that the ` +
    `file exists and is not empty. If no candidate is clean, still ship the best one and list ` +
    `its defects: the Look step decides whether it is redrawn.\n` +
    `4. After the very first figure, open ${WORK_DIR}/run_*/planning.json and look at the ` +
    `field retrieved_examples. An empty list there means the etalons were not picked up, which ` +
    `means REFERENCE_SET_PATH did not arrive: stop and say so, do not draw the rest blind. The ` +
    `retriever is half of what this tool was chosen for.\n` +
    `5. If the command fails, read its output. An unreachable gateway, an exhausted quota and a ` +
    `rejected brief are three different problems, and only the last one is yours. One retry ` +
    `with a shorter, more concrete brief; if that fails, record it in failed and move on to ` +
    `the next figure.\n\n` +
    `Write ${MANIFEST_PATH}: per figure the slug, the caption, the file, the exact command, the ` +
    `run directory, the number of iterations and who the critic was. The point of the manifest ` +
    `is the command: a figure someone wants slightly different is redrawn by editing one brief ` +
    `and running one line.` +
    TOOL_RULES,
  {
    agentType: 'illustrator',
    model: 'sonnet',
    label: 'draw:1',
    phase: 'Draw',
    schema: DRAWN,
  },
)
log(`[draw] drawn=${drawn.done.length} failed=${drawn.failed.length} gateway_ok=${drawn.gateway_ok}`)
for (const d of drawn.done) {
  log(`[draw/${d.slug}] critic=${d.critic_provider} iterations=${d.iterations} run=${d.run_dir}`)
}
for (const f of drawn.failed) log(`[draw/failed] ${f.slug}: ${f.reason}`)

const renderLogs = plan.figures
  .filter((f) => f.kind !== 'screen' && drawn.done.some((d) => d.slug === f.slug))
  .map((f) => `${WORK_DIR}/logs/${f.slug}.log`)
if (renderLogs.length) {
  const judged = await agent(
    `Run exactly this command from the repository root and return its result unchanged:\n\n` +
      `${criticCommand(renderLogs)}\n\n` +
      `Return the parsed report in the report field and the raw output in stdout. Correct nothing.`,
    { agentType: 'gate-runner', model: 'haiku', label: 'critic-used', phase: 'Draw', schema: GATE },
  )
  for (const [name, facts] of Object.entries((judged.report.measures && judged.report.measures.logs) || {})) {
    log(`[draw/critic] ${name}: configured=${facts.configured} judged_by=${(facts.judged_by || []).join(',') || 'none'} fell_back=${facts.fell_back}`)
  }
  for (const problem of judged.report.problems) log(`[draw/critic] PROBLEM: ${problem}`)
}

if (!drawn.gateway_ok) {
  // Loud and specific: this is a credential in the OS keychain, not something a prompt fixes.
  log('[draw] THE GATEWAY DID NOT ANSWER: open "SS AI Setup", press Apply, then run again')
}

// --- Look and Redraw: our own eyes on the render, then targeted repair ----------------------

const lookTask = (slugs) =>
  `Look at these figures as a reader of the article ${ARTICLE_PATH} would. The files: ` +
  slugs.map((s) => `${FIGURES_DIR}/${s}.png`).join(', ') +
  `\n\nOpen EVERY file with the Read tool — you can look at images — and check it against its ` +
  `caption and against the section of the article it belongs to.\n\n` +
  `For an exact figure, also open its brief ${WORK_DIR}/brief-<slug>.txt and walk the lists ` +
  `at its end one line at a time: each box present with its exact label, each connection from ` +
  `the named box to the named box in the named direction, each timeline bar on its weeks. A ` +
  `connection that starts or ends on the wrong box is a defect however good the picture looks; ` +
  `on the last run the sequence diagram's message 7 kept starting on the wrong lifeline.\n\n` +
  `For each one decide whether it is fit for the article as it stands. Look at: are the labels ` +
  `legible; is the notation the same as in the text; are there invented elements the article ` +
  `does not have; are the directions of any relations reversed; is the picture empty or a ` +
  `mess. Typos inside the picture's labels are a defect and they are visible.\n\n` +
  `NUMBERS are labels too, and the most expensive ones to get wrong. Read the section's own ` +
  `numbers and check every number printed on the figure against them: a comparison panel that ` +
  `shows 0.0924 where the text says 0.0449 is a wrong figure however clean it looks, and one ` +
  `such panel passed a vision critic. A number on the figure that the text does not contain ` +
  `is a defect, named with both values.\n\n` +
  `Separately and pedantically — SPELLING. Image generators break words, and they break a ` +
  `non-Latin script worst of all: letters get substituted and a word turns into plausible-looking ` +
  `noise. Read every label out to yourself: if it is not a real word in ${LANG}, that is a ` +
  `defect, and say which label went wrong. A document with a figure that has gibberish written ` +
  `on it is worse than a document with no figure.\n\n` +
  `If you crop fragments to inspect details, put them in ${WORK_DIR}, not in ${FIGURES_DIR}: ` +
  `that directory holds only what ships with the article.

` +
  `Phrase the defects so they can be handed to whoever redraws: "the arrow from K to Q is ` +
  `drawn the wrong way round", not "unclear".\n\n` +
  `FIRST write out into labels_seen every label on the picture verbatim — all of them, ` +
  `including the small ones under blocks and on arrows. Pass no verdict until you have: this ` +
  `is the step at which what a quick glance skips becomes visible.\n\n` +
  `THE LANGUAGE OF THE LABELS. The document is written in ${LANG}, so every worded label is in ` +
  `${LANG}. The exceptions are notation, formulas, identifiers and product names that the ` +
  `document itself writes as they are — those carry over unchanged. A worded label in any other ` +
  `language is a defect: name it and give the word the document uses instead. All the figures of ` +
  `one document must be in one language; a mismatch between them is a defect even if each reads ` +
  `fine on its own.\n\n` +
  `THE TYPOGRAPHY OF THE NOTATION. Subscripts must be subscripts: d_k and d_v are printed as a ` +
  `d with a small k or v below, not as "d_k" with an underscore in the middle of the line. A ` +
  `raw underscore in a formula is a defect, and it is especially visible when both spellings ` +
  `sit side by side on one picture. Check every dimension separately.`

phase('Look')
let looked = await agent(lookTask(drawn.done.map((d) => d.slug)), {
  agentType: 'figure-critic',
  model: 'sonnet',
  label: 'look:1',
  phase: 'Look',
  schema: LOOKED,
})
for (const c of looked.checks) {
  log(`[look/${c.slug}] ok=${c.ok}${c.defects.length ? ' | ' + c.defects.join('; ') : ''}`)
}

let redraws = 0
while (redraws < MAX_REDRAWS && looked.checks.some((c) => !c.ok)) {
  redraws += 1
  const bad = looked.checks.filter((c) => !c.ok)
  phase('Redraw')
  log(`[redraw/${redraws}] redrawing: ${bad.map((c) => c.slug).join(', ')}`)

  const byslug = {}
  for (const d of drawn.done) byslug[d.slug] = d

  const again = await agent(
    `Redraw only these figures and leave the rest alone. What is wrong with each:\n\n` +
      bad
        .map(
          (c, i) =>
            `${i + 1}. ${c.slug} (run directory ${byslug[c.slug] ? byslug[c.slug].run_dir : 'unknown'})\n` +
            c.defects.map((d) => `   - ${d}`).join('\n'),
        )
        .join('\n\n') +
      `\n\nDo not continue the old run: --continue-run regenerates the whole figure from text and ` +
      `breaks what was already right. Instead write the defects into the brief as explicit ` +
      `rules ("message 7 starts on the Cloud API lifeline and ends on the Technician tablet ` +
      `lifeline"), save it as ${WORK_DIR}/brief-<slug>-r<N>.txt, and render afresh with the ` +
      `ordinary command pointed at the revised brief — ${CANDIDATES} candidates again:\n\n` +
      drawCommand('<slug>', '<caption>', '-r<N>').replace(`brief-<slug>.txt`, `brief-<slug>-r<N>.txt`) +
      `\n\nA SCREEN is redrawn by editing its brief and its HTML mockup and running its two ` +
      `commands again, never with the tool:\n\n${screenCommands('<slug>')}` +
      `\n\nChoose the clean candidate by the same full-size check as before, then make the web ` +
      `copy again, over the old one:\n\n${shrinkCommand('<the chosen png>', '<slug>')}\n\n` +
      `Update ${MANIFEST_PATH}.` +
      TOOL_RULES,
    {
      agentType: 'illustrator',
      model: 'sonnet',
      label: `redraw:${redraws}`,
      phase: 'Redraw',
      schema: DRAWN,
    },
  )
  for (const d of again.done) {
    log(`[redraw/${redraws}/${d.slug}] critic=${d.critic_provider} iterations=${d.iterations}`)
  }
  for (const f of again.failed) log(`[redraw/${redraws}/failed] ${f.slug}: ${f.reason}`)

  looked = await agent(lookTask(bad.map((c) => c.slug)), {
    agentType: 'figure-critic',
    model: 'sonnet',
    label: `look:${redraws + 1}`,
    phase: 'Redraw',
    schema: LOOKED,
  })
  for (const c of looked.checks) {
    log(`[look/${redraws + 1}/${c.slug}] ok=${c.ok}${c.defects.length ? ' | ' + c.defects.join('; ') : ''}`)
  }
}

// --- Gate: how many files are actually on disk, counted by python ---------------------------

phase('Gate')
const gate = await agent(
  `Run exactly this command from the repository root and return its result unchanged:\n\n` +
    `python -X utf8 tools/gate.py --dir ${FIGURES_DIR} --min-entries ${plan.figures.length + 1}\n\n` +
    `Return the parsed report in the report field and the raw output in stdout. Correct nothing.`,
  { agentType: 'gate-runner', model: 'haiku', label: 'gate', phase: 'Gate', schema: GATE },
)
log(
  `[gate] ok=${gate.report.ok} problems=${gate.report.problems.length} ` +
    `measures=${JSON.stringify(gate.report.measures)}`,
)
for (const p of gate.report.problems) log(`[gate/problem] ${p}`)

// A floor is not enough for a delivery directory. The vision check cropped fragments to look
// at them closely and left four crop_*.png next to the figures; `--min-entries 4` counted
// eight and said ok, so the debris would have shipped with the article.
const expectedEntries = plan.figures.length + 1
const actualEntries = gate.report.measures.entries
if (typeof actualEntries === 'number' && actualEntries !== expectedEntries) {
  log(
    `[gate] EXTRA FILES IN THE DELIVERY: ${actualEntries} files, expected ${expectedEntries} ` +
      `(${plan.figures.length} figures and the manifest). Working files belong in ${WORK_DIR}.`,
  )
}

const stillBad = looked.checks.filter((c) => !c.ok)
if (stillBad.length) {
  // Same rule as the article loop: an unmet verdict goes into the log by name, never silently.
  log(`[summary] NOT BROUGHT UP TO QUALITY: ${stillBad.map((c) => c.slug).join(', ')}`)
  for (const c of stillBad) for (const d of c.defects) log(`[summary/defect] ${c.slug}: ${d}`)
}

log(
  `[summary] planned=${plan.figures.length} drawn=${drawn.done.length} ` +
    `redraws=${redraws} not_good_enough=${stillBad.length} gate_ok=${gate.report.ok}`,
)

return {
  article: ARTICLE_PATH,
  figures_dir: FIGURES_DIR,
  manifest: MANIFEST_PATH,
  planned: plan.figures.map((f) => f.slug),
  drawn: drawn.done.map((d) => d.slug),
  failed: drawn.failed,
  redraws,
  not_good_enough: stillBad.map((c) => ({ slug: c.slug, defects: c.defects })),
  gateway_ok: drawn.gateway_ok,
  gate_ok: gate.report.ok,
  gate_measures: gate.report.measures,
}
