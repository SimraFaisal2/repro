import pytest

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
