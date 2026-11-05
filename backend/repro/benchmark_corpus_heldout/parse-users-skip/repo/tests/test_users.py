import pytest

from src.users import parse_users


def test_missing_name_raises():
    with pytest.raises(ValueError):
        parse_users([{"id": 1}])


def test_valid_rows():
    assert parse_users([{"name": "Ada"}]) == [{"name": "Ada"}]


def test_empty():
    assert parse_users([]) == []
