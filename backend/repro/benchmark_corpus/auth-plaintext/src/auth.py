"""Authentication with a plaintext-comparison bug.

Credentials are stored hashed (`hash_password`), but `authenticate()`
compares the incoming plaintext password directly against the hash —
so the correct password never matches.
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
