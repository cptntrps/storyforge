"""HTML deck renderer: one self-contained file that storyforge.ingest.html reads back.

Contract with the ingester: one `section.slide` per slide, the first h2 is the title,
`p.subtitle` is the subtitle, detail slides carry `hidden` and the class `detail-slide`.
Charts are inlined as SVG inside a figure; text is escaped and never reformatted.
"""

import re
from html import escape
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent / 'html_template.html'
EM_DASH = chr(0x2014)

_XML_PROLOG = re.compile(r'<\?xml[^>]*\?>\s*|<!DOCTYPE[^>]*>\s*', re.IGNORECASE)


def _e(text):
    return escape('' if text is None else str(text), quote=True)


def _ul(items):
    if not items:
        return ''
    return '<ul>' + ''.join(f'<li>{_e(i)}</li>' for i in items) + '</ul>'


def _inline_svg(slide_id, entry):
    """The SVG file content for one chart entry, or None when the entry holds no svg."""
    svg_path = (entry or {}).get('svg')
    if not svg_path:
        return None
    svg_path = Path(svg_path)
    if not svg_path.is_file():
        raise FileNotFoundError(f'{slide_id}: chart svg {svg_path} does not exist')
    svg = _XML_PROLOG.sub('', svg_path.read_text(encoding='utf-8')).strip()
    if not svg.startswith('<svg'):
        raise ValueError(f'{slide_id}: {svg_path} does not start with an <svg> element')
    return svg


def _figure(slide_id, chart, entry, caption=None):
    chart_title = (chart or {}).get('title') or 'Chart'
    svg = _inline_svg(slide_id, entry)
    if svg is None:
        return f'<figure class="chart-missing"><figcaption>{_e(chart_title)}</figcaption></figure>'
    cap = f'<figcaption>{_e(caption)}</figcaption>' if caption else f'<figcaption>{_e(chart_title)}</figcaption>'
    return f'<figure>{svg}{cap}</figure>'


def _chart_figure(slide, charts):
    return _figure(slide['id'], slide.get('chart'), charts.get(slide['id']))


def _callout(slide):
    return f'<p class="callout">{_e(slide["callout"])}</p>' if slide.get('callout') else ''


def _charts_row(slide, charts):
    specs = slide.get('charts') or []
    items = (charts.get(slide['id']) or {}).get('items') or []
    cols = []
    for n, chart in enumerate(specs):
        entry = items[n] if n < len(items) else None
        svg = _inline_svg(slide['id'], entry)
        takeaway = chart.get('takeaway')
        cap = f'<figcaption class="chart-takeaway"><strong>{_e(takeaway)}</strong></figcaption>' if takeaway else ''
        if svg is None:
            cols.append(f'<figure class="chart-missing">{cap}<p class="chart-title">{_e(chart.get("title") or "Chart")}</p></figure>')
        else:
            cols.append(f'<figure>{cap}{svg}</figure>')
    return f'{_callout(slide)}<div class="charts-row" style="--n:{len(specs)}">' + ''.join(cols) + '</div>'


def _summary(story):
    blocks = []
    for block in story.get('summary_blocks', []):
        lead = block.get('lead') or block.get('name', '')
        blocks.append(
            f'<div class="block"><p class="block-lead"><strong>{_e(lead)}</strong></p>'
            f'{_ul(block.get("bullets", []))}</div>'
        )
    return '<div class="summary-grid">' + ''.join(blocks) + '</div>'


def _chart_left(slide, charts):
    panel = ''
    if slide.get('callout'):
        panel += f'<p class="callout">{_e(slide["callout"])}</p>\n'
    if slide.get('takeaway'):
        panel += f'<div class="takeaway">{_e(slide["takeaway"])}</div>\n'
    aside = f'<aside class="panel">\n{panel}</aside>' if panel else ''
    return f'<div class="chart-left">{_chart_figure(slide, charts)}{aside}</div>'


def _table(slide):
    rows = ((slide.get('table') or {}).get('rows')) or []
    if not rows:
        return '<p class="chart-missing">Table has no rows</p>'
    out = ['<table>']
    for n, row in enumerate(rows):
        tag = 'th' if n == 0 else 'td'
        cells = ''.join(f'<{tag}>{_e(c)}</{tag}>' for c in row)
        out.append(f'<tr>{cells}</tr>')
    out.append('</table>')
    return ''.join(out)


