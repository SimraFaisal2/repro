from src.windows import sliding_pairs


def test_empty():
    assert sliding_pairs([]) == []


def test_pairs():
    assert sliding_pairs([1, 2, 3]) == [(1, 2), (2, 3)]


def test_longer():
    assert sliding_pairs([1, 2, 3, 4, 5]) == [(1, 2), (2, 3), (3, 4), (4, 5)]
