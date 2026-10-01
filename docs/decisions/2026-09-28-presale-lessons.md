# Lessons of one presale: why the documents were redone and what the pipeline does now

An analysis of two runs on a real presale, 27–29 September 2026: requirements, design, a
proposal with diagrams. The documents had to be redone by hand many times. The detailed analysis
with the project's materials is kept in the project folder, not here: the builder's repository
holds no client names, no client words and no details of their case.

## What broke

1. **The document profile did not know who it was written for.** Internal versions with sources
   went to the client as they were: tags, source locators, notes about our own process.
2. **The architect's decisions arrived after the design.** The stack, the hosting and the
   boundaries of the first version, decided before the run, were chosen again by the designer,
   and differently: the text of the order reached no agent at all.
3. **A requirement lost its weight.** The caveat "this happens rarely" got lost on the way from
   the call to the requirement, and the design built a heavy mechanism for a rare case.
4. **The input was not collected in full.** The pipeline looked only at the top level of the
   folder and missed a nested folder with the transcript; our notes lay next to the client's
   words without a mark.
5. **The diagrams were drawn before the text was finished, and with a single candidate.**
   Finishing a drawing "as a continuation" broke what was already right. Exact screens with
   numbers were generated as pictures, and the error sat in the brief itself.
6. **The environment broke silently.** The external critic's key had expired, the quota ran out,
   and the figures went out as "accepted by the critic", although the critic had not seen them.
7. **There was no inventory of what the client asked for.** Every forgotten request surfaced as a
   separate question from the author after a "finished" draft.
8. **The mechanical style rules were checked by a human**, and the independent review came after
   the author.
9. **An internal note went to Confluence** without the "internal" mark being checked.

## What was done

| Cause | What the pipeline has now |
|---|---|
| 1 | the `client` stage: client versions without sources and tags, a gate on traces of internal work, continuous numbering, a check of the quotes |
| 2 | the order (`order`) and the decisions (`decisions`) are passed to the agents as text in the task |
| 3 | a "Client voice" sheet before the requirements; weight and frequency in every requirement; the design critic catches a heavy mechanism with no weight behind it |
| 4 | an inventory of the input folder (`tools/intake.py`): nested folders, duplicates, our notes; Word is converted to text (`tools/to_text.py`) |
| 5 | three candidates per figure, no finishing of drawings; exact screens as an HTML mockup with a fact check (`figure_facts.py`, `render_html.py`); `figure-critic` |
| 6 | `preflight.py` checks the critic before the start; a fallback to Claude on refusal; who judged a figure comes from the log (`critic_used.py`) |
| 7 | a coverage map (`coverage-mapper`, `tools/coverage.py`) |
| 8 | a style gate for the proposal, `slop-critic`, `proposal-review.js` before the author |
| 9 | the publisher does not send a document marked internal without `--allow-internal` |

Separately, a wiring check (`facet/wiring.py`): every stage of every script on stubs, the agents'
inputs are checked against their contracts, no written file gets lost.
