# Presentation Storytelling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A skill plus a Python package that diagnoses a deck's story (rate card), writes a pyramid story contract, renders charts and slides, proves them with gates, or emits a handoff package for another builder.

**Architecture:** `story.json` is the one contract. Ingesters produce `deck.json`; checks are pure functions over `deck.json` or `story.json`; the agent supplies judged verdicts in `judgments.json`; `ratecard.py` joins both; renderers and `handoff.py` read `story.json`; `gates.py` re-runs the checks on the built PPTX.

**Tech Stack:** Python 3.12, python-pptx 1.0.2, Playwright (python), jsonschema 4.23, openpyxl 3.1.5, node 22 with `~/repos/svg-charts/charts.js`, deckcraft-cli, SlideForge pptx-review scripts at `/repos/SlideForge/pptx-review/scripts`.

**Spec:** `docs/superpowers/specs/2026-11-05-presentation-storytelling-design.md`

## Global Constraints

- No client, product or person name from any reference deck appears in this repo. Fixtures come from `STORYFORGE_FIXTURES` (a local directory); tests SKIP with a printed reason when a fixture is absent.
- Scripts decide every gate. The model proposes; a script verifies its proposal.
- Prose in ASD-STE100; no em dashes anywhere, including generated BRIEF.md.
- Commit after each task: `type: what and why (owner order 2026-11-05)`. No attribution lines.
- Every check returns `Check(id, method, result, evidence)` with `result` in PASS, FAIL, NA, DISAGREE.
- `python3 -m pytest -q` is green before each commit.

---

### Task 0: Package skeleton and schemas

**Files:**
- Create: `pyproject.toml`, `storyforge/__init__.py`, `storyforge/schema.py`, `storyforge/schemas/{deck,frame,story,ratecard,judgments}.schema.json`, `tests/test_schema.py`, `tests/fixtures/README.md`, `tests/conftest.py`

**Interfaces:**
- Produces: `schema.validate(kind: str, obj: dict) -> list[str]` (empty list means valid); `conftest.fixture_path(name) -> Path | pytest.skip`.
- `Check` dataclass in `storyforge/checks/__init__.py`: `id, method ('script'|'judged'), result, evidence: list[dict]`.

- [ ] Test: a minimal valid `story.json` validates; a slide without `title_roles` fails with the path in the message.
- [ ] Test: `fixture_path('deck_a.html')` skips when `STORYFORGE_FIXTURES` is unset.
- [ ] Implement schemas from the spec's Contracts section, `required` fields only where the spec says the field always exists.
- [ ] Commit: `feat: storyforge package, JSON schemas for deck, frame, story, ratecard, judgments`.

### Task 1: Harvested assets, sanitised

**Files:**
- Create: `tools/harvest.py` (reads the local source paths from `tools/harvest.local.json`, which is gitignored), `storyforge/assets/mbb_titles.json`, `storyforge/assets/element_definitions.json`, `storyforge/assets/editorial_standard.json`, `storyforge/assets/owner_rules.json`, `storyforge/assets/summary_blocks.json`, `tests/test_assets.py`

**Interfaces:**
- Produces: `assets.load(name) -> dict|list`.

- [ ] `mbb_titles.json`: the 17 verified entries only (`verify.status == 'verified'`), fields `firm, title, parts, pattern, reuse_template, url`.
- [ ] `editorial_standard.json`: rules, avoid_phrases, semantic_review; the `examples` block rewritten with neutral product names (`Product A`, `$125 target`).
- [ ] `owner_rules.json`: one row per rule, fields `id, rule, date, applies_to` (title, chart, summary, narrative, layout). Rules: SVOM titles; data, analysis, insight, so what, takeaway; key and detail slides; build in slide format first then HTML; callouts and takeaways; every chart has a title and units; parallelism in comparisons; number plus share of total; tradeoffs, not yes or no; falsify claims; primary MBB sources; no "xxx: yyy" titles; not wordy; no em dashes; no filler.
- [ ] `summary_blocks.json`: the five blocks in order with `name, purpose, max_bullets`.
- [ ] Test: no asset contains any word in `tests/forbidden_words.txt` (that file lists the client words and is itself gitignored; the test SKIPs when it is absent and says so).
- [ ] Test: every `mbb_titles` entry's parts are ordered substrings of its title.
- [ ] Commit: `feat: harvested rubric assets (MBB titles, element definitions, editorial contract, owner rules, summary blocks)`.

