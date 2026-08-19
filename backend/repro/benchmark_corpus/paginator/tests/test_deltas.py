from src.deltas import adjacent_deltas


def test_adjacent_deltas():
    assert adjacent_deltas([10, 12, 17]) == [2, 5]


def test_adjacent_deltas_longer():
    assert adjacent_deltas([1, 4, 9, 16]) == [3, 5, 7]
