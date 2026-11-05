---
name: presentation-storytelling
description: Diagnose and rebuild the story of a presentation. Use when asked to review a deck's storytelling, whether the story is clear, for a pyramid or SCQA check, SVOM or action titles, an MBB-ready deck, a rate card for a presentation, or a handoff package another agent can build the deck from. Input is a PPTX, Google Slides, HTML deck or an outline. Output 1 is always a rate card plus questions; the rebuild follows only on the owner's go.
---

# Presentation storytelling

Code: this repository (`python3 -m storyforge <command>`, run from the repo root or with it on
`PYTHONPATH`). Contract: `story.json`. Scripts decide every gate; you propose, you never enforce.
Prose without em dashes.

## Decision tree

Read `references/decision-tree.md` once. Five exits: rate card and questions (STOP, wait for the
owner); data gap (STOP, name the rows, invent nothing); draft deck with FAIL rows; MBB-ready deck
with an all-PASS after card; handoff package.

## Stage 1: Ingest

```
python3 -m storyforge ingest <deck.pptx|deck.html|slides.json> -o work/deck.json
```
Google Slides: read the presentation with the Slides API or tool, save its JSON, ingest that file.
Slides with `unreadable: true` go into the rate card questions; do not guess their text.

## Stage 2: Frame

1. Read the implied story from `deck.json` titles, the summary slide, the ask slide and notes.
2. Fill `work/frame.json` (schema `storyforge/schemas/frame.schema.json`) from the brief when one
   exists; else from the deck, with `provenance` = `deck` or `inferred` and `confirm: true`.
   Fields: audience, decision, question, situation, complication, beliefs, objections (id, text),
   data_available, constraints. Leave a field empty when nothing supports it; the rate card asks.

## Stage 3: Rate card (Output 1, always, then STOP)

Judged checks: run two blind passes. Dispatch two subagents, each with only `references/rubrics.md`
and the text of `deck.json`, no other context, no access to the other pass. Each writes the JSON the
rubric names to `work/pass_a.json` and `work/pass_b.json`. Then:
```
python3 -m storyforge judgments work/pass_a.json work/pass_b.json -o work/judgments.json
python3 -m storyforge ratecard work/deck.json --frame work/frame.json --judgments work/judgments.json -o work/ratecard.json
```
Hand over `work/ratecard.md`: the scorecard, the story the deck tells today, the gap to the frame,
the defects ranked, and the questions. Ask only what deck, brief and data cannot answer, at most
five, each with its default. Then wait.

## Stage 4: Storylines (only when the story is unclear or options are asked for)

Write two or three candidate `story.json` files with different answer shapes: inductive (answer,
three to five reasons), deductive (situation, complication, therefore), tradeoff (options,
criteria, recommendation; mandatory when the decision is not a yes or no). Run the necessity test
from the rubric for each. Then:
```
python3 -m storyforge storylines work/cand_a.json work/cand_b.json --frame work/frame.json --rows <rows.csv|rows.json|pg://schema.table> --judgments work/judgments.json -o work/scores.json
```
A chosen candidate continues. A tie, or a choice between recommend and tradeoff framing, is taste:
show both with their scores and ask one question.

## Stage 5: Narrate

Write `work/story.json` (schema `storyforge/schemas/story.schema.json`, example
`tests/data/story_min.json`). Rules:
- Governing thought first; SCQA in four sentences at most.
- Five summary blocks in order: goals, period_result, what_we_see, what_we_propose,
  what_we_need_today. Bullets in blocks 2 to 4 are slide titles, word for word.
- Every title is one SVOM sentence with `title_roles` (subject, verb, object, measure), each an
  ordered substring of the title. The measure carries the number and the so-what. No colon. At most
  two lines (140 characters). Every percentage names its base; every amount names its metric.
- Each key slide: subtitle (context and data), takeaway (one line), callout (the one figure the
  eye must find), layout, chart or charts (2 or 3 in a row, each with its own takeaway) or table,
  source, `numbers[]` with a `trace` to a data row, `covers[]` naming the objections it answers,
  `footnotes[]` for definitions, `implication` on evidence slides. Details name their `parent`.
- Charts: `type` in lineChart, barChart, waterfall, scatter, divergingBars, dumbbell, stackedBars;
  `title`, `unit`, `source`, exactly one `annotations` entry; `target` when a target exists.
  `story.colors` maps each entity to one colour for the whole deck.
- Observed and modeled figures are marked in the subtitle. Nothing from outside the data.
```
python3 -m storyforge validate work/story.json --rows <rows>
```
On FAIL, rewrite the failing element only. Three rounds, then stop and list what fails.

## Stage 6: Charts, then build here or hand off

```
python3 -m storyforge charts work/story.json -o work/charts
```
Build here (default):
```
python3 -m storyforge build work/story.json --charts work/charts -o work/out --html
python3 -m storyforge gates work/out/deck.pptx --story work/story.json --rows <rows> --judgments work/judgments_after.json
```
Look at `work/out/png/*.png` before handover. A dense summary continues on a second slide and a
table that does not fit under its charts follows on a data slide; the title gate collapses those
continuations. The after card must be all PASS before you call the deck MBB-ready; otherwise hand
over the files as a draft with the FAIL rows listed.

Hand off instead when the deck is built on another machine or by another agent (corporate
PowerPoint, another model, a colleague):
```
python3 -m storyforge handoff work/story.json --charts work/charts --ratecard work/ratecard.json -o work/handoff
```
`work/handoff/BRIEF.md` is the output description; `data.xlsx`, `data/*.csv`, `charts/` and
`CHECKLIST.md` travel with it. The builder verifies with
`python3 -m storyforge gates <their.pptx> --story story.json`.

## Hand over

Send the PPTX and the PDF, or the handoff directory zipped. Report in a table: stage, result,
evidence path. Never paste JSON at the owner.
