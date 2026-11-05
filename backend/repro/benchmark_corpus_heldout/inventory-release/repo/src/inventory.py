"""Inventory reservations."""


class Inventory:
    def __init__(self, available):
        self.available = available
        self.reserved = 0

    def reserve(self, amount):
        if amount > self.available:
            raise ValueError("not enough stock")
        self.available -= amount
        self.reserved += amount
        return self.reserved

    def release(self, amount):
        if amount > self.reserved:
            raise ValueError("not enough reserved stock")
        self.reserved -= amount
        self.available -= amount
        return self.available
