"""R20: every number in a story traces to a data row.

A trace is {where: {col: value, ...}, column, agg, of?: {col: value}}. The rows come from a CSV, a JSON list,
or Postgres through pg-exec (pg://schema.table). Nothing is invented: a number with no trace, or whose
traced value differs beyond the tolerance, fails.
"""

import csv
import json
import subprocess
from pathlib import Path

from . import Check

PG_EXEC = Path.home() / 'src/infrastructure/bin/pg-exec'


def load_rows(source):
    src = str(source)
    if src.startswith('pg://'):
        table = src[5:]
        if not all(ch.isalnum() or ch in '._' for ch in table):
            raise ValueError(f'bad table name {table!r}')
        out = subprocess.run([str(PG_EXEC), '-At', '-c', f'select row_to_json(t) from {table} t'], capture_output=True, text=True, check=True)
        return [json.loads(line) for line in out.stdout.splitlines() if line.strip()]
    p = Path(src)
    if p.suffix.lower() == '.json':
        data = json.loads(p.read_text())
        return data if isinstance(data, list) else data['rows']
    with p.open(newline='') as f:
        return [dict(r) for r in csv.DictReader(f)]


def _num(v):
    if v is None or v == '':
        return None
    try:
        return float(str(v).replace(',', '').replace('$', '').replace('%', ''))
    except ValueError:
        return None


def _match(row, where):
    return all(str(row.get(k)) == str(v) for k, v in (where or {}).items())


def resolve(trace, rows):
    """The traced value, or None with a reason."""
    if not trace or 'column' not in trace:
        return None, 'no trace'
    col, agg = trace['column'], trace.get('agg', 'value')
    sel = [r for r in rows if _match(r, trace.get('where'))]
    vals = [x for x in (_num(r.get(col)) for r in sel) if x is not None]
    if not vals:
        return None, f'no row matches {trace.get("where")} with a numeric {col}'
    if agg == 'value':
        if len(vals) != 1:
            return None, f'{len(vals)} rows match {trace.get("where")}; value needs one'
        return vals[0], None
    if agg == 'sum':
        return sum(vals), None
    if agg == 'mean':
        return sum(vals) / len(vals), None
    if agg == 'count':
        return float(len(sel)), None
    if agg in ('share', 'ratio'):
        base = [x for x in (_num(r.get(col)) for r in rows if _match(r, trace.get('of'))) if x is not None]
        if not base or sum(base) == 0:
            return None, f'no base rows for {trace.get("of")}'
        v = sum(vals) / sum(base)
        return (v * 100 if agg == 'share' else v), None
    if agg == 'delta':
        base = [x for x in (_num(r.get(col)) for r in rows if _match(r, trace.get('of'))) if x is not None]
        if len(base) != 1 or len(vals) != 1:
            return None, 'delta needs one row on each side'
        return vals[0] - base[0], None
    return None, f'unknown agg {agg!r}'


def check_number_trace(story, rows, tolerance=0.005):
    fails = []
    for s in story['slides']:
        for n in s.get('numbers', []):
            got, why = resolve(n.get('trace'), rows)
            if got is not None and (n.get('trace') or {}).get('abs'):
                got = abs(got)
            if got is None:
                fails.append({'slide': s['id'], 'value': n['value'], 'metric': n['metric'], 'problem': why})
                continue
            want = float(n['value'])
            # Accept a rounded title value: compare at the title's precision, then the tolerance.
            if abs(got - want) > max(abs(want) * tolerance, 0.5 if float(want).is_integer() else 0.005):
                fails.append({'slide': s['id'], 'value': want, 'traced': round(got, 4), 'metric': n['metric'], 'problem': 'traced value differs'})
    return Check('R20', 'script', 'PASS' if not fails else 'FAIL', fails)
