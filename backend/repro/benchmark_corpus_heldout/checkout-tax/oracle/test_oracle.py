from src.checkout import total


def test_large_subtotal():
    assert total(1000) == 1100.0


def test_small_subtotal():
    assert total(0.1) == 0.11


def test_decimal_rounding():
    assert total(12.34) == 13.57


def test_negative_subtotal():
    assert total(-10) == -11.0
