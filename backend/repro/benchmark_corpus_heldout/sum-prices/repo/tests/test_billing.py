from src.billing import total


def test_decimal_strings():
    assert total(["1.5", "2.5"]) == 4.0


def test_empty():
    assert total([]) == 0


def test_ints_and_strings():
    assert total([2, "3.5"]) == 5.5
