"""Demo fixture: incorrect SQL query.

`get_user_by_email()` filters on `email_addr`, a column that does not
exist — the schema column is `email`.
"""
import sqlite3


def create_schema(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS users ("
        " id INTEGER PRIMARY KEY,"
        " email TEXT NOT NULL,"
        " name TEXT NOT NULL,"
        " role TEXT NOT NULL DEFAULT 'member')"
    )


def add_user(conn, email, name, role="member"):
    conn.execute("INSERT INTO users (email, name, role) VALUES (?, ?, ?)", (email, name, role))
    conn.commit()


def get_user_by_email(conn, email):
    cur = conn.execute("SELECT * FROM users WHERE email_addr = ?", (email,))
    return cur.fetchone()
