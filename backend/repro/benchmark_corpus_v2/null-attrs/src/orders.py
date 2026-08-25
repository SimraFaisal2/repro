"""Order store. find_order() returns None for unknown ids, and the caller
subscripts the result unconditionally — a NULL dereference."""


def find_order(orders, order_id):
    for o in orders:
        if o["id"] == order_id:
            return o
    return None


def order_total(orders, order_id):
    order = find_order(orders, order_id)
    return order["amount"]
