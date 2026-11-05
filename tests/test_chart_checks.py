import copy

from storyforge.checks.charts import check_charts


def by_id(checks):
    return {(c.id, c.result): c for c in checks}


def test_story_min_charts_pass(story_min):
    res = {c.id: c.result for c in check_charts(story_min)}
    assert res == {'R16': 'PASS', 'R17': 'PASS'}


def test_missing_unit_fails(story_min):
    s = copy.deepcopy(story_min)
    del s['slides'][1]['chart']['unit']
    c = [x for x in check_charts(s) if x.id == 'R16'][0]
    assert c.result == 'FAIL' and c.evidence[0] == {'slide': 'q2_result', 'missing': ['unit']}


def test_two_annotations_fail(story_min):
    s = copy.deepcopy(story_min)
    s['slides'][1]['chart']['annotations'] = [{'index': 0, 'text': 'a'}, {'index': 1, 'text': 'b'}]
    c = [x for x in check_charts(s) if x.id == 'R17'][0]
    assert c.result == 'FAIL' and c.evidence[0]['annotations'] == 2


def test_pie_is_na(story_min):
    s = copy.deepcopy(story_min)
    s['slides'][1]['chart']['type'] = 'pie'
    na = [x for x in check_charts(s) if x.result == 'NA']
    assert na and na[0].evidence[0]['note'] == 'not a builder; rendered as table'
