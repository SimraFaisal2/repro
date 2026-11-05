from src.payloads import items


def test_empty_list():
    assert items({"items": []}) == []


def test_tuple_is_preserved():
    assert items({"items": (1, 2)}) == (1, 2)


def test_falsey_empty_string_becomes_list():
    assert items({"items": ""}) == []


def test_nested_payload():
    assert items({"items": [{"id": 1}]}) == [{"id": 1}]
