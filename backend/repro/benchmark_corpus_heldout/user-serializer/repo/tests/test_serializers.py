from src.models import User
from src.serializers import serialize


def test_full_name():
    assert User("Ada", "Lovelace").full_name() == "Ada Lovelace"


def test_serialize_user():
    assert serialize(User("Ada", "Lovelace")) == {"name": "Ada Lovelace"}


def test_single_name():
    assert serialize(User("Prince", "")) == {"name": "Prince "}
