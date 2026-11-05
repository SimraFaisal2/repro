from src.tags import with_tag


def test_input_order_preserved():
    assert with_tag(["b", "a"], "c") == ["b", "a", "c"]


def test_duplicate_tag_is_kept():
    assert with_tag(["a"], "a") == ["a", "a"]


def test_original_not_changed_even_when_result_is_mutated():
    tags = ["a"]
    out = with_tag(tags, "b")
    out.append("c")
    assert tags == ["a"]


def test_tuple_input():
    assert with_tag(("a",), "b") == ["a", "b"]
