"""Handoff package: story.json plus rendered charts to a directory another agent or person can build the deck from."""

import csv
import json
import shutil
from pathlib import Path
from string import Template

from openpyxl import Workbook

VERIFY_COMMAND = 'python3 -m storyforge gates <your.pptx> --story story.json'

# The Rate card checks table from the design spec, one line per gate.
GATES = {
    'R01': 'A governing thought exists and is first',
    'R02': 'SCQA opening present',
    'R03': 'Pyramid depth: answer, 3 to 5 reasons, supports',
    'R04': 'MECE at each level',
    'R05': 'Vertical logic: body proves title',
    'R06': 'Horizontal logic: siblings parallel and of one type',
    'R07': 'One message per slide',
    'R08': 'SVOM title: lexical filter',
    'R09': 'SVOM title: role dissection verified',
    'R10': 'Title at most two lines (chars per line from the renderer)',
    'R11': 'No "xxx: yyy" title, no two sentences',
    'R12': 'Key and detail split explicit',
    'R13': 'Every number in a title names its metric and base, and shares carry the total',
    'R14': 'Observed versus modeled marked',
    'R15': 'Tradeoffs present where the decision is not yes or no',
    'R16': 'Every chart has title, units, source',
    'R17': 'Every chart has one callout',
    'R18': 'Editorial filler absent; relative comparisons name the benchmark',
    'R19': 'Summary bullets equal slide titles verbatim',
    'R20': 'Every title number traces to a data row',
    'R21': 'Read the titles alone: one argument that reaches the decision',
    'R22': 'Spatial gate (SlideForge pptx-review)',
}

# One ASCII box per renderer layout: where each element sits on the 16:9 slide.
LAYOUT_SKETCHES = {
    'summary': """\
+--------------------------------------------------------------+
| TITLE (governing thought, one or two lines)                   |
|--------------------------------------------------------------|
| 1 Goals     | 2 Result   | 3 We see  | 4 Propose | 5 Need    |
|  lead       |  lead      |  lead     |  lead     |  lead     |
|  - bullet   |  - bullet  |  - bullet |  - bullet |  - bullet |
|--------------------------------------------------------------|
| SOURCE                                                FOOTER |
+--------------------------------------------------------------+""",
    'chart_left': """\
+--------------------------------------------------------------+
| TITLE (one or two lines)                                      |
| subtitle                                                     |
|------------------------------------+-------------------------|
| CHART (title, unit, one annotation) | CALLOUT (one figure)    |
|                                    | TAKEAWAY (one line)     |
|------------------------------------+-------------------------|
| SOURCE                                                FOOTER |
+--------------------------------------------------------------+""",
    'chart_full': """\
+--------------------------------------------------------------+
| TITLE (one or two lines)                                      |
| subtitle                                                     |
|--------------------------------------------------------------|
| CHART, full width (title, unit, one annotation)   [CALLOUT]  |
|                                                              |
| TAKEAWAY (one line, under the chart)                         |
| SOURCE                                                FOOTER |
+--------------------------------------------------------------+""",
    'charts_row': """\
+--------------------------------------------------------------+
| TITLE (one or two lines)                                      |
| subtitle                                                     |
|--------------------+-------------------+---------------------|
| CHART 1 takeaway   | CHART 2 takeaway  | CHART 3 takeaway    |
|  chart (title,     |  chart (title,    |  chart (title,      |
|  unit, annotation) |  unit, annotation)|  unit, annotation)  |
| TAKEAWAY (one line)                               [CALLOUT]  |
| SOURCE                                                FOOTER |
+--------------------------------------------------------------+""",
    'table': """\
+--------------------------------------------------------------+
| TITLE (one or two lines)                                      |
| subtitle                                                     |
|--------------------------------------------------------------|
| TABLE: header row, then one row per item          [CALLOUT]  |
|   col 1      | col 2      | col 3      | col 4               |
| TAKEAWAY (one line, under the table)                         |
| SOURCE                                                FOOTER |
+--------------------------------------------------------------+""",
    'three_columns': """\
+--------------------------------------------------------------+
| TITLE (one or two lines)                                      |
| subtitle                                                     |
|--------------------+-------------------+---------------------|
| COLUMN 1 takeaway  | COLUMN 2 takeaway | COLUMN 3 takeaway   |
|  FIGURE            |  FIGURE           |  FIGURE             |
|  evidence          |  evidence         |  evidence           |
| TAKEAWAY / CALLOUT                                           |
| SOURCE                                                FOOTER |
+--------------------------------------------------------------+""",
    'text_only': """\
+--------------------------------------------------------------+
| TITLE (one or two lines)                                      |
| subtitle                                                     |
|--------------------------------------------------------------|
| BODY: short paragraphs or bullets                 [CALLOUT]  |
|                                                              |
| TAKEAWAY (one line)                                          |
| SOURCE                                                FOOTER |
+--------------------------------------------------------------+""",
}

