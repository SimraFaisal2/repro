"""Held-out None-handling cases (5)."""

CASES = [
    {
        "id": "profile-city",
        "name": "Missing address crashes profile lookup",
        "category": "none-handling",
        "difficulty": "easy",
        "root_cause_file": "src/profile.py",
        "root_cause_line": 4,
        "hidden_bug": "city() indexes user['address']['city'] without allowing a missing or "
                       "null address.",
        "expected_behavior": "A user without an address, or with a null city, returns 'unknown'.",
        "ground_truth_summary": "Guard the address lookup and default to 'unknown'.",
        "files": {
            "src/profile.py": '''"""Profile display helpers."""


def city(user):
    return user["address"]["city"]
''',
            "tests/test_profile.py": '''from src.profile import city


def test_present_address():
    assert city({"address": {"city": "Berlin"}}) == "Berlin"


def test_missing_address():
    assert city({"name": "Ada"}) == "unknown"


def test_null_address():
    assert city({"address": None}) == "unknown"
''',
        },
        "fixed": {
            "src/profile.py": '''"""Profile display helpers."""


def city(user):
    address = user.get("address")
    if not address:
        return "unknown"
    return address.get("city") or "unknown"
''',
        },
        "oracle": '''from src.profile import city


def test_empty_city():
    assert city({"address": {"city": ""}}) == "unknown"


def test_null_city():
    assert city({"address": {"city": None}}) == "unknown"


def test_empty_user():
    assert city({}) == "unknown"


def test_does_not_mutate_input():
    user = {"address": {"city": "Paris"}}
    city(user)
    assert user == {"address": {"city": "Paris"}}
''',
    },
    {
        "id": "average-nonnull",
        "name": "Average divides by the wrong count when values are null",
        "category": "none-handling",
        "difficulty": "medium",
        "root_cause_file": "src/stats.py",
        "root_cause_line": 4,
        "hidden_bug": "average() sums with None values in the list and divides by the original "
                       "length instead of ignoring missing readings; an empty list divides by zero.",
        "expected_behavior": "average([1, None, 3]) is 2.0 and average([]) is 0.0.",
        "ground_truth_summary": "Filter None, return 0.0 when nothing remains.",
        "files": {
            "src/stats.py": '''"""Summary statistics."""


def average(values):
    return sum(values) / len(values)
''',
            "tests/test_stats.py": '''from src.stats import average


def test_ignores_null():
    assert average([1, None, 3]) == 2.0


def test_empty():
    assert average([]) == 0.0


def test_plain_values():
    assert average([2, 4]) == 3.0
''',
        },
        "fixed": {
            "src/stats.py": '''"""Summary statistics."""


def average(values):
    present = [value for value in values if value is not None]
    if not present:
        return 0.0
    return sum(present) / len(present)
''',
        },
        "oracle": '''from src.stats import average


def test_all_null():
    assert average([None, None]) == 0.0


def test_single_value():
    assert average([7]) == 7.0


def test_zero_is_not_null():
    assert average([0, None, 2]) == 1.0


def test_negative_values():
    assert average([-2, None, -4]) == -3.0
''',
    },
    {
        "id": "timeout-default",
        "name": "Explicit null timeout bypasses the default",
        "category": "none-handling",
        "difficulty": "medium",
        "root_cause_file": "src/config.py",
        "root_cause_line": 4,
        "hidden_bug": "timeout() uses dict.get(key, default), which returns None when the key "
                       "exists with a null value; callers then get None instead of 30.",
        "expected_behavior": "A missing or null timeout returns 30; an explicit 0 is preserved.",
        "ground_truth_summary": "Check for None explicitly rather than relying on the get default.",
        "files": {
            "src/config.py": '''"""Runtime configuration helpers."""


def timeout(config):
    return config.get("timeout", 30)
''',
            "tests/test_config.py": '''from src.config import timeout


def test_missing():
    assert timeout({}) == 30


def test_null():
    assert timeout({"timeout": None}) == 30


def test_explicit_zero():
    assert timeout({"timeout": 0}) == 0
''',
        },
        "fixed": {
            "src/config.py": '''"""Runtime configuration helpers."""


def timeout(config):
    value = config.get("timeout")
    return 30 if value is None else value
''',
        },
        "oracle": '''from src.config import timeout


def test_explicit_value():
    assert timeout({"timeout": 5}) == 5


def test_negative_value_is_preserved():
    assert timeout({"timeout": -1}) == -1


def test_other_keys_ignored():
    assert timeout({"retries": 3}) == 30


def test_false_is_preserved():
    assert timeout({"timeout": False}) is False
''',
    },
    {
        "id": "customer-name",
        "name": "Guest orders crash on the customer name",
        "category": "none-handling",
        "difficulty": "easy",
        "root_cause_file": "src/orders.py",
        "root_cause_line": 12,
        "hidden_bug": "customer_name() dereferences order.customer.name without handling a "
                       "null customer.",
        "expected_behavior": "An order with no customer returns 'guest'; a customer with no "
                            "name also returns 'guest'.",
        "ground_truth_summary": "Guard the customer and name lookups.",
        "files": {
            "src/orders.py": '''"""Order display helpers."""


class Customer:
    def __init__(self, name):
        self.name = name


class Order:
    def __init__(self, customer):
        self.customer = customer


def customer_name(order):
    return order.customer.name
''',
            "tests/test_orders.py": '''from src.orders import Customer, Order, customer_name


def test_named_customer():
    assert customer_name(Order(Customer("Ada"))) == "Ada"


def test_guest_order():
    assert customer_name(Order(None)) == "guest"


def test_unnamed_customer():
    assert customer_name(Order(Customer(None))) == "guest"
''',
        },
        "fixed": {
            "src/orders.py": '''"""Order display helpers."""


class Customer:
    def __init__(self, name):
        self.name = name


class Order:
    def __init__(self, customer):
        self.customer = customer


def customer_name(order):
    if order.customer is None or not order.customer.name:
        return "guest"
    return order.customer.name
''',
        },
        "oracle": '''from src.orders import Customer, Order, customer_name


def test_empty_name():
    assert customer_name(Order(Customer(""))) == "guest"


def test_whitespace_is_a_name():
    assert customer_name(Order(Customer(" "))) == " "


def test_order_without_customer_attribute():
    class Bare:
        customer = None

    assert customer_name(Bare()) == "guest"


def test_does_not_mutate():
    order = Order(Customer("Grace"))
    assert customer_name(order) == "Grace"
    assert order.customer.name == "Grace"
''',
    },
    {
        "id": "items-field",
        "name": "Null items payload is not normalized",
        "category": "none-handling",
        "difficulty": "easy",
        "root_cause_file": "src/payloads.py",
        "root_cause_line": 4,
        "hidden_bug": "items() indexes payload['items'], so a missing key raises KeyError and "
                       "a null value returns None instead of an empty list.",
        "expected_behavior": "A missing or null items field returns [].",
        "ground_truth_summary": "Use .get('items') or [].",
        "files": {
            "src/payloads.py": '''"""API payload normalization."""


def items(payload):
    return payload["items"]
''',
            "tests/test_payloads.py": '''from src.payloads import items


def test_present():
    assert items({"items": [1, 2]}) == [1, 2]


def test_missing():
    assert items({}) == []


def test_null():
    assert items({"items": None}) == []
''',
        },
        "fixed": {
            "src/payloads.py": '''"""API payload normalization."""


def items(payload):
    return payload.get("items") or []
''',
        },
        "oracle": '''from src.payloads import items


def test_empty_list():
    assert items({"items": []}) == []


def test_tuple_is_preserved():
    assert items({"items": (1, 2)}) == (1, 2)


def test_falsey_empty_string_becomes_list():
    assert items({"items": ""}) == []


def test_nested_payload():
    assert items({"items": [{"id": 1}]}) == [{"id": 1}]
''',
    },
]
