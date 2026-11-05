import pytest

from src.chunks import chunks


def test_pairs():
    assert chunks([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]


def test_size_one():
    assert chunks(["a", "b"], 1) == [["a"], ["b"]]


def test_empty():
    assert chunks([], 3) == []


def test_invalid_size():
    with pytest.raises(ValueError):
        chunks([1], 0)
