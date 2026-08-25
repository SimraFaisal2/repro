"""JSON fetch helper. A broad except converts every failure into None,
hiding real errors from callers."""


def fetch_json(client, url):
    try:
        return client.get(url)
    except Exception:
        return None
