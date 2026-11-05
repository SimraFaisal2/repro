from src.plugins.alpha import NAME
from src.registry import get


def test_lookup_by_exported_name():
    assert get(NAME) is not None


def test_plugin_doubles():
    assert get(NAME)(3) == 6


def test_unknown_plugin():
    import pytest

    with pytest.raises(KeyError):
        get("missing")
