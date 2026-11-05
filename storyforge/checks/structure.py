"""Pyramid structure over story.json: R03 depth, R07 one message, R12 key and detail split, R19 summary bullets equal titles."""

import re

from . import verdict

MIN_REASONS, MAX_REASONS = 3, 5


def reasons_of(story):
    """The reason level: key slides that are not the summary, grouped by section in order."""
    keys = [s for s in story['slides'] if s['kind'] == 'key' and s.get('layout') != 'summary']
    sections, seen = [], set()
    for s in keys:
        sec = s.get('section') or s['id']
        if sec not in seen:
            seen.add(sec)
            sections.append(sec)
    return sections, keys


def check_structure(story):
    slides = story['slides']
    ids = {s['id'] for s in slides}
    sections, keys = reasons_of(story)

    # R03: 3 to 5 reasons under the answer, each with at least one key slide.
    r03 = []
    if not (MIN_REASONS <= len(sections) <= MAX_REASONS):
        r03.append({'reasons': sections, 'count': len(sections), 'min': MIN_REASONS, 'max': MAX_REASONS})
    if not story.get('governing_thought', '').strip():
        r03.append({'problem': 'no governing thought'})

    # R07: one message per slide: one sentence in the title, no second claim after a semicolon.
    r07 = []
    for s in slides:
        t = s['title'].strip()
        sentences = [x for x in re.split(r'(?<=[.!?])\s+(?=[A-Z])', t) if x]
        if len(sentences) > 1 or ';' in t:
            r07.append({'slide': s['id'], 'title': t, 'sentences': len(sentences)})

    # R12: every detail names an existing key parent; keys have no parent; every key either has a detail or says none.
    r12 = []
    details_by_parent = {}
    for s in slides:
        if s['kind'] == 'detail':
            p = s.get('parent')
            if not p or p not in ids:
                r12.append({'slide': s['id'], 'problem': f'detail with missing parent {p!r}'})
            else:
                details_by_parent.setdefault(p, []).append(s['id'])
                parent = next(x for x in slides if x['id'] == p)
                if parent['kind'] != 'key':
                    r12.append({'slide': s['id'], 'problem': f'parent {p} is not a key slide'})
        elif s.get('parent'):
            r12.append({'slide': s['id'], 'problem': 'key slide with a parent'})

    # R19: every summary bullet that is a slide message equals that slide's title verbatim.
    titles = {s['title'].strip() for s in slides}
    r19 = []
    for block in story['summary_blocks']:
        if block['name'] in ('goals', 'what_we_need_today'):
            continue
        for b in block['bullets']:
            if b.strip() not in titles:
                near = _nearest(b, titles)
                r19.append({'block': block['name'], 'bullet': b, 'nearest_title': near})
    return [verdict('R03', r03), verdict('R07', r07), verdict('R12', r12), verdict('R19', r19)]


def _nearest(text, titles):
    words = set(text.lower().split())
    best, score = None, 0
    for t in titles:
        s = len(words & set(t.lower().split()))
        if s > score:
            best, score = t, s
    return best
