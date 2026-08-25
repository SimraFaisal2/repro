from src.orders import find_order, order_total


def test_order_total_missing():
    # must not raise: the order is unknown, so order_total should return None
    assert order_total([], 99) is None


def test_order_total_known():
    orders = [{"id": 1, "amount": 42}]
    assert order_total(orders, 1) == 42
    assert find_order(orders, 1) == {"id": 1, "amount": 42}
