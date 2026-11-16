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


def _run(script, *args):
    r = subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, text=True)
    if r.returncode not in (0, 2):
        raise RuntimeError(f'svg-charts deck/chart.py failed: {r.stderr.strip()[-800:]}')
    return r.returncode == 0, r.stderr.strip().removeprefix('chart: ')


def _box(slot):
    return ','.join(f'{v:.2f}' for v in slot['rect'])


def check(slots, story, out_dir, svg_charts_path=DEFAULT_SVG_CHARTS):
    """Per chart ref: (fits as native shapes in its slot, the reason when it does not). Writes the spec files."""
    script = deck_script(svg_charts_path)
    if not script.exists():
        raise RuntimeError(f'{script} is missing: native charts need svg-charts 0.14.1 or later (STORYFORGE_SVG_CHARTS)')
    specs = Path(out_dir) / 'native'
    specs.mkdir(parents=True, exist_ok=True)
    out = {}
    for slot in slots:
        try:
            spec = native_spec(slot['chart'], story.get('colors'))
        except ValueError as e:
            out[slot['ref']] = (False, str(e))
            continue
        path = specs / (slot['ref'].replace('#', '_') + '.json')
        path.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding='utf-8')
        out[slot['ref']] = _run(script, path, '--check', '--box', _box(slot))
    return out


def swap(pptx, slots, story, out_dir, svg_charts_path=DEFAULT_SVG_CHARTS):
    """Replace the shape of each chart slot by native shapes. Returns one row per chart: {ref, native, reason}.
    Then renders the PNGs and the .deckcraft again from the changed deck, so the three files agree."""
    script = deck_script(svg_charts_path)
    if not script.exists():
        raise RuntimeError(f'{script} is missing: native charts need svg-charts 0.14 or later (STORYFORGE_SVG_CHARTS)')
    specs = Path(out_dir) / 'native'
    specs.mkdir(parents=True, exist_ok=True)
    fits = check(slots, story, out_dir, svg_charts_path)
    rows, done = [], 0
    # The charts of one slide are native together or not at all, so a row never mixes shapes with pictures.
    for slot in slots:
        ok, why = fits[slot['ref']]
        bad = next((x for x in slots if x['slide'] == slot['slide'] and not fits[x['ref']][0]), None)
        if ok and bad is not None:
            ok, why = False, f"{bad['ref']} on the same slide does not fit as native shapes"
        row = {'ref': slot['ref'], 'slide': slot['slide'], 'native': False, 'reason': why}
        rows.append(row)
        if not ok:
            continue
        path = specs / (slot['ref'].replace('#', '_') + '.json')
        drawn, why = _run(script, path, '--into', pptx, '--slide', slot['slide'], '--replace', slot['name'], '--box', _box(slot),
                          '--palette', PALETTE, '--out', pptx)
        if not drawn:
            raise RuntimeError(f'{slot["ref"]} passed the check and failed the draw: {why}')
        _rename_group(pptx, slot['slide'], native_spec(slot['chart'])['chart'], slot['name'])
        row['native'] = True
        done += 1
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
