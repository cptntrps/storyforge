import copy
import os
from pathlib import Path

import pytest

from storyforge.checks.numbers import check_number_trace, load_rows, resolve

ROWS = Path(__file__).resolve().parent / 'data' / 'rows.csv'


def test_resolve_value_sum_share():
    rows = load_rows(ROWS)
    assert resolve({'where': {'period': '2025-06', 'sku': 'Product A'}, 'column': 'orders', 'agg': 'value'}, rows)[0] == 4055
    assert resolve({'where': {'period': '2025-06', 'sku': 'Product A'}, 'column': 'orders', 'agg': 'share', 'of': {'period': '2025-06', 'sku': ''}}, rows)[0] == pytest.approx(74.75, abs=0.01)
    got, why = resolve({'where': {'period': '2099-01'}, 'column': 'orders'}, rows)
    assert got is None and 'no row' in why


def test_story_min_traces_with_fixture_rows(story_min):
    rows = load_rows(ROWS)
    c = check_number_trace(story_min, rows)
    assert c.result == 'PASS', c.evidence


def test_missing_trace_fails(story_min):
    s = copy.deepcopy(story_min)
    s['slides'][1]['numbers'][0]['trace'] = None
    c = check_number_trace(s, load_rows(ROWS))
    assert c.result == 'FAIL' and c.evidence[0]['slide'] == 'q2_result' and c.evidence[0]['value'] == 119


def test_two_percent_off_fails(story_min):
    s = copy.deepcopy(story_min)
    s['slides'][1]['numbers'][0]['value'] = 121.4
    c = check_number_trace(s, load_rows(ROWS))
    assert c.result == 'FAIL' and c.evidence[0]['problem'] == 'traced value differs'


def test_pg_source_opt_in():
    if os.environ.get('STORYFORGE_PG') != '1':
        pytest.skip('STORYFORGE_PG!=1; Postgres row source not exercised')
    rows = load_rows('pg://information_schema.schemata')
    assert rows and 'schema_name' in rows[0]
