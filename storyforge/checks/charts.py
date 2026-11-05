"""R16 every chart has title, unit and source; R17 every chart has exactly one callout."""

from . import Check, verdict

BUILDERS = ('lineChart', 'barChart', 'waterfall', 'scatter', 'divergingBars', 'dumbbell', 'stackedBars')


def check_charts(story):
    r16, r17, na = [], [], []
    for s in story['slides']:
        ch = s.get('chart')
        if not ch:
            continue
        if ch.get('type') not in BUILDERS:
            na.append({'slide': s['id'], 'type': ch.get('type'), 'note': 'not a builder; rendered as table'})
            continue
        missing = [k for k in ('title', 'unit', 'source') if not str(ch.get(k) or '').strip()]
        if missing:
            r16.append({'slide': s['id'], 'missing': missing})
        ann = ch.get('annotations') or []
        if len(ann) != 1:
            r17.append({'slide': s['id'], 'annotations': len(ann)})
    out = [verdict('R16', r16), verdict('R17', r17)]
    if na:
        out.append(Check('R16', 'script', 'NA', na))
    return out
