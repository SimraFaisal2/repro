from src.config import timeout


def test_explicit_value():
    assert timeout({"timeout": 5}) == 5


def test_negative_value_is_preserved():
    assert timeout({"timeout": -1}) == -1


def test_other_keys_ignored():
    assert timeout({"retries": 3}) == 30


def test_false_is_preserved():
    assert timeout({"timeout": False}) is False
