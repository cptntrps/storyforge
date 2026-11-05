import json

from openpyxl import load_workbook

import copy

import pytest

from storyforge.handoff import GATES, LAYOUT_SKETCHES, build_handoff, chart_rows, data_sheets, sheet_name

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
        if s.get('charts'):
            for i in range(1, len(s['charts']) + 1):
                assert (out / 'data' / f"{s['id']}_{i}.csv").exists()
        elif s.get('chart') or s.get('table'):
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
    section = brief.split('## Slide 3: q2_by_product')[1].split('## Slide 4')[0]
    assert '- Charts: 3, left to right' in section
    for i, c in enumerate(story_min['slides'][2]['charts'], 1):
        assert f'- Chart {i}: takeaway "{c["takeaway"]}", type {c["type"]}' in section
        assert f'data.xlsx sheet q2_by_product_{i}' in section
    assert '### charts_row' in brief and LAYOUT_SKETCHES['charts_row'] in brief
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


def test_charts_row_slide_gets_one_sheet_per_chart(story_min, tmp_path):
    out = build_handoff(story_min, {}, None, tmp_path)
    wb = load_workbook(out / 'data.xlsx')
    assert [n for n in wb.sheetnames if n.startswith('q2_by_product_')] == ['q2_by_product_1', 'q2_by_product_2', 'q2_by_product_3']
    header = lambda n: list(next(wb[n].iter_rows(values_only=True)))
    assert header('q2_by_product_1') == ['label', 'value']
    assert header('q2_by_product_2') == ['label', 'Product A', 'Product B', 'Product C']
    assert header('q2_by_product_3') == ['label', 'Spend', 'Revenue']
    assert [list(r) for r in wb['q2_by_product_1'].iter_rows(values_only=True)][1:] == [['Product A', 4055], ['Product B', 870], ['Product C', 500]]
    assert [list(r) for r in wb['q2_by_product_2'].iter_rows(values_only=True)][1] == ['Spend', 75600, 140400, 54000]
    assert (out / 'data' / 'q2_by_product_2.csv').read_text().splitlines()[0] == 'label,Product A,Product B,Product C'
    assert sheet_name('a' * 40, 2) == 'a' * 29 + '_2'


def test_charts_row_items_copied(story_min, tmp_path):
    items = []
    for i in range(1, 4):
        p = tmp_path / f'c{i}.svg'
        p.write_text(f'<svg id="{i}"/>')
        items.append({'svg': p, 'png': tmp_path / f'c{i}.png'})
    out = build_handoff(story_min, {'q2_by_product': {'items': items}}, None, tmp_path / 'h')
    for i in range(1, 4):
        assert (out / 'charts' / f'q2_by_product_{i}.svg').read_text() == f'<svg id="{i}"/>'
        assert not (out / 'charts' / f'q2_by_product_{i}.png').exists()


def test_colors_footnotes_implication_and_table_on_charts_row(story_min, tmp_path):
    out = build_handoff(story_min, {}, None, tmp_path)
    brief = (out / 'BRIEF.md').read_text()
    colours = brief.split('## Colours')[1].split('One section per slide')[0]
    for entity, hexv in story_min['colors'].items():
        assert f'| {entity} | {hexv} |' in colours
    slide = next(s for s in story_min['slides'] if s['id'] == 'q2_by_product')
    section = brief.split('## Slide 3: q2_by_product')[1].split('## Slide 4')[0]
    assert f"- Implication: {slide['implication']}" in section
    for i, f in enumerate(slide['footnotes'], 1):
        assert f'  {i}. {f}' in section
    assert 'data.xlsx sheet q2_by_product_3' in section and '- Table: 4 rows plus header, data: see data.xlsx sheet q2_by_product' in section
    wb = load_workbook(out / 'data.xlsx')
    assert [n for n in wb.sheetnames if n.startswith('q2_by_product')] == ['q2_by_product_1', 'q2_by_product_2', 'q2_by_product_3', 'q2_by_product']
    assert [list(r) for r in wb['q2_by_product'].iter_rows(values_only=True)] == slide['table']['rows']
    assert [list(r) for r in wb['colors'].iter_rows(values_only=True)] == [['entity', 'hex']] + [list(kv) for kv in story_min['colors'].items()]
    slides = [list(r) for r in wb['slides'].iter_rows(values_only=True)]
    header = slides[0]
    assert 'implication' in header and 'footnotes' in header
    row = next(r for r in slides[1:] if r[0] == 'q2_by_product')
    assert row[header.index('implication')] == slide['implication']
    assert row[header.index('footnotes')] == ' | '.join(slide['footnotes'])
    assert (out / 'data' / 'colors.csv').read_text().splitlines()[0] == 'entity,hex'
    assert (out / 'data' / 'q2_by_product.csv').exists()


def test_sheet_name_collision_fails_loudly(story_min):
    bad = copy.deepcopy(story_min)
    clash = copy.deepcopy(bad['slides'][3])
    clash['id'] = 'q2_by_product_1'
    bad['slides'].append(clash)
    with pytest.raises(ValueError, match='collision'):
        data_sheets(bad)
