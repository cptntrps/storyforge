import copy

import pytest

from storyforge.ingest.html import ingest_html
from storyforge.render.html import render_html

EM_DASH = chr(0x2014)


def _svg(title, text):
    return (f'<svg viewBox="0 0 100 40" role="img" aria-label="{title}">'
            f'<title>{title}</title><text x="1" y="10">{text}</text></svg>')


def _by_id(story):
    return {s['id']: s for s in story['slides']}


def test_round_trip_through_ingest_html(story_min, tmp_path):
    out = render_html(story_min, {}, tmp_path / 'deck.html')
    assert out.is_file()

    deck = ingest_html(out)
    assert [s['title'] for s in deck['slides']] == [s['title'] for s in story_min['slides']]
    assert [s['id'] for s in deck['slides']] == [s['id'] for s in story_min['slides']]
    got, want = _by_id(deck), _by_id(story_min)
    assert got['q2_detail']['kind'] == 'detail'
    assert got['q2_result']['subtitle'] == want['q2_result']['subtitle']
    assert got['q2_detail']['tables'] == [want['q2_detail']['table']]
    assert got['q2_by_product']['tables'] == [want['q2_by_product']['table']]
    # callout, takeaway, implication and footnotes are slide content, not speaker notes
    assert want['q2_result']['callout'] in got['q2_result']['body']
    assert want['q2_result']['takeaway'] in got['q2_result']['body']
    assert want['q2_by_product']['implication'] in got['q2_by_product']['body']
    for note in want['q2_by_product']['footnotes']:
        assert note in got['q2_by_product']['body']
    assert all(s['notes'] is None for s in deck['slides'])


def test_self_contained_and_clean(story_min, tmp_path):
    out = render_html(story_min, {}, tmp_path / 'deck.html')
    html = out.read_text()
    assert '<script' not in html
    assert 'http' not in html
    assert EM_DASH not in html
    for var in ('--chart-grid', '--chart-axis-text', '--chart-ink', '--chart-target',
                '--chart-1', '--chart-2', '--chart-3', '--chart-4', '--chart-5',
                '--bg:#f6f5f1', '--accent:#1f5fbf', '--s5:#9333ea'):
        assert var in html
    # dark scheme tokens, both the media query and the data-theme form
    assert '@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#111317' in html
    assert ':root[data-theme="dark"]{--bg:#111317' in html
    assert 'ui-sans-serif,system-ui' in html
    assert '@media print' in html
    assert html.count('<section class="slide') == len(story_min['slides'])
    assert '<section class="slide mbb detail-slide" id="q2_detail" data-kind="detail" hidden>' in html
    assert '<h2 class="title">' in html and '<p class="kicker">Q2</p>' in html
    assert 'href="#q2_detail"' in html
    assert 'href="#q2_result"' in html
    assert '<figure class="chart-missing">' in html
    assert '<p class="source">Source: Ad platform export, June 2025</p>' in html
    # summary as bcg rows, the goals row highlighted
    assert html.count('<div class="row ask"><div class="msg">') == 1
    assert html.count('<div class="msg">') == 5
    # numbers stay as written in the story
    assert '2,495 to 5,425' in html
    assert '$270k' in html


