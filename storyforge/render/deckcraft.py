"""Render story.json to a PPTX through deckcraft-cli.

Every primitive appends deckcraft-cli commands; build() runs them, saves the .deckcraft, converts
it to .pptx and renders one PNG per slide. Fonts, colours and the grid come from a style file in
styles/; the story may set `footer` to put text in the footer's right corner.

Shapes carry names (Take_1_Badge, Implication_Bar, ...) so the spatial gate treats a badge and its
text, or a bar and its body, as one intentional group.
"""

import base64
import json
import math
import re
import struct
import subprocess
from pathlib import Path

STYLES = Path(__file__).resolve().parent / 'styles'
# One base64 picture must stay under the Linux per-argument limit (128 KB); larger PNGs go by path.
MAX_INLINE_B64 = 100_000
LINE = 1.75  # box height per text line, as a multiple of the font size; the spatial gate models text at 1.4 and caps fill at 85%
NUMERIC = re.compile(r'^[+\-−]?\$?\d[\d,.]*\s?[kKMB%]?$')


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

    def _font(self, size, color, bold=False, align='left', anchor=None):
        self.c('format.font', {'family': self.font})
        self.c('format.size', {'size': size})
        self.c('format.color', {'color': color})
        if bold:
            self.c('format.bold', {'on': True})
        if align != 'left':
            self.c('format.align', {'align': align})
        if anchor:
            self.c('format.anchor', {'anchor': anchor})

    def _name(self, name):
        if name:
            self.c('shape.rename', {'name': name})

    # ---------- primitives ----------
    def text(self, x, y, w, text, size=12, color=None, bold=False, align='left', anchor=None, h=None, name=None):
        hh = h or round(size * LINE, 2)
        self.c('insert.textBox', {'rect': [x, y, w, hh], 'text': text})
        # DeckCraft sizes a new text box to its text (28.8 pt minimum); hold the requested box instead.
        self.c('format.autofit', {'mode': 'none'})
        self.c('shape.setBounds', {'x': x, 'y': y, 'w': w, 'h': hh})
        self.c('format.margins', {'left': 0, 'top': 0, 'right': 0, 'bottom': 0})
        self._font(size, color or self.c_['ink'], bold, align, anchor)
        self._name(name)

    def rect(self, x, y, w, h, fill, line=None, text=None, size=11, color=None, bold=False, align='left',
             margin=8, preset='rect', name=None):
        p = {'preset': preset, 'rect': [x, y, w, h]}
        if text is not None:
            p['text'] = text
        self.c('shape.insert', p)
        self.c('shape.fill', {'color': fill} if fill else {'none': True})
        self.c('shape.line', {'color': line, 'width': 1} if line else {'none': True})
        if text is not None:
            self.c('format.margins', {'left': margin, 'top': 4, 'right': margin, 'bottom': 4})
            self._font(size, color or self.c_['white'], bold, align, 'middle')
            if align == 'left':
                self.c('format.align', {'align': 'left'})   # a shape's text is centred by default
        self._name(name)

    def badge(self, x, y, n, name=None):
        """A 16 pt accent circle with the white number: one shape."""
        self.c('shape.insert', {'preset': 'ellipse', 'rect': [x, y, 16, 16], 'text': str(n)})
        self.c('shape.fill', {'color': self.c_['accent']})
        self.c('shape.line', {'none': True})
        self.c('format.margins', {'left': 0, 'top': 0, 'right': 0, 'bottom': 0})
        self._font(9, self.c_['white'], True, 'center', 'middle')
        self._name(name)

    def line(self, x1, y1, x2, y2, color=None, width=1, name='Rule_Line'):
        self.c('shape.freeform', {'points': [[x1, y1], [x2, y2]], 'closed': False})
        self.c('shape.line', {'color': color or self.c_['line'], 'width': width})
        self._name(name)

    def picture(self, png, rect, name=None):
        png = Path(png)
        w, h = _png_size(png)
        box = _fit(rect, w / h)
        b64 = base64.b64encode(png.read_bytes()).decode('ascii')
        src = {'data': b64} if len(b64) <= MAX_INLINE_B64 else {'path': str(png.resolve())}
        self.c('insert.picture', {**src, 'rect': box})
        self._name(name)
        return box

    def bullets(self, x, y, w, items, size=11, color=None, line_h=None, h=None, anchor='top', name=None):
        """Bulleted text, one paragraph per item; returns the bottom y. `h` forces the box height."""
        line_h = line_h or round(size * LINE, 2)
        text = '\n'.join(f'•  {b}' for b in items)
        n = self.lines(text, w, size)
        box_h = round(max(h or 0, n * line_h), 2)
        self.text(x, y, w, text, size=size, color=color, h=box_h, anchor=anchor, name=name)
        return y + box_h

    def table(self, x, y, w, rows, size=10, row_h=20, head_h=22, name='Table'):
        """Reference table: muted bold header, hairline under every row, numeric columns right-aligned,
        bold last row when its first cell is Total."""
        c = self.c_
        n, m = len(rows), max(len(r) for r in rows)
        rows = [[str(v) for v in r] + [''] * (m - len(r)) for r in rows]
        self.c('insert.table', {'rows': n, 'cols': m, 'rect': [x, y, w, head_h + row_h * (n - 1)]})
        self._name(name)
        self.c('table.style', {'style': 'none'})
        self.c('table.cellMargins', {'left': 6, 'right': 6, 'top': 2, 'bottom': 2})
        for r, row in enumerate(rows):
            for k, val in enumerate(row):
                self.c('text.set', {'cell': [r, k], 'text': val})
        cells = [[r, k] for r in range(n) for k in range(m)]
        self.c('table.cellFill', {'none': True, 'cells': cells})
        self.c('table.borders', {'which': 'none', 'cells': cells})
        self.c('table.borders', {'which': 'bottom', 'color': c['line'], 'width': 0.75, 'cells': cells})
        self.c('table.selectCells', {'from': [0, 0], 'to': [n - 1, m - 1]})
        self._font(size, c['ink'])
        self.c('table.selectCells', {'from': [0, 0], 'to': [0, m - 1]})
        self._font(max(size - 1, 7), c['muted'], True)
        self.c('table.borders', {'which': 'bottom', 'color': c['muted'], 'width': 0.75, 'cells': [[0, k] for k in range(m)]})
        if n > 1 and rows[-1][0].strip().lower() == 'total':
            self.c('table.selectCells', {'from': [n - 1, 0], 'to': [n - 1, m - 1]})
            self.c('format.bold', {'on': True})
            self.c('table.borders', {'which': 'top', 'color': c['muted'], 'width': 0.75, 'cells': [[n - 1, k] for k in range(m)]})
        for k in range(m):
            body = [rows[r][k].strip() for r in range(1, n) if rows[r][k].strip()]
            if body and all(NUMERIC.match(v) for v in body):
                self.c('table.selectCells', {'from': [0, k], 'to': [n - 1, k]})
                self.c('format.align', {'align': 'right'})
        self.c('table.cellAlign', {'anchor': 'middle', 'cells': cells})
        for r in range(n):
            self.c('table.rowHeight', {'row': r, 'height': head_h if r == 0 else row_h})
        self.c('edit.select', {'ids': []})
        return y + head_h + row_h * (n - 1)

    # ---------- slide frame ----------
    def slide(self, title, section, callout=None, notes=None):
        """Kicker row (slide number and section, the callout on the right), then the title placeholder."""
        g, c = self.g, self.c_
        self.count += 1
        self.c('slide.new', {'layout': 'titleOnly', 'title': title})
        self.c('design.hideBackgroundGraphics', {'hide': True})
        self.c('edit.selectAll')
        self.c('shape.setBounds', {'x': g['x0'], 'y': g['title_y'], 'w': g['w0'], 'h': g['title_h']})
        self.c('format.margins', {'left': 0, 'top': 0, 'right': 0, 'bottom': 0})
        self._font(self.st['title_size'], c['ink'], True, 'left', 'top')
        kicker = str(self.count) + (f'   \u00b7   {section.upper()}' if section else '')
        self.text(g['x0'], g['kicker_y'], 380, kicker, size=10, bold=True, color=c['accent'], h=g['kicker_h'], name='Kicker')
        if callout:
            self.text(g['x0'] + 380 + g['gap'], g['kicker_y'], g['w0'] - 380 - g['gap'], callout, size=10, bold=True,
                      color=c['accent'], align='right', h=g['kicker_h'], name='Callout')
        if notes:
            self.c('slide.notes', {'text': notes})

    def footer(self, footnotes, footer_text):
        """Footer row: slide number, numbered footnotes (7.5 pt) and the story footer; returns the row's top."""
        g, c = self.g, self.c_
        bottom = g['foot_y'] + g['foot_h']
        fn_x = g['x0'] + 24 + g['gap']
        fn_w = g['w0'] - 24 - g['gap'] - (500 + g['gap'] if footer_text else 0)
        fn_h = 0
        if footnotes:
            text = '\n'.join(f'{i + 1}  {t}' for i, t in enumerate(footnotes))
            fn_h = round(self.lines(text, fn_w, 7.5) * 9.5, 2)
        top = round(bottom - max(g['foot_h'], fn_h), 2)
        self.text(g['x0'], top, 24, str(self.count), size=9, color=c['muted'], h=g['foot_h'], name='Footer_Num')
        if footnotes:
            self.text(fn_x, top, fn_w, text, size=7.5, color=c['muted'], h=round(bottom - top, 2), anchor='top', name='Footnotes')
        if footer_text:
            self.text(g['x0'] + g['w0'] - 500, top, 500, footer_text, size=9, color=c['muted'], align='right',
                      h=g['foot_h'], name='Footer_Text')
        return top

    # ---------- build ----------
    def build(self, out_dir, name):
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        c = self.c_
        theme = {'dk1': c['ink'], 'lt1': c['bg'], 'dk2': c['navy'], 'lt2': c['soft'],
                 'accent1': c['accent'], 'accent2': c['navy'], 'accent3': c['good'],
                 'accent4': c['muted'], 'accent5': c['line'], 'accent6': c['bad']}
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


