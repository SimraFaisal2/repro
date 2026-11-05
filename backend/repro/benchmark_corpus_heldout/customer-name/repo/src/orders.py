"""Order display helpers."""


class Customer:
    def __init__(self, name):
        self.name = name


class Order:
    def __init__(self, customer):
        self.customer = customer


def customer_name(order):
    return order.customer.name
