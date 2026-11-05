"""HTML deck renderer: one self-contained file that storyforge.ingest.html reads back.

Contract with the ingester: one `section.slide` per slide, the first h2 is the title,
`p.subtitle` is the subtitle, detail slides carry `hidden` and the class `detail-slide`,
speaker notes live only in `.notes`. Charts are inlined as SVG inside a figure; text is
escaped and never reformatted. The slide number is a CSS counter, so it adds no text.
"""

import re
from html import escape
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent / 'html_template.html'
EM_DASH = chr(0x2014)

_XML_PROLOG = re.compile(r'<\?xml[^>]*\?>\s*|<!DOCTYPE[^>]*>\s*', re.IGNORECASE)
_NUMERIC_CELL = re.compile(r'^[+-]?\$?\d[\d,]*(\.\d+)?\s?[kKmMbBx%]?$')


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


def _figure(slide_id, chart, entry):
    """svg-charts draws its own title, unit and source bands, so a present chart gets no caption."""
    svg = _inline_svg(slide_id, entry)
    if svg is None:
        chart_title = (chart or {}).get('title') or 'Chart'
        return f'<figure class="chart-missing"><figcaption>{_e(chart_title)}</figcaption></figure>'
    return f'<figure>{svg}</figure>'


def _chart_figure(slide, charts):
    return _figure(slide['id'], slide.get('chart'), charts.get(slide['id']))


def _callout(slide):
    return f'<p class="callout">{_e(slide["callout"])}</p>' if slide.get('callout') else ''


def _subtitle_row(slide):
    """chart_full and charts_row put the callout as a compact accent line at the right end of the
    subtitle row; it wraps to its own line when the subtitle is long. chart_left keeps it in the aside."""
    subtitle = f'<p class="subtitle">{_e(slide["subtitle"])}</p>' if slide.get('subtitle') else ''
    callout = _callout(slide) if slide['layout'] in ('chart_full', 'charts_row') else ''
    if subtitle and callout:
        return f'<div class="subrow">{subtitle}{callout}</div>'
    return subtitle + callout


def _cell_is_numeric(cell):
    text = str(cell).strip()
    return bool(text) and (text.startswith('$') or text.endswith('%') or bool(_NUMERIC_CELL.match(text)))


def _table(slide):
    rows = ((slide.get('table') or {}).get('rows')) or []
    if not rows:
        return ''
    width = max(len(r) for r in rows)
    numeric = [i > 0 and _column_numeric(rows, i) for i in range(width)]
    out = ['<div class="tbl"><table>']
    for n, row in enumerate(rows):
        tag = 'th' if n == 0 else 'td'
        cells = ''.join(
            f'<{tag}{" class=\"n\"" if numeric[i] else ""}>{_e(c)}</{tag}>' for i, c in enumerate(row))
        is_sum = n == len(rows) - 1 and n > 0 and str(row[0]).strip().lower() == 'total'
        tr = '<tr class="sum">' if is_sum else '<tr>'
        out.append(f'{tr}{cells}</tr>')
    out.append('</table></div>')
    return ''.join(out)


def _column_numeric(rows, i):
    """A whole column is right-aligned when most of its body cells with text are numeric."""
    body = [r[i] for r in rows[1:] if i < len(r) and str(r[i]).strip()]
    return bool(body) and sum(_cell_is_numeric(c) for c in body) * 2 > len(body)


def _summary(story):
    rows = []
    for block in story.get('summary_blocks', []):
        lead = block.get('lead') or block.get('name', '')
        cls = 'row ask' if block.get('name') == 'goals' else 'row'
        rows.append(
            f'<div class="{cls}"><div class="msg">{_e(lead)}</div>'
            f'<div class="pts">{_ul(block.get("bullets", []))}</div></div>'
        )
    return '<div class="bcg">' + ''.join(rows) + '</div>'


def _takeaway_band(slide):
    return f'<div class="takeaway msg-band">{_e(slide["takeaway"])}</div>' if slide.get('takeaway') else ''


def _chart_left(slide, charts):
    """The right column stacks the callout box and the takeaway band; the band is not repeated below."""
    right = ''
    if slide.get('callout'):
        right += f'<div class="aside-box"><p class="callout-num">{_e(slide["callout"])}</p></div>'
    right += _takeaway_band(slide)
    aside = f'<div class="split-aside">{right}</div>' if right else ''
    return f'<div class="split">{_chart_figure(slide, charts)}{aside}</div>'


