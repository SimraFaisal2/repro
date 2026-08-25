from src.stats import average


def test_average_empty():
    # the empty-input case used to return 0.0 — that guard must not regress
    assert average([]) == 0.0


def test_average_normal():
    assert average([1, 2, 3]) == 2.0
