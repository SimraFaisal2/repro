import pytest

from src.store import Store


def test_failed_batch_is_atomic():
    store = Store()
    with pytest.raises(ValueError):
        store.add_all([1, None, 2])
    assert store.items == []


def test_valid_batch():
    store = Store()
    store.add_all([1, 2])
    assert store.items == [1, 2]


def test_empty_batch():
    store = Store()
    store.add_all([])
    assert store.items == []
