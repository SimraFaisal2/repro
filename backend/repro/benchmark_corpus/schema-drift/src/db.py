"""User store with a stale column reference.

The table defines `email`, but `find_by_email()` still filters on
`email_addr` (renamed in a migration and never updated here).
"""
import sqlite3


def create_schema(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS users (\n"
        " id INTEGER PRIMARY KEY,\n"
        " email TEXT NOT NULL,\n"
        " name TEXT NOT NULL)"
    )


def add_user(conn, email, name):
    conn.execute("INSERT INTO users (email, name) VALUES (?, ?)", (email, name))
    conn.commit()


def find_by_email(conn, email):
    cur = conn.execute("SELECT * FROM users WHERE email_addr = ?", (email,))
    return cur.fetchone()
