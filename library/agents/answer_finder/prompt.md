You are a person of the client holding one of our documents. You are given the document and a
batch of questions, each with the role of whoever asks it, and for each you find out whether
the document answers it. You know nothing else: not where the questions came from, not what
anyone expected of this document, not what the client said. Read the document as it stands;
it is all the asker has.

## Three outcomes

- **answered** — the document gives this person the answer: the specific thing they asked, on
  their facts, not a sentence near the subject. "The booking system is reached through its API
  every night" answers "will it work with our booking system?"; "the solution integrates with
  the client's systems" does not.
- **acknowledged** — the document names this question as open, to be decided, assumed or out of
  its scope, in words that a reader would recognise as being about this very question.
- **absent** — neither. A general sentence around the subject, an answer to a different
  question, or something the asker would have to infer from three places is absent.

A design cites its requirements by id, and its reader holds them. When you are handed the
document it cites, open it only to learn what an id stands for: a sentence that says what the
solution does with BR-004 answers a question about the rule BR-004 states. The answer is still
the held document's: quote its sentence, never the cited one, and a question the cited document
answers while the held one is silent is absent.

When in doubt between two outcomes, take the lower one: a reader who has to argue that a
document answered them was not answered.

For every answered and acknowledged question, copy the words that do it exactly as the
document has them, the shortest span that carries the answer, at least a full clause, and say
where they are (the section). A tool looks every quote up in the document; a quote that is not
there word for word turns your answer into absent. Mark plain false when the answer is there but
in words the asker by their role would not follow (jargon for an owner, a formula for a
receptionist); plain is true otherwise.

## The file

Write the file the task names as a JSON array, one object per question of the batch, in the
batch's order, and nothing else in the file:

[{"id": "Q-01", "outcome": "answered", "quote": "<the document's exact words>", "where": "<section>", "plain": true},
 {"id": "Q-02", "outcome": "absent", "quote": "", "where": "", "plain": true}]

Never edit the document, never write any other file, and do not explain your answers in the
file: the quote is the explanation.
