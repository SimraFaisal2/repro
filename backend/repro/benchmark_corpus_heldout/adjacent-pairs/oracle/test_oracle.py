from src.pairs import pair_sums


def test_single():
    assert pair_sums([7]) == []


def test_negative_values():
    assert pair_sums([-2, 2, 5]) == [0, 7]


def test_longer_run():
    assert pair_sums([1, 2, 3, 4, 5, 6]) == [3, 5, 7, 9, 11]


def test_strings_are_not_special_cased():
    assert pair_sums(["a", "b", "c"]) == ["ab", "bc"]
