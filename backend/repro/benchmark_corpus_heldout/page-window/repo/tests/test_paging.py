from src.paging import page


def test_second_page():
    assert page(list(range(25)), 2, 10) == list(range(10, 20))


def test_first_page():
    assert page([1, 2, 3, 4, 5], 1, 2) == [1, 2]


def test_empty_items():
    assert page([], 1, 5) == []
