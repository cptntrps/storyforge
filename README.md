# storyforge

Diagnose the story of a presentation, rewrite it as one pyramid, render it, and prove it with gates.

storyforge is the code behind the `presentation-storytelling` agent skill (`SKILL.md`). It takes a deck
(PPTX, Google Slides JSON or an HTML deck), returns a **rate card** of its storytelling, and, on your
go, rebuilds the deck from one contract, `story.json`, into a PPTX and a one-file HTML deck, or into a
**handoff package** another builder can work from.

- Scripts decide every gate. A model proposes titles, roles and judgments; a script verifies them.
- Judged checks (MECE, vertical and horizontal logic, title read-through) run as two blind passes that
  must agree; a disagreement is reported, not resolved.
- Every number in a title traces to a data row (CSV, JSON or Postgres), or the gate fails.
- Charts come from [svg-charts](https://github.com/cptntrps/svg-charts): inline SVG with title, unit,
  source, legend, one colour per entity and one callout.

## Install

```
git clone https://github.com/cptntrps/storyforge && cd storyforge
pip install jsonschema python-pptx openpyxl playwright pyyaml && python3 -m playwright install chromium
git clone https://github.com/cptntrps/svg-charts ~/repos/svg-charts   # or set STORYFORGE_SVG_CHARTS
```

Optional: [DeckCraft](https://github.com/storytold/deckcraft) (`deckcraft-cli`) for the PPTX renderer,
and the SlideForge `pptx-review` scripts for the spatial gate (R22 reports NA without them;
set `STORYFORGE_SPATIAL`).

## Use

```
python3 -m storyforge ingest deck.pptx -o work/deck.json
python3 -m storyforge ratecard work/deck.json --frame work/frame.json --judgments work/judgments.json -o work/ratecard.json
python3 -m storyforge validate work/story.json --rows rows.csv
python3 -m storyforge charts work/story.json -o work/charts
python3 -m storyforge build work/story.json --charts work/charts -o work/out --html
python3 -m storyforge gates work/out/deck.pptx --story work/story.json --rows rows.csv
python3 -m storyforge handoff work/story.json --charts work/charts --ratecard work/ratecard.json -o work/handoff
```

`SKILL.md` holds the decision tree, the question policy and the narration rules an agent follows;
`references/rubrics.md` holds the rubric for the judged checks.

## The 22 checks

| id | Check | Method |
|---|---|---|
| R01 | A governing thought exists and is first | script plus judged |
| R02 | SCQA opening present | judged |
| R03 | Pyramid depth: answer, 3 to 5 reasons, supports | script plus judged |
| R04 | MECE at each level | judged |
| R05 | Vertical logic: body proves title | judged |
| R06 | Horizontal logic: siblings parallel and of one type | script plus judged |
| R07 | One message per slide | script plus judged |
| R08 | SVOM title: lexical filter | script |
| R09 | SVOM title: role dissection verified | model proposes, script verifies |
| R10 | Title at most two lines | script |
| R11 | No "xxx: yyy" title, no two sentences | script |
| R12 | Key and detail split explicit | script |
| R13 | Every number names its metric and base | script |
| R14 | Observed versus modeled marked | judged |
| R15 | Tradeoffs present where the decision is not yes or no | judged |
| R16 | Every chart has title, units, source | script |
| R17 | Every chart has one callout | script |
| R18 | Editorial filler absent; comparisons name the benchmark | script |
| R19 | Summary bullets equal slide titles verbatim | script |
| R20 | Every title number traces to a data row | script |
| R21 | Read the titles alone: one argument that reaches the decision | judged |
| R22 | Spatial gate | script |

## Layout

`storyforge/ingest` readers, `storyforge/checks` the script checks, `storyforge/judge` the rubric,
`storyforge/render` the DeckCraft and HTML renderers, `storyforge/handoff.py` the package,
`storyforge/schemas` the JSON schemas, `storyforge/assets` the harvested rubric assets
(MBB title corpus with sources, slide element definitions, editorial contract, owner rules).
`tests/data/story_min.json` is a complete example story. Reference decks are not in this repository;
tests that need them read `STORYFORGE_FIXTURES` and SKIP otherwise.

## License

MIT.
