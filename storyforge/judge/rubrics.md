# Judged checks: rubrics for the two blind passes

A judged check is answered by a model twice, by two agents that share no context, each given
only this rubric and the deck text (`deck.json`, or `story.json` for the after card). Each pass
writes one JSON object per check. A script joins the passes: equal verdicts stand; unequal
verdicts become `DISAGREE`. The model never writes the final result.

Output per pass, per check:

```json
{"R04": {"verdict": "PASS", "evidence": [{"slides": [3, 4], "text": "why, in one sentence"}]}}
```

The joiner stores pass one as `pass_a` and pass two as `pass_b` in `judgments.json`.

Also in each pass, once per deck:

```json
{"implied_story": {"governing_thought": "...", "slides": [1], "reasons": ["...", "..."]} | null,
 "defects": [{"text": "...", "slides": [n]}],
 "off_path": [n, n]}
```

`implied_story` is the answer the deck states today, quoted or tightly paraphrased from the
summary or the first content slide. `null` when no slide states an answer. `off_path` lists
slides whose message is not needed to reach the implied answer.

## R01 A governing thought exists and is first

Question: does the first content slide state the deck's answer as one claim?
PASS: one sentence on the first content slide tells the reader what to decide or believe.
FAIL: the first content slide is an agenda, a topic list, a background slide, or several unranked points.

## R02 SCQA opening present

Question: before the answer, does the deck give the reader the situation they already accept, the complication that changed it, and the question that follows?
PASS: all three are present, in that order, in the first one or two slides, in at most four sentences.
FAIL: any of the three is missing, or the opening is longer than the answer.

## R03 Pyramid depth (over deck.json)

Question: can you draw the deck as one answer, three to five reasons, and supports under each?
PASS: you can list the reasons from the titles and place every key slide under one of them.
FAIL: fewer than three or more than five reasons, or key slides that sit under no reason.

## R04 MECE at each level

Question: at each level of the pyramid, do the siblings overlap, and do they leave a gap the reader will notice?
PASS: no two siblings make the same claim; no obvious reason is missing for the answer to hold.
FAIL: two siblings restate one claim, or a necessary reason is absent.

## R05 Vertical logic: body proves title

Question: for each slide, does the body (chart, table, bullets) contain the figures the title claims?
PASS: every number in the title appears in the body, and the body contains nothing that contradicts the title.
FAIL: a title number is absent from the body, or the body shows a figure that undercuts the title.

## R06 Horizontal logic

Question: are sibling titles of one type (all reasons, or all steps) and in parallel form (same subject position, same measure, same base)?
PASS: siblings share type and form.
FAIL: a mix of reasons and steps, or comparisons that change the measure or base between siblings.

## R07 One message per slide

Question: does each slide make one claim, with the body serving that claim only?
PASS: one claim per slide.
FAIL: two claims in the title, or a body that argues a second point.

## R14 Observed versus modeled marked

Question: can the reader tell which figures were measured and which were modeled or assumed?
PASS: every modeled or assumed figure carries a marker (model, scenario, assumed, if) in its title or subtitle.
FAIL: a modeled figure reads as a measured fact.

## R15 Tradeoffs present

Applies only when the frame's decision is not a yes or no. Question: does the deck show the options, the criteria, and what each option gives up?
PASS: at least two real options with what each costs.
FAIL: one option, or options with no stated cost.
NA: the decision is a yes or no.

## R21 Title read-through

Procedure: read only the slide titles, in order, nothing else. Question: do they form one argument that reaches the decision in the frame?
PASS: the titles alone take the reader from the situation to the decision with no step missing.
FAIL: a step is missing, a title breaks the chain, or the titles do not end in the decision.

## Necessity test (storylines)

For a candidate storyline, remove one reason at a time. Question: does the governing thought still hold without it?
Output `{"necessity": {"<candidate id>": {"<reason id>": true|false}}}` where `true` means the reason is necessary (the answer falls without it).
