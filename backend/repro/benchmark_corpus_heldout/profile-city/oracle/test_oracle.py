from src.profile import city


def test_empty_city():
    assert city({"address": {"city": ""}}) == "unknown"


def test_null_city():
    assert city({"address": {"city": None}}) == "unknown"


def test_empty_user():
    assert city({}) == "unknown"


def test_does_not_mutate_input():
    user = {"address": {"city": "Paris"}}
    city(user)
    assert user == {"address": {"city": "Paris"}}