# ---------- shared pieces ----------

def _placeholder(d, rect, title, name=None):
    x, y, w, h = rect
    d.rect(x, y, w, h, d.c_['soft'], line=d.c_['line'], text=title or 'Chart', size=11, color=d.c_['muted'],
           align='center', name=name)


def _chart_or_placeholder(d, slide, charts, rect, name='Chart'):
    png = (charts.get(slide['id']) or {}).get('png')
    if png and Path(png).exists():
        d.picture(png, rect, name=name)
        return
    _placeholder(d, rect, (slide.get('chart') or {}).get('title'), name=name)


def _numbered_takeaway(d, x, w, y, n, text, size=12):
    """Badge circle, 8 pt gap, bold takeaway; returns the bottom y."""
    d.badge(x, y + 2, n, name=f'Take_{n}_Badge')
    k = d.lines(text, w - 24, size)
    h = k * 21
    d.text(x + 24, y, w - 24, text, size=size, bold=True, h=h, anchor='top', name=f'Take_{n}_Text')
    return y + h


# ---------- layouts ----------

def _layout_summary(d, story, slide, charts, top, bottom):
    """The reference rows: a navy message box (34%) and the points to its right, one row per block."""
    g, c = d.g, d.c_
    blocks = story['summary_blocks']
    gap = g['gap']
    msg_w = round(g['w0'] * 0.34, 2)
    pts_x = round(g['x0'] + msg_w + 14, 2)
    pts_w = round(g['x0'] + g['w0'] - pts_x, 2)
    avail = bottom - top - gap * (len(blocks) - 1)
    leads = [b.get('lead') or b['name'].replace('_', ' ').capitalize() for b in blocks]
    for size in (10.5, 10, 9.5, 9):
        lh = round(size * LINE, 2)
        hs = []
        for b, lead in zip(blocks, leads):
            n_pts = d.lines('\n'.join(f'•  {t}' for t in b['bullets']), pts_w, size) if b.get('bullets') else 0
            n_lead = d.lines(lead, msg_w - 24, 12)
            hs.append(max(n_pts * lh + 10, n_lead * 21 + 12, 36))
        if sum(hs) <= avail:
            break
    else:
        raise ValueError(f"slide {slide['id']}: the summary rows do not fit at 9 pt; shorten the bullets")
    scale = min(1.35, avail / sum(hs))
    y = top
    for i, (b, lead, h) in enumerate(zip(blocks, leads, hs)):
        h = round(h * scale, 2)
        fill = c['accent'] if (b.get('name') == 'goals' or i == 0) else c['navy']
        d.rect(g['x0'], y, msg_w, h, fill, text=lead, size=12, color=c['white'], bold=True, margin=12, name=f'Row_{i + 1}_Msg')
        if b.get('bullets'):
            d.bullets(pts_x, y + 5, pts_w, b['bullets'], size=size, color=c['ink2'], line_h=lh, h=h - 10,
                      anchor='middle', name=f'Row_{i + 1}_Pts')
        y += h + gap


