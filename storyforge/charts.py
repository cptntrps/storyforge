"""Chart rendering: story.json chart specs to SVG through svg-charts (node), SVG to PNG through Playwright."""

import json
import subprocess
from pathlib import Path

from .checks.charts import BUILDERS, slide_charts

PKG = Path(__file__).resolve().parent
BRIDGE = PKG / 'charts_bridge.mjs'
DEFAULT_SVG_CHARTS = Path.home() / 'repos/svg-charts/charts.js'
# Pixel size per layout so chart text stays legible once the PNG is fitted into its column.
LAYOUT_SIZES = {'charts_row': (420, 340), 'chart_left': (700, 340), 'chart_full': (900, 330)}
PASS_THROUGH = ('colors', 'legend', 'valueLabels', 'title', 'unit', 'source', 'annotations', 'labels', 'series', 'data', 'items', 'groups', 'rows', 'columns',
                'keys', 'colors', 'target', 'aLabel', 'bLabel', 'width', 'height', 'label')


MULTI_SERIES = ('lineChart', 'scatter', 'stackedBars', 'dumbbell')


def spec_for(chart, layout=None, colors=None):
    """The options object svg-charts receives: the story spec minus storyforge-only keys, sized for the layout,
    with the deck colour map (one colour per entity across every chart) and a legend on multi-series charts."""
    spec = {k: v for k, v in chart.items() if k in PASS_THROUGH}
    w, h = LAYOUT_SIZES.get(layout, (600, 300))
    spec.setdefault('width', w)
    if chart.get('type') != 'dumbbell':
        spec.setdefault('height', h)
    if colors:
        spec.setdefault('colors', dict(colors))
    if chart.get('type') in MULTI_SERIES:
        spec.setdefault('legend', True)
    return spec


def render_svg(chart, svg_charts_path=DEFAULT_SVG_CHARTS, layout=None, colors=None):
    if chart.get('type') not in BUILDERS:
        raise ValueError(f"{chart.get('type')!r} is not an svg-charts builder")
    r = subprocess.run(['node', str(BRIDGE), str(svg_charts_path), chart['type'], json.dumps(spec_for(chart, layout, colors), ensure_ascii=False)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f'svg-charts failed for {chart["type"]}: {r.stderr.strip()[-800:]}')
    return r.stdout


def svg_to_png(svg_text, out_png, scale=2):
    from playwright.sync_api import sync_playwright
    html = ('<!doctype html><html><head><meta charset="utf-8"><style>body{margin:0;background:#fff;'
            'font-family:Inter,Arial,sans-serif}svg{display:block}</style></head><body>' + svg_text + '</body></html>')
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(device_scale_factor=scale)
        page.set_content(html)
        page.locator('svg').first.screenshot(path=str(out_png))
        b.close()
    return Path(out_png)


def render_charts(story, out_dir, svg_charts_path=DEFAULT_SVG_CHARTS, png=True):
    """Per slide id: {'svg', 'png'} for a single chart; {'items': [{'svg', 'png'}, ...]} for charts[];
    {'table': rows, 'gap': why} when the type is not a builder."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    result = {}

    def one(ref, ch, layout):
        if ch.get('type') not in BUILDERS:
            return {'table': ch.get('rows') or [], 'gap': f"{ch.get('type')} is not a builder; rendered as table"}
        svg = render_svg(ch, svg_charts_path, layout, story.get('colors'))
        name = ref.replace('#', '_')
        svg_path = out / f'{name}.svg'
        svg_path.write_text(svg)
        entry = {'svg': svg_path}
        if png:
            entry['png'] = svg_to_png(svg, out / f'{name}.png')
        return entry

    for s in story['slides']:
        if s.get('chart'):
            result[s['id']] = one(s['id'], s['chart'], s.get('layout'))
        elif s.get('charts'):
            result[s['id']] = {'items': [one(f"{s['id']}#{i}", ch, s.get('layout')) for i, ch in enumerate(s['charts'])]}
    return result
