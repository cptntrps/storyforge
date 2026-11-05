import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'tests' / 'data'


def run(*args):
    return subprocess.run([sys.executable, '-m', 'storyforge', *args], cwd=ROOT, capture_output=True, text=True)


def test_ingest_then_ratecard(tmp_path):
    r = run('ingest', str(DATA / 'mini_deck.html'), '-o', str(tmp_path / 'deck.json'))
    assert r.returncode == 0, r.stderr
    r = run('ratecard', str(tmp_path / 'deck.json'), '-o', str(tmp_path / 'rc.json'))
    assert r.returncode == 0, r.stderr
    md = (tmp_path / 'rc.md').read_text()
    assert '| R08 |' in md and '## Questions' in md
    rc = json.loads((tmp_path / 'rc.json').read_text())
    assert len(rc['checks']) == 22


def test_validate_invalid_story_exits_1(tmp_path):
    bad = json.loads((DATA / 'story_min.json').read_text())
    del bad['slides'][0]['title_roles']
    p = tmp_path / 'bad.json'
    p.write_text(json.dumps(bad))
    r = run('validate', str(p))
    assert r.returncode == 1 and 'title_roles' in r.stderr


def test_validate_story_min_with_rows():
    r = run('validate', str(DATA / 'story_min.json'), '--rows', str(DATA / 'rows.csv'))
    assert r.returncode == 0, r.stdout + r.stderr
    assert 'R20 PASS' in r.stdout
