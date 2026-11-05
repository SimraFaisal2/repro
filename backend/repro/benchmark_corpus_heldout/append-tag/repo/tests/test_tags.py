from src.tags import with_tag


def test_returns_tagged_list():
    assert with_tag(["a"], "b") == ["a", "b"]


def test_does_not_mutate_input():
    tags = ["a"]
    with_tag(tags, "b")
    assert tags == ["a"]


def test_empty_input():
    assert with_tag([], "new") == ["new"]
