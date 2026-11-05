import pytest

from src.lookup import lookup


def test_string_key_for_int_dict():
    assert lookup({1: "a"}, "1") == "a"


def test_int_key():
    assert lookup({1: "a"}, 1) == "a"


def test_missing_key():
    with pytest.raises(KeyError):
        lookup({1: "a"}, "2")
