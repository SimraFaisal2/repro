from src.config import db_host


def test_db_host_known_section():
    assert db_host("database") == "localhost"


def test_db_host_missing_section():
    # regression: an unknown section must not crash — returns None
    assert db_host("search") is None
