import copy
import re

from storyforge import schema
from storyforge.ratecard import build_ratecard, render_md


def deck(**over):
    d = {
        'source': 'mini.pptx', 'format': 'pptx',
        'slides': [
            {'n': 1, 'id': 's1', 'title': 'Executive summary', 'subtitle': None, 'body': ['Q2 result: cost fell', 'What we propose: test first'], 'kind': 'summary', 'numbers': []},
            {'n': 2, 'id': 's2', 'title': 'Cost per order: down 34% in June', 'body': ['June $119'], 'kind': 'key', 'charts': [{'type': 'line', 'title': None}], 'numbers': []},
            {'n': 3, 'id': 's3', 'title': 'Product A cut June cost per order to $119, 5% below the $125 target.', 'body': [], 'kind': 'key', 'numbers': []},
            {'n': 4, 'id': 's4', 'title': 'Appendix', 'body': [], 'kind': 'appendix', 'numbers': []},
        ],
    }
    d.update(over)
    return d


def by_id(rc):
    return {c['id']: c for c in rc['checks']}


def test_colon_title_fails_r11_with_slide():
    rc = build_ratecard(deck())
    c = by_id(rc)
    assert c['R11']['result'] == 'FAIL' and c['R11']['evidence'][0]['slide'] == 's2'
    assert schema.validate('ratecard', rc) == []


def test_no_judgments_is_na_and_disagree_joins():
    rc = build_ratecard(deck())
    assert by_id(rc)['R04']['result'] == 'NA'
    rc = build_ratecard(deck(), judgments={'R04': {'pass_a': 'PASS', 'pass_b': 'FAIL'}})
    assert by_id(rc)['R04']['result'] == 'DISAGREE'
    rc = build_ratecard(deck(), judgments={'R04': {'pass_a': 'FAIL', 'pass_b': 'FAIL'}})
    assert by_id(rc)['R04']['result'] == 'FAIL'


def test_frame_missing_decision_yields_question_with_default():
    frame = {'audience': 'the CMO', 'provenance': {'audience': 'brief'}}
    rc = build_ratecard(deck(), frame=frame)
    fields = [q['field'] for q in rc['questions']]
    assert 'decision' in fields and 'audience' not in fields
    assert all(q['default'] and q['why'] for q in rc['questions']) and len(rc['questions']) <= 5


def test_summary_without_goals_block_is_a_defect():
    rc = build_ratecard(deck())
    assert any('goals block' in d['text'] for d in rc['diagnostic']['defects'])
    good = deck()
    good['slides'][0]['body'] = ['Our goal today: agree the Q3 plan', 'Q2 result']
    rc = build_ratecard(good)
    assert not any('goals block' in d['text'] for d in rc['diagnostic']['defects'])


def test_first_slide_not_summary_fails_r01():
    d = deck()
    d['slides'][0]['kind'] = 'key'
    rc = build_ratecard(d, judgments={'R01': {'pass_a': 'PASS', 'pass_b': 'PASS'}})
    assert by_id(rc)['R01']['result'] == 'FAIL'


def test_r16_chart_without_title():
    rc = build_ratecard(deck())
    assert by_id(rc)['R16']['result'] == 'FAIL' and by_id(rc)['R16']['evidence'][0]['slide'] == 's2'


def test_gap_and_implied_story():
    j = {'implied_story': {'governing_thought': 'Test first.', 'slides': [1], 'reasons': ['a']}}
    rc = build_ratecard(deck(), frame={'decision': 'approve $270k', 'provenance': {'decision': 'owner'}}, judgments=j)
    assert rc['story_unclear'] is False and 'approve $270k' in rc['diagnostic']['gap']


def test_render_md_rows_and_questions_last():
    rc = build_ratecard(deck(), frame={'provenance': {}})
    md = render_md(rc)
    assert len(re.findall(r'^\| R\d\d \|', md, re.M)) == 22
    assert md.rstrip().splitlines()[-1].startswith('- ') and '## Questions' in md
    assert '—' not in md


def test_join_passes_marks_disagreement():
    from storyforge.ratecard import join_passes
    a = {'R04': {'verdict': 'PASS', 'evidence': [{'slides': [1], 'text': 'a'}]}, 'R21': {'verdict': 'FAIL'}, 'implied_story': {'governing_thought': 'x', 'slides': [1]}, 'defects': [{'text': 'dup', 'slides': [2]}], 'off_path': [3, 4]}
    b = {'R04': {'verdict': 'FAIL', 'evidence': [{'slides': [2], 'text': 'b'}]}, 'R21': {'verdict': 'FAIL'}, 'defects': [{'text': 'Dup', 'slides': [2]}, {'text': 'other'}], 'off_path': [4]}
    j = join_passes(a, b)
    assert j['R04'] == {'pass_a': 'PASS', 'pass_b': 'FAIL', 'evidence': [{'pass': 'a', 'slides': [1], 'text': 'a'}, {'pass': 'b', 'slides': [2], 'text': 'b'}]}
    assert j['R21']['pass_a'] == j['R21']['pass_b'] == 'FAIL'
    assert [d['text'] for d in j['defects']] == ['dup', 'other'] and j['off_path'] == [4]
    rc = build_ratecard(deck(), judgments=j)
    assert by_id(rc)['R04']['result'] == 'DISAGREE' and by_id(rc)['R21']['result'] == 'FAIL'
