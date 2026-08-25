import sqlite3

from src.store import add_product, create_schema, find_by_sku


def test_find_by_sku():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    add_product(conn, "SKU-1", 9.99)
    row = find_by_sku(conn, "SKU-1")
    assert row is not None
    assert row[1] == "SKU-1"


def test_add_and_count():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    add_product(conn, "A", 1.0)
    add_product(conn, "B", 2.0)
    assert conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 2