def _side_text(d, slide, x, w, top, bottom):
    """Callout and body stacked in a side column; the takeaway lives in the takeaway band only."""
    c = d.c_
    y = top
    if slide.get('callout'):
        n = d.lines(slide['callout'], w, 14)
        d.text(x, y, w, slide['callout'], size=14, bold=True, color=c['accent'], h=n * 24.5, anchor='top', name='Callout')
        y += n * 24.5 + 10
    if slide.get('body'):
        d.bullets(x, y, w, slide['body'], size=11, color=c['ink2'], name='Body')


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
    col_w = round((g['w0'] - g['gutter'] * (n - 1)) / n, 2)
    for i, col in enumerate(cols):
        x = round(g['x0'] + i * (col_w + g['gutter']), 2)
        d.line(x, top, x + col_w, top, color=c['navy'], width=2, name=f'Col_{i + 1}_Line')
        y = top + 12
        if col.get('takeaway'):
            y = _numbered_takeaway(d, x, col_w, y, i + 1, col['takeaway']) + 10
        if col.get('figure'):
            d.text(x, y, col_w, col['figure'], size=28, bold=True, color=c['accent'], h=48, anchor='top', name=f'Col_{i + 1}_Figure')
            y += 58
        if col.get('evidence'):
            k = d.lines(col['evidence'], col_w, 11)
            d.text(x, y, col_w, col['evidence'], size=11, color=c['muted'], h=max(k * 19.25, bottom - y), anchor='top',
                   name=f'Col_{i + 1}_Evidence')


