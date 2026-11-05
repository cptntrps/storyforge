"""Title checks: R08 lexical SVOM filter, R09 role verification, R10 length, R11 shape, R13 numbers with metric and base.

These are scripts. They catch the cheap defects; the judged checks in judge/rubrics.md cover meaning.
"""

import re

from . import Check, verdict

IMPERATIVES = {
    'use', 'make', 'build', 'ensure', 'consider', 'note', 'see', 'review', 'focus', 'increase', 'reduce', 'test', 'invest',
    'approve', 'move', 'shift', 'stop', 'start', 'launch', 'scale', 'prioritize', 'prioritise', 'leverage', 'drive', 'align',
    'optimize', 'optimise', 'improve', 'accelerate', 'deliver', 'develop', 'implement', 'adopt', 'expand', 'cut', 'grow',
    'maintain', 'keep', 'fund', 'release', 'let', 'think', 'imagine', 'remember', 'avoid', 'explore', 'define', 'establish',
}
# Gerund-shaped nouns that are a fine sentence subject.
DOMAIN_NOUNS = {
    'marketing', 'spending', 'pricing', 'advertising', 'onboarding', 'funding', 'prospecting', 'retargeting', 'branding',
    'sourcing', 'manufacturing', 'staffing', 'training', 'testing', 'scaling', 'shipping', 'booking', 'billing', 'reporting',
    'planning', 'engineering', 'trading', 'lending', 'banking', 'earnings', 'holdings', 'housing', 'mining', 'streaming',
    'gaming', 'learning', 'consulting', 'operating', 'licensing', 'purchasing', 'outsourcing', 'offshoring', 'forecasting',
}
METRIC_WORDS = (
    'cpo', 'cpa', 'cac', 'roas', 'cost', 'revenue', 'orders', 'order', 'customers', 'customer', 'spend', 'share', 'growth',
    'margin', 'rate', 'target', 'profit', 'sales', 'volume', 'price', 'budget', 'headcount', 'hours', 'users', 'churn',
    'retention', 'conversion', 'traffic', 'leads', 'pipeline', 'bookings', 'ebitda', 'opex', 'capex', 'savings', 'fte',
)
BASE_MARKERS = (' of ', 'below the', 'above the', 'under the', 'over the', 'from ', ' to ', 'versus', ' vs', 'against',
                'compared', 'per ', 'out of', 'on ', 'within', 'at ')

NUM_RE = re.compile(
    r'(?P<cur>[$€£])?(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)(?P<suf>\s?(?:%|k\b|K\b|M\b|m\b|bn\b|x\b|×|pp\b|pts?\b))?',
)


def numbers_in(text):
    """Every numeric token with its unit and 40 chars of context either side."""
    out = []
    for m in NUM_RE.finditer(text or ''):
        raw = m.group('num').replace(',', '')
        try:
            value = float(raw)
        except ValueError:
            continue
        suf = (m.group('suf') or '').strip()
        cur = m.group('cur') or ''
        unit = None
        if suf in ('%', 'pp', 'pt', 'pts'):
            unit = '%' if suf == '%' else 'pp'
        elif suf in ('x', '×'):
            unit = 'x'
        else:
            # k, M, bn expand to base units so a title value compares with a data row.
            value *= {'k': 1e3, 'm': 1e6, 'bn': 1e9}.get(suf.lower(), 1)
            unit = cur or None
        a, b = max(0, m.start() - 40), min(len(text), m.end() + 40)
        out.append({'value': value, 'unit': unit, 'context': text[a:b].strip(), 'raw': text[m.start():m.end()]})
    return out