SLIDES_COLUMNS = ['id', 'kind', 'parent', 'section', 'layout', 'title', 'subtitle', 'takeaway', 'callout', 'source']
NUMBERS_COLUMNS = ['slide', 'value', 'metric', 'base', 'trace']
SHEET_NAME_MAX = 31


def _cell(v):
    """A scalar openpyxl and csv accept: dicts and lists become JSON."""
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return v


def _series_value(series, label, index):
    """The y of a series at a label: match points by x, else by position."""
    points = series.get('points')
    if points is not None:
        for p in points:
            if p.get('x') == label:
                return p.get('y')
        if index < len(points):
            return points[index].get('y')
        return None
    values = series.get('values') or []
    return values[index] if index < len(values) else None


def chart_rows(chart):
    """A chart spec in flat rows with a header, one shape per svg-charts builder."""
    kind = chart.get('type', '')
    if kind == 'lineChart':
        series = chart.get('series') or []
        labels = list(chart.get('labels') or [])
        if not labels:
            seen = []
            for s in series:
                for p in s.get('points') or []:
                    if p.get('x') not in seen:
                        seen.append(p.get('x'))
            labels = seen
        rows = [['label'] + [s.get('name', f'series {i + 1}') for i, s in enumerate(series)]]
        for i, lab in enumerate(labels):
            rows.append([lab] + [_series_value(s, lab, i) for s in series])
        return rows
    if kind in ('barChart', 'divergingBars'):
        items = chart.get('data') or chart.get('items') or []
        return [['label', 'value']] + [[d.get('label'), d.get('value')] for d in items]
    if kind == 'waterfall':
        items = chart.get('items') or chart.get('data') or []
        return [['label', 'value', 'total']] + [[d.get('label'), d.get('value'), bool(d.get('total'))] for d in items]
    if kind == 'scatter':
        rows = [['group', 'x', 'y']]
        for g in chart.get('groups') or chart.get('series') or []:
            for p in g.get('points') or []:
                rows.append([g.get('name'), p.get('x'), p.get('y')])
        return rows
    if kind == 'dumbbell':
        items = chart.get('rows') or chart.get('data') or []
        return [['label', 'a', 'b']] + [[d.get('label'), d.get('a'), d.get('b')] for d in items]
    if kind == 'stackedBars':
        columns = chart.get('columns') or chart.get('data') or []
        keys = list(chart.get('keys') or [])
        if not keys:
            for c in columns:
                for k in (c.get('parts') or {}):
                    if k not in keys:
                        keys.append(k)
        return [['label'] + keys] + [[c.get('label')] + [(c.get('parts') or {}).get(k) for k in keys] for c in columns]
    raise ValueError(f'chart type {kind!r} has no flat row form')


def sheet_name(slide_id, index=None):
    """The sheet for a slide's chart or table: the id, or `<id>_<i>` for a charts[] slide, cut to Excel's 31 chars."""
    if index is None:
        return slide_id[:SHEET_NAME_MAX]
    suffix = f'_{index}'
    return slide_id[:SHEET_NAME_MAX - len(suffix)] + suffix


def slide_charts(slide):
    """The chart specs of a slide in order: charts[] when present, else the single chart."""
    if slide.get('charts'):
        return list(slide['charts'])
    return [slide['chart']] if slide.get('chart') else []


def data_sheets(story):
    """Every sheet of data.xlsx as {name: rows}, in order: slides, numbers, then one per chart or table."""
    sheets = {}
    sheets['slides'] = [SLIDES_COLUMNS] + [[_cell(s.get(c)) for c in SLIDES_COLUMNS] for s in story['slides']]
    numbers = [NUMBERS_COLUMNS]
    for s in story['slides']:
        for n in s.get('numbers') or []:
            numbers.append([s['id'], n.get('value'), n.get('metric'), n.get('base'), json.dumps(n.get('trace'), ensure_ascii=False)])
    sheets['numbers'] = numbers
    for s in story['slides']:
        if s.get('charts'):
            for i, c in enumerate(s['charts'], 1):
                sheets[sheet_name(s['id'], i)] = chart_rows(c)
        elif s.get('chart'):
            sheets[sheet_name(s['id'])] = chart_rows(s['chart'])
        elif s.get('table'):
            sheets[sheet_name(s['id'])] = [list(r) for r in s['table'].get('rows') or []]
    return sheets


