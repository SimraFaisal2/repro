import pytest

from src.models import User
from src.repository import email_of


def test_user_roundtrip():
    user = User("Grace", "grace@example.com")
    assert email_of(user.as_dict()) == "grace@example.com"


def test_empty_email():
    assert email_of({"email_address": ""}) == ""


def test_none_email_is_preserved():
    assert email_of({"email_address": None}) is None


def test_empty_row_raises():
    with pytest.raises(KeyError):
        email_of({})
