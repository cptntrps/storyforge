# Decision tree (approved 2026-11-05)

"STOP" means the skill hands Gui an output and waits.

```
INPUT
├─ no file, only a topic ........................ STOP: ask for the deck or the data source
├─ outline or notes, no deck .................... go to FRAME with implied_story = none
└─ deck (PPTX, Google Slides, HTML, DeckCraft)
   └─ INGEST → deck.json
      ├─ text unreadable (image-only slides) .... STOP: list the slides it could not read, ask for the source file
      └─ readable
         └─ FRAME
            ├─ read implied story from titles, summary, ask slide, notes
            │  ├─ governing thought found ....... implied_story, with the slides that carry it
            │  └─ none found .................... story_unclear = true
            ├─ frame known (audience, decision, question)?
            │  ├─ brief present ................. frame.json
            │  ├─ inferable from the deck ....... frame.json marked "inferred, confirm"
            │  └─ neither ....................... questions
            └─ OUTPUT 1, always: RATE CARD ........................................ STOP
               • scorecard: each rubric check, method (script or judged), PASS/FAIL, evidence slide
               • diagnostic: the story the deck tells today, the gap to the frame,
                 slides off the path, top defects ranked
               • questions: only what deck, brief and data cannot answer; at most 5,
                 each with a default and the reason
               └─ Gui's answers
                  ├─ frame confirmed, story clear ............ go to NARRATE
                  ├─ story unclear ........................... go to STORYLINES
                  ├─ the decision needs data the deck lacks .. STOP: name the missing rows; nothing is invented
                  └─ "rate card is enough" ................... END (evaluation only)

STORYLINES
├─ generate 2 to 3 candidates (inductive, deductive, tradeoff)
├─ score each: key-slide count, necessity per reason, objection coverage,
│  data trace per claim, numbers the reader must hold, read-through (judged, 2 blind passes)
├─ one candidate dominates .......................... choose, record why, go to NARRATE
└─ tie, or the choice is taste (recommend vs. tradeoff frame) ... STOP: show both with scores, one question

NARRATE → story.json
├─ schema and gates: summary bullets equal titles, every title number traces to a row,
│  SVOM role dissection verified, editorial filler
├─ PASS .......................................... go to CHARTS
└─ FAIL .......................................... rewrite only the failing element, 3 rounds max,
                                                   then STOP with the failing titles listed

CHARTS (svg-charts) → one SVG per chart spec, with title, units, source, one callout
├─ chart type not among the 7 builders .......... table instead, and the gap is reported, never hand-drawn
└─ check PASS
   ├─ build here ................................ go to SLIDES
   └─ build elsewhere (corporate PowerPoint, another agent) ... go to HANDOFF

HANDOFF → handoff/ package .......................................................... END
   • BRIEF.md: the output description, one section per slide (title, subtitle, takeaway,
     callout, layout sketch, chart or table reference, source)
   • story.json, data.xlsx and data/*.csv (one sheet per chart or table, numbers with traces,
     slides sheet), charts/*.svg and *.png, ratecard_before, CHECKLIST.md with the gate command
   • the builder runs `python3 -m storyforge gates <pptx> --story story.json` on its result

SLIDES
├─ DeckCraft PPTX from story.json → spatial gate
│  └─ FAIL ...................................... shorten or relayout, 3 rounds, then STOP with the slide numbers
├─ HTML deck from the same story.json
└─ GATES → OUTPUT 2: AFTER RATE CARD
   ├─ all PASS ................................... END: PPTX, PDF, HTML, before/after rate card, "MBB-ready"
   └─ any FAIL ................................... END: same files marked draft, FAIL rows listed; never "MBB-ready"
```

Rules the tree encodes: scripts decide every gate, the model proposes and never enforces;
the skill asks only when deck, brief and data cannot answer, and each question carries a default.
