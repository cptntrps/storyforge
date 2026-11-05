import json
import os
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parent / 'data'


def fixture_path(name):
    """A reference-deck fixture from STORYFORGE_FIXTURES, or a reported SKIP."""
    root = os.environ.get('STORYFORGE_FIXTURES')
    if not root:
        pytest.skip(f'STORYFORGE_FIXTURES is unset; fixture {name} not available')
    p = Path(root) / name
    if not p.exists():
        pytest.skip(f'fixture {name} absent under {root}')
    return p


@pytest.fixture
def story_min():
    return json.loads((DATA / 'story_min.json').read_text())
