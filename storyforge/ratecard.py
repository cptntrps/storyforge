"""Rate card: the diagnosis of a deck. Scripts decide what they can; judged checks come in from judgments.json
(two blind passes) and a script joins them. Output validates against ratecard.schema.json."""

import json

from . import schema
from .checks import Check
from .checks.charts import BUILDERS
from .checks.editorial import check_editorial
from .checks.titles import check_titles

JUDGED = {
    'R01': 'A governing thought exists and is first',
    'R02': 'SCQA opening present',
    'R03': 'Pyramid depth: answer, 3 to 5 reasons, supports',
    'R04': 'MECE at each level',
    'R05': 'Vertical logic: body proves title',
    'R06': 'Horizontal logic: siblings parallel and of one type',
    'R07': 'One message per slide',
    'R14': 'Observed versus modeled marked',
    'R15': 'Tradeoffs present where the decision is not yes or no',
    'R21': 'Read the titles alone: one argument that reaches the decision',
}
SCRIPT_ONLY_AFTER = {'R12': 'Key and detail split explicit', 'R19': 'Summary bullets equal slide titles verbatim',
                     'R20': 'Every title number traces to a data row', 'R22': 'Spatial gate'}
MEANING = {
    **JUDGED, **SCRIPT_ONLY_AFTER,
    'R08': 'SVOM title: lexical filter', 'R09': 'SVOM title: role dissection verified', 'R10': 'Title at most two lines',
    'R11': 'No "xxx: yyy" title, no two sentences', 'R13': 'Every number names its metric and base',
    'R16': 'Every chart has title, units, source', 'R17': 'Every chart has one callout',
    'R18': 'Editorial filler absent; comparisons name the benchmark',
}
ORDER = [f'R{i:02d}' for i in range(1, 23)]
FRAME_QUESTIONS = [
    ('audience', 'Who reads this deck and takes the decision?', 'the executive who approves the budget', 'the storyline is built for one reader'),
    ('decision', 'What decision must the audience take at the end?', 'approve the proposed plan and its gates', 'the governing thought is the answer to this decision'),
    ('question', 'What question is in the reader\'s mind when the deck opens?', 'how much can we grow without breaking the target', 'the SCQA opening answers this question'),
    ('objections', 'What will the audience object to?', 'reliance on one product; untested scale; budget source', 'each objection needs a slide or a stated gap'),
    ('data_available', 'Which data tables back the figures?', 'the export behind the current deck', 'every title number must trace to a row'),
]
CONTENT_KINDS = ('summary', 'key', 'detail')


def _content(deck):
    return [s for s in deck['slides'] if s.get('kind') in CONTENT_KINDS and not s.get('unreadable')]


def _judged(check_id, judgments):
    j = (judgments or {}).get(check_id)
    if not j:
        return Check(check_id, 'judged', 'NA', [{'note': 'no judgment supplied'}])
    a, b = j.get('pass_a'), j.get('pass_b')
    ev = list(j.get('evidence') or [])
    if a == b:
        return Check(check_id, 'judged', a, ev)
    return Check(check_id, 'judged', 'DISAGREE', ev + [{'pass_a': a, 'pass_b': b}])


def _summary_goals_defect(deck):
    """Owner rule OR17: the executive summary opens with a goals block."""
    summ = next((s for s in deck['slides'] if s.get('kind') == 'summary'), None)
    if not summ:
        return {'text': 'no executive summary slide found', 'slides': []}
    head = ' '.join([summ.get('subtitle') or ''] + summ.get('body', [])[:4]).lower()
    if 'goal' not in head and 'objective' not in head:
        return {'text': 'the executive summary has no goals block in its first block', 'slides': [summ['n']]}
    return None


