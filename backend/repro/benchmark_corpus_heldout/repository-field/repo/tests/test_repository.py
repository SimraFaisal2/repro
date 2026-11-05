from src.models import User
from src.repository import email_of


def test_reads_renamed_field():
    assert email_of(User("Ada", "ada@example.com").as_dict()) == "ada@example.com"


def test_missing_field():
    import pytest

    with pytest.raises(KeyError):
        email_of({"name": "Ada"})
