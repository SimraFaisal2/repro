from src.payloads import items


def test_present():
    assert items({"items": [1, 2]}) == [1, 2]


def test_missing():
    assert items({}) == []


def test_null():
    assert items({"items": None}) == []
