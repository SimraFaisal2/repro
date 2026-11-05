"""Held-out mutation / aliasing cases (5)."""

CASES = [
    {
        "id": "append-tag",
        "name": "Adding a tag mutates the caller's list",
        "category": "mutation-aliasing",
        "difficulty": "easy",
        "root_cause_file": "src/tags.py",
        "root_cause_line": 4,
        "hidden_bug": "with_tag() appends to the caller's list and returns the same object, "
                       "so constructing a tagged copy changes the original.",
        "expected_behavior": "with_tag(['a'], 'b') returns ['a', 'b'] without modifying ['a'].",
        "ground_truth_summary": "Build and return a new list.",
        "files": {
            "src/tags.py": '''"""Tag helpers."""


def with_tag(tags, tag):
    tags.append(tag)
    return tags
''',
            "tests/test_tags.py": '''from src.tags import with_tag


def test_returns_tagged_list():
    assert with_tag(["a"], "b") == ["a", "b"]


def test_does_not_mutate_input():
    tags = ["a"]
    with_tag(tags, "b")
    assert tags == ["a"]


def test_empty_input():
    assert with_tag([], "new") == ["new"]
''',
        },
        "fixed": {
            "src/tags.py": '''"""Tag helpers."""


def with_tag(tags, tag):
    return [*tags, tag]
''',
        },
        "oracle": '''from src.tags import with_tag


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
''',
    },
    {
        "id": "sort-in-place",
        "name": "Ordering helper sorts the caller's list in place",
        "category": "mutation-aliasing",
        "difficulty": "easy",
        "root_cause_file": "src/ordering.py",
        "root_cause_line": 4,
        "hidden_bug": "ordered() calls list.sort() on the argument and returns the same list, "
                       "silently reordering the caller's data.",
        "expected_behavior": "ordered([3, 1, 2]) returns [1, 2, 3] while the input stays [3, 1, 2].",
        "ground_truth_summary": "Return sorted(values) instead of sorting in place.",
        "files": {
            "src/ordering.py": '''"""Ordering helpers."""


def ordered(values):
    values.sort()
    return values
''',
            "tests/test_ordering.py": '''from src.ordering import ordered


def test_sorts():
    assert ordered([3, 1, 2]) == [1, 2, 3]


def test_does_not_mutate():
    values = [3, 1, 2]
    ordered(values)
    assert values == [3, 1, 2]


def test_empty():
    assert ordered([]) == []
''',
        },
        "fixed": {
            "src/ordering.py": '''"""Ordering helpers."""


def ordered(values):
    return sorted(values)
''',
        },
        "oracle": '''from src.ordering import ordered


def test_duplicates():
    assert ordered([2, 1, 2]) == [1, 2, 2]


def test_already_sorted():
    assert ordered([1, 2, 3]) == [1, 2, 3]


def test_negative_numbers():
    assert ordered([0, -3, 2]) == [-3, 0, 2]


def test_tuple_input():
    assert ordered((3, 1, 2)) == [1, 2, 3]
''',
    },
    {
        "id": "mutable-default",
        "name": "Mutable default argument leaks items across calls",
        "category": "mutation-aliasing",
        "difficulty": "medium",
        "root_cause_file": "src/buckets.py",
        "root_cause_line": 4,
        "hidden_bug": "add_item() uses a mutable default list, so items accumulate between "
                       "calls that do not pass an explicit bucket.",
        "expected_behavior": "Two separate calls with no bucket each return a one-item list.",
        "ground_truth_summary": "Use None as the sentinel and create a fresh list per call.",
        "files": {
            "src/buckets.py": '''"""Bucket helpers."""


def add_item(item, bucket=[]):
    bucket.append(item)
    return bucket
''',
            "tests/test_buckets.py": '''from src.buckets import add_item


def test_first_call():
    assert add_item("a") == ["a"]


def test_second_call_is_fresh():
    add_item("a")
    assert add_item("b") == ["b"]


def test_explicit_bucket_is_used():
    bucket = ["x"]
    assert add_item("y", bucket) == ["x", "y"]
''',
        },
        "fixed": {
            "src/buckets.py": '''"""Bucket helpers."""


def add_item(item, bucket=None):
    if bucket is None:
        bucket = []
    bucket.append(item)
    return bucket
''',
        },
        "oracle": '''from src.buckets import add_item


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
''',
    },
    {
        "id": "archive-shallow-copy",
        "name": "Archive shallow-copies rows and mutates originals",
        "category": "mutation-aliasing",
        "difficulty": "medium",
        "root_cause_file": "src/archive.py",
        "root_cause_line": 5,
        "hidden_bug": "archive() copies the outer list but not each row dict, so setting "
                       "'archived' on the copies also changes the caller's rows.",
        "expected_behavior": "archive(rows) returns archived copies while rows stay unchanged.",
        "ground_truth_summary": "Copy each row dict before mutating it.",
        "files": {
            "src/archive.py": '''"""Archive rows."""


def archive(rows):
    copied = list(rows)
    for row in copied:
        row["archived"] = True
    return copied
''',
            "tests/test_archive.py": '''from src.archive import archive


def test_returns_archived_rows():
    assert archive([{"id": 1}]) == [{"id": 1, "archived": True}]


def test_does_not_mutate_original_rows():
    rows = [{"id": 1}]
    archive(rows)
    assert rows == [{"id": 1}]


def test_empty():
    assert archive([]) == []
''',
        },
        "fixed": {
            "src/archive.py": '''"""Archive rows."""


def archive(rows):
    copied = [dict(row) for row in rows]
    for row in copied:
        row["archived"] = True
    return copied
''',
        },
        "oracle": '''from src.archive import archive


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
''',
    },
    {
        "id": "zero-grid-aliasing",
        "name": "Grid rows alias one shared list",
        "category": "mutation-aliasing",
        "difficulty": "medium",
        "root_cause_file": "src/grid.py",
        "root_cause_line": 4,
        "hidden_bug": "zero_grid() builds [[0] * cols] * rows, which repeats the same inner "
                       "list object, so writing one cell changes every row.",
        "expected_behavior": "Each grid row is an independent list.",
        "ground_truth_summary": "Build each row with a separate comprehension.",
        "files": {
            "src/grid.py": '''"""Grid helpers."""


def zero_grid(rows, cols):
    return [[0] * cols] * rows
''',
            "tests/test_grid.py": '''from src.grid import zero_grid


def test_dimensions():
    grid = zero_grid(3, 2)
    assert len(grid) == 3
    assert all(len(row) == 2 for row in grid)


def test_rows_are_independent():
    grid = zero_grid(2, 2)
    grid[0][0] = 1
    assert grid == [[1, 0], [0, 0]]


def test_zero_rows():
    assert zero_grid(0, 3) == []
''',
        },
        "fixed": {
            "src/grid.py": '''"""Grid helpers."""


def zero_grid(rows, cols):
    return [[0] * cols for _ in range(rows)]
''',
        },
        "oracle": '''from src.grid import zero_grid


def test_single_row():
    grid = zero_grid(1, 3)
    grid[0][1] = 5
    assert grid == [[0, 5, 0]]


def test_single_column():
    grid = zero_grid(3, 1)
    grid[1][0] = 9
    assert grid == [[0], [9], [0]]


def test_zero_columns():
    assert zero_grid(2, 0) == [[], []]


def test_each_row_has_distinct_identity():
    grid = zero_grid(3, 1)
    assert len({id(row) for row in grid}) == 3
''',
    },
]
