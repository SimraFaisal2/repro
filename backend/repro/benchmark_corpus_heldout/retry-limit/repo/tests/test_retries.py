from src.retries import can_retry


def test_first_attempt():
    assert can_retry(0, 3) is True


def test_at_limit():
    assert can_retry(3, 3) is False


def test_over_limit():
    assert can_retry(4, 3) is False
