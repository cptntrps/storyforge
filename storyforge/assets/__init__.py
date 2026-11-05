"""Rubric assets: harvested, sanitised JSON. Load by name without the extension."""

import json
from functools import lru_cache
from pathlib import Path

ASSETS = Path(__file__).resolve().parent
NAMES = ('mbb_titles', 'element_definitions', 'editorial_standard', 'owner_rules', 'summary_blocks')


@lru_cache(maxsize=None)
def load(name):
    if name not in NAMES:
        raise KeyError(f'unknown asset {name!r}; choose from {NAMES}')
    return json.loads((ASSETS / f'{name}.json').read_text())
