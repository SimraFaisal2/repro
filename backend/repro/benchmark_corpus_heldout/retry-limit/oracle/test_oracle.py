from src.retries import can_retry


def test_zero_limit():
    assert can_retry(0, 0) is False


def test_negative_limit():
    assert can_retry(0, -1) is False


def test_one_below():
    assert can_retry(2, 3) is True


def test_returns_bool():
    assert can_retry(0, 1) is True
