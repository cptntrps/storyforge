# Presentation Storytelling skill: design

Date: 2026-11-05. Owner: Gui. Approved in chat ("ok build this", 2026-11-05).

## Goal

Given a presentation, the skill tells Gui what story the deck tells today, what story the
audience needs, and how far apart the two are. On Gui's go, it rebuilds the deck as one
pyramid with SVOM titles, charts with title, units, source and one callout, and proves the
result with deterministic gates. When the deck must be built elsewhere, the skill emits a
handoff package instead: the output description plus the supporting documents another
agent needs to build it.

Falsifiable success test:

1. Run on reference deck A (an HTML QBR deck, 9 key slides plus appendices, built in
   October 2026). The before rate card must flag every title that fails the SVOM lexical
   filter and the colon title, and the two blind judged passes must agree on the implied
   story. The goals-block defect (the owner's critique of 2026-11-01) fires on a summary
   that lacks the block; deck A gained the block on 2026-11-02, so reference deck B is the
   case that proves the check fires.
2. The rebuilt deck A passes every gate, and every number in a title traces to a row in
   its metrics table (531 rows, Postgres) or to the deck's own data table.
3. Run on reference deck B (a corporate PPTX brief). The rate card and the questions come
   out without any deck-specific code path.
4. The handoff package for deck A, given to a fresh agent with no other context, is enough
   to build the same slides: every slide has its title, subtitle, takeaway, callout,
   layout, chart data and source in the package.

Reference decks are not named in this repo. `tests/fixtures/README.md` says how to point
`STORYFORGE_FIXTURES` at a local directory; tests report SKIP when a fixture is absent.

## Harvested assets

Copied into `storyforge/assets/`, stripped of client names and figures:

| Asset | File | Use |
|---|---|---|
| Lexical SVOM filter | `checks/titles.py::svom_problems` | first, cheap title filter |
| MBB title corpus with role parts, verified against primary sources | `assets/mbb_titles.json` | few-shot examples and regression set for the role dissection |
| Slide element definitions, 26, each sourced | `assets/element_definitions.json` | rubric source |
| Editorial contract (rules, banned filler, semantic review) | `assets/editorial_standard.json` | R18 and the narration rubric |
| Owner rulings on decks, 2026-10-30 to 2026-11-01 | `assets/owner_rules.json` | rubric, one row per rule with its date |
| Executive summary in five blocks | `assets/summary_blocks.json` | the summary template |
| DeckCraft slide primitives | `render/deckcraft.py` plus `render/styles/default.json` | renderer base |

## Pipeline and decision tree

Stages: Ingest, Frame, Rate card (STOP), Storylines, Narrate, Charts, then either Slides
and Gates, or Handoff. The approved decision tree is in `docs/decision-tree.md`. Five
exits: rate card and questions; data gap; draft deck with FAIL rows; MBB-ready deck with a
PASS card; handoff package.

Division of labour: scripts decide every gate; the model proposes and never enforces.
Judged checks (MECE, vertical and horizontal logic, title read-through) run as two blind
passes that must agree; a disagreement is reported as `DISAGREE` with both verdicts.

## Contracts (JSON, schema-validated)

`deck.json` (from Ingest): `source`, `format`, `slides[]` with `n`, `id`, `title`,
`subtitle`, `body[]` (text runs in reading order), `tables[]`, `charts[]` (type, series,
categories when extractable), `notes`, `numbers[]` (every numeric token with its context),
`kind` guess (cover, summary, key, detail, appendix), `unreadable` flag.

`frame.json` (from Frame): `audience`, `decision` (the decision the audience takes at the
end), `question` (the question in the reader's mind), `situation`, `complication`,
`beliefs[]`, `objections[]`, `data_available[]`, `constraints[]`, and `provenance` per
field (brief, deck, inferred, owner). Inferred fields carry `confirm: true` until the
owner answers.

`ratecard.json` (Output 1): `implied_story` (governing thought and the slides that carry
it, or `null` with `story_unclear: true`), `checks[]` with `id`, `method` (script or
judged), `result` (PASS, FAIL, NA, DISAGREE), `evidence` (slide numbers and text),
`diagnostic` (gap to the frame, slides off the path, defects ranked), `questions[]` (at
most 5; each with `default` and `why`).

`story.json` (from Narrate): `governing_thought`, `scqa`, `summary_blocks[5]`
(goals and subgoals, period result, what we see, what we propose, what we need today;
each block's bullets are slide titles verbatim), `slides[]` with `id`, `kind` (key or
detail), `parent`, `title` (SVOM), `title_roles` (subject, verb, object, measure; each an
ordered substring of the title), `subtitle`, `takeaway`, `callout`, `layout` (one of the
renderer layouts), `chart` (svg-charts spec plus `title`, `unit`, `source`,
`annotations`), `table`, `source`, `numbers[]` (value, metric, base, `trace` to a data
row).

`storyline_scores.json` (from Storylines): per candidate `key_slides`, `necessity`
(reasons that survive the removal test), `coverage` (objections with a slide),
`data_trace` (claims with a row over claims), `numbers_held`, `read_through` (two blind
verdicts), `chosen`, `why`.

## Handoff package

`handoff/` directory, built from `story.json` and the chart outputs:

| File | Holds |
|---|---|
| `BRIEF.md` | the output description: governing thought, SCQA, summary blocks, then one section per slide with title, subtitle, takeaway, callout, layout name and a layout sketch, chart or table reference, source, speaker-note line |
| `story.json` | the contract itself |
| `data.xlsx` | one sheet per chart or table with its rows; a `numbers` sheet with value, metric, base, trace; a `slides` sheet (id, kind, parent, title, subtitle, takeaway, callout, layout) |
| `data/*.csv` | the same sheets as CSV |
| `charts/*.svg`, `charts/*.png` | every chart, rendered |
| `ratecard_before.json`, `ratecard_before.md` | the diagnosis the package answers |
| `CHECKLIST.md` | the gates the builder must pass, with the command that checks a finished PPTX (`python3 -m storyforge gates <pptx> --story story.json`) |

## Rate card checks

| id | Check | Method |
|---|---|---|
| R01 | A governing thought exists and is first | script (position) plus judged (is it an answer) |
| R02 | SCQA opening present | judged |
| R03 | Pyramid depth: answer, 3 to 5 reasons, supports | script over `story.json`, judged over `deck.json` |
| R04 | MECE at each level | judged, two blind passes |
| R05 | Vertical logic: body proves title | judged, two blind passes |
| R06 | Horizontal logic: siblings parallel and of one type | script (grammatical parallelism) plus judged |
| R07 | One message per slide | script (one title sentence) plus judged |
| R08 | SVOM title: lexical filter | script (`svom_problems`) |
| R09 | SVOM title: role dissection verified | model proposes roles, script verifies ordered substrings and presence of subject, verb, object, measure |
| R10 | Title at most two lines (chars per line from the renderer) | script |
| R11 | No "xxx: yyy" title, no two sentences | script |
| R12 | Key and detail split explicit | script |
| R13 | Every number in a title names its metric and base, and shares carry the total | script (regex over `numbers[]`) |
| R14 | Observed versus modeled marked | judged |
| R15 | Tradeoffs present where the decision is not yes or no | judged, gated by `frame.decision` |
| R16 | Every chart has title, units, source | script |
| R17 | Every chart has one callout | script |
| R18 | Editorial filler absent; relative comparisons name the benchmark | script |
| R19 | Summary bullets equal slide titles verbatim | script |
| R20 | Every title number traces to a data row | script |
| R21 | Read the titles alone: one argument that reaches the decision | judged, two blind passes |
| R22 | Spatial gate (SlideForge pptx-review) | script |

## Components

Repo `~/repos/storyforge`, Python package `storyforge`, CLI `python3 -m storyforge <command>`.

| Module | Does | Depends on |
|---|---|---|
| `ingest/pptx.py` | PPTX to `deck.json` | python-pptx |
| `ingest/html.py` | HTML deck (`section.slide`) to `deck.json` | Playwright |
| `ingest/gslides.py` | Google Slides JSON (from the MCP read) to `deck.json` | none |
| `schema.py` | JSON schemas and `validate(kind, obj)` | jsonschema |
| `checks/titles.py` | R08 to R11, R13 | regex |
| `checks/structure.py` | R03, R07, R12, R19 | `story.json` |
| `checks/numbers.py` | R20: numbers to rows (CSV, JSON or Postgres through pg-exec) | |
| `checks/editorial.py` | R18 | `assets/editorial_standard.json` |
| `checks/charts.py` | R16, R17 | chart specs |
| `judge/` | rubric prompts for judged checks; `verify_roles.py` verifies model output | agent runs them |
| `ratecard.py` | assembles `ratecard.json`, renders `ratecard.md` | |
| `storylines.py` | scores candidate `story.json` files | checks |
| `charts.py` | chart specs to SVG through svg-charts, SVG to PNG through Playwright | node, svg-charts |
| `render/deckcraft.py` | `story.json` to PPTX through deckcraft-cli, style file for tokens | |
| `render/html.py` | `story.json` to one HTML deck with inline SVG | |
| `handoff.py` | `story.json` plus charts to the handoff package | openpyxl |
| `gates.py` | after rate card, verdict per gate, exit code 0 only on all PASS | SlideForge pptx-review |

svg-charts gains `title`, `unit`, `source`, `annotations[]` ({x, y or index, text}) on every
builder. That change lands in `~/repos/svg-charts` with its own tests.

The skill text lives at `~/.claude/skills/presentation-storytelling/SKILL.md`. It holds the
decision tree, the rubric for judged checks, the question policy (ask only what deck, brief
and data cannot answer, each with a default) and the commands.

## Error handling

- Ingest cannot read a slide: `deck.json` records the slide with `unreadable: true`; the
  rate card lists them and asks for the source file.
- A gate fails after three rewrite rounds: the run stops and the failing elements are
  listed; the deck is never called MBB-ready.
- A chart type outside the seven builders: a table is rendered and the gap is reported.
- A number in a title with no data row: FAIL on R20; nothing is invented.
- Judged passes disagree: the check reports `DISAGREE` with both verdicts.

## Testing

- Unit tests per check with positive and negative titles from `assets/mbb_titles.json`
  and synthetic titles.
- Ingest tests on the fixtures in `STORYFORGE_FIXTURES` (SKIP, reported, when absent).
- End to end: the rate card on deck A flags the known defects; a hand-written `story.json`
  builds, renders, passes every gate, and produces a handoff package whose `data.xlsx`
  sheets equal the chart rows in `story.json`.
- Renderer tests look at the PNGs: title inside its box, chart inside the body area,
  takeaway above the footer.

## Out of scope

Google Slides write-back, animation, speaker-note generation, restyle to a corporate
template (slideforge owns that).
