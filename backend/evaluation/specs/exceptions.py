"""Held-out exception/error-handling cases (5)."""

CASES = [
    {
        "id": "fetch-swallow",
        "name": "Fetch helper converts every failure into None",
        "category": "exception-handling",
        "difficulty": "easy",
        "root_cause_file": "src/fetch.py",
        "root_cause_line": 9,
        "hidden_bug": "fetch() catches every exception and returns None, so callers cannot "
                       "distinguish a missing value from a broken client.",
        "expected_behavior": "Client errors propagate; a successful response is returned unchanged.",
        "ground_truth_summary": "Remove the broad except and let the client exception propagate.",
        "files": {
            "src/fetch.py": '''"""HTTP fetch helper."""


class FetchError(Exception):
    """Raised by the client on a failed request."""


def fetch(client):
    try:
        return client.get()
    except Exception:
        return None
''',
            "tests/test_fetch.py": '''import pytest

from src.fetch import FetchError, fetch


class Broken:
    def get(self):
        raise FetchError("backend down")


class Good:
    def get(self):
        return {"ok": True}


def test_propagates_client_error():
    with pytest.raises(FetchError):
        fetch(Broken())


def test_returns_success():
    assert fetch(Good()) == {"ok": True}
''',
        },
        "fixed": {
            "src/fetch.py": '''"""HTTP fetch helper."""


class FetchError(Exception):
    """Raised by the client on a failed request."""


def fetch(client):
    return client.get()
''',
        },
        "oracle": '''import pytest

from src.fetch import FetchError, fetch


class OtherError(Exception):
    pass


class OtherBroken:
    def get(self):
        raise OtherError("different failure")


def test_other_exceptions_also_propagate():
    with pytest.raises(OtherError):
        fetch(OtherBroken())


def test_none_is_a_valid_response():
    class NoneClient:
        def get(self):
            return None

    assert fetch(NoneClient()) is None


def test_exception_message_is_preserved():
    class Client:
        def get(self):
            raise FetchError("specific message")

    with pytest.raises(FetchError, match="specific message"):
        fetch(Client())


def test_client_is_called_once():
    calls = []

    class Client:
        def get(self):
            calls.append(1)
            return "ok"

    assert fetch(Client()) == "ok"
    assert calls == [1]
''',
    },
    {
        "id": "parse-int-swallow",
        "name": "Integer parser hides invalid input as zero",
        "category": "exception-handling",
        "difficulty": "easy",
        "root_cause_file": "src/parse.py",
        "root_cause_line": 7,
        "hidden_bug": "parse() catches ValueError and returns 0, so malformed input silently "
                       "becomes a valid zero instead of raising.",
        "expected_behavior": "parse('x') raises ValueError; parse('3') returns 3.",
        "ground_truth_summary": "Remove the except and let int() raise.",
        "files": {
            "src/parse.py": '''"""Integer parsing helper."""


def parse(text):
    try:
        return int(text)
    except ValueError:
        return 0
''',
            "tests/test_parse.py": '''import pytest

from src.parse import parse


def test_invalid_raises():
    with pytest.raises(ValueError):
        parse("x")


def test_valid():
    assert parse("3") == 3


def test_whitespace():
    assert parse(" 4 ") == 4
''',
        },
        "fixed": {
            "src/parse.py": '''"""Integer parsing helper."""


def parse(text):
    return int(text)
''',
        },
        "oracle": '''import pytest

from src.parse import parse


def test_none_raises_type_error():
    with pytest.raises(TypeError):
        parse(None)


def test_empty_raises():
    with pytest.raises(ValueError):
        parse("")


def test_negative():
    assert parse("-7") == -7


def test_float_string_raises():
    with pytest.raises(ValueError):
        parse("3.5")
''',
    },
    {
        "id": "ratio-swallow",
        "name": "Ratio helper turns division by zero into zero",
        "category": "exception-handling",
        "difficulty": "easy",
        "root_cause_file": "src/ratio.py",
        "root_cause_line": 7,
        "hidden_bug": "ratio() catches ZeroDivisionError and returns 0, hiding an invalid "
                       "denominator instead of letting the error reach the caller.",
        "expected_behavior": "A zero denominator raises ZeroDivisionError; normal division works.",
        "ground_truth_summary": "Remove the exception handler.",
        "files": {
            "src/ratio.py": '''"""Ratio helper."""


def ratio(numerator, denominator):
    try:
        return numerator / denominator
    except ZeroDivisionError:
        return 0
''',
            "tests/test_ratio.py": '''import pytest

from src.ratio import ratio


def test_zero_denominator_raises():
    with pytest.raises(ZeroDivisionError):
        ratio(1, 0)


def test_normal_division():
    assert ratio(6, 3) == 2


def test_float_division():
    assert ratio(1, 4) == 0.25
''',
        },
        "fixed": {
            "src/ratio.py": '''"""Ratio helper."""


def ratio(numerator, denominator):
    return numerator / denominator
''',
        },
        "oracle": '''import pytest

from src.ratio import ratio


def test_negative_numerator():
    assert ratio(-6, 3) == -2


def test_negative_denominator():
    assert ratio(6, -3) == -2


def test_zero_numerator():
    assert ratio(0, 5) == 0


def test_zero_over_zero_raises():
    with pytest.raises(ZeroDivisionError):
        ratio(0, 0)
''',
    },
    {
        "id": "transaction-partial",
        "name": "Failed transaction leaves earlier items committed",
        "category": "exception-handling",
        "difficulty": "medium",
        "root_cause_file": "src/store.py",
        "root_cause_line": 9,
        "hidden_bug": "Store.add_all() appends items one by one before validating the whole "
                       "batch, so an invalid item leaves a partial commit behind.",
        "expected_behavior": "If any item is None, add_all raises and the store is unchanged.",
        "ground_truth_summary": "Validate the full batch before mutating the store.",
        "files": {
            "src/store.py": '''"""Batch store writes."""


class Store:
    def __init__(self):
        self.items = []

    def add_all(self, items):
        for item in items:
            if item is None:
                raise ValueError("null item")
            self.items.append(item)
''',
            "tests/test_store.py": '''import pytest

from src.store import Store


def test_failed_batch_is_atomic():
    store = Store()
    with pytest.raises(ValueError):
        store.add_all([1, None, 2])
    assert store.items == []


def test_valid_batch():
    store = Store()
    store.add_all([1, 2])
    assert store.items == [1, 2]


def test_empty_batch():
    store = Store()
    store.add_all([])
    assert store.items == []
''',
        },
        "fixed": {
            "src/store.py": '''"""Batch store writes."""


class Store:
    def __init__(self):
        self.items = []

    def add_all(self, items):
        if any(item is None for item in items):
            raise ValueError("null item")
        self.items.extend(items)
''',
        },
        "oracle": '''import pytest

from src.store import Store


def test_first_item_null():
    store = Store()
    with pytest.raises(ValueError):
        store.add_all([None, 1])
    assert store.items == []


def test_existing_items_survive_failed_batch():
    store = Store()
    store.add_all([1])
    with pytest.raises(ValueError):
        store.add_all([2, None])
    assert store.items == [1]


def test_multiple_valid_batches():
    store = Store()
    store.add_all([1, 2])
    store.add_all([3])
    assert store.items == [1, 2, 3]


def test_tuple_batch():
    store = Store()
    store.add_all((1, 2))
    assert store.items == [1, 2]
''',
    },
    {
        "id": "parse-users-skip",
        "name": "User parser silently skips malformed rows",
        "category": "exception-handling",
        "difficulty": "medium",
        "root_cause_file": "src/users.py",
        "root_cause_line": 8,
        "hidden_bug": "parse_users() catches KeyError and continues, so a missing name silently "
                       "drops a user instead of failing the import.",
        "expected_behavior": "A row without name raises ValueError; valid rows are returned.",
        "ground_truth_summary": "Validate the name field and raise ValueError instead of skipping.",
        "files": {
            "src/users.py": '''"""User import parsing."""


def parse_users(rows):
    parsed = []
    for row in rows:
        try:
            parsed.append({"name": row["name"]})
        except KeyError:
            continue
    return parsed
''',
            "tests/test_users.py": '''import pytest

from src.users import parse_users


def test_missing_name_raises():
    with pytest.raises(ValueError):
        parse_users([{"id": 1}])


def test_valid_rows():
    assert parse_users([{"name": "Ada"}]) == [{"name": "Ada"}]


def test_empty():
    assert parse_users([]) == []
''',
        },
        "fixed": {
            "src/users.py": '''"""User import parsing."""


def parse_users(rows):
    parsed = []
    for row in rows:
        if "name" not in row:
            raise ValueError("missing name")
        parsed.append({"name": row["name"]})
    return parsed
''',
        },
        "oracle": '''import pytest

from src.users import parse_users


def test_error_after_valid_row_is_not_partial_success():
    with pytest.raises(ValueError):
        parse_users([{"name": "Ada"}, {"id": 2}])


def test_none_name_is_preserved():
    assert parse_users([{"name": None}]) == [{"name": None}]


def test_empty_name_is_preserved():
    assert parse_users([{"name": ""}]) == [{"name": ""}]


def test_multiple_valid_rows():
    assert parse_users([{"name": "Ada"}, {"name": "Grace"}]) == [
        {"name": "Ada"},
        {"name": "Grace"},
    ]
''',
    },
]
