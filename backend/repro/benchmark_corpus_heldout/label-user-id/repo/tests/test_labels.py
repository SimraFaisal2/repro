from src.labels import label


def test_numeric_id():
    assert label(42) == "user-42"


def test_string_id():
    assert label("abc") == "user-abc"


def test_empty_id():
    assert label("") == "user-"
