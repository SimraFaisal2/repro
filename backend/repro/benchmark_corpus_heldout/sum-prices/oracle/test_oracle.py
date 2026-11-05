from src.billing import total


def test_zero_string():
    assert total(["0"]) == 0.0


def test_negative():
    assert total([-1.5, "0.5"]) == -1.0


def test_whitespace():
    assert total([" 2 ", 3]) == 5.0


def test_single_value():
    assert total(["7.25"]) == 7.25
