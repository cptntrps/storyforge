"""Score candidate storylines (each a story.json) and choose one. Efficiency is measured, not asserted."""

from .checks.numbers import check_number_trace
from .checks.structure import reasons_of

CRITERIA = ('data_trace', 'coverage', 'necessity', 'key_slides', 'numbers_held')


def score_one(story, frame, rows, judgments):
    cid = story.get('id') or story.get('title') or 'candidate'
    sections, keys = reasons_of(story)
    n_numbers = sum(len(s.get('numbers', [])) for s in story['slides'])
    traced = n_numbers
    if rows is not None:
        traced = n_numbers - len(check_number_trace(story, rows).evidence)
    objections = [o['id'] for o in (frame or {}).get('objections', [])]
    covered = {c for s in story['slides'] for c in s.get('covers', [])}
    nec = ((judgments or {}).get('necessity') or {}).get(cid, {})
    necessary = [r for r in sections if nec.get(r, True)]
    rt = (judgments or {}).get('read_through', {}).get(cid)
    held = len({n['value'] for s in keys for n in s.get('numbers', [])})
    return {
        'id': cid,
        'key_slides': len(keys) + sum(1 for s in story['slides'] if s.get('layout') == 'summary'),
        'reasons': sections,
        'necessity': {'necessary': necessary, 'removable': [r for r in sections if r not in necessary]},
        'coverage': {'covered': sorted(covered & set(objections)), 'missing': sorted(set(objections) - covered)},
        'data_trace': {'traced': traced, 'total': n_numbers},
        'numbers_held': held,
        'read_through': rt,
    }


def _key(sc):
    dt = sc['data_trace']
    trace_ratio = dt['traced'] / dt['total'] if dt['total'] else 1.0
    cov = len(sc['coverage']['covered']) - len(sc['coverage']['missing'])
    nec = -len(sc['necessity']['removable'])
    return (round(trace_ratio, 4), cov, nec, -sc['key_slides'], -sc['numbers_held'])


def score_storylines(candidates, frame=None, rows=None, judgments=None):
    scores = [score_one(c, frame, rows, judgments) for c in candidates]
    ranked = sorted(scores, key=_key, reverse=True)
    out = {'candidates': scores, 'criteria_order': list(CRITERIA), 'chosen': None, 'tie': [], 'why': None}
    if not ranked:
        return out
    top = _key(ranked[0])
    tied = [s['id'] for s in ranked if _key(s) == top]
    if len(tied) > 1:
        out['tie'] = tied
        out['why'] = 'equal on every criterion; the choice is taste and goes to the owner'
        return out
    best = ranked[0]
    out['chosen'] = best['id']
    reasons = []
    if len(ranked) > 1:
        second = ranked[1]
        for name, a, b in zip(CRITERIA, _key(best), _key(second)):
            if a != b:
                reasons.append(f'{name}: {a} against {b}')
                break
    out['why'] = reasons[0] if reasons else 'only candidate'
    return out
