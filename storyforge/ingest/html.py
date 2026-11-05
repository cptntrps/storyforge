"""HTML deck ingest: Playwright renders the file, one JS pass per section fills deck.json."""

import re
from pathlib import Path

from storyforge.schema import require_valid

DEFAULT_SELECTOR = 'section.slide, section.appendix'

# Runs on each matched section inside the rendered page. Text comes from
# textContent so hidden (detail) sections still yield their words. Body runs are
# text nodes grouped by their nearest block-level ancestor, in DOM order, after
# the title, subtitle, notes, tables, svg, sup markers and scripts are cut out.
_READ_SECTION = r"""
(section) => {
  const collapse = (s) => (s || '').replace(/\s+/g, ' ').trim();
  const titleEl = section.querySelector('h1, h2');
  const subtitleEl = section.querySelector('.subtitle, .sub, h3, p.lead');
  const notesEl = section.querySelector('.notes');
  const SKIP_TAGS = new Set(['TABLE', 'SCRIPT', 'STYLE', 'TEMPLATE', 'NOSCRIPT', 'SUP']);
  const isSvg = (el) => el.namespaceURI === 'http://www.w3.org/2000/svg';
  const skipped = (el) => SKIP_TAGS.has(el.tagName) || isSvg(el)
    || el === titleEl || el === subtitleEl || el === notesEl;
  const textOf = (el) => {
    if (!el) return '';
    const parts = [];
    const walk = (node) => {
      for (const child of node.childNodes) {
        if (child.nodeType === Node.TEXT_NODE) parts.push(child.nodeValue);
        else if (child.nodeType === Node.ELEMENT_NODE && child.tagName !== 'SUP'
                 && child.tagName !== 'SCRIPT' && child.tagName !== 'STYLE') walk(child);
      }
    };
    walk(el);
    return collapse(parts.join(''));
  };
  const isBlock = (el) => {
    if (el === section) return true;
    const d = getComputedStyle(el).display;
    return !(d === 'inline' || d === 'inline-block' || d === 'inline-flex' || d === 'contents');
  };
  const blockOwner = (textNode) => {
    let el = textNode.parentElement;
    while (el && el !== section && !isBlock(el)) el = el.parentElement;
    return el || section;
  };
  const body = [];
  let current = null;
  let buf = [];
  const flush = () => {
    const t = collapse(buf.join(''));
    if (t) body.push(t);
    buf = [];
  };
  const walker = document.createTreeWalker(section, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
    acceptNode: (node) => {
      if (node.nodeType === Node.ELEMENT_NODE) {
        return skipped(node) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_SKIP;
      }
      return NodeFilter.FILTER_ACCEPT;
    },
  });
  let node;
  while ((node = walker.nextNode())) {
    const owner = blockOwner(node);
    if (owner !== current) { flush(); current = owner; }
    buf.push(node.nodeValue);
  }
  flush();

  const tables = Array.from(section.querySelectorAll('table')).map((t) => ({
    rows: Array.from(t.querySelectorAll('tr')).map((tr) =>
      Array.from(tr.querySelectorAll('th, td')).map((c) => collapse(c.textContent))),
  }));
  const charts = Array.from(section.querySelectorAll('svg')).map((svg) => {
    const t = svg.querySelector('title');
    return { type: 'svg', title: svg.getAttribute('aria-label') || (t ? collapse(t.textContent) : null) || null };
  });
  const title = textOf(titleEl);
  const subtitle = subtitleEl ? textOf(subtitleEl) : null;
  return {
    id: section.id || null,
    title,
    subtitle: subtitle || null,
    body,
    tables,
    charts,
    notes: notesEl ? (textOf(notesEl) || null) : null,
    hidden: section.hasAttribute('hidden') || getComputedStyle(section).display === 'none',
    className: section.className || '',
    lists: section.querySelectorAll('ul, ol').length,
    images: section.querySelectorAll('img').length,
  };
}
"""

_NUMBER = re.compile(r'(?<![\w.])(\$?)(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s?([kKmMbB](?![\w.])|%|x(?![\w.]))?')
_SCALE = {'k': 1e3, 'm': 1e6, 'b': 1e9}


def _local_numbers_in(text):
    """Fallback with the conventions of checks.titles.numbers_in: k, M, bn expand to base units."""
    out = []
    for m in _NUMBER.finditer(text):
        currency, digits, suffix = m.group(1), m.group(2), m.group(3) or ''
        value = float(digits.replace(',', ''))
        if suffix in ('%', 'x'):
            unit = suffix
        else:
            value *= _SCALE.get(suffix.lower(), 1)
            unit = currency or None
        out.append({'value': value, 'unit': unit, 'context': text})
    return out


def _numbers_in():
    try:
        from storyforge.checks.titles import numbers_in
        return numbers_in
    except ImportError:
        return _local_numbers_in


def _kind(raw, n, title):
    cls = raw['className'].lower()
    sid = (raw['id'] or '').lower()
    if raw['hidden'] or 'detail' in cls:
        return 'detail'
    if 'appendix' in cls or title.lower().startswith('appendix'):
        return 'appendix'
    if n == 1:
        if title and (raw['lists'] >= 3 or any(k in sid or k in cls for k in ('summary', 'exec'))):
            return 'summary'
        if title and not raw['body']:
            return 'cover'
    return 'key'


def ingest_html(path, selector=DEFAULT_SELECTOR):
    from playwright.sync_api import sync_playwright

    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(path.as_uri(), wait_until='load')
            raws = [h.evaluate(_READ_SECTION) for h in page.query_selector_all(selector)]
        finally:
            browser.close()
    if not raws:
        raise ValueError(f'{path}: no element matches {selector!r}')

    numbers_in = _numbers_in()
    slides = []
    for n, raw in enumerate(raws, start=1):
        title = raw['title']
        numbers = []
        for text in [title, *raw['body']]:
            numbers.extend(numbers_in(text))
        slides.append({
            'n': n,
            'id': raw['id'] or f's{n}',
            'title': title,
            'subtitle': raw['subtitle'],
            'body': raw['body'],
            'tables': raw['tables'],
            'charts': raw['charts'],
            'notes': raw['notes'],
            'numbers': numbers,
            'kind': _kind(raw, n, title),
            'unreadable': raw['images'] > 0 and not title and not raw['body'],
        })
    return require_valid('deck', {'source': str(path), 'format': 'html', 'slides': slides})
