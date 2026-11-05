from src.tail import last_n


def test_last_two():
    assert last_n([1, 2, 3, 4, 5], 2) == [4, 5]


def test_n_larger_than_input():
    assert last_n([1, 2, 3], 10) == [1, 2, 3]


def test_zero():
    assert last_n([1, 2, 3], 0) == []
