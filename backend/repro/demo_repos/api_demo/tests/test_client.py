from src.client import UserFetcher


class FakeSession:
    """Stands in for an HTTP session; returns the real API response shape."""

    def get(self, url):
        return self

    def json(self):
        return {"data": [{"name": "Ada"}, {"name": "Grace"}, {"name": "Alan"}]}


def test_fetch_users():
    fetcher = UserFetcher(FakeSession())
    users = fetcher.fetch_users()
    assert users == ["Ada", "Grace", "Alan"]
