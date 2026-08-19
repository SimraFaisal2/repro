from src.pairs import consecutive_pairs


def test_consecutive_pairs():
    assert consecutive_pairs([1, 2, 3]) == [(1, 2), (2, 3)]


def test_consecutive_pairs_longer():
    assert consecutive_pairs([1, 2, 3, 4, 5]) == [(1, 2), (2, 3), (3, 4), (4, 5)]
