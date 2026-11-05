"""A simple switch."""


class Switch:
    def __init__(self):
        self.on = False

    def press(self):
        self.on = True
        return self.on
