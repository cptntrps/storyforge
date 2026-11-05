"""R16 every chart has title, unit and source; R17 every chart has exactly one callout."""

from . import Check, verdict

BUILDERS = ('lineChart', 'barChart', 'waterfall', 'scatter', 'divergingBars', 'dumbbell', 'stackedBars')


def slide_charts(slide):
    """(ref, chart) for every chart on a slide: the single `chart` as the slide id, `charts[]` as id#index."""
    out = []
    if slide.get('chart'):
        out.append((slide['id'], slide['chart']))
    for i, ch in enumerate(slide.get('charts') or []):
        out.append((f"{slide['id']}#{i}", ch))
    return out


def check_charts(story):
    r16, r17, na = [], [], []
    for s in story['slides']:
        for ref, ch in slide_charts(s):
            if ch.get('type') not in BUILDERS:
                na.append({'slide': ref, 'type': ch.get('type'), 'note': 'not a builder; rendered as table'})
                continue
            missing = [k for k in ('title', 'unit', 'source') if not str(ch.get(k) or '').strip()]
            if missing:
                r16.append({'slide': ref, 'missing': missing})
            ann = ch.get('annotations') or []
            if len(ann) != 1:
                r17.append({'slide': ref, 'annotations': len(ann)})
    out = [verdict('R16', r16), verdict('R17', r17)]
    if na:
        out.append(Check('R16', 'script', 'NA', na))
    return out