def svom_problems(title):
    """Lexical reasons a title is not one SVOM sentence. Empty list means the cheap filter passes."""
    t = (title or '').strip()
    if not t:
        return ['empty title']
    first = t.split()[0].lower().strip(',')
    probs = []
    if ':' in t or ';' in t:
        probs.append('colon or semicolon')
    if not re.search(r'\d', t):
        probs.append('no number')
    if first in IMPERATIVES:
        probs.append('starts with an imperative verb')
    if first.endswith('ing') and first not in DOMAIN_NOUNS:
        probs.append('gerund subject')
    if not t.endswith('.'):
        probs.append('not one full sentence')
    if re.search(r'\.\s+[A-Z]', t):
        probs.append('more than one sentence')
    if t.startswith('$') or t.startswith('€'):
        probs.append('an amount as the subject: SVOM needs an actor first')
    if re.search(r', (but|yet) (\w+ ){0,4}(loses|earns|adds|gains|falls|rises|rose|fell|costs|returns|drops)\b', t):
        probs.append('a second claim after ", but" or ", yet"')
    if re.search(r'\bdepend(s|ing)? on\b', t):
        probs.append('hedge clause: the title states no claim')
    if re.search(r'\b(earns?|adds?|gains?|returns?|makes?)\s+(up to\s+)?[−-]', t):
        probs.append('gain verb with a loss as its object')
    if '—' in t:
        probs.append('em dash')
    if len(t.split()) < 5:
        probs.append('too short to carry subject, verb, object and measure')
    return probs


ROLE_KEYS = ('subject', 'verb', 'object', 'measure')


def verify_roles(title, roles):
    """R09 verification of a model's role dissection: all four roles present, each an ordered substring of the title."""
    probs = []
    if not isinstance(roles, dict):
        return ['title_roles is not an object']
    for k in ROLE_KEYS:
        if not str(roles.get(k) or '').strip():
            probs.append(f'missing {k}')
    if probs:
        return probs
    pos = 0
    for k in ROLE_KEYS:
        part = roles[k].strip()
        i = title.find(part, pos)
        if i < 0:
            probs.append(f'{k} {part!r} is not found after position {pos} in the title')
            break
        pos = i + len(part)
    s = roles['subject'].strip()
    if s.startswith('$') or s.startswith('€'):
        probs.append('subject is an amount; SVOM needs an actor')
    if not re.search(r'\d', roles['measure']) and not re.search(r'\d', roles['object']):
        probs.append('neither object nor measure carries a number')
    return probs


def number_problems(title):
    """R13: every percentage names a base; every amount sits next to a metric word."""
    low = (title or '').lower()
    probs = []
    has_metric = any(re.search(rf'\b{w}\b', low) for w in METRIC_WORDS)
    for n in numbers_in(title or ''):
        if n['unit'] == '%':
            after = low[low.find(n['raw'].lower()) + len(n['raw']):]
            window = after[:60]
            if not any(mk in window or mk in low for mk in BASE_MARKERS):
                probs.append(f"{n['raw']}: a share without its base")
        elif n['unit'] and n['unit'].startswith(('$', '€', '£')):
            if not has_metric:
                probs.append(f"{n['raw']}: an amount with no metric named")
    return probs


def check_titles(slides, chars_per_line=70):
    """R08, R10, R11, R13 over slides with 'title' (and 'n' or 'id')."""
    r08, r10, r11, r13 = [], [], [], []
    for s in slides:
        t, ref = s.get('title') or '', s.get('id') or s.get('n')
        p = svom_problems(t)
        if p:
            r08.append({'slide': ref, 'title': t, 'problems': p})
        if len(t) > 2 * chars_per_line:
            r10.append({'slide': ref, 'title': t, 'chars': len(t), 'max': 2 * chars_per_line})
        shape = [x for x in p if x in ('colon or semicolon', 'more than one sentence')]
        if shape:
            r11.append({'slide': ref, 'title': t, 'problems': shape})
        q = number_problems(t)
        if q:
            r13.append({'slide': ref, 'title': t, 'problems': q})
    return [verdict('R08', r08), verdict('R10', r10), verdict('R11', r11), verdict('R13', r13)]