### Task 2: Title checks R08 to R11, R13

**Files:**
- Create: `storyforge/checks/titles.py`, `tests/test_titles.py`

**Interfaces:**
- Produces: `svom_problems(title) -> list[str]`; `check_titles(slides: list[dict], chars_per_line=70) -> list[Check]` covering R08, R10, R11, R13; `numbers_in(text) -> list[dict(value, unit, context)]`; `verify_roles(title, roles: dict) -> list[str]` (R09 verification: subject, verb, object, measure present, each an ordered substring).

- [ ] Tests for `svom_problems`: "Sales outlook" fails (no number, not a sentence); "Revenue: up 12%." fails (colon); "Winners implement all five strategies to multiply growth by 2×." passes; a 150-char title fails R10 at 70 chars per line.
- [ ] Tests for R13: "CPO fell 34%." fails (no metric base); "June CPO fell to $119, 5% below the $125 target." passes; "Product A took 55% of orders on 28% of spend." passes (share with total).
- [ ] Tests for `verify_roles`: parts out of order fail; a missing measure fails; every `mbb_titles` entry passes with its own parts mapped (subject→subject, verb→verb, the rest→object or measure).
- [ ] Commit: `feat: title checks R08 to R11 and R13, role verification for R09`.

### Task 3: Editorial check R18

**Files:** `storyforge/checks/editorial.py`, `tests/test_editorial.py`

**Interfaces:** `check_editorial(texts: list[tuple[str, str]]) -> list[Check]` (slide id, text).

- [ ] Test: "in order to" fails; "5% below target" fails (benchmark unnamed); "5% below the $125 target" passes; an em dash fails.
- [ ] Commit: `feat: editorial check R18 from the editorial contract`.

### Task 4: Structure checks R03, R07, R12, R19 over story.json

**Files:** `storyforge/checks/structure.py`, `tests/test_structure.py`, `tests/data/story_min.json`

**Interfaces:** `check_structure(story: dict) -> list[Check]`.

- [ ] Test: 3 reasons pass R03; 1 or 6 fail; a detail slide with a missing parent fails R12; a summary bullet that differs from its slide title by one word fails R19 with both strings in evidence; a title with two sentences fails R07.
- [ ] Commit: `feat: pyramid structure checks over story.json`.

### Task 5: Number trace R20

**Files:** `storyforge/checks/numbers.py`, `tests/test_numbers.py`, `tests/data/rows.csv`

**Interfaces:** `load_rows(source: str) -> list[dict]` for `.csv`, `.json`, or `pg://schema.table` (through `~/src/infrastructure/bin/pg-exec -At`); `check_number_trace(story, rows, tolerance=0.005) -> Check`; a title number traces when `trace` names a row filter and a column and the row value rounds to the title value.

- [ ] Test: a traced number passes; a number with no `trace` fails with the slide and the value; a trace whose row value differs by 2% fails.
- [ ] Test: `load_rows('pg://...')` is exercised only when `STORYFORGE_PG=1`; otherwise SKIP with reason.
- [ ] Commit: `feat: number to data-row trace R20`.

### Task 6: Chart checks R16, R17

**Files:** `storyforge/checks/charts.py`, `tests/test_chart_checks.py`

**Interfaces:** `check_charts(story) -> list[Check]`; a chart spec needs `type` in the seven builders, `title`, `unit`, `source`, exactly one `annotations` entry.

- [ ] Tests: missing unit fails R16; two annotations fail R17; type `pie` yields NA with evidence "not a builder; rendered as table".
- [ ] Commit: `feat: chart checks R16 and R17`.

### Task 7: PPTX ingest

**Files:** `storyforge/ingest/__init__.py`, `storyforge/ingest/pptx.py`, `tests/test_ingest_pptx.py`

**Interfaces:** `ingest_pptx(path) -> dict` (valid `deck.json`); title = the title placeholder or the top-most largest text box; `body[]` in reading order (top to bottom, left to right); tables as rows; native charts as `{type, categories, series:[{name, values}]}`; notes; `numbers[]` via `titles.numbers_in`; `kind` guess: cover (slide 1 with no body), summary (title contains "summary" or 4+ bullet groups), appendix (title starts with "Appendix"), detail (title contains "detail" or "back-up"), else key; `unreadable` when the slide has pictures and no text.

