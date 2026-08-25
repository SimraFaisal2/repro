"""Product store. The table defines `sku`, but the lookup filters on the
stale column name `sku_code` (renamed in a migration and never updated)."""
import sqlite3


def create_schema(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS products (\n"
        " id INTEGER PRIMARY KEY,\n"
        " sku TEXT NOT NULL,\n"
        " price REAL NOT NULL)"
    )


def add_product(conn, sku, price):
    conn.execute("INSERT INTO products (sku, price) VALUES (?, ?)", (sku, price))
    conn.commit()


def find_by_sku(conn, sku):
    cur = conn.execute("SELECT * FROM products WHERE sku_code = ?", (sku,))
    return cur.fetchone()
