import copy
import shutil
from pathlib import Path

import pytest
from pptx import Presentation

from storyforge.checks.numbers import load_rows
from storyforge.gates import all_pass, run_gates, story_checks
from storyforge.render.deckcraft import render_pptx

ROWS = load_rows(Path(__file__).resolve().parent / 'data' / 'rows.csv')


def need_deckcraft():
    if not shutil.which('deckcraft-cli'):
        pytest.skip('deckcraft-cli not on PATH')


def test_story_checks_pass_on_story_min(story_min):
    checks = story_checks(story_min, ROWS)
    bad = {k: v.evidence for k, v in checks.items() if v.result not in ('PASS', 'NA')}
    assert bad == {}, bad
    assert checks['R09'].result == 'PASS' and checks['R20'].result == 'PASS'


def test_role_mismatch_fails_r09(story_min):
    s = copy.deepcopy(story_min)
    s['slides'][1]['title_roles']['subject'] = 'Company Y'
    assert story_checks(s)['R09'].result == 'FAIL'


def test_gates_on_rendered_deck(story_min, tmp_path):
    need_deckcraft()
    pptx = render_pptx(story_min, {}, tmp_path / 'out')
    rc = run_gates(pptx, story_min, ROWS, judgments=None, out_dir=tmp_path / 'gates')
    by = {c['id']: c for c in rc['checks']}
    scripts = {k: v['result'] for k, v in by.items() if v['method'] == 'script'}
    assert all(r in ('PASS', 'NA') for r in scripts.values()), {k: by[k]['evidence'][:2] for k, r in scripts.items() if r not in ('PASS', 'NA')}
    assert rc['stage'] == 'after' and not all_pass(rc)  # judged checks are NA without judgments


def test_edited_title_fails_with_slide_number(story_min, tmp_path):
    need_deckcraft()
    pptx = render_pptx(story_min, {}, tmp_path / 'out')
    prs = Presentation(str(pptx))
    prs.slides[1].shapes.title.text_frame.text = 'Edited title 1.'
    edited = tmp_path / 'edited.pptx'
    prs.save(str(edited))
    rc = run_gates(edited, story_min, ROWS, out_dir=tmp_path / 'gates')
    r22 = next(c for c in rc['checks'] if c['id'] == 'R22')
    assert r22['result'] == 'FAIL' and r22['evidence'][0]['slide'] == 2
