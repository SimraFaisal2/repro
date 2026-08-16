"""Demo fixture: authentication logic bug.

`authenticate()` compares the incoming plaintext password directly with
the stored hash — it must hash the input first.
"""
import hashlib


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


USERS = [
    {"username": "alice", "password": hash_password("hunter2")},
]


def authenticate(users, username, password):
    for u in users:
        if u["username"] == username:
            return u["password"] == password
    return False
