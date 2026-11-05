"""PPTX to deck.json through python-pptx.

Title is the title placeholder, else the top-most of the largest-font text frames.
Body paragraphs follow reading order: top to bottom, then left to right.
"""

import re
from collections import Counter
from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER
from pptx.util import Pt

TITLE_PLACEHOLDERS = {PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE}
SUBTITLE_PLACEHOLDERS = {PP_PLACEHOLDER.SUBTITLE}
BULLET_CHARS = ('•', '–', '-', '·', '▪', '○', '●', '◦', '*')
CHART_TYPE_SUFFIXES = ('_clustered', '_stacked_100', '_stacked', '_markers', '_exploded', '_3d')

_NUMBER_RE = re.compile(
    r'(?<![\w.$])(?P<dollar>\$)?(?P<num>\d{1,3}(?:,\d{3})+|\d+)(?P<frac>\.\d+)?'
    r'(?P<suffix>%|k\b|K\b|x\b|×)?'
)


def numbers_in(text):
    """Fallback for checks.titles.numbers_in: [{value, unit, context}] per numeric token.

    unit is '$' for $119 and $270k (value scaled to 270000), '%' for 5%,
    'k' for a bare 270k (value scaled), else None (2,495 and 1.6x).
    """
    out = []
    for m in _NUMBER_RE.finditer(text):
        value = float(m.group('num').replace(',', '') + (m.group('frac') or ''))
        suffix = (m.group('suffix') or '').lower()
        unit = None
        if suffix == 'k':
            value *= 1000
            unit = 'k'
        if m.group('dollar'):
            unit = '$'
        elif suffix == '%':
            unit = '%'
        start, end = m.span()
        context = text[max(0, start - 20):end + 20].strip()
        out.append({'value': value, 'unit': unit, 'context': context})
    return out


def _numbers_in():
    try:
        from storyforge.checks.titles import numbers_in as real
        return real
    except ImportError:
        return numbers_in


class _Frame:
    """One text frame with its absolute position and the largest font it uses."""

    def __init__(self, shape, top, left, placeholder):
        self.shape = shape
        self.top = top
        self.left = left
        self.height = shape.height or 0
        self.placeholder = placeholder
        self.paragraphs = [p for p in shape.text_frame.paragraphs]
        self.text = '\n'.join(p.text for p in self.paragraphs).strip()
        self.size = _font_size(shape.text_frame)

    @property
    def lines(self):
        return [p.text.strip() for p in self.paragraphs if p.text.strip()]

    @property
    def has_bullets(self):
        for p in self.paragraphs:
            if not p.text.strip():
                continue
            if p.level > 0 or p.text.lstrip().startswith(BULLET_CHARS):
                return True
            ppr = p._p.pPr
            if ppr is not None and (ppr.find(_qn('a:buChar')) is not None or ppr.find(_qn('a:buAutoNum')) is not None):
                return True
        return False


def _qn(tag):
    from pptx.oxml.ns import qn
    return qn(tag)


def _font_size(text_frame):
    sizes = []
    for p in text_frame.paragraphs:
        for r in p.runs:
            if r.font.size is not None and r.text.strip():
                sizes.append(r.font.size.pt)
        if not p.runs and p.font.size is not None:
            sizes.append(p.font.size.pt)
    return max(sizes) if sizes else None


def _walk(shapes, dx=0, dy=0):
    """Yield (shape, abs_top, abs_left), flattening group shapes."""
    for sh in shapes:
        top = (sh.top or 0) + dy
        left = (sh.left or 0) + dx
        if sh.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _walk(sh.shapes, left, top)
        else:
            yield sh, top, left


def _placeholder_type(shape):
    if not shape.is_placeholder:
        return None
    try:
        return shape.placeholder_format.type
    except (AttributeError, ValueError):
        return None


def _chart_dict(chart):
    raw = chart.chart_type.name.lower() if chart.chart_type is not None else 'unknown'
    kind = raw
    for suffix in CHART_TYPE_SUFFIXES:
        kind = kind.replace(suffix, '')
    if kind.startswith('xy'):
        kind = 'scatter'
    title = None
    if chart.has_title and chart.chart_title.has_text_frame:
        title = chart.chart_title.text_frame.text.strip() or None
    categories = []
    series = []
    for plot in chart.plots:
        if not categories:
            try:
                categories = [_plain(c) for c in plot.categories]
            except Exception:
                categories = []
        for s in plot.series:
            series.append({'name': s.name or None, 'values': [_plain(v) for v in s.values]})
    return {'type': kind, 'chart_type': raw, 'title': title, 'categories': categories, 'series': series}


