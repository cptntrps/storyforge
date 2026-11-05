from storyforge.ingest.html import ingest_html
from storyforge.render.html import render_html

EM_DASH = chr(0x2014)


def test_round_trip_through_ingest_html(story_min, tmp_path):
    out = render_html(story_min, {}, tmp_path / 'deck.html')
    assert out.is_file()

    deck = ingest_html(out)
    story_titles = [s['title'] for s in story_min['slides']]
    assert [s['title'] for s in deck['slides']] == story_titles
    assert [s['id'] for s in deck['slides']] == [s['id'] for s in story_min['slides']]
    by_id = {s['id']: s for s in deck['slides']}
    assert by_id['q2_detail']['kind'] == 'detail'
    by_story = {s['id']: s for s in story_min['slides']}
    assert by_id['q2_result']['subtitle'] == by_story['q2_result']['subtitle']
    assert by_id['q2_detail']['tables'] == [by_story['q2_detail']['table']]
    # chart_left callout and takeaway are slide content, not speaker notes
    assert by_story['q2_result']['callout'] in by_id['q2_result']['body']
    assert by_story['q2_result']['takeaway'] in by_id['q2_result']['body']
    assert by_id['q2_result']['notes'] is None


def test_self_contained_and_clean(story_min, tmp_path):
    out = render_html(story_min, {}, tmp_path / 'deck.html')
    html = out.read_text()
    assert '<script' not in html
    assert 'http' not in html
    assert EM_DASH not in html
    for var in ('--chart-grid', '--chart-axis-text', '--chart-ink', '--chart-target',
                '--chart-1', '--chart-2', '--chart-3', '--chart-4', '--chart-5'):
        assert var in html
    assert 'prefers-color-scheme: dark' in html
    assert '@media print' in html
    assert html.count('<section class="slide') == len(story_min['slides'])
    assert '<section class="slide detail-slide" id="q2_detail" data-kind="detail" hidden>' in html
    assert 'href="#q2_detail"' in html
    assert 'href="#q2_result"' in html
    assert '<figure class="chart-missing">' in html
    assert '<div class="charts-row" style="--n:3">' in html
    for chart in story_min['slides'][2]['charts']:
        assert f'<strong>{chart["takeaway"]}</strong>' in html
    assert '<p class="source">Source: Ad platform export, June 2025</p>' in html
    # numbers stay as written in the story
    assert '2,495 to 5,425' in html
    assert '$270k' in html


def test_inlines_svg_chart(story_min, tmp_path):
    svg = ('<?xml version="1.0"?>\n'
           '<svg viewBox="0 0 100 40" role="img" aria-label="Cost per order by month">'
           '<title>Cost per order by month</title><text x="1" y="10">chart text</text></svg>')
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
    by_id = {s['id']: s for s in deck['slides']}
    assert by_id['q2_result']['charts'] == [{'type': 'svg', 'title': 'Cost per order by month'}]


def test_em_dash_in_story_fails_loudly(story_min, tmp_path):
    import copy
    import pytest
    bad = copy.deepcopy(story_min)
    bad['slides'][0]['subtitle'] = 'A subtitle ' + EM_DASH + ' with a dash'
    with pytest.raises(ValueError, match='em dash'):
        render_html(bad, {}, tmp_path / 'deck.html')


def _svg(title, text):
    return (f'<svg viewBox="0 0 100 40" role="img" aria-label="{title}">'
            f'<title>{title}</title><text x="1" y="10">{text}</text></svg>')


def test_charts_row_inlines_each_chart(story_min, tmp_path):
    slide = story_min['slides'][2]
    assert slide['id'] == 'q2_by_product' and slide['layout'] == 'charts_row'
    items = []
    for n, chart in enumerate(slide['charts']):
        p = tmp_path / f'q2_by_product_{n}.svg'
        p.write_text(_svg(chart['title'], f'row chart {n}'))
        items.append({'svg': p, 'png': p.with_suffix('.png')})
    out = render_html(story_min, {'q2_by_product': {'items': items}}, tmp_path / 'deck.html')
    html = out.read_text()
    for n in range(3):
        assert f'row chart {n}' in html

    deck = ingest_html(out)
    by_id = {s['id']: s for s in deck['slides']}
    assert by_id['q2_by_product']['charts'] == [
        {'type': 'svg', 'title': c['title']} for c in slide['charts']]
    assert slide['callout'] in by_id['q2_by_product']['body']
    assert slide['takeaway'] in by_id['q2_by_product']['body']
    for chart in slide['charts']:
        assert chart['takeaway'] in by_id['q2_by_product']['body']


def test_charts_row_table_entry_is_chart_missing(story_min, tmp_path):
    slide = story_min['slides'][2]
    p = tmp_path / 'c0.svg'
    p.write_text(_svg(slide['charts'][0]['title'], 'only chart'))
    items = [{'svg': p, 'png': p.with_suffix('.png')},
             {'table': [['a', 1]], 'gap': 'stackedBars: not a builder'},
             {'table': [['b', 2]], 'gap': 'lineChart: not a builder'}]
    out = render_html(story_min, {'q2_by_product': {'items': items}}, tmp_path / 'deck.html')
    html = out.read_text()
    assert 'only chart' in html
    row = html[html.index('<div class="charts-row"'):html.index('</div>', html.index('<div class="charts-row"'))]
    assert row.count('<figure class="chart-missing">') == 2
    assert row.count('<figure>') == 1
