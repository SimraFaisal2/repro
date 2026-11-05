from src.pairs import pair_sums


def test_pairs():
    assert pair_sums([1, 2, 3]) == [3, 5]


def test_empty():
    assert pair_sums([]) == []
