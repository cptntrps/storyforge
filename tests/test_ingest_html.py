from pathlib import Path

from storyforge.ingest.html import ingest_html
from storyforge.schema import validate
from tests.conftest import DATA, fixture_path


def test_mini_deck():
    deck = ingest_html(DATA / 'mini_deck.html')
    assert validate('deck', deck) == []
    assert deck['format'] == 'html'
    slides = deck['slides']
    assert [s['id'] for s in slides] == ['s1', 's2', 's3']
    assert [s['n'] for s in slides] == [1, 2, 3]
    assert [s['title'] for s in slides] == [
        'Product A cut June cost per order to $119, so Company X met its $125 target.',
        'Detail: cost per order by product',
        'Cost per order fell 5% in June.',
    ]
    assert [s['kind'] for s in slides] == ['key', 'detail', 'key']

    s1, s2, s3 = slides
    assert s1['subtitle'] == 'Without Product A, June cost per order was $192.'
    assert s1['body'] == [
        'New customers rose from 2,495 to 5,425 a month, April to June.',
        'Spend held at $270k a week, 1.6x the April level.',
    ]
    values = {(n['value'], n['unit']) for n in s1['numbers']}
    assert {(119.0, '$'), (125.0, '$'), (2495.0, None), (5425.0, None), (1.6, 'x')} <= values
    # $270k: the tokenizer owns the scale convention (270000 '$' or 270 '$k'); either names a dollar token.
    assert any(n['value'] in (270.0, 270000.0) and n['unit'] in ('$', '$k') for n in s1['numbers'])
    assert all(n['context'] for n in s1['numbers'])

    assert s2['tables'] == [{'rows': [['Product', 'CPO'], ['A', '$119']]}]
    assert s2['body'] == ['Source: ad platform export, April to June.']

    assert s3['charts'] == [{'type': 'svg', 'title': 'Cost per order by month'}]
    assert s3['body'] == ['June held the target.', 'May did not.']
    assert s3['notes'] == 'Speaker note for s3.'
    assert {(5.0, '%')} <= {(n['value'], n['unit']) for n in s3['numbers']}
    assert all(s['unreadable'] is False for s in slides)


def test_deck_a_fixture():
    deck = ingest_html(fixture_path('deck_a.html'))
    assert validate('deck', deck) == []
    kinds = [s['kind'] for s in deck['slides']]
    # The first section is the executive summary (3+ lists after render), so the
    # nine storyline slides read as one summary plus eight key slides.
    assert kinds[0] == 'summary'
    assert kinds.count('key') >= 8
    assert kinds.count('key') + kinds.count('summary') >= 9
    assert 'detail' in kinds
    assert 'appendix' in kinds
    assert all(s['charts'] or s['tables'] or s['body'] for s in deck['slides'])
    assert all(s['title'] for s in deck['slides'] if s['kind'] == 'key')
