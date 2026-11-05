from src.cart import Cart


def test_multiple_skus_are_independent():
    cart = Cart()
    cart.add("a", 1)
    cart.add("b", 2)
    cart.add("a", 3)
    assert cart.items == {"a": 4, "b": 2}


def test_zero_quantity():
    cart = Cart()
    cart.add("a", 0)
    assert cart.items["a"] == 0


def test_add_zero_to_existing():
    cart = Cart()
    cart.add("a", 2)
    cart.add("a", 0)
    assert cart.items["a"] == 2


def test_negative_quantity_is_recorded():
    cart = Cart()
    cart.add("a", 2)
    cart.add("a", -1)
    assert cart.items["a"] == 1
