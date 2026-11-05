import json
import re
from pathlib import Path

import pytest

from storyforge import assets

ROOT = Path(__file__).resolve().parents[1]


def test_every_asset_loads():
    for name in assets.NAMES:
        assert assets.load(name)


def test_no_forbidden_words_in_assets():
    words = ROOT / 'tests' / 'forbidden_words.txt'
    if not words.exists():
        pytest.skip('tests/forbidden_words.txt absent (local file); forbidden-word check not run')
    pat = re.compile('|'.join(re.escape(w) for w in words.read_text().split('\n') if w.strip()), re.I)
    for f in (ROOT / 'storyforge' / 'assets').glob('*.json'):
        hits = pat.findall(f.read_text())
        assert not hits, f'{f.name}: {sorted(set(hits))}'


def test_no_em_dash_in_assets():
    for f in (ROOT / 'storyforge' / 'assets').glob('*.json'):
        assert '—' not in f.read_text(), f.name


def test_mbb_title_parts_are_ordered_substrings():
    for t in assets.load('mbb_titles'):
        pos = 0
        for p in t['parts']:
            k = t['title'].find(p['text'], pos)
            assert k >= 0, (t['title'], p['text'])
            pos = k + len(p['text'])


def test_mbb_titles_count_and_firms():
    t = assets.load('mbb_titles')
    assert len(t) >= 15
    assert {'McKinsey', 'BCG'} <= {x['firm'] for x in t}


def test_summary_blocks_order():
    b = assets.load('summary_blocks')
    assert [x['name'] for x in b] == ['goals', 'period_result', 'what_we_see', 'what_we_propose', 'what_we_need_today']
    assert [x['order'] for x in b] == [1, 2, 3, 4, 5]


def test_owner_rules_dated():
    for r in assets.load('owner_rules'):
        assert re.fullmatch(r'\d{4}-\d{2}-\d{2}', r['date']) and r['applies_to'] and r['rule'].endswith('.')
