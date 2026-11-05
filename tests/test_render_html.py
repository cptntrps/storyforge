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
    assert by_id['q2_result']['subtitle'] == story_min['slides'][1]['subtitle']
    assert by_id['q2_detail']['tables'] == [story_min['slides'][2]['table']]


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
    assert html.count('<figure class="chart-missing">') == 1

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
