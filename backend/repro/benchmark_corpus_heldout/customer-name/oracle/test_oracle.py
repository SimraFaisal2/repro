from src.orders import Customer, Order, customer_name


def test_empty_name():
    assert customer_name(Order(Customer(""))) == "guest"


def test_whitespace_is_a_name():
    assert customer_name(Order(Customer(" "))) == " "


def test_order_without_customer_attribute():
    class Bare:
        customer = None

    assert customer_name(Bare()) == "guest"


def test_does_not_mutate():
    order = Order(Customer("Grace"))
    assert customer_name(order) == "Grace"
    assert order.customer.name == "Grace"
