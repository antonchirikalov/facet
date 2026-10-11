---
name: holdout-questions-profile
description: Document-type profile for the holdout questions (requirements.js holdout step, scored by design.js and proposal.js). Preloaded into the client questioner and the question skeptic. The questions the client's people will ask of our documents, written from the client's own material before any of those documents exists and never shown to their writers - readers and their lenses, five layers, the record of one question, grounds, research, selection criteria, quotas and the gate rules.
user-invocable: false
---

# Profile: holdout questions

The writer, the corrector and the critic of a document read one profile, so a critic checks the
document against rules its writer already knew. That measures whether the document keeps its
contract, not whether it serves its reader. These questions are the other measure: what the
client's people will ask when the documents reach them, written from the client's own material
alone, before any document exists, and never handed to a writer or a critic. After the rounds a
reader with nothing but the document looks for each answer, and a tool counts.

So two rules come before everything below:

1. **The questions come from the client, not from us.** The questioner reads the client's
   material and nothing of ours: not the extracts, not the requirements, not a profile of a
   document, not a document. A question that follows from our contract measures the contract
   again.
2. **A question is a person in a situation.** "What database is used" is a quiz. "The shift lead,
   third month after launch: the assistant booked a patient to the wrong doctor. Who notices, and
   what happens then?" is a question someone will ask.

## The file

```
# Holdout questions: <client>

## 1. Readers
| Role | In the material | Wants | Fears | Source |

## 2. Research log
| # | Query | What came back | Question it changed |

## 3. Questions

### Q-01
- Layer: asked | implied | role | situation | domain
- Role: <who asks>
- Situation: <the moment, in one line; "-" for a plain question>
- Question: <the question, in the language of the material>
- Ground: <see Grounds>
- Decides: <what this person decides or does differently on the answer>
- Weight: blocking | important
- Design: answer | acknowledge | none
- Proposal: answer | acknowledge | none
```

The keys and the values of Layer, Weight, Design and Proposal stay in English exactly as above:
a tool reads them. Everything else is in the language of the client's material. One block per
question, ids Q-01, Q-02 … in the order written, never reused.

## 1. Readers

Every person of the client the material names, by role, with what they want and fear, quoted
where they said it. Then the roles any client of this kind has and the material does not name:
whoever pays (finance), whoever runs the systems and answers for data (IT and security), whoever
uses the product every day, whoever signs for the law. Such a row says "not in the material" and
why this client has the role.

## 2. Research log

Each search: the query, what came back with its URL, and the question it created or changed. A
search that changed nothing is not listed. When the domain needed no research, one row says so.

## 3. Questions: five layers

- **asked** — what someone of the client asked in the material, in a call, a letter or the RFP.
  Verbatim where it was a question; the ground is the question itself.
- **implied** — what a pain, a worry, a goal or a constraint the client stated turns into: "how
  does the solution deal with this?" The ground is the statement.
- **role** — what each reader of section 1 asks by virtue of the role, applied to this client's
  facts. The lens: an owner asks about value, risk and when; finance about the cost of owning
  and running it; IT and security about integration, data, access and where it runs; the head of
  operations about who does what every day, the load and the training; the daily user about what
  changes in their day; legal about data and regulation.
- **situation** — the life of the system on this client's facts: the first day; an ordinary day;
  the peak; a failure (the system is down, the data is wrong, the model is wrong, and for a
  model also confidently wrong); a change (a new site, a new law, a key person leaves); the
  exit (the contract ends: their data, their dependence on us).
- **domain** — what any buyer in this trade asks: the norm or the regulator by name, the known
  failure of systems of this class, the integration such systems normally need. Grounded in
  research, not in memory.

## Grounds

Every question has one ground, in one of three forms:

- a quote: `“<verbatim words>” (<document>, <place>)`, the words copied exactly from the client's
  material; a tool finds them there;
- a source: `<URL> “<short quote>”`, for the domain layer only;
- `absent role: <why this client has the role>`, for a role-layer question of a reader the
  material does not name.

A situation question is grounded in the fact it rests on ("Monday mornings the front desk is on
the phone"), not in the lens.

## Selection criteria

The questioner drafts wide; the skeptic keeps only what passes all six:

1. **Grounded.** The ground is in the material, or it is a source, or an absent role with a
   reason.
2. **Substitution.** Put any other client's name in its place: if the question still makes the
   same sense, it is generic. "How is security ensured?" fails; "Who will see the recordings of
   calls with patients?" passes.
3. **Consequence.** The answer changes what the person decides or does. Blocking: without an
   answer they will not sign or start. Important: they will ask until answered. Curiosity is
   not kept.
4. **Expectation.** For each document, what a fair reader may expect of it, judged from the one
   line the task gives about that document and nothing else: answer, acknowledge (it is enough
   that the document names the question as open or out of its scope), or none (not this
   document's question).
5. **Atomic.** One question, one answer.
6. **No duplicates.** Two questions one answer settles are one question.

Every asked question is kept: the client asked it. The quotas below hold for the rest.

## Questioner checklist

- every role of section 1 asks at least one question, an absent role included;
- every layer is drafted, the domain layer only with research behind it;
- no question names a document, a section of ours or our process: the client has not seen any;
- no question answers itself or carries the expected answer.

## Skeptic checklist

Drop, with the reason in one line:
1. a question without a ground, or with a ground that does not say what the question rests on;
2. a generic question (substitution);
3. a curiosity;
4. a question the client's material already answers in plain words: a document cannot be blamed
   for not repeating a known fact back;
5. a bundle of several questions;
6. a duplicate;
7. an expectation that asks a document for what its one line says it does not carry (an estimate
   of a design that carries none).

Keep the layers balanced by the quotas; do not keep a weak question to fill one.

## Gate rules

```gate
--require-heading "^##\s+1\." --require-heading "^##\s+2\." --require-heading "^##\s+3\."
--no-empty-sections
--unique-ids "\bQ-\d{2}\b"
--forbid "\x60"
```

```holdout
draft-min 40
draft-max 60
layer-min 4
others-max 24
blocking-max 0.34
batch 10
```

- headings ## 1. to ## 3. present, none empty; Q- ids unique; no backticks;
- every block carries the nine keys with valid values, and every quote ground is found verbatim
  in the client's material or its extracts (tools/holdout.py --check);
- a draft of draft-min to draft-max questions; after selection, every asked question, at least
  layer-min of each other layer, at most others-max beyond the asked ones, and blocking at most
  blocking-max of all (tools/holdout.py --select);
- the reader gets batches of at most batch questions (tools/holdout.py --blind).

## Output language

The language of the client's material. Keys and enumerated values stay in English.
