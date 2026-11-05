import copy

import pytest

from storyforge import schema
from storyforge.checks import Check
from tests.conftest import fixture_path


def test_story_min_is_valid(story_min):
    assert schema.validate('story', story_min) == []


def test_slide_without_roles_fails_with_path(story_min):
    bad = copy.deepcopy(story_min)
    del bad['slides'][1]['title_roles']
    errs = schema.validate('story', bad)
    assert errs and errs[0].startswith('slides/1:')
    assert 'title_roles' in errs[0]


def test_summary_needs_five_blocks(story_min):
    bad = copy.deepcopy(story_min)
    bad['summary_blocks'] = bad['summary_blocks'][:4]
    assert any(e.startswith('summary_blocks:') for e in schema.validate('story', bad))


def test_unknown_kind():
    with pytest.raises(KeyError):
        schema.validate('nope', {})


def test_ratecard_question_cap():
    rc = {'checks': [], 'diagnostic': {}, 'questions': [{'q': 'a', 'default': 'b', 'why': 'c'}] * 6}
    assert any('questions' in e for e in schema.validate('ratecard', rc))


def test_judgments_pattern():
    assert schema.validate('judgments', {'R04': {'pass_a': 'PASS', 'pass_b': 'FAIL'}}) == []
    assert schema.validate('judgments', {'R04': {'pass_a': 'MAYBE', 'pass_b': 'FAIL'}}) != []


def test_check_rejects_bad_result():
    with pytest.raises(ValueError):
        Check('R01', 'script', 'OK')


def test_fixture_skips_when_unset(monkeypatch):
    monkeypatch.delenv('STORYFORGE_FIXTURES', raising=False)
    with pytest.raises(pytest.skip.Exception):
        fixture_path('deck_a.html')
