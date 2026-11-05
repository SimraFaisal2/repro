import pytest

from src.parse import parse


def test_none_raises_type_error():
    with pytest.raises(TypeError):
        parse(None)


def test_empty_raises():
    with pytest.raises(ValueError):
        parse("")


def test_negative():
    assert parse("-7") == -7


def test_float_string_raises():
    with pytest.raises(ValueError):
        parse("3.5")
