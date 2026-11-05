import pytest

from src.store import Store


def test_first_item_null():
    store = Store()
    with pytest.raises(ValueError):
        store.add_all([None, 1])
    assert store.items == []


def test_existing_items_survive_failed_batch():
    store = Store()
    store.add_all([1])
    with pytest.raises(ValueError):
        store.add_all([2, None])
    assert store.items == [1]


def test_multiple_valid_batches():
    store = Store()
    store.add_all([1, 2])
    store.add_all([3])
    assert store.items == [1, 2, 3]


def test_tuple_batch():
    store = Store()
    store.add_all((1, 2))
    assert store.items == [1, 2]
