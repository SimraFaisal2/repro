from src.chunks import chunks


def test_exact_division():
    assert chunks([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]


def test_last_chunk_is_partial():
    assert chunks([1, 2, 3, 4, 5], 3) == [[1, 2, 3], [4, 5]]


def test_larger_than_input():
    assert chunks([1, 2], 10) == [[1, 2]]


def test_strings():
    assert chunks("abcdef", 4) == ["abcd", "ef"]
