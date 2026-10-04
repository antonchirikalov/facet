---
name: animated-scene-profile
description: Document-type profile for an animated scene (scene.js) - one self-contained HTML page that walks a client through a process step by step on a canvas or SVG stage. Preloaded into the scene animator. Sections of the page, the stage, the step contract the renderer relies on, facts, look, accessibility and the critic checklist.
user-invocable: false
---

# Profile: animated scene

An animated scene shows a client one process with their product, step by step: a house traced
from above, a layout of piers growing along the walls, a quote filling in. It accompanies a
proposal: the document carries a still of each step as a figure, and the live page goes as a
link or an attachment, because Word and Confluence cannot play it.

One accepted scene was a single HTML file of about 23 KB: a dark stage on the left, five
numbered steps on the right, a caption per step, "play" and "start over" buttons, every
drawing done on a canvas with plain JavaScript and requestAnimationFrame. That is the shape.

## The file

- One self-contained .html file. No JavaScript libraries, no external scripts, no images from
  the network; fonts from Google Fonts are the one allowed external link, with system
  fallbacks. Everything else is drawn: canvas 2D or inline SVG.
- Colours, fonts and spacing as CSS custom properties on :root, redefined for dark mode under
  @media (prefers-color-scheme: dark), and again under :root[data-theme="dark"]. body has an
  explicit background.
- Works at phone width: the stage and the step list stack below 960 px, no horizontal scroll.
- Deterministic: any randomness (texture, trees, noise) comes from a seeded generator, so the
  same step renders the same picture every time.

## The page

1. Eyebrow, title and one or two lines of lead: what the scene shows, in the client's terms.
2. Optionally the client's own words that ask for this, as a blockquote with its source.
3. The stage: the drawing on the left, the numbered steps on the right; each step has a short
   title, two or three sentences, and chips that say who does what ("Human: the final
   choice", "App: suggestion").
4. Controls: play the story, start over, and every step clickable.
5. A label on the stage when the picture is illustrative ("Illustration, not real satellite
   imagery"), placed where no other label is.

## The step contract

The renderer and the critic depend on it; a scene that breaks it cannot be checked.

- The steps are one array in the script, in order; step numbers start at 1.
- Opening the page with #step=N in the URL shows step N with its animation finished, after at
  most four seconds of page time. No click is needed.
- Without a fragment the page shows step 1 and waits for "play".
- The step list marks the current step with aria-current="step".

## Facts

Every number, count, dimension, label and price the stage shows is a fact. The brief lists
them in a Facts block (- text: … / - check: …) and the scene shows exactly those; the gate checks
the block against the proposal before the scene is written (tools/figure_facts.py), and the
critic checks the rendered steps against the block. Counts are drawn by the code from the same
numbers (fourteen piers come from a loop over the spacing, not from fourteen hand-placed
dots), so a figure cannot drift from its label.

## Look

The look follows the frontend-design skill when it is available: a deliberate palette and
type pairing that fits the client's trade, not a template. One accent colour; a caution colour
only for what is preliminary or needs a human. Labels on the stage in a mono face with a dark
backing so they read over any drawing; no two labels overlap at any step.

## Language

The language of the proposal the scene accompanies. The client is named; their people by role.

## Critic checklist

HIGH
1. A label, number or count on the stage that differs from the Facts block or the proposal.
2. Two labels overlapping, or a label cut off by the stage edge, at any step.
3. A step that shows something the steps' text does not say, or a step text describing what
   the stage does not show.
4. #step=N not showing step N finished.
MEDIUM
5. A preliminary or illustrative picture without its label.
6. Our words where the client has their own; an addressed reader ("your") outside a quote.
LOW
7. Taste the critic would merely do differently: not a defect.
