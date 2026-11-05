from src.models import User
from src.serializers import serialize


def test_unicode_name():
    assert serialize(User("Zoë", "Müller")) == {"name": "Zoë Müller"}


def test_full_name_does_not_mutate():
    user = User("Grace", "Hopper")
    assert user.full_name() == "Grace Hopper"
    assert user.first == "Grace"
    assert user.last == "Hopper"


def test_serialized_dict_is_fresh():
    user = User("Alan", "Turing")
    first = serialize(user)
    first["name"] = "changed"
    assert serialize(user)["name"] == "Alan Turing"


def test_names_with_spaces():
    assert serialize(User("Mary Ann", "Evans")) == {"name": "Mary Ann Evans"}
