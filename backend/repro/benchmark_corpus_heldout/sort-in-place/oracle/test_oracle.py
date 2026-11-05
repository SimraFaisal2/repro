from src.ordering import ordered


def test_duplicates():
    assert ordered([2, 1, 2]) == [1, 2, 2]


def test_already_sorted():
    assert ordered([1, 2, 3]) == [1, 2, 3]


def test_negative_numbers():
    assert ordered([0, -3, 2]) == [-3, 0, 2]


def test_tuple_input():
    assert ordered((3, 1, 2)) == [1, 2, 3]
