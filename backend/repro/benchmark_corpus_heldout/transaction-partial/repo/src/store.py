"""Batch store writes."""


class Store:
    def __init__(self):
        self.items = []

    def add_all(self, items):
        for item in items:
            if item is None:
                raise ValueError("null item")
            self.items.append(item)
