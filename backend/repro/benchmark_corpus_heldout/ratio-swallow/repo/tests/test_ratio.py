import pytest

from src.ratio import ratio


def test_zero_denominator_raises():
    with pytest.raises(ZeroDivisionError):
        ratio(1, 0)


def test_normal_division():
    assert ratio(6, 3) == 2


def test_float_division():
    assert ratio(1, 4) == 0.25
