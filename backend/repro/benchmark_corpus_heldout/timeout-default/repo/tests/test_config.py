from src.config import timeout


def test_missing():
    assert timeout({}) == 30


def test_null():
    assert timeout({"timeout": None}) == 30


def test_explicit_zero():
    assert timeout({"timeout": 0}) == 0
