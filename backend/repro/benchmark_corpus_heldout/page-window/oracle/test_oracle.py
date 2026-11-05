from src.paging import page


def test_last_page_is_partial():
    assert page(list(range(25)), 3, 10) == list(range(20, 25))


def test_page_beyond_end():
    assert page([1, 2, 3], 5, 2) == []


def test_size_one():
    assert page(["a", "b", "c"], 2, 1) == ["b"]


def test_exact_boundary():
    assert page([1, 2, 3, 4], 2, 2) == [3, 4]
