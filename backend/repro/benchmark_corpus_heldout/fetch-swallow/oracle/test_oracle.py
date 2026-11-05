import pytest

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
