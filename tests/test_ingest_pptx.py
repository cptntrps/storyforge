import io

import pytest
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Inches

from storyforge import schema
from storyforge.ingest import ingest_pptx
from tests.conftest import fixture_path


def _png_bytes():
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (10, 10), (200, 30, 30)).save(buf, format='PNG')
    buf.seek(0)
    return buf


def _build_deck(path):
    prs = Presentation()

    s1 = prs.slides.add_slide(prs.slide_layouts[1])
    s1.shapes.title.text = 'Revenue rose 12% to $2.4M in Q2.'
    tf = s1.placeholders[1].text_frame
    tf.text = 'Product A took 55% of orders'
    tf.add_paragraph().text = 'Cost per order fell to $119'
    tf.add_paragraph().text = ''
    s1.notes_slide.notes_text_frame.text = 'Speaker note one'

    s2 = prs.slides.add_slide(prs.slide_layouts[5])
    s2.shapes.title.text = 'Appendix: weekly detail'
    table = s2.shapes.add_table(3, 3, Inches(0.5), Inches(1.5), Inches(4), Inches(1.5)).table
    for r in range(3):
        for c in range(3):
            table.cell(r, c).text = f'r{r}c{c}'
    data = CategoryChartData()
    data.categories = ['Apr', 'May', 'Jun']
    data.add_series('Spend', (10.0, 20.0, 30.0))
    data.add_series('Orders', (1.0, 2.0, 3.0))
    gf = s2.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(5), Inches(1.5), Inches(4), Inches(3), data)
    gf.chart.has_title = True
    gf.chart.chart_title.text_frame.text = 'Spend and orders'

    s3 = prs.slides.add_slide(prs.slide_layouts[6])
    s3.shapes.add_picture(_png_bytes(), Inches(1), Inches(1), Inches(2), Inches(2))

    prs.save(str(path))


def test_generated_deck(tmp_path):
    p = tmp_path / 'gen.pptx'
    _build_deck(p)
    deck = ingest_pptx(p)

    assert schema.validate('deck', deck) == []
    assert deck['format'] == 'pptx'
    assert [s['id'] for s in deck['slides']] == ['s1', 's2', 's3']

    s1, s2, s3 = deck['slides']
    assert s1['title'] == 'Revenue rose 12% to $2.4M in Q2.'
    assert s1['body'] == ['Product A took 55% of orders', 'Cost per order fell to $119']
    assert s1['notes'] == 'Speaker note one'
    assert s1['kind'] == 'key'
    values = {(n['value'], n['unit']) for n in s1['numbers']}
    assert (12.0, '%') in values and (119.0, '$') in values and (55.0, '%') in values

    assert s2['title'] == 'Appendix: weekly detail'
    assert s2['kind'] == 'appendix'
    assert s2['tables'] == [{'rows': [[f'r{r}c{c}' for c in range(3)] for r in range(3)]}]
    assert len(s2['charts']) == 1
    chart = s2['charts'][0]
    assert chart['type'] == 'bar'
    assert chart['title'] == 'Spend and orders'
    assert chart['categories'] == ['Apr', 'May', 'Jun']
    assert [s['name'] for s in chart['series']] == ['Spend', 'Orders']
    assert [s['values'] for s in chart['series']] == [[10.0, 20.0, 30.0], [1.0, 2.0, 3.0]]

    assert s3['unreadable'] is True
    assert s3['title'] == ''
    assert s3['body'] == []


def test_local_numbers_in():
    from storyforge.ingest.pptx import numbers_in
    found = numbers_in('CPO fell to $119, 5% below the $125 target; 2,495 orders; $270k spend; 1.6x return')
    got = [(n['value'], n['unit']) for n in found]
    assert got == [(119.0, '$'), (5.0, '%'), (125.0, '$'), (2495.0, None), (270000.0, '$'), (1.6, None)]
    assert all(n['context'] for n in found)


def test_fixture_pyramid_deck():
    p = fixture_path('deck_pyramid.pptx')
    deck = ingest_pptx(p)
    assert schema.validate('deck', deck) == []
    assert len(deck['slides']) >= 40
    assert all(s['title'].strip() for s in deck['slides'])
