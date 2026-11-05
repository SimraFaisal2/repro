from src.cart import Cart


def test_add_existing_sku():
    cart = Cart()
    cart.add("apple", 3)
    cart.add("apple", 2)
    assert cart.items["apple"] == 5


def test_add_new_sku():
    cart = Cart()
    cart.add("pear", 4)
    assert cart.items == {"pear": 4}


def test_empty_cart():
    assert Cart().items == {}
