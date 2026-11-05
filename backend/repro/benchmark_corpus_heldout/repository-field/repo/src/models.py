"""User model."""


class User:
    def __init__(self, name, email_address):
        self.name = name
        self.email_address = email_address

    def as_dict(self):
        return {"name": self.name, "email_address": self.email_address}
