"""Session store with a None-attribute bug.

`get_user()` returns None for anonymous sessions, but `current_email()`
reads `user.email` without checking — crashing on logged-out visitors.
"""


class User:
    def __init__(self, email):
        self.email = email


class Session:
    def __init__(self, user=None):
        self._user = user

    def get_user(self):
        return self._user


def current_email(session):
    user = session.get_user()
    return user.email
