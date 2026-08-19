from src.client import ApiClient


class FakeSession:
    """Stands in for an HTTP session; returns the real (v2) payload shape."""

    def get(self, url):
        return {"data": [{"text": "hello"}, {"text": "world"}]}


def test_fetch_tweets():
    client = ApiClient(FakeSession())
    assert client.fetch_tweets() == ["hello", "world"]