def write_xlsx(sheets, path):
    wb = Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(title=name)
        for r in rows:
            ws.append([_cell(v) for v in r])
    wb.save(path)


def write_csvs(sheets, folder):
    folder.mkdir(parents=True, exist_ok=True)
    for name, rows in sheets.items():
        with (folder / f'{name}.csv').open('w', newline='') as f:
            w = csv.writer(f)
            for r in rows:
                w.writerow(['' if v is None else _cell(v) for v in r])


def copy_charts(charts, folder):
    """Copy rendered charts into folder; skip paths that do not exist.

    `charts` maps a slide id to {'svg': Path, 'png': Path} for one chart, or to
    {'items': [{'svg': Path, 'png': Path}, ...]} for a charts[] slide, copied as <id>_<i>.<ext>.
    """
    folder.mkdir(parents=True, exist_ok=True)
    copied = []
    for sid, files in (charts or {}).items():
        if not isinstance(files, dict):
            continue
        targets = [(sid, files)]
        if 'items' in files:
            targets = [(f'{sid}_{i}', item) for i, item in enumerate(files['items'], 1)]
        for name, item in targets:
            for ext in ('svg', 'png'):
                src = item.get(ext) if isinstance(item, dict) else None
                if src and Path(src).exists():
                    dst = folder / f'{name}.{ext}'
                    shutil.copyfile(src, dst)
                    copied.append(dst)
    return copied


def _md_table(header, rows):
    out = [f"| {' | '.join(header)} |", f"|{'|'.join('---' for _ in header)}|"]
    for r in rows:
        out.append(f"| {' | '.join(_md_text(v) for v in r)} |")
    return '\n'.join(out)


def _md_text(v):
    if v is None:
        return ''
    s = _cell(v) if isinstance(v, (dict, list)) else str(v)
    return s.replace('|', '\\|').replace('\n', ' ')


def speaker_note(slide):
    """One plain line: the takeaway when present, else the title."""
    return (slide.get('takeaway') or slide['title']).strip()


def _chart_line(chart, sheet, file_stem):
    ann = '; '.join(str(a.get('text', '')) for a in chart.get('annotations') or []) or 'none'
    return (f"type {chart.get('type')}, title \"{chart.get('title', '')}\", unit {chart.get('unit', '')}, "
            f"source {chart.get('source', '')}, annotation {ann}, data: see data.xlsx sheet {sheet}, rendered charts/{file_stem}.svg")


def _slide_section(n, s):
    lines = [f"## Slide {n}: {s['id']}", '']
    lines.append(_md_table(['field', 'value'], [
        ['kind', s.get('kind')], ['parent', s.get('parent') or 'none'],
        ['section', s.get('section') or ''], ['layout', s.get('layout')]]))
    lines.append('')
    lines.append(f"- Title: {s['title']}")
    lines.append(f"- Subtitle: {s.get('subtitle') or 'none'}")
    lines.append(f"- Takeaway: {s.get('takeaway') or 'none'}")
    lines.append(f"- Callout: {s.get('callout') or 'none'}")
    lines.append(f"- Layout sketch: see \"{s.get('layout')}\" under Layout sketches")
    charts, table = slide_charts(s), s.get('table')
    if s.get('charts'):
        lines.append(f'- Charts: {len(charts)}, left to right')
        for i, c in enumerate(charts, 1):
            stem = f"{s['id']}_{i}"
            lines.append(f"- Chart {i}: takeaway \"{c.get('takeaway', '')}\", {_chart_line(c, sheet_name(s['id'], i), stem)}")
    elif charts:
        lines.append(f"- Chart: {_chart_line(charts[0], sheet_name(s['id']), s['id'])}")
    elif table:
        rows = table.get('rows') or []
        lines.append(f"- Table: {max(len(rows) - 1, 0)} rows plus header, data: see data.xlsx sheet {sheet_name(s['id'])}")
    else:
        lines.append('- Chart: none')
    if s.get('columns'):
        lines.append('- Columns:')
        for c in s['columns']:
            lines.append(f"  - {c.get('takeaway', '')} | {c.get('figure', '')} | {c.get('evidence', '')}")
    if s.get('body'):
        lines.append('- Body:')
        for b in s['body']:
            lines.append(f'  - {b}')
    lines.append(f"- Source: {s.get('source') or 'none'}")
    numbers = s.get('numbers') or []
    if numbers:
        lines.append('- Numbers:')
        lines.append('')
        lines.append(_md_table(['value', 'metric', 'base', 'trace'],
                               [[n.get('value'), n.get('metric'), n.get('base'), json.dumps(n.get('trace'), ensure_ascii=False)] for n in numbers]))
        lines.append('')
    else:
        lines.append('- Numbers: none')
    lines.append(f'- Speaker note: {speaker_note(s)}')
    lines.append('')
    return '\n'.join(lines)


