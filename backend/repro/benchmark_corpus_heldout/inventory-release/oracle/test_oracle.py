import pytest

from src.inventory import Inventory


def test_release_all():
    inventory = Inventory(5)
    inventory.reserve(5)
    assert inventory.release(5) == 5
    assert inventory.available == 5
    assert inventory.reserved == 0


def test_release_zero():
    inventory = Inventory(5)
    inventory.reserve(2)
    assert inventory.release(0) == 3
    assert inventory.reserved == 2


def test_reserve_then_release_twice():
    inventory = Inventory(4)
    inventory.reserve(4)
    inventory.release(1)
    assert inventory.release(1) == 2
    assert inventory.reserved == 2


def test_over_release_does_not_change_state():
    inventory = Inventory(3)
    inventory.reserve(2)
    with pytest.raises(ValueError):
        inventory.release(3)
    assert inventory.available == 1
    assert inventory.reserved == 2
