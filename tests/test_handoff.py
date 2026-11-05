import json

from openpyxl import load_workbook

from storyforge.handoff import GATES, build_handoff, chart_rows

EM_DASH = chr(0x2014)

RATECARD = {
    'checks': [{'id': 'R08', 'method': 'script', 'result': 'FAIL', 'evidence': [{'slide': 's1'}]}],
    'diagnostic': {'defects': [{'rank': 1, 'text': 'x'}]},
    'questions': [],
}

SPEC_FILES = ['BRIEF.md', 'story.json', 'data.xlsx', 'data/slides.csv', 'data/numbers.csv',
              'ratecard_before.json', 'ratecard_before.md', 'CHECKLIST.md']


def test_every_spec_file_exists(story_min, tmp_path):
    out = build_handoff(story_min, {}, RATECARD, tmp_path / 'handoff')
    assert out == tmp_path / 'handoff'
    missing = [f for f in SPEC_FILES if not (out / f).exists()]
    assert not missing, missing
    assert (out / 'charts').is_dir()
    for s in story_min['slides']:
        if s.get('chart') or s.get('table'):
            assert (out / 'data' / f"{s['id']}.csv").exists()
    assert json.loads((out / 'story.json').read_text()) == story_min


def test_xlsx_chart_sheet_rows_equal_story_rows(story_min, tmp_path):
    out = build_handoff(story_min, {}, RATECARD, tmp_path)
    wb = load_workbook(out / 'data.xlsx')
    assert wb.sheetnames[:2] == ['slides', 'numbers']
    rows = [list(r) for r in wb['q2_result'].iter_rows(values_only=True)]
    assert len(rows) == 4
    assert rows[0] == ['label', 'All products', 'Without Product A']
    assert [r[0] for r in rows[1:]] == ['Apr', 'May', 'Jun']
    assert [r[1] for r in rows[1:]] == [224, 171, 119]
    assert all(len(r) == 3 for r in rows)
    detail = next(s for s in story_min['slides'] if s['id'] == 'q2_detail')
    table_rows = [list(r) for r in wb['q2_detail'].iter_rows(values_only=True)]
    assert table_rows == detail['table']['rows']
    numbers = [list(r) for r in wb['numbers'].iter_rows(values_only=True)]
    assert numbers[0] == ['slide', 'value', 'metric', 'base', 'trace']
    assert len(numbers) - 1 == sum(len(s.get('numbers') or []) for s in story_min['slides'])
    assert json.loads(numbers[1][4]) == story_min['slides'][0]['numbers'][0]['trace']


def test_brief_has_one_section_per_slide_and_no_em_dash(story_min, tmp_path):
    out = build_handoff(story_min, {}, RATECARD, tmp_path)
    brief = (out / 'BRIEF.md').read_text()
    assert EM_DASH not in brief
    headings = [l for l in brief.splitlines() if l.startswith('## Slide ')]
    assert len(headings) == len(story_min['slides'])
    for n, s in enumerate(story_min['slides'], 1):
        assert f"## Slide {n}: {s['id']}" in brief
        assert s['title'] in brief
    assert 'data.xlsx sheet q2_result' in brief
    assert 'python3 -m storyforge gates <your.pptx> --story story.json' in brief
    for other in ('CHECKLIST.md', 'ratecard_before.md'):
        assert EM_DASH not in (out / other).read_text()


def test_checklist_names_every_gate(story_min, tmp_path):
    out = build_handoff(story_min, {}, RATECARD, tmp_path)
    text = (out / 'CHECKLIST.md').read_text()
    assert 'R01' in text and 'R22' in text
    assert all(f'| {g} |' in text for g in GATES)
    assert len(GATES) == 22


def test_ratecard_md_and_optional(story_min, tmp_path):
    out = build_handoff(story_min, {}, RATECARD, tmp_path / 'with')
    md = (out / 'ratecard_before.md').read_text()
    assert '| R08 | script | FAIL | 1 |' in md and '1. x' in md
    out2 = build_handoff(story_min, {}, None, tmp_path / 'without')
    assert not (out2 / 'ratecard_before.json').exists() and not (out2 / 'ratecard_before.md').exists()


def test_charts_copied_when_present(story_min, tmp_path):
    svg = tmp_path / 'c.svg'
    svg.write_text('<svg/>')
    out = build_handoff(story_min, {'q2_result': {'svg': svg, 'png': tmp_path / 'missing.png'}}, None, tmp_path / 'h')
    assert (out / 'charts' / 'q2_result.svg').read_text() == '<svg/>'
    assert not (out / 'charts' / 'q2_result.png').exists()


def test_chart_rows_per_type():
    assert chart_rows({'type': 'waterfall', 'items': [{'label': 'Start', 'value': 10, 'total': True}, {'label': 'A', 'value': -2}]}) == \
        [['label', 'value', 'total'], ['Start', 10, True], ['A', -2, False]]
    assert chart_rows({'type': 'scatter', 'groups': [{'name': 'g', 'points': [{'x': 1, 'y': 2}]}]}) == [['group', 'x', 'y'], ['g', 1, 2]]
    assert chart_rows({'type': 'dumbbell', 'rows': [{'label': 'r', 'a': 1, 'b': 3}]}) == [['label', 'a', 'b'], ['r', 1, 3]]
    assert chart_rows({'type': 'stackedBars', 'keys': ['k1', 'k2'], 'columns': [{'label': 'c', 'parts': {'k1': 0.4, 'k2': 0.6}}]}) == \
        [['label', 'k1', 'k2'], ['c', 0.4, 0.6]]
    assert chart_rows({'type': 'divergingBars', 'data': [{'label': 'a', 'value': -1}]}) == [['label', 'value'], ['a', -1]]
