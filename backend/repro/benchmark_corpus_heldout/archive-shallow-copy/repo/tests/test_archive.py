from src.archive import archive


def test_returns_archived_rows():
    assert archive([{"id": 1}]) == [{"id": 1, "archived": True}]


def test_does_not_mutate_original_rows():
    rows = [{"id": 1}]
    archive(rows)
    assert rows == [{"id": 1}]


def test_empty():
    assert archive([]) == []