def build_ratecard(deck, frame=None, judgments=None, stage='before'):
    errs = schema.validate('deck', deck)
    if errs:
        raise ValueError('invalid deck.json: ' + '; '.join(errs[:5]))
    if judgments:
        errs = schema.validate('judgments', judgments)
        if errs:
            raise ValueError('invalid judgments.json: ' + '; '.join(errs[:5]))
    slides = _content(deck)
    checks = {}

    for c in check_titles(slides):
        checks[c.id] = c
    for c in check_editorial([(s.get('id') or s['n'], ' '.join([s.get('title') or ''] + list(s.get('body') or []))) for s in slides]):
        checks[c.id] = c

    # R16 on an ingested deck: only the chart title is observable; unit and source need the story.
    r16 = [{'slide': s.get('id') or s['n'], 'chart': ch.get('type'), 'missing': ['title']}
           for s in slides for ch in s.get('charts', []) if not (ch.get('title') or '').strip()]
    n_charts = sum(len(s.get('charts', [])) for s in slides)
    checks['R16'] = Check('R16', 'script', 'NA' if n_charts == 0 else ('FAIL' if r16 else 'PASS'),
                          r16 + [{'note': 'unit and source are checked on story.json, not on an ingested deck'}])
    checks['R17'] = Check('R17', 'script', 'NA', [{'note': 'callouts are checked on story.json'}])

    # R01: a script part (the first content slide is the summary) and a judged part (it states an answer).
    first = slides[0] if slides else None
    j01 = _judged('R01', judgments)
    if first and first.get('kind') != 'summary':
        checks['R01'] = Check('R01', 'judged', 'FAIL', [{'first_slide': first['n'], 'kind': first.get('kind'), 'note': 'the first content slide is not the summary'}] + j01.evidence)
    else:
        checks['R01'] = j01
    for cid in ('R02', 'R03', 'R04', 'R05', 'R06', 'R14', 'R15', 'R21'):
        checks[cid] = _judged(cid, judgments)
    # R07: script part (one sentence per title) joined with the judged part.
    multi = [e for e in checks['R11'].evidence if 'more than one sentence' in e.get('problems', [])]
    j07 = _judged('R07', judgments)
    checks['R07'] = Check('R07', 'judged', 'FAIL' if multi else j07.result, multi + j07.evidence)
    for cid, why in SCRIPT_ONLY_AFTER.items():
        checks[cid] = Check(cid, 'script', 'NA', [{'note': f'{why}: needs story.json or the built deck'}])
    checks['R09'] = Check('R09', 'script', 'NA', [{'note': 'role dissection runs on story.json titles'}])

    implied = (judgments or {}).get('implied_story')
    defects = []
    g = _summary_goals_defect(deck)
    if g:
        defects.append(g)
    for d in (judgments or {}).get('defects', []):
        defects.append({'text': d['text'], 'slides': d.get('slides', [])})
    for cid in ORDER:
        c = checks[cid]
        if c.result == 'FAIL' and c.method == 'script':
            defects.append({'text': f'{cid} {MEANING[cid]}: {len(c.evidence)} slide(s)', 'slides': [e.get('slide') for e in c.evidence if 'slide' in e]})
    defects = [{'rank': i + 1, **d} for i, d in enumerate(defects)]

    gap = None
    if frame and frame.get('decision') and implied:
        gap = f"The deck argues: {implied['governing_thought']} The audience must decide: {frame['decision']}"
    elif frame and frame.get('decision') and not implied:
        gap = f"No governing thought found. The audience must decide: {frame['decision']}"

    questions = []
    prov = (frame or {}).get('provenance', {})
    for field, q, default, why in FRAME_QUESTIONS:
        val = (frame or {}).get(field)
        if not val or prov.get(field) in (None, 'missing'):
            questions.append({'field': field, 'q': q, 'default': default, 'why': why})
    if any(s.get('unreadable') for s in deck['slides']):
        unread = [s['n'] for s in deck['slides'] if s.get('unreadable')]
        questions.insert(0, {'field': 'source_file', 'q': f'Slides {unread} hold only pictures. Can you share the source file?',
                             'default': 'treat them as images without a message', 'why': 'the text behind them cannot be read'})
    rc = {
        'subject': deck.get('source', ''), 'stage': stage,
        'implied_story': implied, 'story_unclear': implied is None,
        'checks': [checks[c].to_dict() for c in ORDER],
        'diagnostic': {'gap': gap, 'off_path': list((judgments or {}).get('off_path', [])), 'defects': defects},
        'questions': questions[:5],
    }
    schema.require_valid('ratecard', rc)
    return rc


def render_md(rc):
    lines = [f"# Rate card ({rc.get('stage', 'before')}): {rc.get('subject', '')}", '']
    if rc.get('implied_story'):
        lines += ['**Story the deck tells today:** ' + rc['implied_story']['governing_thought'], '']
    else:
        lines += ['**Story the deck tells today:** not found (story unclear)', '']
    if rc['diagnostic'].get('gap'):
        lines += ['**Gap:** ' + rc['diagnostic']['gap'], '']
    lines += ['| Check | Meaning | Method | Result | Evidence |', '|---|---|---|---|---|']
    for c in rc['checks']:
        ev = c['evidence']
        first = ''
        if ev:
            e0 = ev[0]
            first = e0.get('title') or e0.get('note') or e0.get('text') or json.dumps(e0, ensure_ascii=False)
            first = first[:90]
        lines.append(f"| {c['id']} | {MEANING.get(c['id'], '')} | {c['method']} | {c['result']} | {len(ev)}: {first} |")
    if rc['diagnostic'].get('defects'):
        lines += ['', '## Defects, ranked', '']
        for d in rc['diagnostic']['defects']:
            lines.append(f"{d['rank']}. {d['text']}" + (f" (slides {d['slides']})" if d.get('slides') else ''))
    if rc['diagnostic'].get('off_path'):
        lines += ['', f"Slides off the path to the decision: {rc['diagnostic']['off_path']}"]
    if rc['questions']:
        lines += ['', '## Questions', '']
        for q in rc['questions']:
            lines.append(f"- {q['q']} Default: {q['default']}. Why: {q['why']}.")
    return '\n'.join(lines) + '\n'


def join_passes(pass_a, pass_b):
    """Two blind passes ({check_id: {verdict, evidence}, implied_story, defects, off_path}) into judgments.json.
    Pass A supplies the deck-level fields; pass B's defects are appended when their text is new."""
    out = {}
    ids = sorted({k for k in list(pass_a) + list(pass_b) if k.startswith('R') and k[1:].isdigit()})
    for cid in ids:
        a, b = pass_a.get(cid) or {}, pass_b.get(cid) or {}
        out[cid] = {'pass_a': a.get('verdict', 'NA'), 'pass_b': b.get('verdict', 'NA'),
                    'evidence': [{'pass': 'a', **e} for e in a.get('evidence', [])] + [{'pass': 'b', **e} for e in b.get('evidence', [])]}
    out['implied_story'] = pass_a.get('implied_story') or pass_b.get('implied_story')
    seen, defects = set(), []
    for d in list(pass_a.get('defects', [])) + list(pass_b.get('defects', [])):
        key = d['text'].strip().lower()[:60]
        if key not in seen:
            seen.add(key)
            defects.append(d)
    out['defects'] = defects
    out['off_path'] = sorted(set(pass_a.get('off_path', [])) & set(pass_b.get('off_path', [])))
    schema.require_valid('judgments', out)
    return out
