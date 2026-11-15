from src.eval_harness import results_match


def test_identical_results_match():
    rows = [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]
    assert results_match(rows, [dict(r) for r in rows])


def test_order_insensitive():
    a = [{"n": 1}, {"n": 2}]
    b = [{"n": 2}, {"n": 1}]
    assert results_match(a, b)


def test_float_noise_tolerated():
    a = [{"rev": 100.00001}]
    b = [{"rev": 100.00002}]
    assert results_match(a, b)


def test_different_results_fail():
    assert not results_match([{"n": 1}], [{"n": 2}])


def test_different_row_counts_fail():
    assert not results_match([{"n": 1}, {"n": 2}], [{"n": 1}])
