"""JSON schema loading and validation for the storyforge contracts."""

import json
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator

SCHEMAS = Path(__file__).resolve().parent / 'schemas'
KINDS = ('deck', 'frame', 'story', 'ratecard', 'judgments')


@lru_cache(maxsize=None)
def load(kind):
    if kind not in KINDS:
        raise KeyError(f'unknown schema kind {kind!r}; choose from {KINDS}')
    return json.loads((SCHEMAS / f'{kind}.schema.json').read_text())


def validate(kind, obj):
    """Return a list of 'path: message' strings; an empty list means obj is valid."""
    v = Draft202012Validator(load(kind))
    out = []
    for e in sorted(v.iter_errors(obj), key=lambda e: list(e.absolute_path)):
        path = '/'.join(str(p) for p in e.absolute_path) or '<root>'
        out.append(f'{path}: {e.message}')
    return out


def require_valid(kind, obj):
    errs = validate(kind, obj)
    if errs:
        raise ValueError(f'invalid {kind}:\n  ' + '\n  '.join(errs))
    return obj
