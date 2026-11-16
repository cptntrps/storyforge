"""Swap the chart pictures of a built deck for native, editable PowerPoint shapes.

svg-charts draws a chart spec as native shapes (deck/chart.py): bars are rectangles, lines are lines, each label is a
text box, in the theme of the deck. This module turns each story chart into such a spec and puts it in the slot the
layout gave the picture. A chart that does not fit its slot as native shapes keeps its picture; the report says so."""

import json
import os
import subprocess
import sys
from pathlib import Path

from .charts import DEFAULT_SVG_CHARTS, MULTI_SERIES

# The spec fields svg-charts takes per chart type (its chart() refuses an unknown field).
FIELDS = {
    'lineChart': ('series', 'labels', 'target', 'annotations', 'legend', 'colors', 'valueLabels'),
    'barChart': ('data', 'target', 'annotations', 'legend', 'colors'),
    'waterfall': ('items', 'annotations', 'legend', 'colors'),
    'scatter': ('groups', 'annotations', 'legend', 'colors'),
    'divergingBars': ('data', 'annotations', 'legend', 'colors'),
    'dumbbell': ('rows', 'aLabel', 'bLabel', 'annotations', 'legend', 'colors'),
    'stackedBars': ('columns', 'keys', 'colors', 'annotations', 'legend'),
}
# The palette of the chart pictures (the svg-charts defaults), so a series keeps its colour as native shapes.
PALETTE = '2a78d6,0ca37a,8d5bd6,d98500,d03b3b'


def deck_script(svg_charts_path=DEFAULT_SVG_CHARTS):
    return Path(svg_charts_path).parent / 'deck' / 'chart.py'


def native_spec(chart, colors=None):
    """The svg-charts spec of a story chart. The formatters follow the unit, as in the picture bridge."""
    kind = chart.get('type')
    if kind not in FIELDS:
        raise ValueError(f'{kind!r} has no native form')
    spec = {'chart': kind}
    spec.update({k: chart[k] for k in ('title', 'unit', 'source') + FIELDS[kind] if k in chart})
    if colors and 'colors' not in spec:
        spec['colors'] = dict(colors)
    if kind in MULTI_SERIES:
        spec.setdefault('legend', True)
    if kind == 'lineChart':
        spec.setdefault('valueLabels', True)
    unit = str(chart.get('unit') or '')
    if kind != 'stackedBars':            # stackedBars formats its shares itself
        spec['format'] = {'prefix': '$', 'maxDecimals': 2} if unit.startswith('$') else \
            {'suffix': '%', 'maxDecimals': 2} if unit == '%' else {'maxDecimals': 3}
    return spec


def swap(pptx, slots, story, out_dir, svg_charts_path=DEFAULT_SVG_CHARTS):
    """Replace the shape of each chart slot by native shapes. Returns one row per chart: {ref, native, reason}.
    Then renders the PNGs and the .deckcraft again from the changed deck, so the three files agree."""
    script = deck_script(svg_charts_path)
    if not script.exists():
        raise RuntimeError(f'{script} is missing: native charts need svg-charts 0.14 or later (STORYFORGE_SVG_CHARTS)')
    specs = Path(out_dir) / 'native'
    specs.mkdir(parents=True, exist_ok=True)
    rows, done = [], 0
    box = lambda slot: ','.join(f'{v:.2f}' for v in slot['rect'])  # noqa: E731

    def run(*args):
        r = subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, text=True)
        if r.returncode not in (0, 2):
            raise RuntimeError(f'svg-charts deck/chart.py failed: {r.stderr.strip()[-800:]}')
        return r.returncode == 0, r.stderr.strip().removeprefix('chart: ')

    # Pass 1: write each spec and check its fit. The charts of one slide are native together or not at all,
    # so a row never mixes shapes with pictures.
    for slot in slots:
        row = {'ref': slot['ref'], 'slide': slot['slide'], 'native': False, 'reason': '', 'slot': slot}
        rows.append(row)
        try:
            spec = native_spec(slot['chart'], story.get('colors'))
        except ValueError as e:
            row['reason'] = str(e)
            continue
        row['kind'] = spec['chart']
        row['path'] = specs / (slot['ref'].replace('#', '_') + '.json')
        row['path'].write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding='utf-8')
        row['fits'], row['reason'] = run(row['path'], '--check', '--box', box(slot))
    for row in rows:
        mates = [r for r in rows if r['slide'] == row['slide']]
        bad = next((r for r in mates if not r.get('fits')), None)
        if bad is not None and row.get('fits'):
            row['fits'], row['reason'] = False, f"{bad['ref']} on the same slide does not fit as native shapes"
    # Pass 2: draw.
    for row in rows:
        slot = row.pop('slot')
        if row.pop('fits', False):
            ok, why = run(row['path'], '--into', pptx, '--slide', slot['slide'], '--replace', slot['name'], '--box', box(slot),
                          '--palette', PALETTE, '--out', pptx)
            if not ok:
                raise RuntimeError(f'{slot["ref"]} passed the check and failed the draw: {why}')
            _rename_group(pptx, slot['slide'], row['kind'], slot['name'])
            row['native'] = True
            done += 1
        row.pop('path', None)
        row.pop('kind', None)
    (specs / 'report.json').write_text(json.dumps(rows, indent=1), encoding='utf-8')
    if done:
        pptx, png = Path(pptx), Path(pptx).parent / 'png'
        for f in png.glob('*.png'):
            f.unlink()
        subprocess.run(['deckcraft-cli', 'render', str(pptx), '--all', '--scale', '1.5', str(png)], check=True, capture_output=True, text=True)
        subprocess.run(['deckcraft-cli', 'convert', str(pptx), str(pptx.with_suffix('.deckcraft'))], check=True, capture_output=True, text=True)
    return rows


def _rename_group(pptx, slide_no, kind, name):
    """The chart group keeps the name of its slot (Chart, Chart_1 ...), so the gates find it as before."""
    from pptx import Presentation
    prs = Presentation(str(pptx))
    for shape in prs.slides[slide_no - 1].shapes:
        if shape.name == f'Chart {kind}':
            shape.name = name
    prs.save(str(pptx))