- [ ] Test on a generated PPTX (python-pptx builds it in the test: 3 slides, one table, one bar chart, one picture-only slide): titles, table rows, chart series, unreadable flag.
- [ ] Test on fixture `deck_pyramid.pptx` (SKIP when absent): 40+ slides, every slide has a title.
- [ ] Commit: `feat: PPTX ingest to deck.json`.

### Task 8: HTML ingest

**Files:** `storyforge/ingest/html.py`, `tests/test_ingest_html.py`

**Interfaces:** `ingest_html(path, selector='section.slide, section.appendix') -> dict`; Playwright renders the file, evaluates per section: first `h1|h2` as title, `.subtitle|h3` as subtitle, visible text runs, `table` rows, `svg[aria-label]` as charts with `title` from the aria-label; `hidden` sections become `kind: detail`.

- [ ] Test on `tests/data/mini_deck.html` (3 sections, one hidden, one table, one svg): titles, kinds, chart label.
- [ ] Test on fixture `deck_a.html` (SKIP when absent): 9 key slides, appendices present.
- [ ] Commit: `feat: HTML deck ingest through Playwright`.

### Task 9: Google Slides ingest

**Files:** `storyforge/ingest/gslides.py`, `tests/test_ingest_gslides.py`, `tests/data/gslides_min.json`

**Interfaces:** `ingest_gslides(presentation: dict) -> dict` from the Slides API JSON (`slides[].pageElements[].shape.text.textElements[].textRun.content`, `table.tableRows`, `sheetsChart` as chart with `type: 'sheetsChart'`).

- [ ] Test on the minimal JSON: title from the TITLE placeholder, body runs, table rows.
- [ ] Commit: `feat: Google Slides JSON ingest`.

### Task 10: Rate card

**Files:** `storyforge/ratecard.py`, `storyforge/judge/rubrics.md`, `storyforge/judge/judgments.example.json`, `tests/test_ratecard.py`

**Interfaces:** `build_ratecard(deck: dict, frame: dict|None, judgments: dict|None) -> dict` (valid `ratecard.json`); script checks run on `deck.json` (R07, R08, R10, R11, R13, R16, R18 over slide texts); judged checks (R01 judged part, R02, R04, R05, R06 judged part, R14, R15, R21) read `judgments[check_id] = {pass_a, pass_b, evidence}`; two passes equal → that result, else DISAGREE; missing judgment → NA with evidence "no judgment supplied"; `implied_story` from `judgments['implied_story']` or `null` with `story_unclear`; `questions[]` built from frame fields with provenance `missing` (at most 5, each with `default` and `why`); `render_md(ratecard) -> str`.
- `rubrics.md`: one section per judged check with the question, the PASS criterion, the FAIL criterion, and the output JSON shape; the agent runs two blind passes (two subagents, no shared context) and writes `judgments.json`.

- [ ] Test: a deck with colon titles yields FAIL on R11 with the slide numbers; no judgments yields NA on R04; `pass_a != pass_b` yields DISAGREE; a frame missing `decision` yields a question with a default.
- [ ] Test: `render_md` output has one row per check and the questions section last.
- [ ] Commit: `feat: rate card assembly and markdown rendering, judge rubrics`.

### Task 11: Storyline scoring

**Files:** `storyforge/storylines.py`, `tests/test_storylines.py`

**Interfaces:** `score_storylines(candidates: list[dict], frame: dict, rows: list[dict], judgments: dict) -> dict` (valid `storyline_scores.json`); `key_slides` = count of `kind == key`; `necessity` = reasons whose removal, per `judgments[cand_id]['necessity'][reason_id]`, breaks the governing thought; `coverage` = objections in `frame.objections` that some slide names in `covers[]`; `data_trace` = traced numbers over numbers; `numbers_held` = distinct numbers in key titles; `chosen` = the candidate that wins on data_trace, then coverage, then necessity, then fewer key slides, then fewer numbers; a tie on all five → `chosen: null`, `tie: [ids]`.

- [ ] Test: two candidates where B has full trace and A does not → B chosen with `why`; identical scores → tie.
- [ ] Commit: `feat: storyline scoring and choice`.

### Task 12: svg-charts gains title, unit, source, annotations

**Files (in `~/repos/svg-charts`):** `charts.js`, `test/charts.test.mjs` (node:test), `SKILL.md`, `README.md`, `demo.html`

