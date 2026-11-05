from src.buckets import add_item


def test_first_call():
    assert add_item("a") == ["a"]


def test_second_call_is_fresh():
    add_item("a")
    assert add_item("b") == ["b"]


def test_explicit_bucket_is_used():
    bucket = ["x"]
    assert add_item("y", bucket) == ["x", "y"]
