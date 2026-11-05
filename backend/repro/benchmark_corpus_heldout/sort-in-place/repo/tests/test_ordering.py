from src.ordering import ordered


def test_sorts():
    assert ordered([3, 1, 2]) == [1, 2, 3]


def test_does_not_mutate():
    values = [3, 1, 2]
    ordered(values)
    assert values == [3, 1, 2]


def test_empty():
    assert ordered([]) == []
