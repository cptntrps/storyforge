"""Render story.json to a PPTX through deckcraft-cli.

Every primitive appends deckcraft-cli commands; build() runs them, saves the .deckcraft, converts
it to .pptx and renders one PNG per slide. Fonts, colours and the grid come from a style file in
styles/; the story may set `footer` to put text in the footer's right corner.
"""

import base64
import json
import math
import struct
import subprocess
from pathlib import Path

STYLES = Path(__file__).resolve().parent / 'styles'
# One base64 picture must stay under the Linux per-argument limit (128 KB); larger PNGs go by path.
MAX_INLINE_B64 = 100_000


LINE = 1.75  # box height per text line, as a multiple of the font size; the spatial gate models text at 1.4 and caps fill at 85%


def load_style(style='default'):
    p = Path(style) if str(style).endswith('.json') else STYLES / f'{style}.json'
    return json.loads(p.read_text())


def _png_size(path):
    head = Path(path).read_bytes()[:24]
    if head[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError(f'{path} is not a PNG')
    w, h = struct.unpack('>II', head[16:24])
    return w, h


def _fit(rect, aspect):
    """The largest box with width/height = aspect inside rect, top-left aligned."""
    x, y, w, h = rect
    if w / h > aspect:
        fw, fh = h * aspect, h
    else:
        fw, fh = w, w / aspect
    return [x, y, round(fw, 2), round(fh, 2)]


class _Deck:
    def __init__(self, style):
        self.st = style
        self.c_ = style['colors']
        self.g = style['grid']
        self.font = style['fonts']['family']
        self.cmds = []
        self.count = 0

    def c(self, cmd, params=None):
        self.cmds.append(cmd if params is None else f'{cmd}={json.dumps(params, ensure_ascii=False)}')

    def lines(self, text, width, size):
        """Estimated wrapped line count for text in a box `width` pt wide at `size` pt."""
        per_line = max(8, int(self.st['chars_per_line'] * (self.st['title_size'] / size) * (width / self.g['w0'])))
        return sum(max(1, math.ceil(len(t) / per_line)) for t in str(text).split('\n'))

    # ---------- primitives ----------
    def text(self, x, y, w, text, size=12, color=None, bold=False, align='left', anchor=None, h=None, bg=None):
        hh = h or round(size * LINE, 2)
        self.c('insert.textBox', {'rect': [x, y, w, hh], 'text': text})
        # DeckCraft sizes a new text box to its text (28.8 pt minimum); hold the requested box instead.
        self.c('format.autofit', {'mode': 'none'})
        self.c('shape.setBounds', {'x': x, 'y': y, 'w': w, 'h': hh})
        if bg:
            self.c('shape.fill', {'color': bg})
        self.c('format.margins', {'left': 0, 'top': 0, 'right': 0, 'bottom': 0})
        self.c('format.font', {'family': self.font})
        self.c('format.size', {'size': size})
        self.c('format.color', {'color': color or self.c_['ink']})
        if bold:
            self.c('format.bold', {'on': True})
        if align != 'left':
            self.c('format.align', {'align': align})
        if anchor:
            self.c('format.anchor', {'anchor': anchor})

    def rect(self, x, y, w, h, fill, line=None, text=None, size=11, color=None, bold=False, align='left', margin=8):
        p = {'preset': 'rect', 'rect': [x, y, w, h]}
        if text is not None:
            p['text'] = text
        self.c('shape.insert', p)
        self.c('shape.fill', {'color': fill} if fill else {'none': True})
        self.c('shape.line', {'color': line, 'width': 1} if line else {'none': True})
        if text is not None:
            self.c('format.margins', {'left': margin, 'top': 4, 'right': margin, 'bottom': 4})
            self.c('format.font', {'family': self.font})
            self.c('format.size', {'size': size})
            self.c('format.color', {'color': color or self.c_['white']})
            self.c('format.align', {'align': align})
            self.c('format.anchor', {'anchor': 'middle'})
            if bold:
                self.c('format.bold', {'on': True})

    def line(self, x1, y1, x2, y2, color=None, width=1):
        self.c('shape.freeform', {'points': [[x1, y1], [x2, y2]], 'closed': False})
        self.c('shape.line', {'color': color or self.c_['line'], 'width': width})

    def picture(self, png, rect):
        png = Path(png)
        w, h = _png_size(png)
        box = _fit(rect, w / h)
        b64 = base64.b64encode(png.read_bytes()).decode('ascii')
        src = {'data': b64} if len(b64) <= MAX_INLINE_B64 else {'path': str(png.resolve())}
        self.c('insert.picture', {**src, 'rect': box})
        return box

    def bullets(self, x, y, w, items, size=11, color=None, line_h=None, h=None):
        """Bulleted text, one paragraph per item; returns the estimated bottom y. `h` forces the box height."""
        line_h = line_h or round(size * LINE, 2)
        text = '\n'.join(f'•  {b}' for b in items)
        n = self.lines(text, w, size)
        box_h = round(max(h or 0, n * line_h), 2)
        self.text(x, y, w, text, size=size, color=color, h=box_h, anchor='top')
        return y + box_h

    def table(self, x, y, w, rows, size=10, row_h=20, head_h=22):
        n, m = len(rows), max(len(r) for r in rows)
        rows = [[str(v) for v in r] + [''] * (m - len(r)) for r in rows]
        self.c('insert.table', {'rows': n, 'cols': m, 'rect': [x, y, w, head_h + row_h * (n - 1)]})
        self.c('table.style', {'style': 'none'})
        self.c('table.cellMargins', {'left': 6, 'right': 6, 'top': 2, 'bottom': 2})
        for r, row in enumerate(rows):
            for k, val in enumerate(row):
                self.c('text.set', {'cell': [r, k], 'text': val})
        cells = [[r, k] for r in range(n) for k in range(m)]
        self.c('table.cellFill', {'none': True, 'cells': cells})
        band = [[r, k] for r in range(1, n) for k in range(m) if (r - 1) % 2 == 0]
        if band:
            self.c('table.cellFill', {'color': self.c_['band'], 'cells': band})
        self.c('table.borders', {'which': 'none', 'cells': cells})
        self.c('table.borders', {'which': 'bottom', 'color': self.c_['muted'], 'width': 0.5, 'cells': [[n - 1, k] for k in range(m)]})
        self.c('table.selectCells', {'from': [0, 0], 'to': [n - 1, m - 1]})
        self.c('format.font', {'family': self.font})
        self.c('format.size', {'size': size})
        self.c('format.color', {'color': self.c_['ink']})
        self.c('table.cellFill', {'color': self.c_['accent_dark'], 'cells': [[0, k] for k in range(m)]})
        self.c('table.selectCells', {'from': [0, 0], 'to': [0, m - 1]})
        self.c('format.color', {'color': self.c_['white']})
        self.c('format.bold', {'on': True})
        self.c('table.cellAlign', {'anchor': 'middle', 'cells': cells})
        for r in range(n):
            self.c('table.rowHeight', {'row': r, 'height': head_h if r == 0 else row_h})
        self.c('edit.select', {'ids': []})

    # ---------- slide frame ----------
    def slide(self, title, section, footer_text, notes=None):
        g, c = self.g, self.c_
        self.count += 1
        self.c('slide.new', {'layout': 'titleOnly', 'title': title})
        self.c('design.hideBackgroundGraphics', {'hide': True})
        self.c('edit.selectAll')
        self.c('shape.setBounds', {'x': g['x0'], 'y': g['title_y'], 'w': g['w0'], 'h': g['title_h']})
        self.c('format.margins', {'left': 0, 'top': 0, 'right': 0, 'bottom': 0})
        self.c('format.font', {'family': self.font})
        self.c('format.size', {'size': self.st['title_size']})
        self.c('format.color', {'color': c['ink']})
        self.c('format.align', {'align': 'left'})
        self.c('format.anchor', {'anchor': 'top'})
        self.rect(g['x0'], g['rule_y'], g['w0'], 3, c['accent'])
        foot = str(self.count) + (f'   ·   {section}' if section else '')
        self.text(g['x0'], g['foot_y'], 300, foot, size=9, color=c['muted'])
        if footer_text:
            self.text(g['x0'] + g['w0'] - 400, g['foot_y'], 400, footer_text, size=9, color=c['muted'], align='right')
        if notes:
            self.c('slide.notes', {'text': notes})

    # ---------- build ----------
    def build(self, out_dir, name):
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        c = self.c_
        theme = {'dk1': c['ink'], 'lt1': c['white'], 'dk2': c['accent_dark'], 'lt2': c['band'],
                 'accent1': c['accent'], 'accent2': c['accent_dark'], 'accent3': c['green'],
                 'accent4': c['muted'], 'accent5': c['line'], 'accent6': c['red']}
        head = ['design.fonts=' + json.dumps({'major': self.font, 'minor': self.font}),
                'design.colors=' + json.dumps({'colors': theme})]
        tail = ['slide.delete={"index": 0}', 'slide.go={"index": 0}']   # the blank starter slide
        deck = out / f'{name}.deckcraft'
        pptx = out / f'{name}.pptx'
        args = ['deckcraft-cli', 'run']
        for cmd in head + self.cmds + tail:
            args += ['--cmd', cmd]
        args += ['--save', str(deck)]
        r = subprocess.run(args, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f'deckcraft-cli run failed: {r.stderr.strip()[-2000:]}')
        subprocess.run(['deckcraft-cli', 'convert', str(deck), str(pptx)], check=True, capture_output=True, text=True)
        png = out / 'png'
        png.mkdir(exist_ok=True)
        for f in png.glob('*.png'):
            f.unlink()
        subprocess.run(['deckcraft-cli', 'render', str(deck), '--all', '--scale', '1.5', str(png)],
                       check=True, capture_output=True, text=True)
        return pptx


# ---------- layouts ----------

def _chart_or_placeholder(d, slide, charts, rect):
    png = (charts.get(slide['id']) or {}).get('png')
    if png and Path(png).exists():
        d.picture(png, rect)
        return
    title = (slide.get('chart') or {}).get('title') or 'Chart'
    x, y, w, h = rect
    d.rect(x, y, w, h, d.c_['band'], line=d.c_['line'], text=title, size=12, color=d.c_['muted'], align='center')


def _layout_summary(d, story, slide, charts, top, bottom):
    g, c = d.g, d.c_
    blocks = story['summary_blocks']
    col_w = (g['w0'] - g['gutter']) / 2
    avail = bottom - top
    LEAD_Y, LEAD_H, PAD = 10, 21, 10

    def plan(size):
        lh = round(size * LINE, 2)
        hs = []
        for b in blocks:
            text = '\n'.join(f'•  {t}' for t in b.get('bullets', []))
            n = d.lines(text, col_w, size) if b.get('bullets') else 0
            hs.append(LEAD_Y + LEAD_H + 9 + n * lh + PAD)
        # Split so the taller column is as short as possible, keeping block order.
        best = min(range(1, len(blocks)), key=lambda k: max(sum(hs[:k]), sum(hs[k:])))
        return size, lh, hs, best

    for size in (10.5, 9.5, 9.0):
        size, lh, hs, split = plan(size)
        if max(sum(hs[:split]), sum(hs[split:])) <= avail:
            break
    else:
        raise ValueError(f"slide {slide['id']}: the summary does not fit two columns at 9 pt; shorten the bullets")

    cols = [(g['x0'], blocks[:split], hs[:split]), (g['x0'] + col_w + g['gutter'], blocks[split:], hs[split:])]
    for x, items, col_hs in cols:
        # Blocks stretch to fill the column (up to 1.6x); they never shrink below their text.
        scale = min(1.6, avail / sum(col_hs)) if col_hs else 1.0
        y = top
        for b, h in zip(items, col_hs):
            h = h * scale
            d.line(x, y, x + col_w, y, color=c['accent'], width=1.5)
            d.text(x, y + LEAD_Y, col_w, b.get('lead') or b['name'].replace('_', ' ').capitalize(), size=12, bold=True, h=LEAD_H)
            if b.get('bullets'):
                by = y + LEAD_Y + LEAD_H + 9
                d.bullets(x, by, col_w, b['bullets'], size=size, color=c['ink'], line_h=lh, h=h - (by - y) - PAD)
            y += h


def _side_text(d, slide, x, w, top, bottom):
    """Takeaway, callout and body stacked in a side column."""
    c = d.c_
    y = top
    # The takeaway lives in the takeaway bar only; the side column carries the callout and the body.
    if slide.get('callout'):
        n = d.lines(slide['callout'], w, 14)
        d.text(x, y, w, slide['callout'], size=14, bold=True, color=c['accent'], h=n * 24.5, anchor='top')
        y += n * 24.5 + 10
    if slide.get('body'):
        d.bullets(x, y, w, slide['body'], size=11, color=c['ink'])


def _layout_chart_left(d, story, slide, charts, top, bottom):
    g = d.g
    left_w = round(g['w0'] * 0.67 - g['gutter'] / 2)
    right_x = g['x0'] + left_w + g['gutter']
    right_w = g['x0'] + g['w0'] - right_x
    _chart_or_placeholder(d, slide, charts, [g['x0'], top, left_w, bottom - top])
    _side_text(d, slide, right_x, right_w, top, bottom)


def _layout_chart_full(d, story, slide, charts, top, bottom):
    g = d.g
    _chart_or_placeholder(d, slide, charts, [g['x0'], top, g['w0'], bottom - top])


def _layout_table(d, story, slide, charts, top, bottom):
    g = d.g
    rows = ((slide.get('table') or {}).get('rows')) or []
    if not rows:
        raise ValueError(f'slide {slide["id"]}: layout table needs table.rows')
    n = len(rows)
    head_h = 28
    row_h = max(12, min(44, math.floor((bottom - top - head_h) / max(1, n - 1))))
    size = 12 if row_h >= 30 else (11 if row_h >= 22 else (10 if row_h >= 16 else 8))
    d.table(g['x0'], top, g['w0'], rows, size=size, row_h=row_h, head_h=head_h)


def _layout_three_columns(d, story, slide, charts, top, bottom):
    g, c = d.g, d.c_
    cols = slide.get('columns') or []
    if not cols:
        raise ValueError(f'slide {slide["id"]}: layout three_columns needs columns')
    n = len(cols)
    col_w = (g['w0'] - g['gutter'] * (n - 1)) / n
    for i, col in enumerate(cols):
        x = g['x0'] + i * (col_w + g['gutter'])
        d.line(x, top, x + col_w, top, color=c['accent'], width=1.5)
        xi, wi = x, col_w
        y = top + 12
        if col.get('takeaway'):
            k = d.lines(col['takeaway'], wi, 12)
            d.text(xi, y, wi, col['takeaway'], size=12, bold=True, h=k * 21, anchor='top')
            y += k * 21 + 10
        if col.get('figure'):
            d.text(xi, y, wi, col['figure'], size=32, bold=True, color=c['accent'], h=56, anchor='top')
            y += 66
        if col.get('evidence'):
            k = d.lines(col['evidence'], wi, 11)
            d.text(xi, y, wi, col['evidence'], size=11, color=c['muted'], h=max(k * 19.25, bottom - y), anchor='top')


def _layout_text_only(d, story, slide, charts, top, bottom):
    g = d.g
    if slide.get('body'):
        d.bullets(g['x0'], top, g['w0'], slide['body'], size=12)


def _layout_charts_row(d, story, slide, charts, top, bottom):
    """Two or three charts side by side; each column: the chart's takeaway, then its PNG."""
    g, c = d.g, d.c_
    specs = slide.get('charts') or []
    if len(specs) < 2:
        raise ValueError(f'slide {slide["id"]}: layout charts_row needs 2 or 3 charts')
    items = (charts.get(slide['id']) or {}).get('items') or []
    n = len(specs)
    col_w = round((g['w0'] - g['gutter'] * (n - 1)) / n, 2)
    for i, spec in enumerate(specs):
        x = round(g['x0'] + i * (col_w + g['gutter']), 2)
        y = top
        if spec.get('takeaway'):
            k = d.lines(spec['takeaway'], col_w, 12)
            d.text(x, y, col_w, spec['takeaway'], size=12, bold=True, h=k * 21, anchor='top')
            y += k * 21 + 10
        rect = [x, y, col_w, round(bottom - y, 2)]
        item = items[i] if i < len(items) and isinstance(items[i], dict) else {}
        png = item.get('png')
        if png and Path(png).exists():
            d.picture(png, rect)
        else:
            d.rect(x, y, col_w, rect[3], c['band'], line=c['line'], text=spec.get('title') or 'Chart',
                   size=11, color=c['muted'], align='center')


LAYOUTS = {
    'summary': _layout_summary,
    'chart_left': _layout_chart_left,
    'chart_full': _layout_chart_full,
    'charts_row': _layout_charts_row,
    'table': _layout_table,
    'three_columns': _layout_three_columns,
    'text_only': _layout_text_only,
}


def check_titles(story, style):
    limit = 2 * style['chars_per_line']
    for s in story['slides']:
        if len(s['title']) > limit:
            raise ValueError(f'slide {s["id"]}: title is {len(s["title"])} chars, over two lines of {style["chars_per_line"]}')


def render_pptx(story, charts, out_dir, style='default', name='deck'):
    """Build the deck; returns the .pptx path. Also writes <name>.deckcraft and png/slide-NN.png."""
    st = load_style(style)
    check_titles(story, st)
    charts = charts or {}
    d = _Deck(st)
    g, c = st['grid'], st['colors']
    footer_text = story.get('footer') or st.get('footer_text') or ''
    by_id = {s['id']: s for s in story['slides']}
    for slide in story['slides']:
        if slide['layout'] not in LAYOUTS:
            raise ValueError(f'slide {slide["id"]}: unknown layout {slide["layout"]}')
        d.slide(slide['title'], slide.get('section'), footer_text, notes=slide.get('notes'))
        sub_y = g['sub_y']
        if slide.get('kind') == 'detail' and slide.get('parent') in by_id:
            d.text(g['x0'], sub_y, g['w0'], f'Detail for {by_id[slide["parent"]]["title"][:60]}', size=10, color=c['muted'])
            sub_y += 24
        if slide.get('subtitle'):
            n_sub = d.lines(slide['subtitle'], g['w0'], 13)
            d.text(g['x0'], sub_y, g['w0'], slide['subtitle'], size=13, color=c['muted'],
                   h=min(g['body_y'] - sub_y - 10, round(n_sub * 13 * LINE, 2)), anchor='top')
        # A slide with no subtitle and no detail kicker starts its body at the subtitle line.
        has_kicker = slide.get('kind') == 'detail' and slide.get('parent') in by_id
        top, bottom = (g['body_y'] if (slide.get('subtitle') or has_kicker) else g['sub_y']), g['body_end']
        chart_src = ((slide.get('chart') or {}).get('source') or '').strip()
        if slide.get('source') and not (slide['id'] in charts and slide['source'].strip() == chart_src):
            d.text(g['x0'], g['source_y'], g['w0'], 'Source: ' + slide['source'], size=8, color=c['muted'])
        if slide.get('takeaway'):
            d.rect(g['x0'], g['take_y'], g['w0'], 28, c['accent_dark'], text=slide['takeaway'], size=11.5,
                   color=c['white'], bold=True, margin=12)
        if slide.get('callout') and slide['layout'] != 'chart_left':
            d.text(g['x0'], top, g['w0'], slide['callout'], size=12, bold=True, color=c['accent'], align='right', h=21)
            top += 31
        LAYOUTS[slide['layout']](d, story, slide, charts, top, bottom)
    return d.build(out_dir, name)