def _three_columns(slide):
    cols = []
    for col in slide.get('columns') or []:
        cols.append(
            '<div class="col">'
            f'<p class="col-takeaway">{_e(col.get("takeaway"))}</p>'
            f'<p class="big-figure">{_e(col.get("figure"))}</p>'
            f'<p class="evidence">{_e(col.get("evidence"))}</p>'
            '</div>'
        )
    return '<div class="three-columns">' + ''.join(cols) + '</div>'


def _body(slide, story, charts):
    layout = slide['layout']
    if layout == 'summary':
        return _summary(story)
    if layout == 'chart_left':
        return _chart_left(slide, charts)
    if layout == 'chart_full':
        return _callout(slide) + _chart_figure(slide, charts)
    if layout == 'charts_row':
        return _charts_row(slide, charts)
    if layout == 'table':
        return _table(slide)
    if layout == 'three_columns':
        return _three_columns(slide)
    if layout == 'text_only':
        return _ul(slide.get('body') or [])
    raise ValueError(f'{slide["id"]}: unknown layout {layout!r}')


def _section(slide, story, charts, details_by_parent, titles):
    kind = slide['kind']
    classes = 'slide detail-slide' if kind == 'detail' else 'slide'
    hidden = ' hidden' if kind == 'detail' else ''
    parts = [f'<section class="{classes}" id="{_e(slide["id"])}" data-kind="{kind}"{hidden}>']
    if slide.get('section'):
        parts.append(f'<div class="kicker">{_e(slide["section"])}</div>')
    parts.append(f'<h2>{_e(slide["title"])}</h2>')
    if slide.get('subtitle'):
        parts.append(f'<p class="subtitle">{_e(slide["subtitle"])}</p>')
    parts.append(f'<div class="body">{_body(slide, story, charts)}</div>')
    chart_src = ((slide.get('chart') or {}).get('source') or '').strip()
    has_chart = bool((charts.get(slide['id']) or {}).get('svg'))
    if slide.get('source') and not (has_chart and slide['source'].strip() == chart_src):
        parts.append(f'<p class="source">Source: {_e(slide["source"])}</p>')
    # chart_left already placed the takeaway inside its aside
    if slide.get('takeaway') and slide['layout'] != 'chart_left':
        parts.append(f'<div class="takeaway">{_e(slide["takeaway"])}</div>')
    if kind == 'key':
        for detail in details_by_parent.get(slide['id'], []):
            parts.append(
                f'<p class="details">Detail: <a href="#{_e(detail["id"])}">{_e(detail["title"])}</a></p>'
            )
    elif slide.get('parent'):
        parent = slide['parent']
        parts.append(
            f'<p class="back"><a href="#{_e(parent)}">Back to: {_e(titles.get(parent, parent))}</a></p>'
        )
    parts.append('</section>')
    return '\n'.join(parts)


def render_html(story, charts, out_path):
    """Write the deck as one HTML file and return its path.

    `charts` maps slide id to {'svg': Path, 'png': Path}; the SVG file is inlined
    when present, otherwise the slide shows a chart-missing figure with the chart title.
    """
    charts = charts or {}
    slides = story['slides']
    titles = {s['id']: s['title'] for s in slides}
    details_by_parent = {}
    for s in slides:
        if s['kind'] == 'detail' and s.get('parent'):
            details_by_parent.setdefault(s['parent'], []).append(s)

    nav = '\n'.join(
        f'    <li><a href="#{_e(s["id"])}">{_e(s["title"])}</a></li>'
        for s in slides if s['kind'] == 'key'
    )
    sections = '\n'.join(_section(s, story, charts, details_by_parent, titles) for s in slides)
    title = story.get('title') or story['governing_thought']

    html = (
        TEMPLATE.read_text(encoding='utf-8')
        .replace('{{title}}', _e(title))
        .replace('{{governing_thought}}', _e(story['governing_thought']))
        .replace('{{nav}}', nav)
        .replace('{{slides}}', sections)
    )
    if EM_DASH in html:
        raise ValueError('rendered HTML contains an em dash; fix the story text')

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding='utf-8')
    return out_path
