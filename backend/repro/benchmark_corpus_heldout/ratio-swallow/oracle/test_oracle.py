import pytest

from src.ratio import ratio


def test_negative_numerator():
    assert ratio(-6, 3) == -2


def test_negative_denominator():
    assert ratio(6, -3) == -2


def test_zero_numerator():
    assert ratio(0, 5) == 0


def test_zero_over_zero_raises():
    with pytest.raises(ZeroDivisionError):
        ratio(0, 0)