def _layout_text_only(d, story, slide, charts, top, bottom):
    g = d.g
    if slide.get('body'):
        d.bullets(g['x0'], top, g['w0'], slide['body'], size=12, name='Body')


def _layout_charts_row(d, story, slide, charts, top, bottom):
    """Two or three charts side by side, each under its numbered takeaway; an optional compact table below."""
    g, c = d.g, d.c_
    specs = slide.get('charts') or []
    if len(specs) < 2:
        raise ValueError(f'slide {slide["id"]}: layout charts_row needs 2 or 3 charts')
    items = (charts.get(slide['id']) or {}).get('items') or []
    rows = ((slide.get('table') or {}).get('rows')) or []
    chart_bottom = bottom
    if rows:
        head_h, row_h = 20, 16
        table_h = head_h + row_h * (len(rows) - 1)
        chart_bottom = bottom - table_h - g['gap']
    n = len(specs)
    col_w = round((g['w0'] - g['gutter'] * (n - 1)) / n, 2)
    for i, spec in enumerate(specs):
        x = round(g['x0'] + i * (col_w + g['gutter']), 2)
        y = top
        if spec.get('takeaway'):
            y = _numbered_takeaway(d, x, col_w, y, i + 1, spec['takeaway']) + 10
        rect = [x, y, col_w, round(chart_bottom - y, 2)]
        if rect[3] < 80:
            raise ValueError(f'slide {slide["id"]}: only {rect[3]:.0f} pt left for chart {i + 1}; '
                             'drop the table, the subtitle or the implication')
        item = items[i] if i < len(items) and isinstance(items[i], dict) else {}
        png = item.get('png')
        if png and Path(png).exists():
            d.picture(png, rect, name=f'Chart_{i + 1}')
        else:
            _placeholder(d, rect, spec.get('title'), name=f'Chart_{i + 1}')
    if rows:
        d.table(g['x0'], round(bottom - table_h, 2), g['w0'], rows, size=9, row_h=row_h, head_h=head_h)


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


