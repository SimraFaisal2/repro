"""Demo fixture: null/None handling bug.

`login()` assumes `get_user()` always returns a user object, but it
returns None for unknown usernames — subscripting that None crashes.
"""

USERS = [
    {"username": "alice", "password": "secret-alice"},
    {"username": "bob", "password": "secret-bob"},
]


def get_user(db, username):
    for u in db:
        if u["username"] == username:
            return u
    return None


def verify_password(password, stored):
    return password == stored


def create_token(user):
    return f"tok-{user['username']}"


def login(db, username, password):
    user = get_user(db, username)
    if verify_password(password, user["password"]):
        return {"token": create_token(user), "user": username}
    return None
