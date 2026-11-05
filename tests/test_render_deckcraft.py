import copy
import json
import subprocess

import pytest

from storyforge.render.deckcraft import load_style, render_pptx


def _info(deckcraft):
    out = subprocess.run(['deckcraft-cli', 'info', str(deckcraft)], check=True, capture_output=True, text=True)
    return json.loads(out.stdout)


def test_story_min_renders(story_min, tmp_path):
    pptx = render_pptx(story_min, {}, tmp_path)
    assert pptx.exists() and pptx.suffix == '.pptx'
    deck = tmp_path / 'deck.deckcraft'
    assert deck.exists()
    n = len(story_min['slides'])
    assert n == 6
    info = _info(deck)
    assert len(info['slides']) == n
    assert [s['title'] for s in info['slides']] == [s['title'] for s in story_min['slides']]
    pngs = sorted((tmp_path / 'png').glob('*.png'))
    assert len(pngs) == n
    assert (tmp_path / 'png' / 'slide-02.png').exists()


def test_title_over_two_lines_raises(story_min, tmp_path):
    story = copy.deepcopy(story_min)
    story['slides'][1]['title'] = 'x' * 200
    assert 200 > 2 * load_style()['chars_per_line']
    with pytest.raises(ValueError, match='q2_result'):
        render_pptx(story, {}, tmp_path)


def test_story_min_titles_fit_two_lines(story_min):
    limit = 2 * load_style()['chars_per_line']
    for s in story_min['slides']:
        assert len(s['title']) <= limit, s['id']


def _png(path, w=600, h=300, hue=0):
    from PIL import Image, ImageDraw
    img = Image.new('RGB', (w, h), 'white')
    draw = ImageDraw.Draw(img)
    draw.line([(40, 60), (w // 2, h * 3 // 5), (w - 40, h * 4 // 5)], fill=(37 + 60 * hue, 99, 235 - 60 * hue), width=4)
    draw.rectangle([0, 0, w - 1, h - 1], outline=(107, 114, 128))
    img.save(path)
    return path


def test_render_with_chart_png(story_min, tmp_path):
    pytest.importorskip('PIL')
    png = _png(tmp_path / 'q2_result.png')
    charts = {'q2_result': {'svg': tmp_path / 'q2_result.svg', 'png': png}}
    pptx = render_pptx(story_min, charts, tmp_path / 'out')
    assert pptx.exists()
    info = _info(tmp_path / 'out' / 'deck.deckcraft')
    assert len(info['slides']) == len(story_min['slides'])
    assert len(info.get('media') or []) >= 1
    assert (tmp_path / 'out' / 'png' / 'slide-02.png').exists()


def _slide_index(story, sid):
    return [s['id'] for s in story['slides']].index(sid) + 1


def test_charts_row_renders_with_items_and_without(story_min, tmp_path):
    pytest.importorskip('PIL')
    sid = 'q2_by_product'
    slide = next(s for s in story_min['slides'] if s['id'] == sid)
    assert slide['layout'] == 'charts_row' and len(slide['charts']) == 3
    items = [{'svg': tmp_path / f'{sid}_{i}.svg', 'png': _png(tmp_path / f'{sid}_{i}.png', 400, 300, hue=i)} for i in range(3)]
    pptx = render_pptx(story_min, {sid: {'items': items}}, tmp_path / 'with')
    assert pptx.exists()
    info = _info(tmp_path / 'with' / 'deck.deckcraft')
    assert len(info['slides']) == 6 and len(info.get('media') or []) >= 3
    n = _slide_index(story_min, sid)
    assert (tmp_path / 'with' / 'png' / f'slide-{n:02d}.png').exists()
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    pics = [sh for sh in Presentation(str(pptx)).slides[n - 1].shapes if sh.shape_type == MSO_SHAPE_TYPE.PICTURE]
    assert len(pics) == 3

    pptx = render_pptx(story_min, {}, tmp_path / 'without')
    assert pptx.exists()
    assert len(_info(tmp_path / 'without' / 'deck.deckcraft')['slides']) == 6
