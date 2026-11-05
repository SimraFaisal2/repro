"""Held-out multi-file cases (5)."""

CASES = [
    {
        "id": "user-serializer",
        "name": "Serializer uses a field the model does not have",
        "category": "multi-file",
        "difficulty": "medium",
        "root_cause_file": "src/serializers.py",
        "root_cause_line": 4,
        "hidden_bug": "User.full_name() returns only the first name, and serialize() reads the "
                       "nonexistent user.name attribute, so profile serialization crashes.",
        "expected_behavior": "full_name() returns 'Ada Lovelace' and serialize() exposes it as name.",
        "ground_truth_summary": "Build the full name in the model and use full_name() in the serializer.",
        "files": {
            "src/models.py": '''"""Domain models."""


class User:
    def __init__(self, first, last):
        self.first = first
        self.last = last

    def full_name(self):
        return self.first
''',
            "src/serializers.py": '''"""API serializers."""


def serialize(user):
    return {"name": user.name}
''',
            "tests/test_serializers.py": '''from src.models import User
from src.serializers import serialize


def test_full_name():
    assert User("Ada", "Lovelace").full_name() == "Ada Lovelace"


def test_serialize_user():
    assert serialize(User("Ada", "Lovelace")) == {"name": "Ada Lovelace"}


def test_single_name():
    assert serialize(User("Prince", "")) == {"name": "Prince "}
''',
        },
        "fixed": {
            "src/models.py": '''"""Domain models."""


class User:
    def __init__(self, first, last):
        self.first = first
        self.last = last

    def full_name(self):
        return f"{self.first} {self.last}"
''',
            "src/serializers.py": '''"""API serializers."""


def serialize(user):
    return {"name": user.full_name()}
''',
        },
        "oracle": '''from src.models import User
from src.serializers import serialize


def test_unicode_name():
    assert serialize(User("Zoë", "Müller")) == {"name": "Zoë Müller"}


def test_full_name_does_not_mutate():
    user = User("Grace", "Hopper")
    assert user.full_name() == "Grace Hopper"
    assert user.first == "Grace"
    assert user.last == "Hopper"


def test_serialized_dict_is_fresh():
    user = User("Alan", "Turing")
    first = serialize(user)
    first["name"] = "changed"
    assert serialize(user)["name"] == "Alan Turing"


def test_names_with_spaces():
    assert serialize(User("Mary Ann", "Evans")) == {"name": "Mary Ann Evans"}
''',
    },
    {
        "id": "plugin-registry",
        "name": "Plugin registered under a name the manifest does not use",
        "category": "multi-file",
        "difficulty": "medium",
        "root_cause_file": "src/registry.py",
        "root_cause_line": 5,
        "hidden_bug": "The alpha plugin exports NAME='alpha-v1' but the registry hardcodes the "
                       "key 'alpha'; the plugin's run() also adds instead of doubles.",
        "expected_behavior": "The plugin is discoverable by its exported name and doubles its input.",
        "ground_truth_summary": "Register by NAME and fix the plugin's arithmetic.",
        "files": {
            "src/plugins/alpha.py": '''"""Alpha plugin."""

NAME = "alpha-v1"


def run(value):
    return value + 2
''',
            "src/registry.py": '''"""Plugin registry."""

from src.plugins.alpha import NAME, run

PLUGINS = {"alpha": run}


def get(name):
    return PLUGINS[name]
''',
            "tests/test_registry.py": '''from src.plugins.alpha import NAME
from src.registry import get


def test_lookup_by_exported_name():
    assert get(NAME) is not None


def test_plugin_doubles():
    assert get(NAME)(3) == 6


def test_unknown_plugin():
    import pytest

    with pytest.raises(KeyError):
        get("missing")
''',
        },
        "fixed": {
            "src/plugins/alpha.py": '''"""Alpha plugin."""

NAME = "alpha-v1"


def run(value):
    return value * 2
''',
            "src/registry.py": '''"""Plugin registry."""

from src.plugins.alpha import NAME, run

PLUGINS = {NAME: run}


def get(name):
    return PLUGINS[name]
''',
        },
        "oracle": '''import pytest

from src.plugins.alpha import NAME, run
from src.registry import get


def test_name_is_exported():
    assert NAME == "alpha-v1"


def test_zero():
    assert get(NAME)(0) == 0


def test_negative():
    assert get(NAME)(-4) == -8


def test_registry_contains_exact_name():
    with pytest.raises(KeyError):
        get("alpha")
''',
    },
    {
        "id": "checkout-tax",
        "name": "Checkout applies the tax rate as a flat surcharge",
        "category": "multi-file",
        "difficulty": "medium",
        "root_cause_file": "src/checkout.py",
        "root_cause_line": 6,
        "hidden_bug": "The configured tax rate is 20% instead of 10%, and checkout adds the rate "
                       "as a flat amount rather than multiplying the subtotal.",
        "expected_behavior": "A 100 subtotal with 10% tax totals 110.0.",
        "ground_truth_summary": "Set the rate to 0.1 and compute subtotal * (1 + rate).",
        "files": {
            "src/settings.py": '''"""Store settings."""

TAX_RATE = 0.2
''',
            "src/checkout.py": '''"""Checkout totals."""

from src.settings import TAX_RATE


def total(subtotal):
    return round(subtotal + TAX_RATE, 2)
''',
            "tests/test_checkout.py": '''from src.checkout import total


def test_standard_total():
    assert total(100) == 110.0


def test_zero_subtotal():
    assert total(0) == 0.0


def test_rounding():
    assert total(19.99) == 21.99
''',
        },
        "fixed": {
            "src/settings.py": '''"""Store settings."""

TAX_RATE = 0.1
''',
            "src/checkout.py": '''"""Checkout totals."""

from src.settings import TAX_RATE


def total(subtotal):
    return round(subtotal * (1 + TAX_RATE), 2)
''',
        },
        "oracle": '''from src.checkout import total


def test_large_subtotal():
    assert total(1000) == 1100.0


def test_small_subtotal():
    assert total(0.1) == 0.11


def test_decimal_rounding():
    assert total(12.34) == 13.57


def test_negative_subtotal():
    assert total(-10) == -11.0
''',
    },
    {
        "id": "event-topic",
        "name": "Handler subscribes to a misspelled topic",
        "category": "multi-file",
        "difficulty": "medium",
        "root_cause_file": "src/handlers.py",
        "root_cause_line": 6,
        "hidden_bug": "The event bus publishes to TOPIC='user.created' but the handler registers "
                       "for 'user-created', so no subscriber is ever called.",
        "expected_behavior": "Publishing TOPIC invokes the registered handler exactly once.",
        "ground_truth_summary": "Subscribe using the shared TOPIC constant.",
        "files": {
            "src/events.py": '''"""Tiny synchronous event bus."""

TOPIC = "user.created"


class Bus:
    def __init__(self):
        self.subscribers = {}

    def subscribe(self, topic, handler):
        self.subscribers.setdefault(topic, []).append(handler)

    def publish(self, topic, payload):
        for handler in list(self.subscribers.get(topic, [])):
            handler(payload)
''',
            "src/handlers.py": '''"""Event handlers."""


def register(bus):
    bus.subscribe("user-created", lambda payload: payload.append("handled"))
''',
            "tests/test_handlers.py": '''from src.events import TOPIC, Bus
from src.handlers import register


def test_handler_receives_event():
    bus = Bus()
    received = []
    register(bus)
    bus.publish(TOPIC, received)
    assert received == ["handled"]


def test_unrelated_topic_is_ignored():
    bus = Bus()
    received = []
    register(bus)
    bus.publish("other", received)
    assert received == []
''',
        },
        "fixed": {
            "src/handlers.py": '''"""Event handlers."""

from src.events import TOPIC


def register(bus):
    bus.subscribe(TOPIC, lambda payload: payload.append("handled"))
''',
        },
        "oracle": '''from src.events import TOPIC, Bus
from src.handlers import register


def test_two_events():
    bus = Bus()
    received = []
    register(bus)
    bus.publish(TOPIC, received)
    bus.publish(TOPIC, received)
    assert received == ["handled", "handled"]


def test_payload_is_passed_through():
    bus = Bus()
    received = []
    register(bus)
    bus.publish(TOPIC, received)
    assert received[-1] == "handled"


def test_other_subscribers_still_work():
    bus = Bus()
    received = []
    bus.subscribe("other", lambda payload: payload.append("other"))
    register(bus)
    bus.publish("other", received)
    assert received == ["other"]


def test_no_subscribers_is_safe():
    Bus().publish(TOPIC, [])
''',
    },
    {
        "id": "repository-field",
        "name": "Repository reads a renamed model field",
        "category": "multi-file",
        "difficulty": "medium",
        "root_cause_file": "src/repository.py",
        "root_cause_line": 5,
        "hidden_bug": "The User model stores the address as email_address, but the repository's "
                       "email_of() still reads the old 'email' key and raises KeyError.",
        "expected_behavior": "email_of() reads email_address from a serialized user.",
        "ground_truth_summary": "Read the renamed field in the repository.",
        "files": {
            "src/models.py": '''"""User model."""


class User:
    def __init__(self, name, email_address):
        self.name = name
        self.email_address = email_address

    def as_dict(self):
        return {"name": self.name, "email_address": self.email_address}
''',
            "src/repository.py": '''"""User repository helpers."""


def email_of(row):
    return row["email"]
''',
            "tests/test_repository.py": '''from src.models import User
from src.repository import email_of


def test_reads_renamed_field():
    assert email_of(User("Ada", "ada@example.com").as_dict()) == "ada@example.com"


def test_missing_field():
    import pytest

    with pytest.raises(KeyError):
        email_of({"name": "Ada"})
''',
        },
        "fixed": {
            "src/repository.py": '''"""User repository helpers."""


def email_of(row):
    return row["email_address"]
''',
        },
        "oracle": '''import pytest

from src.models import User
from src.repository import email_of


def test_user_roundtrip():
    user = User("Grace", "grace@example.com")
    assert email_of(user.as_dict()) == "grace@example.com"


def test_empty_email():
    assert email_of({"email_address": ""}) == ""


def test_none_email_is_preserved():
    assert email_of({"email_address": None}) is None


def test_empty_row_raises():
    with pytest.raises(KeyError):
        email_of({})
''',
    },
]
