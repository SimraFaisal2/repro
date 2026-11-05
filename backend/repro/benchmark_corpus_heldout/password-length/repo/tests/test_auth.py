from src.auth import valid_password


def test_exact_minimum():
    assert valid_password("12345678") is True


def test_longer():
    assert valid_password("123456789") is True


def test_too_short():
    assert valid_password("1234567") is False
