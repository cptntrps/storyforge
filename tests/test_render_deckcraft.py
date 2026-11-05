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


def test_render_with_chart_png(story_min, tmp_path):
    PIL = pytest.importorskip('PIL')
    from PIL import Image, ImageDraw
    png = tmp_path / 'q2_result.png'
    img = Image.new('RGB', (600, 300), 'white')
    draw = ImageDraw.Draw(img)
    draw.line([(40, 60), (300, 180), (560, 240)], fill=(37, 99, 235), width=4)
    draw.rectangle([0, 0, 599, 299], outline=(107, 114, 128))
    img.save(png)
    charts = {'q2_result': {'svg': tmp_path / 'q2_result.svg', 'png': png}}
    pptx = render_pptx(story_min, charts, tmp_path / 'out')
    assert pptx.exists()
    info = _info(tmp_path / 'out' / 'deck.deckcraft')
    assert len(info['slides']) == len(story_min['slides'])
    assert len(info.get('media') or []) >= 1
    assert (tmp_path / 'out' / 'png' / 'slide-02.png').exists()
