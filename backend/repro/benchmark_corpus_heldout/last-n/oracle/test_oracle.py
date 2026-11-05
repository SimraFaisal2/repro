from src.tail import last_n


def test_n_one():
    assert last_n([1, 2, 3], 1) == [3]


def test_n_equals_length():
    assert last_n([1, 2, 3], 3) == [1, 2, 3]


def test_empty_input():
    assert last_n([], 4) == []


def test_string_input_returns_string():
    assert last_n("abcd", 2) == "cd"
