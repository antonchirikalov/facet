# Tells of generated English in client documents

Data for the slop critic. Each tell is one yes/no question about one sentence or one paragraph,
with a defect and the shape of its fix. The patterns a regex can settle are in
`forbid/en-slop.txt` and run in the gate; this file is for what only reading settles. The Russian
counterpart is `ru-style-tells.md` with `forbid/ru-slop.txt`.

A tell is a defect when the sentence would lose nothing if it were deleted, or when it claims
something no mechanism, number or source behind it carries. A tell in a quote of the client is
never a defect: those are their words.

## 1. A claim without a mechanism

The sentence states a quality and nothing that produces it.

- Defect: "The architecture ensures high availability and a smooth user experience."
- Fix: name the mechanism and the number, or cut. "Two app instances behind the load balancer;
  one can fail without a dropped request (NFR-004: 99.5% monthly)."

## 2. The empty summary sentence

A paragraph that ends by restating itself, or a section that opens by announcing what it will say.

- Defect: "In short, this approach provides a solid foundation for future growth."
- Defect: "This section describes the key components of the solution."
- Fix: delete. The heading already says what the section is.

## 3. Rule of three on autopilot

Three adjectives or three parallel nouns where one is meant, the third added for rhythm.

- Defect: "a fast, reliable and intuitive workflow"
- Fix: keep the one the requirements back, with its number. "the quote is in the patient's
  inbox before they leave the front desk (FR-031)".

## 4. The contrast frame

"Not just X, but Y", "It's not about X — it's about Y", "Rather than X, we Y" used as a hook,
where nobody proposed X.

- Fix: say Y.

## 5. Stacked hedges

"may potentially help to", "can typically be expected to", "in most cases generally".

- Fix: one hedge, where the uncertainty is real, and say what it depends on; otherwise none.

## 6. Inflated verbs and nouns

leverage, empower, enable, facilitate, foster, streamline, drive, elevate, harness, robust,
scalable, comprehensive — where a plain verb or a number would do.

- Defect: "The platform empowers front-desk staff to streamline patient visits."
- Fix: "The receptionist books the visit and quotes the price at the desk, once."

## 7. Uniform rhythm

Five or more sentences in a row of the same length and shape, or every paragraph opening with the
same construction ("The system…", "This…", "Additionally,…").

- Fix: vary by content — a short sentence for the decision, a longer one for the reason.

## 8. Signposting and connective filler

"Additionally", "Furthermore", "Moreover", "It should be noted", "As mentioned above", opening one
paragraph after another.

- Fix: delete the connective; if the paragraphs do not follow without it, the order is wrong.

## 9. Our words for their things

When a client-voice sheet is given, its section 3 lists the client's terms and the words drafts
substitute for them. A substituted word in our prose ("receptionist" where the client says
"front desk", "appointment" where they say "visit") is a defect even if it is correct English.

## 10. The document talks about itself or about us

"We are excited to", "Our team of experts", "We pride ourselves", "This proposal aims to" — the
reader learns nothing about their product.

- Fix: delete, or replace with the fact the sentence was avoiding (who, how many, what they built).

## 11. The em dash as a pause

More than one em dash per paragraph used for drama rather than for an aside.

- Fix: a full stop, or a colon where a list or an explanation follows.

## What is not a tell

- Domain terms the client or the requirements use, however buzzword-like.
- A technical "robust to X" or "scalable to N" with X or N stated.
- Repetition of a term on purpose: one name for one thing is a virtue.
- Tables, ids, code, quotes.
