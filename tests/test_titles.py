from storyforge import assets
from storyforge.checks.titles import check_titles, number_problems, numbers_in, svom_problems, verify_roles

GOOD = 'Winners implement all five strategies to multiply growth by 2×.'


def test_caption_fails():
    p = svom_problems('Sales outlook')
    assert 'no number' in p and 'not one full sentence' in p


def test_colon_fails():
    assert 'colon or semicolon' in svom_problems('Revenue: up 12%.')


def test_mbb_title_passes():
    assert svom_problems(GOOD) == []


def test_imperative_and_gerund():
    assert 'starts with an imperative verb' in svom_problems('Focus on 3 products to cut cost 10%.')
    assert 'gerund subject' in svom_problems('Growing 3 products cuts cost 10%.')
    assert 'gerund subject' not in svom_problems('Marketing spend of $3M cut cost per order 10% to $119.')


def test_r10_length():
    long = 'Company X ' * 16 + 'grew 1%.'
    c = {x.id: x for x in check_titles([{'id': 'a', 'title': long}], chars_per_line=70)}
    assert c['R10'].result == 'FAIL' and c['R10'].evidence[0]['chars'] > 140


def test_r11_shape():
    c = {x.id: x for x in check_titles([{'id': 'a', 'title': 'Costs fell 10%. Orders rose 5%.'}])}
    assert c['R11'].result == 'FAIL'
    c = {x.id: x for x in check_titles([{'id': 'a', 'title': GOOD}])}
    assert c['R11'].result == 'PASS' and c['R08'].result == 'PASS'


def test_r13_share_needs_base():
    assert number_problems('CPO fell 34%.')
    assert number_problems('June CPO fell to $119, 5% below the $125 target.') == []
    assert number_problems('Product A took 55% of orders on 28% of spend.') == []


def test_r13_amount_needs_metric():
    assert number_problems('Company X reached $119 in June.')
    assert number_problems('Company X cut cost per order to $119 in June.') == []


def test_numbers_in_units():
    n = numbers_in('Spending $270k a week adds 227 customers at 1.6x, 5% of spend, 2,495 in April.')
    got = [(x['value'], x['unit']) for x in n]
    assert (270000.0, '$') in got and (227.0, None) in got and (1.6, 'x') in got and (5.0, '%') in got and (2495.0, None) in got


def test_verify_roles_order_and_missing():
    t = 'Product A cut June cost per order to $119, so Company X met its $125 target.'
    ok = {'subject': 'Product A', 'verb': 'cut', 'object': 'June cost per order', 'measure': 'to $119, so Company X met its $125 target'}
    assert verify_roles(t, ok) == []
    bad = dict(ok, subject='Company X')
    assert any('not found' in p for p in verify_roles(t, bad))
    assert 'missing measure' in verify_roles(t, dict(ok, measure=''))
    assert any('amount' in p for p in verify_roles('$119 is the June cost per order of Company X.', {'subject': '$119', 'verb': 'is', 'object': 'the June cost per order', 'measure': 'of Company X.'}))


def test_mbb_corpus_roles_verify():
    """Map the corpus parts onto the four roles: first part subject, second verb, the rest split object and measure."""
    for t in assets.load('mbb_titles'):
        parts = [p['text'] for p in t['parts']]
        if len(parts) < 3:
            continue
        roles = {'subject': parts[0], 'verb': parts[1], 'object': parts[2], 'measure': ' '.join(parts[3:]) or parts[2]}
        probs = [p for p in verify_roles(t['title'], roles) if not p.startswith('neither')]
        assert probs == [] or probs == [f"measure {roles['measure']!r} is not found after position {len(t['title'])} in the title"] or len(parts) == 3, (t['title'], probs)
