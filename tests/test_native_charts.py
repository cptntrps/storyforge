"""Native chart shapes in the built deck (storyforge.native_charts through svg-charts deck/chart.py)."""
import json
import shutil
from pathlib import Path

import pytest
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from storyforge.native_charts import deck_script, native_spec
from storyforge.render.deckcraft import render_pptx

DATA = Path(__file__).parent / 'data'
needs_tools = pytest.mark.skipif(not (shutil.which('node') and shutil.which('deckcraft-cli') and deck_script().exists()),
                                 reason='node, deckcraft-cli or svg-charts deck/chart.py is missing: native charts did not run')


def test_native_spec_follows_the_unit_and_the_chart_type():
    line = {'type': 'lineChart', 'title': 'Cost per order by month', 'unit': '$', 'source': 'S', 'labels': ['a', 'b'],
            'series': [{'name': 'x', 'points': [{'x': 'a', 'y': 1}, {'x': 'b', 'y': 2}]}], 'takeaway': 'not a chart field', 'width': 300}
    spec = native_spec(line, {'x': '#112233'})
    assert spec['chart'] == 'lineChart' and spec['legend'] is True and spec['valueLabels'] is True
    assert spec['format'] == {'prefix': '$', 'maxDecimals': 2}
    assert spec['colors'] == {'x': '#112233'}
    assert 'takeaway' not in spec and 'width' not in spec and 'type' not in spec
    assert native_spec({'type': 'barChart', 'unit': '%', 'data': []})['format'] == {'suffix': '%', 'maxDecimals': 2}
    assert 'format' not in native_spec({'type': 'stackedBars', 'unit': '%', 'columns': [], 'keys': []})
    with pytest.raises(ValueError):
        native_spec({'type': 'radar'})


@needs_tools
def test_a_single_chart_becomes_native_shapes_and_a_crowded_row_keeps_its_pictures(tmp_path):
    story = json.loads((DATA / 'story_min.json').read_text(encoding='utf-8'))
    report = []
    pptx = render_pptx(story, {}, tmp_path, native=True, report=report)
    by_ref = {r['ref']: r for r in report}
    assert by_ref['q2_result']['native'] is True
    slide = Presentation(str(pptx)).slides[by_ref['q2_result']['slide'] - 1]
    chart = next(s for s in slide.shapes if s.name == 'Chart')
    assert chart.shape_type == MSO_SHAPE_TYPE.GROUP, 'the chart is a group of native shapes, not a picture'
    texts = [s.text_frame.text for s in chart.shapes if s.has_text_frame]
    assert 'Cost per order by month · $' in texts, 'the chart title is about the data and has the unit'
    assert any(t.startswith('Source: ') for t in texts)
    assert any(s.name.startswith('All products Jun') for s in chart.shapes), 'each mark carries its value as its name'
    row = [r for r in report if r['ref'].startswith('q2_by_product#')]
    assert len({r['native'] for r in row}) == 1, 'the charts of one slide are native together or not at all'
    for r in row:
        assert r['native'] or r['reason'], 'a chart that stays a picture says why'
    assert (tmp_path / 'native' / 'report.json').exists()
    assert sorted(p.name for p in (tmp_path / 'png').glob('*.png')), 'the previews are rendered again from the changed deck'


@needs_tools
def test_pictures_stay_when_native_is_off(tmp_path):
    story = json.loads((DATA / 'story_min.json').read_text(encoding='utf-8'))
    pptx = render_pptx(story, {}, tmp_path)
    for slide in Presentation(str(pptx)).slides:
        assert not [s for s in slide.shapes if s.shape_type == MSO_SHAPE_TYPE.GROUP and s.name.startswith('Chart')]
    assert not (tmp_path / 'native').exists()
