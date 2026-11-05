"""Held-out type-error cases (5)."""

CASES = [
    {
        "id": "parse-quantity",
        "name": "Quantity parser rejects values with units",
        "category": "type-errors",
        "difficulty": "easy",
        "root_cause_file": "src/quantity.py",
        "root_cause_line": 4,
        "hidden_bug": "quantity() calls int() on the whole string, so '3 items' raises "
                       "ValueError instead of reading the numeric prefix.",
        "expected_behavior": "quantity('3 items') returns 3; a bare number still works.",
        "ground_truth_summary": "Take the first whitespace-separated token before int().",
        "files": {
            "src/quantity.py": '''"""Parse item quantities."""


def quantity(text):
    return int(text)
''',
            "tests/test_quantity.py": '''from src.quantity import quantity


def test_with_units():
    assert quantity("3 items") == 3


def test_bare_number():
    assert quantity("7") == 7


def test_surrounding_spaces():
    assert quantity(" 12 ") == 12
''',
        },
        "fixed": {
            "src/quantity.py": '''"""Parse item quantities."""


def quantity(text):
    return int(str(text).split()[0])
''',
        },
        "oracle": '''from src.quantity import quantity


def test_zero():
    assert quantity("0 boxes") == 0


def test_negative():
    assert quantity("-2 refunds") == -2


def test_tab_separator():
    assert quantity("3\\titems") == 3


def test_number_with_plus():
    assert quantity("+4 units") == 4
''',
    },
    {
        "id": "label-user-id",
        "name": "Label concatenates an integer user id",
        "category": "type-errors",
        "difficulty": "easy",
        "root_cause_file": "src/labels.py",
        "root_cause_line": 4,
        "hidden_bug": "label() concatenates str and int, raising TypeError for numeric ids.",
        "expected_behavior": "label(42) returns 'user-42'; string ids keep working.",
        "ground_truth_summary": "Format the id instead of concatenating it directly.",
        "files": {
            "src/labels.py": '''"""User-facing labels."""


def label(user_id):
    return "user-" + user_id
''',
            "tests/test_labels.py": '''from src.labels import label


def test_numeric_id():
    assert label(42) == "user-42"


def test_string_id():
    assert label("abc") == "user-abc"


def test_empty_id():
    assert label("") == "user-"
''',
        },
        "fixed": {
            "src/labels.py": '''"""User-facing labels."""


def label(user_id):
    return f"user-{user_id}"
''',
        },
        "oracle": '''from src.labels import label


def test_zero():
    assert label(0) == "user-0"


def test_negative():
    assert label(-7) == "user--7"


def test_large_integer():
    assert label(10**12) == "user-1000000000000"


def test_string_with_dash():
    assert label("a-b") == "user-a-b"
''',
    },
    {
        "id": "sum-prices",
        "name": "Price total assumes numeric strings",
        "category": "type-errors",
        "difficulty": "medium",
        "root_cause_file": "src/billing.py",
        "root_cause_line": 4,
        "hidden_bug": "total() sums raw values, so decimal strings from the billing feed raise "
                       "TypeError and integer prices are not mixed correctly.",
        "expected_behavior": "total(['1.5', '2.5']) returns 4.0; mixed ints and strings work.",
        "ground_truth_summary": "Convert every price to float before summing.",
        "files": {
            "src/billing.py": '''"""Billing totals."""


def total(prices):
    return sum(prices)
''',
            "tests/test_billing.py": '''from src.billing import total


def test_decimal_strings():
    assert total(["1.5", "2.5"]) == 4.0


def test_empty():
    assert total([]) == 0


def test_ints_and_strings():
    assert total([2, "3.5"]) == 5.5
''',
        },
        "fixed": {
            "src/billing.py": '''"""Billing totals."""


def total(prices):
    return sum(float(price) for price in prices)
''',
        },
        "oracle": '''from src.billing import total


def test_zero_string():
    assert total(["0"]) == 0.0


def test_negative():
    assert total([-1.5, "0.5"]) == -1.0


def test_whitespace():
    assert total([" 2 ", 3]) == 5.0


def test_single_value():
    assert total(["7.25"]) == 7.25
''',
    },
    {
        "id": "lookup-string-key",
        "name": "Lookup does not normalize string keys",
        "category": "type-errors",
        "difficulty": "medium",
        "root_cause_file": "src/lookup.py",
        "root_cause_line": 4,
        "hidden_bug": "lookup() indexes a dict with integer keys using the string form, raising "
                       "KeyError for feed ids that arrive as strings.",
        "expected_behavior": "lookup({1: 'a'}, '1') returns 'a'; an unknown key still raises.",
        "ground_truth_summary": "Try the key as given, then as an int, and re-raise KeyError.",
        "files": {
            "src/lookup.py": '''"""Record lookup."""


def lookup(data, key):
    return data[key]
''',
            "tests/test_lookup.py": '''import pytest

from src.lookup import lookup


def test_string_key_for_int_dict():
    assert lookup({1: "a"}, "1") == "a"


def test_int_key():
    assert lookup({1: "a"}, 1) == "a"


def test_missing_key():
    with pytest.raises(KeyError):
        lookup({1: "a"}, "2")
''',
        },
        "fixed": {
            "src/lookup.py": '''"""Record lookup."""


def lookup(data, key):
    if key in data:
        return data[key]
    try:
        return data[int(key)]
    except (TypeError, ValueError):
        raise KeyError(key)
''',
        },
        "oracle": '''import pytest

from src.lookup import lookup


def test_string_key_for_string_dict():
    assert lookup({"a": 1}, "a") == 1


def test_non_numeric_key():
    with pytest.raises(KeyError):
        lookup({1: "a"}, "name")


def test_none_key():
    with pytest.raises(KeyError):
        lookup({1: "a"}, None)


def test_zero_key():
    assert lookup({0: "zero"}, "0") == "zero"
''',
    },
    {
        "id": "sort-mixed-scores",
        "name": "Score sorter cannot compare ints and strings",
        "category": "type-errors",
        "difficulty": "medium",
        "root_cause_file": "src/scores.py",
        "root_cause_line": 4,
        "hidden_bug": "sorted_scores() calls sorted() on a mixed list of ints and numeric strings, "
                       "which raises TypeError in Python 3.",
        "expected_behavior": "Mixed scores sort numerically while preserving their original values.",
        "ground_truth_summary": "Sort with a float-converting key.",
        "files": {
            "src/scores.py": '''"""Score ordering."""


def sorted_scores(scores):
    return sorted(scores)
''',
            "tests/test_scores.py": '''from src.scores import sorted_scores


def test_mixed_types():
    assert sorted_scores([90, "85", 70]) == [70, "85", 90]


def test_all_ints():
    assert sorted_scores([3, 1, 2]) == [1, 2, 3]


def test_empty():
    assert sorted_scores([]) == []
''',
        },
        "fixed": {
            "src/scores.py": '''"""Score ordering."""


def sorted_scores(scores):
    return sorted(scores, key=lambda value: float(value))
''',
        },
        "oracle": '''from src.scores import sorted_scores


def test_all_strings():
    assert sorted_scores(["10", "2", "1"]) == ["1", "2", "10"]


def test_decimal_strings():
    assert sorted_scores(["2.5", 2, "1.5"]) == ["1.5", 2, "2.5"]


def test_negative_strings():
    assert sorted_scores(["-1", 0, "-2"]) == ["-2", "-1", 0]


def test_stability_for_equal_values():
    assert sorted_scores(["2", 2]) == ["2", 2]
''',
    },
]
