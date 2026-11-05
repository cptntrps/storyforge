"""After gates: the rate card of a built deck. Scripts over story.json, the PPTX read back, and the spatial gate."""

import json
import subprocess
import tempfile
from pathlib import Path

from . import schema
from .checks import Check
from .checks.charts import check_charts
from .checks.editorial import check_editorial
from .checks.numbers import check_number_trace
from .checks.structure import check_structure
from .checks.titles import check_titles, verify_roles
from .ratecard import MEANING, ORDER, _judged

SPATIAL = Path('/repos/SlideForge/pptx-review/scripts')


def story_checks(story, rows=None):
    """Every script check that runs on story.json alone."""
    checks = {}
    for c in check_structure(story) + check_titles(story['slides']) + check_charts(story):
        if c.result == 'NA' and c.id in checks:
            continue
        checks[c.id] = c
    texts = [(s['id'], ' '.join(filter(None, [s.get('title'), s.get('subtitle'), s.get('takeaway'), s.get('callout')] + list(s.get('body') or [])))) for s in story['slides']]
    checks['R18'] = check_editorial(texts)[0]
    r09 = [{'slide': s['id'], 'title': s['title'], 'problems': p} for s in story['slides'] if (p := verify_roles(s['title'], s.get('title_roles')))]
    checks['R09'] = Check('R09', 'script', 'PASS' if not r09 else 'FAIL', r09)
    if rows is not None:
        checks['R20'] = check_number_trace(story, rows)
    else:
        checks['R20'] = Check('R20', 'script', 'NA', [{'note': 'no rows supplied'}])
    return checks


def titles_match(pptx, story):
    from .ingest.pptx import ingest_pptx
    deck = ingest_pptx(pptx)
    want = [s['title'].strip() for s in story['slides']]
    got = [s['title'].strip() for s in deck['slides']]
    ev = []
    if len(got) != len(want):
        ev.append({'problem': f'{len(got)} slides in the PPTX, {len(want)} in the story'})
    for i, (w, g) in enumerate(zip(want, got), 1):
        if w != g:
            ev.append({'slide': i, 'story': w, 'pptx': g})
    return ev


def spatial_gate(pptx, out_dir):
    if not (SPATIAL / 'analyze_pptx.py').exists():
        return Check('R22', 'script', 'NA', [{'note': f'spatial scripts not found at {SPATIAL}'}])
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    a, rep = Path(out_dir) / 'analysis.json', Path(out_dir) / 'spatial.json'
    r1 = subprocess.run(['python3', str(SPATIAL / 'analyze_pptx.py'), str(pptx), '--json', str(a)], capture_output=True, text=True)
    r2 = subprocess.run(['python3', str(SPATIAL / 'spatial_analyzer.py'), str(a), '--json', str(rep)], capture_output=True, text=True)
    if r1.returncode or r2.returncode or not rep.exists():
        return Check('R22', 'script', 'FAIL', [{'problem': 'spatial gate did not run', 'stderr': (r1.stderr + r2.stderr)[-600:]}])
    data = json.loads(rep.read_text())
    issues = []
    for key in ('violations', 'issues', 'findings'):
        if isinstance(data.get(key), list):
            issues = data[key]
            break
    if not issues and isinstance(data.get('slides'), list):
        issues = [i for s in data['slides'] for i in (s.get('violations') or s.get('issues') or [])]
    severe = [i for i in issues if str(i.get('severity', i.get('level', 'error'))).lower() in ('error', 'high', 'critical')]
    return Check('R22', 'script', 'PASS' if not severe else 'FAIL', severe[:50] or [{'note': f'{len(issues)} advisory finding(s)', 'report': str(rep)}])


def run_gates(pptx, story, rows=None, judgments=None, out_dir=None):
    schema.require_valid('story', story)
    out_dir = Path(out_dir or tempfile.mkdtemp(prefix='storyforge-gates-'))
    checks = story_checks(story, rows)
    mism = titles_match(pptx, story)
    checks['R12'] = checks.get('R12') or Check('R12', 'script', 'NA', [])
    checks['R22'] = spatial_gate(pptx, out_dir)
    if mism:
        checks['R22'] = Check('R22', 'script', 'FAIL', mism + checks['R22'].evidence)
    for cid in ('R01', 'R02', 'R04', 'R05', 'R06', 'R14', 'R15', 'R21'):
        checks[cid] = _judged(cid, judgments)
    rc = {
        'subject': str(pptx), 'stage': 'after',
        'implied_story': {'governing_thought': story['governing_thought'], 'slides': [1], 'reasons': []},
        'story_unclear': False,
        'checks': [checks[c].to_dict() for c in ORDER],
        'diagnostic': {'gap': None, 'off_path': [], 'defects': [
            {'rank': i + 1, 'text': f'{cid} {MEANING[cid]}', 'slides': [e.get('slide') for e in checks[cid].evidence if isinstance(e, dict) and 'slide' in e]}
            for i, cid in enumerate(c for c in ORDER if checks[c].result in ('FAIL', 'DISAGREE'))]},
        'questions': [],
    }
    schema.require_valid('ratecard', rc)
    return rc


def all_pass(rc):
    return all(c['result'] == 'PASS' for c in rc['checks'])
