from src.windows import max_windows


def test_width_one():
    assert max_windows([4, 1, 7], 1) == [4, 1, 7]


def test_width_equals_length():
    assert max_windows([4, 1, 7], 3) == [7]


def test_width_larger_than_input():
    assert max_windows([4, 1], 3) == []


def test_negative_values():
    assert max_windows([-5, -2, -9, -1], 2) == [-2, -2, -1]
