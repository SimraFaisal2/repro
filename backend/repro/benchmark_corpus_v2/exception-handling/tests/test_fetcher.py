import pytest

from src.fetcher import fetch_json


class FlakyClient:
    def __init__(self, payload=None):
        self.payload = payload

    def get(self, url):
        if self.payload is None:
            raise ValueError("backend exploded")
        return self.payload


def test_fetch_propagates_errors():
    client = FlakyClient()
    # a real failure must propagate, not be silently swallowed into None
    with pytest.raises(ValueError):
        fetch_json(client, "/data")


def test_fetch_ok():
    client = FlakyClient(payload={"ok": True})
    assert fetch_json(client, "/data") == {"ok": True}
