from src.orders import Customer, Order, customer_name


def test_named_customer():
    assert customer_name(Order(Customer("Ada"))) == "Ada"


def test_guest_order():
    assert customer_name(Order(None)) == "guest"


def test_unnamed_customer():
    assert customer_name(Order(Customer(None))) == "guest"
