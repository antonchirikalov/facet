# Missing input and the holdout questions: 10 October 2026

Two mechanisms added to `requirements.js`, `design.js` and `proposal.js` on one day, and the
removal of the old `solution-design.js` that made room for them. The first live run, on the
invented Acme Clinics case, is the second-to-last section; the last says what is not measured yet.

## The old monolith is gone

`solution-design.js` (2724 lines, 17 August) ran everything from raw documents to a proposal in
one script. `requirements.js`, `design.js` (a `type` naming the profile: `solution-design` or
`ai-solution`) and `proposal.js` had replaced it stage by stage, and nothing retired it. It went,
with the six agents only it used (`arch-probe`, `arch-critic`, `claim-lister`, `client-editor`,
`solution-design-selector`, `story-writer`) and the three profiles only they read (discovery
questions, client edition, day story). The port tests of mechanisms the new scripts share (office
documents, subfolders, duplicates, frames, our notes, ASCII commands, the voice sheet) were moved
to `requirements.js` and pass there; the tests of mechanisms only the monolith had went with it.

## needs_context: a third answer to a remark

A writer had two answers to a numbered remark, fixed and declined. A remark the inputs hold no
data for had neither: the writer either invented what was missing (a placeholder for the client's
name reached a proposal seventy-six times on one live run; a figure was copied from a neighbouring
panel on another) or declined a remark it agreed with. The third answer names the missing fact
and where it was looked for.

- The item leaves the rounds for its own record, `missing-input.md` (`design-missing-input.md`,
  `prop-<stage>-missing-input.md`): what to ask the client. Not `UNRESOLVED.md`, which is our
  unfinished work and has another reader.
- A measurement (a gate item, an edit that did not apply) is never answered so.
- The next critic sees the items and may contest one with `CONTESTED-<n>:` and the place where the
  data is; the item comes back and cannot be answered so again. The design's rule skeptic sees the
  client's gaps too, so a rule checker that flags a declared gap every round does not hold the loop.
- In `design.js` the designer also says whose fact it is. A client's fact goes to the record; a
  fact of practice goes, in the same round, to the domain checker, and comes back to the designer
  as a PRACTICE item with the file that answers it. A second look-up of the same item is refused.
- The profiles say where the gap lives in the document: 8.2 of the requirements, section 7 of a
  solution design, section 14 of an AI design, section 6 or 7 of a proposal.
- A continued launch writes its own `-from-round-<n>` file instead of overwriting an earlier one;
  the items are kept out of the round records, because `rounds.py` would read them back as
  remarks.

## The holdout questions

The writer, the corrector and the critic of a document read one profile, so the rounds measure
whether the document keeps its contract, not whether it serves its reader. The holdout questions
are the second measure, after the scenarios a software factory keeps outside its code.

- **Written in `requirements.js`**, after the pain map: the client's material is all there and no
  design or proposal exists, so the questions provably come before the documents they measure.
  A continued run never rewrites them.
- **`client-questioner`** (opus, Tavily, pdf-reader, no Bash) reads the client's material alone —
  not the extracts, not the requirements, not a profile of a document — and drafts 40 to 60
  questions in five layers (asked, implied, role, situation, domain), each a person in a
  situation, with a ground (a verbatim quote, a source URL, or an absent role with its reason), a
  weight and what each document is expected to do with it. It is told one line about each document,
  and `args.designType` sharpens the line about the design.
- **`question-skeptic`** (a separate agent, read only) keeps 20 to 30 by the profile's criteria —
  grounded, specific to this client (the substitution test), consequential, fair to the
  documents — and never rewrites; `holdout.py --select` copies the kept blocks byte for byte, so
  a ground stays the client's words. A layer below its quota is added to once and selected again,
  never padded.
- **`answer-finder`** (sonnet, Read and Write, no Edit) runs after the rounds of `design.js` and of
  each `proposal.js` stage, on blind batches: the question and who asks, nothing else. Each answer
  carries the document's exact words; `holdout.py --score` turns an answer whose quote is not in
  the document, or is shorter than a clause, into absent, and counts what was met by layer and by
  weight. The text stage is compared with the content stage, so a wording pass that lost an answer
  is named.
- **Never a gate, never a remark.** The score goes to the stage outcome for a person. A score fed
  back to the writer would hand it the questions, and the next score would measure the questions.
  No writer, corrector or critic is handed a path under `holdout/`: a test runs every stage on
  stubs and fails on the first such prompt.
- The contract of the file is `holdout-questions-profile`; its ```holdout block holds the quotas,
  so no script spells them out.

## Decisions taken with the author

1. Missing input has its own file, not a section of `UNRESOLVED.md`.
2. The questions are generated at the end of `requirements.js`, not by whichever later stage runs
   first.
3. The skeptic is a separate agent, not a second call of the questioner.
4. The design is not a required input of the proposal. A question expected only of the design is
   simply not counted in the proposal's score.

## Measured on the first live run, 11 October

On the invented Acme Clinics case (`cases/acme-ai-assistant`): one call of each new agent, then
`requirements.js` (36 agents, accepted in one round) and `design.js` (`ai-solution`, 65 agents,
not accepted after three rounds) on the same inputs.

- **The questions are this client's.** The questioner drafted 60 in five layers from two
  documents and ten searches; every one of the 47 quoted grounds was found in the material word
  for word. Three fail substitution ("how is patient data protected?", "what is the technical
  design?", "how will it be rolled out?"), all of the asked layer, where the client's own words
  are kept by rule. The rest carry the client's facts: a booking-system rate limit, two leaflet
  versions, an anticoagulant pause, a Saturday outage, a second country's language. Two
  independent runs (a separate call and the pipeline's step) agreed on about two thirds of the
  questions by meaning.
- **The skeptic drops by the profile.** 60 to 33 by hand, 56 to 31 in the pipeline; its reasons are
  duplicates, what the client already settled in plain words, and a question no document without a
  plan can fairly answer. The research log rests partly on blogs; the skeptic is the only filter.
- **The score sees what the rounds do not.** The design scored 0.65: every binding requirement
  cited, and none of the four domain questions answered (AI Act disclosure, a messaging
  platform's ban on general-purpose bots, professional secrecy, a leaflet changed after a patient
  got the old one). The profile asks for none of them.
- **Lenient? No.** A vague sentence ("complies with all applicable regulations, including their
  transparency obligations") inserted next to a question stayed absent; a precise answer inserted
  the same way was found.
- **Does it move when a topic goes?** Cutting two whole sections moved one question: the design
  says most things twice, and the reader found them elsewhere, which is right. Cutting every line
  of one topic (the kill switch, the on-call flag) turned exactly those questions absent for both
  readers; the score fell from 0.60 to 0.53.
- **Changed after the run.** One reader moved between answered and acknowledged on the same text
  (0.60 and 0.65 for one design), so every batch is now read by two and the lower outcome stands,
  and the outcome names the questions they disagreed on: one of thirty on the unchanged design. A
  design cites its requirements by id, so its reader is also handed the requirements to learn what
  an id stands for; the quote still has to be the design's.
- **needs_context was not used** in either run: the requirements were accepted in one round, and
  the designer answered all 27 remarks fixed, writing the client's gaps into section 14 as
  assumptions with who confirms them, as the profile says. Whether a writer uses it honestly is not
  measured yet.

## Still to measure

- needs_context on material that really lacks what a critic asks for: count the answers and read
  them.
- What the questioner costs with research, and whether the strongest model available beats opus
  on it, compared by reading the two sets of questions.
- The proposal's scores and the text stage against the content stage.
