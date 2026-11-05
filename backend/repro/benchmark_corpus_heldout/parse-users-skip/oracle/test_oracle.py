import pytest

from src.users import parse_users


def test_error_after_valid_row_is_not_partial_success():
    with pytest.raises(ValueError):
        parse_users([{"name": "Ada"}, {"id": 2}])


def test_none_name_is_preserved():
    assert parse_users([{"name": None}]) == [{"name": None}]


def test_empty_name_is_preserved():
    assert parse_users([{"name": ""}]) == [{"name": ""}]


def test_multiple_valid_rows():
    assert parse_users([{"name": "Ada"}, {"name": "Grace"}]) == [
        {"name": "Ada"},
        {"name": "Grace"},
    ]
