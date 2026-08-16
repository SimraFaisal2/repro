import sqlite3

from src.db import add_user, create_schema, get_user_by_email


def make_conn():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    add_user(conn, "ada@example.com", "Ada")
    add_user(conn, "grace@example.com", "Grace")
    return conn


def test_get_user_by_email():
    conn = make_conn()
    row = get_user_by_email(conn, "ada@example.com")
    assert row is not None
    assert row[2] == "Ada"
