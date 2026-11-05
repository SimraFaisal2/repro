"""HTTP fetch helper."""


class FetchError(Exception):
    """Raised by the client on a failed request."""


def fetch(client):
    try:
        return client.get()
    except Exception:
        return None
