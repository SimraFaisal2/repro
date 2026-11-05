"""Held-out off-by-one cases (5)."""

CASES = [
    {
        "id": "adjacent-pairs",
        "name": "Adjacent sums walk past the last element",
        "category": "off-by-one",
        "difficulty": "easy",
        "root_cause_file": "src/pairs.py",
        "root_cause_line": 4,
        "hidden_bug": "pair_sums iterates over range(len(values)) and reads values[i + 1], "
                       "so the final index is out of range.",
        "expected_behavior": "pair_sums([1, 2, 3]) returns [3, 5]; empty and single inputs "
                            "return an empty list.",
        "ground_truth_summary": "Iterate over range(len(values) - 1).",
        "files": {
            "src/pairs.py": '''"""Adjacent-pair sums."""


def pair_sums(values):
    return [values[i] + values[i + 1] for i in range(len(values))]
''',
            "tests/test_pairs.py": '''from src.pairs import pair_sums


def test_pairs():
    assert pair_sums([1, 2, 3]) == [3, 5]


def test_empty():
    assert pair_sums([]) == []
''',
        },
        "fixed": {
            "src/pairs.py": '''"""Adjacent-pair sums."""


def pair_sums(values):
    return [values[i] + values[i + 1] for i in range(len(values) - 1)]
''',
        },
        "oracle": '''from src.pairs import pair_sums


def test_single():
    assert pair_sums([7]) == []


def test_negative_values():
    assert pair_sums([-2, 2, 5]) == [0, 7]


def test_longer_run():
    assert pair_sums([1, 2, 3, 4, 5, 6]) == [3, 5, 7, 9, 11]


def test_strings_are_not_special_cased():
    assert pair_sums(["a", "b", "c"]) == ["ab", "bc"]
''',
    },
    {
        "id": "page-window",
        "name": "Page window returns one extra item",
        "category": "off-by-one",
        "difficulty": "easy",
        "root_cause_file": "src/paging.py",
        "root_cause_line": 6,
        "hidden_bug": "page() ends the slice at start + size + 1, so every page contains "
                       "size + 1 items and overlaps the next page.",
        "expected_behavior": "page(items, 2, 10) returns exactly items[10:20].",
        "ground_truth_summary": "Use start + size as the slice end.",
        "files": {
            "src/paging.py": '''"""Fixed-size page windows."""


def page(items, number, size):
    start = (number - 1) * size
    return items[start:start + size + 1]
''',
            "tests/test_paging.py": '''from src.paging import page


def test_second_page():
    assert page(list(range(25)), 2, 10) == list(range(10, 20))


def test_first_page():
    assert page([1, 2, 3, 4, 5], 1, 2) == [1, 2]


def test_empty_items():
    assert page([], 1, 5) == []
''',
        },
        "fixed": {
            "src/paging.py": '''"""Fixed-size page windows."""


def page(items, number, size):
    start = (number - 1) * size
    return items[start:start + size]
''',
        },
        "oracle": '''from src.paging import page


def test_last_page_is_partial():
    assert page(list(range(25)), 3, 10) == list(range(20, 25))


def test_page_beyond_end():
    assert page([1, 2, 3], 5, 2) == []


def test_size_one():
    assert page(["a", "b", "c"], 2, 1) == ["b"]


def test_exact_boundary():
    assert page([1, 2, 3, 4], 2, 2) == [3, 4]
''',
    },
    {
        "id": "last-n",
        "name": "last_n returns n+1 items",
        "category": "off-by-one",
        "difficulty": "easy",
        "root_cause_file": "src/tail.py",
        "root_cause_line": 4,
        "hidden_bug": "last_n slices with -n - 1, returning one more element than requested; "
                       "it also mishandles n = 0.",
        "expected_behavior": "last_n([1, 2, 3, 4, 5], 2) returns [4, 5] and n=0 returns [].",
        "ground_truth_summary": "Return [] for n <= 0, otherwise values[-n:].",
        "files": {
            "src/tail.py": '''"""Take the last n items."""


def last_n(values, n):
    return values[-n - 1:]
''',
            "tests/test_tail.py": '''from src.tail import last_n


def test_last_two():
    assert last_n([1, 2, 3, 4, 5], 2) == [4, 5]


def test_n_larger_than_input():
    assert last_n([1, 2, 3], 10) == [1, 2, 3]


def test_zero():
    assert last_n([1, 2, 3], 0) == []
''',
        },
        "fixed": {
            "src/tail.py": '''"""Take the last n items."""


def last_n(values, n):
    if n <= 0:
        return []
    return values[-n:]
''',
        },
        "oracle": '''from src.tail import last_n


def test_n_one():
    assert last_n([1, 2, 3], 1) == [3]


def test_n_equals_length():
    assert last_n([1, 2, 3], 3) == [1, 2, 3]


def test_empty_input():
    assert last_n([], 4) == []


def test_string_input_returns_string():
    assert last_n("abcd", 2) == "cd"
''',
    },
    {
        "id": "chunk-size",
        "name": "Chunker uses size-1 as the chunk width",
        "category": "off-by-one",
        "difficulty": "medium",
        "root_cause_file": "src/chunks.py",
        "root_cause_line": 7,
        "hidden_bug": "chunks() slices values[i:i + size - 1] while stepping by size, so it "
                       "drops the final item of every chunk and produces empty chunks for size 1.",
        "expected_behavior": "chunks([1..5], 2) returns [[1, 2], [3, 4], [5]].",
        "ground_truth_summary": "Slice at i + size and reject size <= 0.",
        "files": {
            "src/chunks.py": '''"""Split a sequence into fixed-size chunks."""


def chunks(values, size):
    if size <= 0:
        raise ValueError("size must be positive")
    return [values[i:i + size - 1] for i in range(0, len(values), size)]
''',
            "tests/test_chunks.py": '''import pytest

from src.chunks import chunks


def test_pairs():
    assert chunks([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]


def test_size_one():
    assert chunks(["a", "b"], 1) == [["a"], ["b"]]


def test_empty():
    assert chunks([], 3) == []


def test_invalid_size():
    with pytest.raises(ValueError):
        chunks([1], 0)
''',
        },
        "fixed": {
            "src/chunks.py": '''"""Split a sequence into fixed-size chunks."""


def chunks(values, size):
    if size <= 0:
        raise ValueError("size must be positive")
    return [values[i:i + size] for i in range(0, len(values), size)]
''',
        },
        "oracle": '''from src.chunks import chunks


def test_exact_division():
    assert chunks([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]


def test_last_chunk_is_partial():
    assert chunks([1, 2, 3, 4, 5], 3) == [[1, 2, 3], [4, 5]]


def test_larger_than_input():
    assert chunks([1, 2], 10) == [[1, 2]]


def test_strings():
    assert chunks("abcdef", 4) == ["abcd", "ef"]
''',
    },
    {
        "id": "window-max",
        "name": "Sliding-window maximum omits the final window",
        "category": "off-by-one",
        "difficulty": "medium",
        "root_cause_file": "src/windows.py",
        "root_cause_line": 5,
        "hidden_bug": "max_windows iterates range(len(values) - width) instead of adding one, "
                       "so the last full window is never evaluated.",
        "expected_behavior": "max_windows([1, 3, 2, 5], 2) returns [3, 3, 5].",
        "ground_truth_summary": "Iterate over the correct number of windows and validate width.",
        "files": {
            "src/windows.py": '''"""Maximum value in each sliding window."""


def max_windows(values, width):
    if width <= 0:
        raise ValueError("width must be positive")
    return [max(values[i:i + width]) for i in range(len(values) - width)]
''',
            "tests/test_windows.py": '''import pytest

from src.windows import max_windows


def test_width_two():
    assert max_windows([1, 3, 2, 5], 2) == [3, 3, 5]


def test_empty():
    assert max_windows([], 1) == []


def test_invalid_width():
    with pytest.raises(ValueError):
        max_windows([1], 0)
''',
        },
        "fixed": {
            "src/windows.py": '''"""Maximum value in each sliding window."""


def max_windows(values, width):
    if width <= 0:
        raise ValueError("width must be positive")
    return [max(values[i:i + width]) for i in range(len(values) - width + 1)]
''',
        },
        "oracle": '''from src.windows import max_windows


def test_width_one():
    assert max_windows([4, 1, 7], 1) == [4, 1, 7]


def test_width_equals_length():
    assert max_windows([4, 1, 7], 3) == [7]


def test_width_larger_than_input():
    assert max_windows([4, 1], 3) == []


def test_negative_values():
    assert max_windows([-5, -2, -9, -1], 2) == [-2, -2, -1]
''',
    },
]