**Interfaces:** every builder accepts `title` (drawn top-left, 14px, `--chart-ink`), `unit` (drawn after the title in `--chart-axis-text`, for example "CPO, $"), `source` (drawn bottom-left, 10px), `annotations: [{index|x, y?, text, series?}]` (a callout: a dot on the point, a short leader, the text in `--chart-ink` bold); the chart height grows by the title and source bands; `label` stays the aria-label and defaults to `title` when given.

- [ ] Test: `barChart({title:'T', unit:'$', source:'S', data:[...], annotations:[{index:1,text:'peak'}]})` output contains `>T<`, `$`, `Source: S`, and `peak`; without `title` the output is unchanged from today (snapshot test on one chart per builder).
- [ ] Update SKILL.md and demo.html with the new options.
- [ ] Commit in svg-charts: `feat: title, unit, source and one-callout annotations on every builder`; push.

### Task 13: Chart rendering bridge

**Files:** `storyforge/charts.py`, `storyforge/charts_bridge.mjs`, `tests/test_charts.py`

**Interfaces:** `render_charts(story, out_dir, svg_charts_path=Path('~/repos/svg-charts/charts.js')) -> dict[slide_id, {svg, png}]`; the bridge is `node charts_bridge.mjs <charts.js> <spec.json>` printing the SVG; PNG through Playwright (`page.set_content(svg); locator('svg').screenshot()` at 2x); a non-builder type returns `{table: rows}` and no files.

- [ ] Test: a story with one bar chart yields an `.svg` containing the title and a `.png` over 1 KB.
- [ ] Commit: `feat: chart rendering through svg-charts and Playwright`.

### Task 14: DeckCraft renderer

**Files:** `storyforge/render/__init__.py`, `storyforge/render/deckcraft.py`, `storyforge/render/styles/default.json`, `tests/test_render_deckcraft.py`

**Interfaces:** `render_pptx(story, charts: dict, out_dir, style='default') -> Path` (the .pptx; also `.deckcraft` and `png/`); layouts: `summary` (five blocks, two columns), `chart_left` (chart 67%, takeaway text 33%), `chart_full`, `table`, `three_columns`, `text_only`; every slide draws rule, title (max two lines at `chars_per_line` from the style), subtitle, body, source line, takeaway bar, footer with slide number and section; the chart PNG goes in through `insert.picture` with base64 `data`; the style file holds fonts, colours and the grid (from the harvested primitives, neutral footer text).

- [ ] Test: `story_min.json` renders; `deckcraft-cli info` lists the expected slide count; the PNG of slide 2 exists; `tests/test_render_deckcraft.py` also asserts no title longer than two lines by the style's chars_per_line.
- [ ] Commit: `feat: DeckCraft renderer from story.json with six layouts`.

### Task 15: HTML renderer

**Files:** `storyforge/render/html.py`, `storyforge/render/html_template.html`, `tests/test_render_html.py`

**Interfaces:** `render_html(story, charts, out_path) -> Path`; one file, inline SVG, `section.slide` per slide (so `ingest_html` reads it back), details `hidden` with a link from the parent, print CSS one slide per page.

- [ ] Test: render then `ingest_html` round-trips the titles exactly.
- [ ] Commit: `feat: HTML deck renderer with inline SVG charts`.

### Task 16: Handoff package

**Files:** `storyforge/handoff.py`, `storyforge/handoff_brief_template.md`, `tests/test_handoff.py`

**Interfaces:** `build_handoff(story, charts, ratecard_before: dict|None, out_dir) -> Path`; writes `BRIEF.md`, `story.json`, `data.xlsx` (sheets: `slides`, `numbers`, one per chart or table named by slide id), `data/*.csv` (same), `charts/*.svg|png`, `ratecard_before.json|md`, `CHECKLIST.md` (the gate list with the command `python3 -m storyforge gates <pptx> --story story.json`); `BRIEF.md` per slide: title, subtitle, takeaway, callout, layout name plus an ASCII layout sketch, chart or table reference, source, one speaker-note line.

- [ ] Test: for `story_min.json`, `data.xlsx` chart sheet rows equal the story's chart rows; `BRIEF.md` has one `## Slide` section per slide and no em dash; `CHECKLIST.md` names every gate id.
- [ ] Commit: `feat: handoff package with brief, xlsx, csv, charts and checklist`.

### Task 17: Gates

**Files:** `storyforge/gates.py`, `tests/test_gates.py`

