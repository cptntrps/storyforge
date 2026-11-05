"""Google Slides ingest: presentations.get JSON to deck.json."""

import re

TITLE_TYPES = ('TITLE', 'CENTERED_TITLE')
SUBTITLE_TYPES = ('SUBTITLE',)

_NUMBER_RE = re.compile(
    r'(?<![\w.])(?P<cur>[$€£])?(?P<num>\d[\d,]*(?:\.\d+)?)(?P<suf>[kKmMbB]|x|%)?(?![\w.])'
)
_SCALE = {'k': 1e3, 'm': 1e6, 'b': 1e9}


def _numbers_in_local(text):
    out = []
    for m in _NUMBER_RE.finditer(text):
        cur, num, suf = m.group('cur'), m.group('num'), m.group('suf')
        if not cur and not suf and ',' not in num and '.' not in num and len(num) < 2:
            continue
        value = float(num.replace(',', ''))
        unit = None
        if suf and suf.lower() in _SCALE:
            value *= _SCALE[suf.lower()]
            unit = cur
        elif suf:
            unit = suf
        else:
            unit = cur
        out.append({'value': value, 'unit': unit, 'context': text.strip()})
    return out


def numbers_in(text):
    try:
        from storyforge.checks.titles import numbers_in as shared
    except ImportError:
        return _numbers_in_local(text)
    return shared(text)


def _run_text(text_obj):
    """Concatenated textRun content of one Slides text object."""
    if not text_obj:
        return ''
    return ''.join(
        el.get('textRun', {}).get('content', '')
        for el in text_obj.get('textElements', [])
    )


def _paragraphs(text):
    return [line.strip() for line in text.split('\n') if line.strip()]


def _placeholder_type(element):
    return element.get('shape', {}).get('placeholder', {}).get('type')


def _kind(n, title, body):
    low = title.lower()
    if n == 1 and not body:
        return 'cover'
    if 'summary' in low:
        return 'summary'
    if title.startswith('Appendix'):
        return 'appendix'
    if 'detail' in low or 'back-up' in low or 'backup' in low:
        return 'detail'
    return 'key'


def _notes(slide):
    page = slide.get('slideProperties', {}).get('notesPage', {})
    for el in page.get('pageElements', []):
        if _placeholder_type(el) == 'BODY':
            text = _run_text(el.get('shape', {}).get('text')).strip()
            return text or None
    return None


def _slide(slide, n):
    title = None
    subtitle = None
    first_text = None
    body = []
    tables = []
    charts = []
    has_image = False
    has_text = False

    for el in slide.get('pageElements', []):
        if 'shape' in el:
            text = _run_text(el['shape'].get('text'))
            if not text.strip():
                continue
            has_text = True
            ptype = _placeholder_type(el)
            if ptype in TITLE_TYPES and title is None:
                title = ' '.join(_paragraphs(text))
            elif ptype in SUBTITLE_TYPES and subtitle is None:
                subtitle = ' '.join(_paragraphs(text))
            else:
                if first_text is None:
                    first_text = text
                body.append(_paragraphs(text))
        elif 'table' in el:
            rows = []
            for row in el['table'].get('tableRows', []):
                rows.append([
                    _run_text(cell.get('text')).strip()
                    for cell in row.get('tableCells', [])
                ])
            if any(any(c for c in r) for r in rows):
                has_text = True
            tables.append({'rows': rows})
        elif 'sheetsChart' in el:
            charts.append({'type': 'sheetsChart', 'title': None})
        elif 'image' in el:
            has_image = True

    if title is None and first_text is not None:
        # Promote the first non-placeholder text shape to the title.
        title = ' '.join(_paragraphs(first_text))
        body = [p for p in body if p != _paragraphs(first_text)]
    flat_body = [p for group in body for p in group]

    texts = [title or '', subtitle or '', *flat_body]
    texts += [c for t in tables for r in t['rows'] for c in r]
    numbers = [num for t in texts if t for num in numbers_in(t)]

    out = {
        'n': n,
        'id': slide.get('objectId', f'slide-{n}'),
        'title': title or '',
        'subtitle': subtitle,
        'body': flat_body,
        'tables': tables,
        'charts': charts,
        'notes': _notes(slide),
        'numbers': numbers,
        'kind': _kind(n, title or '', flat_body),
    }
    if has_image and not has_text:
        out['unreadable'] = True
    return out


def ingest_gslides(presentation, source='gslides'):
    """deck.json from a Google Slides API presentation resource."""
    slides = [_slide(s, i) for i, s in enumerate(presentation.get('slides', []), start=1)]
    return {'source': source, 'format': 'gslides', 'slides': slides}
