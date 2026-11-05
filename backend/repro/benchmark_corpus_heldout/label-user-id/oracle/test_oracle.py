from src.labels import label


def test_zero():
    assert label(0) == "user-0"


def test_negative():
    assert label(-7) == "user--7"


def test_large_integer():
    assert label(10**12) == "user-1000000000000"


def test_string_with_dash():
    assert label("a-b") == "user-a-b"
