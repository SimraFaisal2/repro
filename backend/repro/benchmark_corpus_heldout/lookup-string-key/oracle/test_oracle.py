import pytest

from src.lookup import lookup


def test_string_key_for_string_dict():
    assert lookup({"a": 1}, "a") == 1


def test_non_numeric_key():
    with pytest.raises(KeyError):
        lookup({1: "a"}, "name")


def test_none_key():
    with pytest.raises(KeyError):
        lookup({1: "a"}, None)


def test_zero_key():
    assert lookup({0: "zero"}, "0") == "zero"
