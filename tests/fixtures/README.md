# Reference-deck fixtures

The reference decks are not part of this repository. Set `STORYFORGE_FIXTURES` to a
local directory that holds them. Tests that need a fixture report SKIP with the reason
when the variable is unset or the file is absent.

| File | What it is |
|---|---|
| `deck_a.html` | an HTML QBR deck, 9 key slides plus appendices (reference deck A) |
| `deck_pyramid.pptx` | a 40-plus slide DeckCraft-built pyramid deck |
| `deck_b.pptx` | a corporate PPTX brief (reference deck B) |
| `rows_a.csv` | the metrics table behind deck A, one row per period, product and funnel stage |
| `story_a.json` | the story contract written for deck A |

`tests/forbidden_words.txt` (gitignored) lists the client words that must not appear in
any committed asset; `tests/test_assets.py` checks it when the file exists.