def _charts_row(slide, charts):
    specs = slide.get('charts') or []
    items = (charts.get(slide['id']) or {}).get('items') or []
    cols = []
    for n, chart in enumerate(specs):
        entry = items[n] if n < len(items) else None
        take = ''
        if chart.get('takeaway'):
            take = f'<p class="take"><span class="n">{n + 1}</span><span>{_e(chart["takeaway"])}</span></p>'
        cols.append(f'<div class="mbb-col">{take}{_figure(slide["id"], chart, entry)}</div>')
    row = f'<div class="mbb-cols" style="--n:{len(specs)}">' + ''.join(cols) + '</div>'
    return row + _table(slide)


def _three_columns(slide):
    tiles = []
    for col in slide.get('columns') or []:
        tiles.append(
            '<div class="tile">'
            f'<p class="c">{_e(col.get("takeaway"))}</p>'
            f'<p class="v">{_e(col.get("figure"))}</p>'
            f'<p class="l">{_e(col.get("evidence"))}</p>'
            '</div>'
        )
    return '<div class="tiles">' + ''.join(tiles) + '</div>'


def _body(slide, story, charts):
    layout = slide['layout']
    if layout == 'summary':
        return _summary(story)
    if layout == 'chart_left':
        return _chart_left(slide, charts)
    if layout == 'chart_full':
        return _chart_figure(slide, charts)
    if layout == 'charts_row':
        return _charts_row(slide, charts)
    if layout == 'table':
        return _table(slide) or '<p class="source">Table has no rows</p>'
    if layout == 'three_columns':
        return _three_columns(slide)
    if layout == 'text_only':
        return _ul(slide.get('body') or [])
    raise ValueError(f'{slide["id"]}: unknown layout {layout!r}')


def _footnotes(notes):
    if not notes:
        return ''
    spans = ''.join(f'<span><sup>{n}</sup>{_e(note)}</span>' for n, note in enumerate(notes, start=1))
    return f'<p class="footnotes">{spans}</p>'


def _section(slide, story, charts, details_by_parent, titles):
    kind = slide['kind']
    classes = 'slide mbb detail-slide' if kind == 'detail' else 'slide mbb'
    hidden = ' hidden' if kind == 'detail' else ''
    parts = [f'<section class="{classes}" id="{_e(slide["id"])}" data-kind="{kind}"{hidden}>']
    parts.append(f'<p class="kicker">{_e(slide.get("section") or kind)}</p>')
    parts.append(f'<h2 class="title">{_e(slide["title"])}</h2>')
    parts.append(_subtitle_row(slide))
    parts.append(f'<div class="body">{_body(slide, story, charts)}</div>')
    if slide.get('implication'):
        parts.append(f'<p class="implication"><span>{_e(slide["implication"])}</span></p>')
    if slide['layout'] != 'chart_left':
        parts.append(_takeaway_band(slide))
    if slide.get('source'):
        parts.append(f'<p class="source">Source: {_e(slide["source"])}</p>')
    parts.append(_footnotes(slide.get('footnotes')))
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
    return '\n'.join(p for p in parts if p)


def render_html(story, charts, out_path):
    """Write the deck as one HTML file and return its path.

    `charts` maps slide id to {'svg': Path, 'png': Path}, or for a charts_row slide to
    {'items': [...]} with one entry per chart; an entry without 'svg' renders chart-missing.
    """
    charts = charts or {}
    slides = story['slides']
    titles = {s['id']: s['title'] for s in slides}
    details_by_parent = {}
    for s in slides:
        if s['kind'] == 'detail' and s.get('parent'):
            details_by_parent.setdefault(s['parent'], []).append(s)

    keys = [s for s in slides if s['kind'] == 'key']
    nav = '\n'.join(
        f'  <a href="#{_e(s["id"])}"><b>{n}</b><span>{_e(s["title"])}</span></a>'
        for n, s in enumerate(keys, start=1)
    )
    sections = '\n'.join(_section(s, story, charts, details_by_parent, titles) for s in slides)
    title = story.get('title') or story['governing_thought']
    answer = (story.get('scqa') or {}).get('answer')

    html = (
        TEMPLATE.read_text(encoding='utf-8')
        .replace('{{title}}', _e(title))
        .replace('{{eyebrow}}', _e(story.get('title') or 'Deck'))
        .replace('{{governing_thought}}', _e(story['governing_thought']))
        .replace('{{lede}}', f'<p class="lede">{_e(answer)}</p>' if answer else '')
        .replace('{{nav}}', nav)
        .replace('{{slides}}', sections)
    )
    if EM_DASH in html:
        raise ValueError('rendered HTML contains an em dash; fix the story text')

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding='utf-8')
    return out_path
