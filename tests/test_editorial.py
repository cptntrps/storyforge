from storyforge.checks.editorial import check_editorial, editorial_problems


def test_filler_fails():
    assert any('filler' in p for p in editorial_problems('We cut cost in order to grow.'))


def test_benchmark_must_be_named():
    assert any('benchmark' in p for p in editorial_problems('June cost per order is 5% below target.'))
    assert editorial_problems('June cost per order reached $119, 5% below the $125 target.') == []


def test_em_dash_fails():
    assert 'em dash' in editorial_problems('Growth — the real story.')


def test_check_shape():
    c = check_editorial([('s1', 'Therefore, growth.'), ('s2', 'Growth rose 5% above the $125 target.')])
    assert c[0].id == 'R18' and c[0].result == 'FAIL' and c[0].evidence[0]['slide'] == 's1' and len(c[0].evidence) == 1
