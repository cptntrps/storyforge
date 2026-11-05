import copy

import pytest

from storyforge.charts import DEFAULT_SVG_CHARTS, render_charts, render_svg, spec_for


def need_node():
    if not DEFAULT_SVG_CHARTS.exists():
        pytest.skip(f'svg-charts not found at {DEFAULT_SVG_CHARTS}')


def test_spec_drops_storyforge_keys(story_min):
    ch = dict(story_min['slides'][1]['chart'], type='lineChart', note='x')
    s = spec_for(ch)
    assert 'type' not in s and 'note' not in s and s['title'] == 'Cost per order by month' and len(s['annotations']) == 1


def test_render_svg_has_title_unit_source_callout(story_min):
    need_node()
    svg = render_svg(story_min['slides'][1]['chart'])
    assert svg.startswith('<svg') and 'Cost per order by month' in svg and 'Source:' in svg and 'under the $125 target' in svg


def test_render_charts_writes_svg_and_png(story_min, tmp_path):
    need_node()
    res = render_charts(story_min, tmp_path)
    assert set(res) == {'q2_result', 'q2_by_product', 'what_we_see'}
    assert res['q2_result']['svg'].read_text().startswith('<svg')
    assert res['q2_result']['png'].stat().st_size > 1000
    items = res['q2_by_product']['items']
    assert len(items) == 3 and all(i['png'].stat().st_size > 1000 for i in items)
    assert (tmp_path / 'q2_by_product_1.svg').exists() and 'Share of June spend' in items[1]['svg'].read_text()
    assert 'viewBox="0 0 420 210"' in items[0]['svg'].read_text(), 'a chart row with a table renders wide and short'


def test_non_builder_becomes_table(story_min, tmp_path):
    need_node()
    s = copy.deepcopy(story_min)
    s['slides'][1]['chart'] = {'type': 'pie', 'title': 'x', 'unit': '%', 'source': 's', 'rows': [['a', 1]], 'annotations': [{'index': 0, 'text': 't'}]}
    res = render_charts(s, tmp_path, png=False)
    assert res['q2_result']['table'] == [['a', 1]] and 'not a builder' in res['q2_result']['gap']


def test_layout_sizes_apply_unless_given(story_min):
    ch = story_min['slides'][1]['chart']
    assert spec_for(ch, 'charts_row')['width'] == 420 and spec_for(ch, 'chart_left')['width'] == 700
    assert spec_for(dict(ch, width=333), 'charts_row')['width'] == 333
    assert spec_for(ch, 'chart_left')['legend'] is True and spec_for(ch, 'chart_left')['valueLabels'] is True
    assert spec_for(ch, 'chart_left', {'Product A': '#1f5fbf'})['colors'] == {'Product A': '#1f5fbf'}
