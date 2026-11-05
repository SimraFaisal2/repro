"""Shopping cart."""


class Cart:
    def __init__(self):
        self.items = {}

    def add(self, sku, qty):
        self.items[sku] = qty
