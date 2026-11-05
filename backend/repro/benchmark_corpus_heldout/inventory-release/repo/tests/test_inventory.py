import pytest

from src.inventory import Inventory


def test_reserve():
    inventory = Inventory(10)
    assert inventory.reserve(3) == 3
    assert inventory.available == 7


def test_release():
    inventory = Inventory(10)
    inventory.reserve(3)
    assert inventory.release(2) == 9


def test_over_release():
    inventory = Inventory(10)
    inventory.reserve(3)
    with pytest.raises(ValueError):
        inventory.release(4)
    assert inventory.reserved == 3