def render_brief(story):
    template = Template((Path(__file__).parent / 'handoff_brief_template.md').read_text())
    scqa = story.get('scqa') or {}
    scqa_md = ''
    if scqa:
        scqa_md = '\n## SCQA\n\n' + '\n'.join(f"- {k.capitalize()}: {scqa[k]}" for k in ('situation', 'complication', 'question', 'answer') if scqa.get(k)) + '\n'
    blocks = []
    for i, b in enumerate(story.get('summary_blocks') or [], 1):
        blocks.append(f"### Block {i}: {b.get('name', '')}")
        blocks.append('')
        if b.get('lead'):
            blocks.append(f"Lead: {b['lead']}")
            blocks.append('')
        blocks.extend(f'- {x}' for x in b.get('bullets') or [])
        blocks.append('')
    slides = [_slide_section(n, s) for n, s in enumerate(story['slides'], 1)]
    used = []
    for s in story['slides']:
        if s.get('layout') not in used:
            used.append(s.get('layout'))
    sketches = []
    for name in used:
        sketches.append(f'### {name}')
        sketches.append('')
        sketches.append('```')
        sketches.append(LAYOUT_SKETCHES.get(name, 'no sketch for this layout'))
        sketches.append('```')
        sketches.append('')
    text = template.substitute(
        title=story.get('title') or 'Deck brief',
        governing_thought=story['governing_thought'],
        scqa=scqa_md,
        summary_blocks='\n'.join(blocks),
        slides='\n'.join(slides),
        sketches='\n'.join(sketches),
        verify=VERIFY_COMMAND,
    )
    return _no_em_dash(text)


def _no_em_dash(text):
    return text.replace(' \u2014 ', ' - ').replace('\u2014', ' - ')


def render_ratecard_md(ratecard):
    lines = ['# Rate card before the rebuild', '', 'This is the diagnosis the package answers. Each FAIL here must be a PASS after the build.', '']
    rows = []
    for c in ratecard.get('checks') or []:
        ev = c.get('evidence') or []
        first = ev[0] if ev else ''
        if isinstance(first, dict):
            first = first.get('text') or first.get('title') or first.get('problem') or json.dumps(first, ensure_ascii=False)
        rows.append([c.get('id'), c.get('method'), c.get('result'), len(ev), first])
    lines.append(_md_table(['id', 'method', 'result', 'evidence count', 'first evidence'], rows))
    lines += ['', '## Defects', '']
    defects = (ratecard.get('diagnostic') or {}).get('defects') or []
    lines += [f"{d.get('rank')}. {d.get('text')}" for d in defects] or ['none']
    lines += ['', '## Questions', '']
    questions = ratecard.get('questions') or []
    lines += [f"- {q.get('q')} (default: {q.get('default')}; why: {q.get('why')})" for q in questions] or ['none']
    lines.append('')
    return _no_em_dash('\n'.join(lines))


def render_checklist():
    lines = ['# Checklist', '', 'The finished deck must pass every gate below. Run the verify command from the handoff directory.', '']
    lines.append(_md_table(['gate', 'meaning'], [[k, v] for k, v in GATES.items()]))
    lines += ['', '## Verify', '', f'    {VERIFY_COMMAND}', '', 'Exit code 0 means every gate reports PASS. Any other exit code lists the failing gates and slides.', '']
    return '\n'.join(lines)


def build_handoff(story, charts, ratecard_before, out_dir):
    """Write the handoff package for a story into out_dir and return out_dir."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'BRIEF.md').write_text(render_brief(story))
    (out / 'story.json').write_text(json.dumps(story, indent=2, ensure_ascii=False) + '\n')
    sheets = data_sheets(story)
    write_xlsx(sheets, out / 'data.xlsx')
    write_csvs(sheets, out / 'data')
    copy_charts(charts, out / 'charts')
    if ratecard_before is not None:
        (out / 'ratecard_before.json').write_text(json.dumps(ratecard_before, indent=2, ensure_ascii=False) + '\n')
        (out / 'ratecard_before.md').write_text(render_ratecard_md(ratecard_before))
    (out / 'CHECKLIST.md').write_text(render_checklist())
    return out
