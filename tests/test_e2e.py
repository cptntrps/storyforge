"""End to end on the local reference decks (STORYFORGE_FIXTURES) and on story_min. Every step runs through the CLI."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import fixture_path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'tests' / 'data'


def run(*args, check=True):
    r = subprocess.run([sys.executable, '-m', 'storyforge', *args], cwd=ROOT, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise AssertionError(f'{args}\n{r.stdout}\n{r.stderr}')
    return r


def checks_of(path):
    return {c['id']: c for c in json.loads(Path(path).read_text())['checks']}


def test_deck_a_ratecard_flags_titles(tmp_path):
    deck = fixture_path('deck_a.html')
    run('ingest', str(deck), '-o', str(tmp_path / 'deck.json'))
    run('ratecard', str(tmp_path / 'deck.json'), '-o', str(tmp_path / 'rc.json'))
    c = checks_of(tmp_path / 'rc.json')
    assert c['R08']['result'] == 'FAIL' and len(c['R08']['evidence']) >= 9
    assert c['R11']['result'] == 'FAIL'
    rc = json.loads((tmp_path / 'rc.json').read_text())
    assert len(rc['questions']) == 5 and all(q['default'] for q in rc['questions'])
    d = json.loads((tmp_path / 'deck.json').read_text())
    assert sum(len(s.get('charts', [])) for s in d['slides']) >= 20, 'the ingester must read the multi-chart slides'


def test_deck_b_ratecard_runs_and_flags_goals_block(tmp_path):
    deck = fixture_path('deck_b.pptx')
    run('ingest', str(deck), '-o', str(tmp_path / 'deck.json'))
    run('ratecard', str(tmp_path / 'deck.json'), '-o', str(tmp_path / 'rc.json'))
    rc = json.loads((tmp_path / 'rc.json').read_text())
    assert any('goals block' in x['text'] for x in rc['diagnostic']['defects'])
    assert rc['questions']


def test_story_min_builds_gates_and_hands_off(tmp_path):
    if not shutil.which('deckcraft-cli') or not shutil.which('node'):
        pytest.skip('deckcraft-cli or node missing')
    story = DATA / 'story_min.json'
    run('validate', str(story), '--rows', str(DATA / 'rows.csv'))
    run('charts', str(story), '-o', str(tmp_path / 'charts'))
    run('build', str(story), '--charts', str(tmp_path / 'charts'), '-o', str(tmp_path / 'out'), '--html')
    r = run('gates', str(tmp_path / 'out' / 'deck.pptx'), '--story', str(story), '--rows', str(DATA / 'rows.csv'), '-o', str(tmp_path / 'gates'), check=False)
    c = checks_of(tmp_path / 'gates' / 'ratecard_after.json')
    scripts = {k: v['result'] for k, v in c.items() if v['method'] == 'script'}
    assert all(v in ('PASS', 'NA') for v in scripts.values()), {k: c[k]['evidence'][:2] for k, v in scripts.items() if v not in ('PASS', 'NA')}
    assert r.returncode == 1 and 'NOT all PASS' in r.stdout, 'judged checks are NA without judgments, so the deck is not MBB-ready'
    run('handoff', str(story), '--charts', str(tmp_path / 'charts'), '-o', str(tmp_path / 'handoff'))
    for name in ('BRIEF.md', 'story.json', 'data.xlsx', 'CHECKLIST.md', 'charts', 'data'):
        assert (tmp_path / 'handoff' / name).exists(), name
    pngs = sorted((tmp_path / 'out' / 'png').glob('*.png'))
    assert len(pngs) == len(json.loads(story.read_text())['slides'])
