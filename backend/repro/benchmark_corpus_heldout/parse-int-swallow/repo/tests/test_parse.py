import pytest

from src.parse import parse


def test_invalid_raises():
    with pytest.raises(ValueError):
        parse("x")


def test_valid():
    assert parse("3") == 3


def test_whitespace():
    assert parse(" 4 ") == 4