**Interfaces:** `run_gates(pptx: Path, story: dict, rows: list[dict]|None, judgments: dict|None) -> dict` (an after `ratecard.json`); runs structure, titles, editorial, charts, numbers over `story`; ingests the PPTX and asserts its titles equal the story titles (evidence per mismatch); runs `analyze_pptx.py` then `spatial_analyzer.py --json` and maps violations to R22; `all_pass(ratecard) -> bool`; exit code 0 only on all PASS.

- [ ] Test: the rendered `story_min` deck passes structure and title equality; a PPTX whose title was edited fails with the slide number.
- [ ] Commit: `feat: after-gates over the built PPTX including the spatial gate`.

### Task 18: CLI

**Files:** `storyforge/__main__.py`, `tests/test_cli.py`

**Interfaces:** `python3 -m storyforge ingest <file> -o deck.json`; `ratecard deck.json [--frame frame.json] [--judgments judgments.json] -o ratecard.json` (also writes `.md`); `validate story.json`; `storylines cand1.json cand2.json --frame --rows --judgments -o scores.json`; `charts story.json -o out/charts`; `build story.json -o out/ [--html] [--style]`; `handoff story.json -o out/handoff [--ratecard ratecard.json]`; `gates out/deck.pptx --story story.json [--rows] [--judgments]`; every command exits non-zero on a schema error and prints the path of the invalid field.

- [ ] Test: `ingest` on `mini_deck.html` then `ratecard` produces a markdown table; `validate` on an invalid story exits 1.
- [ ] Commit: `feat: storyforge CLI`.

### Task 19: The skill

**Files:** `~/.claude/skills/presentation-storytelling/SKILL.md`, `~/.claude/skills/presentation-storytelling/references/rubrics.md` (copied from `storyforge/judge/rubrics.md`), `~/.claude/skills/presentation-storytelling/references/decision-tree.md`

**Content:** frontmatter `name`, `description` (triggers: review this deck, is the story clear, pyramid, SVOM titles, MBB-ready, rate card, handoff package); the decision tree; the commands per stage; the question policy; how to run two blind judged passes (two `Agent` subagents with the rubric and the deck text only, no shared context; write `judgments.json`); the Frame questions list with defaults; the narration rubric (governing thought, SCQA, five summary blocks, SVOM titles with roles, subtitle, takeaway, callout, chart spec with title, unit, source, one annotation); the handoff exit and when to take it (deck built on another machine or by another agent); the rule that the deck is called MBB-ready only on an all-PASS after rate card.

- [ ] Commit in `~/.claude/skills`: `feat: presentation-storytelling skill (owner order 2026-11-05)`.

### Task 20: End to end on the reference decks

**Files:** `tests/test_e2e.py`, `tests/fixtures/README.md` (how to set `STORYFORGE_FIXTURES`, the file names expected: `deck_a.html`, `deck_pyramid.pptx`, `deck_b.pptx`, `rows_a.csv`), local `story_a.json` written by the agent in `STORYFORGE_FIXTURES` (not committed)

- [ ] Rate card on `deck_a.html`: R11 or R08 flags at least one title; the summary slide's blocks are read and the first block is not a goals block (evidence in R01 or a `diagnostic.defects` entry "summary has no goals block").
- [ ] Rate card on `deck_b.pptx` runs with no error and produces questions.
- [ ] `story_a.json` validates, builds, and `gates` returns all PASS with `rows_a.csv`.
- [ ] `handoff` for `story_a.json` writes every file in the spec table.
- [ ] Record the four results in `docs/results/2026-11-05-e2e.md` as a table (fixture, command, result, evidence path).
- [ ] Commit: `test: end-to-end on the reference decks (local fixtures)`; bump VERSION to 0.2.0, tag.

## Self-review

- Spec coverage: every rate card id R01 to R22 maps to Task 2, 3, 4, 5, 6, 10 or 17. Contracts map to Task 0. Harvest to Task 1. Handoff to Task 16. svg-charts gap to Task 12. Skill to Task 19. Success tests 1 to 4 to Task 20.
- Names used across tasks: `Check`, `schema.validate`, `svom_problems`, `verify_roles`, `numbers_in`, `check_titles`, `check_editorial`, `check_structure`, `check_number_trace`, `load_rows`, `check_charts`, `ingest_pptx`, `ingest_html`, `ingest_gslides`, `build_ratecard`, `render_md`, `score_storylines`, `render_charts`, `render_pptx`, `render_html`, `build_handoff`, `run_gates`, `all_pass`.
