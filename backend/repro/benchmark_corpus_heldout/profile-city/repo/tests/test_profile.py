from src.profile import city


def test_present_address():
    assert city({"address": {"city": "Berlin"}}) == "Berlin"


def test_missing_address():
    assert city({"name": "Ada"}) == "unknown"


def test_null_address():
    assert city({"address": None}) == "unknown"
