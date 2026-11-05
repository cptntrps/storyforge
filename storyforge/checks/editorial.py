"""R18: editorial contract. Banned filler, relative comparisons that omit the benchmark value, em dashes."""

import re

from .. import assets
from . import verdict

REL_RE = re.compile(r'\b\d+(?:\.\d+)?%\s+(?:below|above|under|over|short of|ahead of|behind)\s+(?!the\s+\$?\d|\$?\d|its\s+\$?\d)(\w+)', re.I)


def editorial_problems(text):
    ed = assets.load('editorial_standard')
    low = (text or '').lower()
    probs = [f'filler phrase: {p!r}' for p in ed.get('avoid_phrases', []) if p.lower() in low]
    for m in REL_RE.finditer(text or ''):
        probs.append(f'relative comparison without the benchmark value: {m.group(0)!r}')
    if '—' in (text or ''):
        probs.append('em dash')
    return probs


def check_editorial(texts):
    """texts: iterable of (ref, text). One R18 Check with evidence per offending text."""
    fails = []
    for ref, text in texts:
        p = editorial_problems(text)
        if p:
            fails.append({'slide': ref, 'text': text, 'problems': p})
    return [verdict('R18', fails)]
