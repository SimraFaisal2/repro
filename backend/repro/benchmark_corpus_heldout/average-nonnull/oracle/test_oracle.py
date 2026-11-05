from src.stats import average


def test_all_null():
    assert average([None, None]) == 0.0


def test_single_value():
    assert average([7]) == 7.0


def test_zero_is_not_null():
    assert average([0, None, 2]) == 1.0


def test_negative_values():
    assert average([-2, None, -4]) == -3.0
