"""Profile store with a None-subscript bug.

`find_user()` returns None for an unknown id, but `display_name()`
subscripts the result without checking — crashing on unknown users.
"""

USERS = [
    {"id": 1, "name": "Ada"},
    {"id": 2, "name": "Grace"},
]


def find_user(users, user_id):
    for u in users:
        if u["id"] == user_id:
            return u
    return None


def display_name(users, user_id):
    user = find_user(users, user_id)
    return user["name"]
