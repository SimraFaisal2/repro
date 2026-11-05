import pytest

from src.plugins.alpha import NAME, run
from src.registry import get


def test_name_is_exported():
    assert NAME == "alpha-v1"


def test_zero():
    assert get(NAME)(0) == 0


def test_negative():
    assert get(NAME)(-4) == -8


def test_registry_contains_exact_name():
    with pytest.raises(KeyError):
        get("alpha")
