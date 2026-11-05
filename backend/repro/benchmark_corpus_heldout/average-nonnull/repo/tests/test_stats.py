from src.stats import average


def test_ignores_null():
    assert average([1, None, 3]) == 2.0


def test_empty():
    assert average([]) == 0.0


def test_plain_values():
    assert average([2, 4]) == 3.0
