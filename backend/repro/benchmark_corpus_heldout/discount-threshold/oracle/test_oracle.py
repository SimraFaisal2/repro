from src.pricing import discount


def test_just_below():
    assert discount(99.99) == 99.99


def test_just_above():
    assert discount(100.01) == 90.01


def test_zero():
    assert discount(0) == 0


def test_two_decimals():
    assert discount(123.45) == 111.11
