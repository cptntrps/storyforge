import copy
from pathlib import Path

from storyforge.checks.numbers import load_rows
from storyforge.storylines import score_storylines

ROWS = load_rows(Path(__file__).resolve().parent / 'data' / 'rows.csv')
FRAME = {'decision': 'approve the plan', 'objections': [{'id': 'obj_one_product', 'text': 'one product'}, {'id': 'obj_budget', 'text': 'budget'}], 'provenance': {}}


def test_full_trace_wins(story_min):
    a = copy.deepcopy(story_min)
    a['id'] = 'A'
    a['slides'][1]['numbers'][0]['trace'] = None
    b = copy.deepcopy(story_min)
    b['id'] = 'B'
    out = score_storylines([a, b], FRAME, ROWS, {})
    assert out['chosen'] == 'B' and out['why'].startswith('data_trace')


def test_identical_is_tie(story_min):
    a = copy.deepcopy(story_min)
    a['id'] = 'A'
    b = copy.deepcopy(story_min)
    b['id'] = 'B'
    out = score_storylines([a, b], FRAME, ROWS, {})
    assert out['chosen'] is None and out['tie'] == ['A', 'B']


def test_coverage_and_necessity_reported(story_min):
    a = copy.deepcopy(story_min)
    a['id'] = 'A'
    out = score_storylines([a], FRAME, ROWS, {'necessity': {'A': {'What we see': False}}})
    c = out['candidates'][0]
    assert c['coverage']['covered'] == ['obj_budget', 'obj_one_product'] and c['coverage']['missing'] == []
    assert c['necessity']['removable'] == ['What we see']
    assert out['chosen'] == 'A' and out['why'] == 'only candidate'
