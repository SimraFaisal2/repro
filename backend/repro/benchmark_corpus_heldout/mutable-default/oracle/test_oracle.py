from src.buckets import add_item


def test_explicit_bucket_is_mutated():
    bucket = []
    out = add_item("a", bucket)
    assert out is bucket
    assert bucket == ["a"]


def test_empty_item():
    assert add_item("") == [""]


def test_three_fresh_calls():
    assert add_item(1) == [1]
    assert add_item(2) == [2]
    assert add_item(3) == [3]


def test_none_bucket_is_treated_as_missing():
    assert add_item("a", None) == ["a"]
