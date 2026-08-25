from src.chunks import adjacent_sum


def test_adjacent_sum():
    assert adjacent_sum([1, 2, 3]) == [3, 5]


def test_adjacent_sum_single():
    assert adjacent_sum([7]) == []
