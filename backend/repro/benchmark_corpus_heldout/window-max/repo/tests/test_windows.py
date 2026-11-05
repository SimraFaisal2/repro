import pytest

from src.windows import max_windows


def test_width_two():
    assert max_windows([1, 3, 2, 5], 2) == [3, 3, 5]


def test_empty():
    assert max_windows([], 1) == []


def test_invalid_width():
    with pytest.raises(ValueError):
        max_windows([1], 0)
