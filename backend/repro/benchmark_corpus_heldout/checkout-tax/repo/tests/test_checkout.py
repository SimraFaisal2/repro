from src.checkout import total


def test_standard_total():
    assert total(100) == 110.0


def test_zero_subtotal():
    assert total(0) == 0.0


def test_rounding():
    assert total(19.99) == 21.99
