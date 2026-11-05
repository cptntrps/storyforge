import json

import pytest

from storyforge import schema
from storyforge.ingest.gslides import ingest_gslides
from tests.conftest import DATA


@pytest.fixture
def deck():
    return ingest_gslides(json.loads((DATA / 'gslides_min.json').read_text()))


def test_schema_valid(deck):
    assert schema.validate('deck', deck) == []
    assert deck['format'] == 'gslides'
    assert [s['n'] for s in deck['slides']] == [1, 2, 3]
    assert [s['id'] for s in deck['slides']] == ['s1', 's2', 's3']


def test_titles(deck):
    assert deck['slides'][0]['title'] == 'Product A grew revenue 12% to $2,495k in Q3'
    assert deck['slides'][1]['title'] == 'Summary of unit economics'
    assert deck['slides'][2]['title'] == ''


def test_body_runs(deck):
    assert deck['slides'][0]['body'] == [
        'Company X added 5 new accounts',
        'Churn stayed at 1.6x the plan',
    ]
    assert deck['slides'][0]['notes'] == 'Mention the Q4 outlook.'
    assert deck['slides'][1]['body'] == []


def test_table_rows(deck):
    assert deck['slides'][1]['tables'] == [{'rows': [['Metric', 'Value'], ['CPO', '$119']]}]


def test_chart_type(deck):
    assert deck['slides'][1]['charts'] == [{'type': 'sheetsChart', 'title': None}]
    assert deck['slides'][0]['charts'] == []


def test_unreadable_flag(deck):
    assert deck['slides'][2].get('unreadable') is True
    assert 'unreadable' not in deck['slides'][0]
    assert 'unreadable' not in deck['slides'][1]


def test_kinds(deck):
    assert [s['kind'] for s in deck['slides']] == ['key', 'summary', 'key']


def test_numbers(deck):
    values = {(n['value'], n['unit']) for n in deck['slides'][0]['numbers']}
    assert (12.0, '%') in values
    assert (2495000.0, '$') in values
    assert (1.6, 'x') in values
    assert (119.0, '$') in {(n['value'], n['unit']) for n in deck['slides'][1]['numbers']}


def test_title_falls_back_to_first_shape():
    pres = {'slides': [{'objectId': 'x', 'pageElements': [
        {'shape': {'text': {'textElements': [{'textRun': {'content': 'Plain box\n'}}]}}},
        {'shape': {'text': {'textElements': [{'textRun': {'content': 'Second box\n'}}]}}},
    ]}]}
    slide = ingest_gslides(pres)['slides'][0]
    assert slide['title'] == 'Plain box'
    assert slide['body'] == ['Second box']
    assert slide['kind'] == 'key'
