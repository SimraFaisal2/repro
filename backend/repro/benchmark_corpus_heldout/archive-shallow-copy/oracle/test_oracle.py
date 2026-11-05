from src.archive import archive


def test_multiple_rows():
    rows = [{"id": 1}, {"id": 2}]
    out = archive(rows)
    assert out == [{"id": 1, "archived": True}, {"id": 2, "archived": True}]
    assert rows == [{"id": 1}, {"id": 2}]


def test_existing_keys_preserved():
    assert archive([{"id": 1, "archived": False}]) == [{"id": 1, "archived": True}]


def test_result_rows_are_independent():
    out = archive([{"id": 1}])
    out[0]["id"] = 99
    assert out == [{"id": 99, "archived": True}]


def test_empty_row():
    assert archive([{}]) == [{"archived": True}]
