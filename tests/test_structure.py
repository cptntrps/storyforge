import copy

from storyforge.checks.structure import check_structure


def by_id(checks):
    return {c.id: c for c in checks}


def test_story_min_passes(story_min):
    c = by_id(check_structure(story_min))
    assert {k: v.result for k, v in c.items()} == {'R03': 'PASS', 'R07': 'PASS', 'R12': 'PASS', 'R19': 'PASS'}, {k: v.evidence for k, v in c.items()}


def test_r03_counts_reasons(story_min):
    one = copy.deepcopy(story_min)
    for s in one['slides']:
        if s['kind'] == 'key' and s['layout'] != 'summary':
            s['section'] = 'Only'
    assert by_id(check_structure(one))['R03'].result == 'FAIL'
    six = copy.deepcopy(story_min)
    for i, s in enumerate(six['slides']):
        s['section'] = f'S{i}'
    six['slides'] += [dict(six['slides'][1], id=f'x{i}', section=f'T{i}', parent=None) for i in range(3)]
    assert by_id(check_structure(six))['R03'].result == 'FAIL'


def test_r12_missing_parent(story_min):
    bad = copy.deepcopy(story_min)
    bad['slides'][2]['parent'] = 'ghost'
    e = by_id(check_structure(bad))['R12']
    assert e.result == 'FAIL' and 'ghost' in e.evidence[0]['problem']


def test_r19_one_word_difference(story_min):
    bad = copy.deepcopy(story_min)
    bad['summary_blocks'][1]['bullets'][0] = bad['summary_blocks'][1]['bullets'][0].replace('$119', '$120')
    e = by_id(check_structure(bad))['R19']
    assert e.result == 'FAIL' and '$120' in e.evidence[0]['bullet'] and '$119' in e.evidence[0]['nearest_title']


def test_r07_two_sentences(story_min):
    bad = copy.deepcopy(story_min)
    bad['slides'][1]['title'] = 'Costs fell 10% in June. Orders rose 5% in June.'
    assert by_id(check_structure(bad))['R07'].result == 'FAIL'