def test_charts_row_markup(story_min, tmp_path):
    slide = _by_id(story_min)['q2_by_product']
    out = render_html(story_min, {}, tmp_path / 'deck.html')
    html = out.read_text()
    section = html[html.index('id="q2_by_product"'):html.index('id="q2_detail"')]
    assert '<div class="mbb-cols" style="--n:3">' in section
    for n, chart in enumerate(slide['charts'], start=1):
        assert f'<p class="take"><span class="n">{n}</span><span>{chart["takeaway"]}</span></p>' in section
    assert section.count('<span class="n">') == 3
    # the callout is a compact line at the right end of the subtitle row, not a box like the implication
    assert (f'<div class="subrow"><p class="subtitle">{slide["subtitle"]}</p>'
            f'<p class="callout">{slide["callout"]}</p></div>') in section
    assert section.index('class="subrow"') < section.index('mbb-cols')
    assert '<tr class="sum"><td>Total</td><td class="n">$779k</td>' in section
    assert section.count('<tr class="sum">') == 1
    # alignment is per column: the first column left, every other column of this table numeric
    assert '<th>Product</th><th class="n">Q2 spend</th>' in section
    assert '<th class="n">Attributed revenue April to June</th>' in section
    assert '<td class="n">new in May</td>' in section
    assert '<td>Product A</td>' in section
    assert f'<p class="implication"><span>{slide["implication"]}</span></p>' in section
    notes = slide['footnotes']
    assert len(notes) == 2
    assert f'<p class="footnotes"><span><sup>1</sup>{notes[0]}</span><span><sup>2</sup>{notes[1]}</span></p>' in section
    assert f'<div class="takeaway msg-band">{slide["takeaway"]}</div>' in section
    # order: body, implication, takeaway band, source, footnotes
    assert section.index('mbb-cols') < section.index('class="tbl"') < section.index('class="implication"') \
        < section.index('msg-band') < section.index('class="source"') < section.index('class="footnotes"')


def test_inlines_svg_chart(story_min, tmp_path):
    svg = '<?xml version="1.0"?>\n' + _svg('Cost per order by month', 'chart text')
    svg_path = tmp_path / 'q2_result.svg'
    svg_path.write_text(svg)
    out = render_html(story_min, {'q2_result': {'svg': svg_path, 'png': tmp_path / 'q2_result.png'}},
                      tmp_path / 'deck.html')
    html = out.read_text()
    assert '<text x="1" y="10">chart text</text>' in html
    assert '<?xml' not in html
    # what_we_see plus the three charts_row columns stay missing
    assert html.count('<figure class="chart-missing">') == 4

    deck = ingest_html(out)
    assert _by_id(deck)['q2_result']['charts'] == [{'type': 'svg', 'title': 'Cost per order by month'}]


def test_charts_row_inlines_each_chart(story_min, tmp_path):
    slide = _by_id(story_min)['q2_by_product']
    assert slide['layout'] == 'charts_row'
    items = []
    for n, chart in enumerate(slide['charts']):
        p = tmp_path / f'q2_by_product_{n}.svg'
        p.write_text(_svg(chart['title'], f'row chart {n}'))
        items.append({'svg': p, 'png': p.with_suffix('.png')})
    out = render_html(story_min, {'q2_by_product': {'items': items}}, tmp_path / 'deck.html')
    html = out.read_text()
    for n in range(3):
        assert f'row chart {n}' in html

    got = _by_id(ingest_html(out))['q2_by_product']
    assert got['charts'] == [{'type': 'svg', 'title': c['title']} for c in slide['charts']]
    assert slide['callout'] in got['body']
    assert slide['takeaway'] in got['body']
    for chart in slide['charts']:
        assert chart['takeaway'] in got['body']


def test_charts_row_table_entry_is_chart_missing(story_min, tmp_path):
    slide = _by_id(story_min)['q2_by_product']
    p = tmp_path / 'c0.svg'
    p.write_text(_svg(slide['charts'][0]['title'], 'only chart'))
    items = [{'svg': p, 'png': p.with_suffix('.png')},
             {'table': [['a', 1]], 'gap': 'stackedBars: not a builder'},
             {'table': [['b', 2]], 'gap': 'lineChart: not a builder'}]
    out = render_html(story_min, {'q2_by_product': {'items': items}}, tmp_path / 'deck.html')
    html = out.read_text()
    assert 'only chart' in html
    row = html[html.index('<div class="mbb-cols"'):html.index('<div class="tbl">', html.index('<div class="mbb-cols"'))]
    assert row.count('<figure class="chart-missing">') == 2
    assert row.count('<figure>') == 1


def test_em_dash_in_story_fails_loudly(story_min, tmp_path):
    bad = copy.deepcopy(story_min)
    bad['slides'][0]['subtitle'] = 'A subtitle ' + EM_DASH + ' with a dash'
    with pytest.raises(ValueError, match='em dash'):
        render_html(bad, {}, tmp_path / 'deck.html')