def _plain(v):
    if v is None or isinstance(v, (int, float, str)):
        return v
    return str(v)


def _table_rows(table):
    return [[cell.text.strip() for cell in row.cells] for row in table.rows]


def _pick_title(frames):
    for f in frames:
        if f.placeholder in TITLE_PLACEHOLDERS and f.text:
            return f
    sized = [f for f in frames if f.text and f.size is not None]
    if sized:
        biggest = max(f.size for f in sized)
        return min((f for f in sized if f.size == biggest), key=lambda f: (f.top, f.left))
    texted = [f for f in frames if f.text]
    return min(texted, key=lambda f: (f.top, f.left)) if texted else None


def _pick_subtitle(frames, title):
    for f in frames:
        if f.placeholder in SUBTITLE_PLACEHOLDERS and f.text:
            return f
    if title is None or title.size is None:
        return None
    below = sorted((f for f in frames if f.text and f.top >= title.top + title.height - Pt(2)), key=lambda f: (f.top, f.left))
    if not below:
        return None
    cand = below[0]
    if cand.size is None or cand.size >= title.size:
        return None
    others = [f.size for f in below[1:] if f.size is not None]
    body_size = Counter(others).most_common(1)[0][0] if others else 0
    return cand if cand.size > body_size else None


def _guess_kind(n, title, body, bullet_frames):
    t = title.lower()
    if n == 1 and not body:
        return 'cover'
    if title.startswith('Appendix'):
        return 'appendix'
    if 'summary' in t or bullet_frames >= 4:
        return 'summary'
    if 'detail' in t or 'back-up' in t or 'backup' in t:
        return 'detail'
    return 'key'


def _slide_dict(slide, n):
    frames, tables, charts, pictures = [], [], [], 0
    for sh, top, left in _walk(slide.shapes):
        if sh.has_text_frame:
            frames.append(_Frame(sh, top, left, _placeholder_type(sh)))
        elif getattr(sh, 'has_table', False) and sh.has_table:
            tables.append({'rows': _table_rows(sh.table)})
        elif getattr(sh, 'has_chart', False) and sh.has_chart:
            charts.append(_chart_dict(sh.chart))
        elif sh.shape_type in (MSO_SHAPE_TYPE.PICTURE, MSO_SHAPE_TYPE.LINKED_PICTURE):
            pictures += 1

    title_f = _pick_title(frames)
    subtitle_f = _pick_subtitle([f for f in frames if f is not title_f], title_f)
    rest = sorted((f for f in frames if f is not title_f and f is not subtitle_f and f.text), key=lambda f: (f.top, f.left))
    body = [line for f in rest for line in f.lines]
    title = title_f.text if title_f else ''
    subtitle = subtitle_f.text if subtitle_f else None

    notes = None
    if slide.has_notes_slide:
        notes = slide.notes_slide.notes_text_frame.text.strip() or None

    table_text = any(cell for t in tables for row in t['rows'] for cell in row)
    unreadable = pictures > 0 and not title and not body and not table_text

    texts = [title] + ([subtitle] if subtitle else []) + body
    numbers = _numbers_in()('\n'.join(texts))
    bullet_frames = sum(1 for f in frames if f.text and f.has_bullets)

    return {
        'n': n,
        'id': f's{n}',
        'title': title,
        'subtitle': subtitle,
        'body': body,
        'tables': tables,
        'charts': charts,
        'notes': notes,
        'numbers': numbers,
        'kind': _guess_kind(n, title, body, bullet_frames),
        'unreadable': unreadable,
    }


def ingest_pptx(path):
    """Read a .pptx and return a deck.json dict (format 'pptx')."""
    path = Path(path)
    prs = Presentation(str(path))
    slides = [_slide_dict(slide, n) for n, slide in enumerate(prs.slides, 1)]
    return {'source': str(path), 'format': 'pptx', 'slides': slides}