def _bottom_stack(d, slide, charts, footer_top):
    """Takeaway band, source line and implication, stacked up from the footer row; returns the body's bottom."""
    g, c = d.g, d.c_
    gap = g['gap']
    y = footer_top - gap
    if slide.get('takeaway'):
        y = round(y - g['take_h'], 2)
        d.rect(g['x0'], y, g['w0'], g['take_h'], c['navy'], text=slide['takeaway'], size=11.5, color=c['white'],
               bold=True, margin=12, name='Takeaway_Band')
        y -= gap
    # Chart PNGs carry their own source line. One chart: skip the slide line when it repeats the chart's.
    # Two or more charts: each chart names its source, so the slide line is skipped.
    chart_src = ((slide.get('chart') or {}).get('source') or '').strip()
    one_same = slide['id'] in charts and (slide.get('source') or '').strip() == chart_src
    multi = slide.get('charts') and all((sp.get('source') or '').strip() for sp in slide['charts'])
    if slide.get('source') and not (one_same or multi):
        y = round(y - g['source_h'], 2)
        d.text(g['x0'], y, g['w0'], 'Source: ' + slide['source'], size=8, color=c['muted'], h=g['source_h'], name='Source')
        y -= gap
    if slide.get('implication'):
        n = d.lines(slide['implication'], g['w0'] - 30, 11)
        imp_h = round(n * 11 * LINE + 10, 2)
        y = round(y - imp_h, 2)
        d.rect(g['x0'], y, g['w0'], imp_h, c['accent_soft'], text=slide['implication'], size=11, color=c['ink'],
               bold=True, align='center', margin=14, name='Implication_Body')
        d.rect(g['x0'], y, 3, imp_h, c['accent'], name='Implication_Bar')
        y -= gap
    return y


def render_pptx(story, charts, out_dir, style='default', name='deck'):
    """Build the deck; returns the .pptx path. Also writes <name>.deckcraft and png/slide-NN.png."""
    st = load_style(style)
    check_titles(story, st)
    charts = charts or {}
    d = _Deck(st)
    g, c = st['grid'], st['colors']
    gap = g['gap']
    footer_text = story.get('footer') or st.get('footer_text') or ''
    by_id = {s['id']: s for s in story['slides']}
    for slide in story['slides']:
        if slide['layout'] not in LAYOUTS:
            raise ValueError(f'slide {slide["id"]}: unknown layout {slide["layout"]}')
        side_callout = slide['layout'] == 'chart_left'
        d.slide(slide['title'], slide.get('section'), callout=None if side_callout else slide.get('callout'),
                notes=slide.get('notes'))
        footer_top = d.footer(slide.get('footnotes'), footer_text)
        sub_y = g['sub_y']
        top = g['sub_y']
        if slide.get('kind') == 'detail' and slide.get('parent') in by_id:
            d.text(g['x0'], sub_y, g['w0'], f'Detail for {by_id[slide["parent"]]["title"][:60]}', size=10,
                   color=c['muted'], h=17, name='Detail_Kicker')
            sub_y += 17 + gap
            top = max(g['body_y'], sub_y)
        if slide.get('subtitle'):
            n_sub = min(3, d.lines(slide['subtitle'], g['w0'], 13))
            sub_h = round(n_sub * 13 * LINE, 2)
            d.text(g['x0'], sub_y, g['w0'], slide['subtitle'], size=13, color=c['ink2'], h=sub_h, anchor='top', name='Subtitle')
            top = max(g['body_y'], sub_y + sub_h + gap)
        bottom = _bottom_stack(d, slide, charts, footer_top)
        LAYOUTS[slide['layout']](d, story, slide, charts, top, bottom)
    return d.build(out_dir, name)
