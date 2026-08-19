import sqlite3

from src.db import add_user, create_schema, find_by_email


def test_find_by_email():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    add_user(conn, "ada@example.com", "Ada")
    row = find_by_email(conn, "ada@example.com")
    assert row is not None
    assert row[1] == "ada@example.com"
