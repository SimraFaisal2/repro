"""Retry accounting."""


class Retrier:
    def __init__(self):
        self.attempts = 0

    def attempt(self, succeed):
        self.attempts += 1
        if succeed:
            self.attempts += 1
            return True
        return False
