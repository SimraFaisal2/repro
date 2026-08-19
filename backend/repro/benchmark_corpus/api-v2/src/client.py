"""Twitter-style API client written against the old response shape.

The endpoint now returns v2 JSON where the list lives under `data`,
but the client still reads `payload["results"]` — a KeyError.
"""


class ApiClient:
    def __init__(self, session):
        self.session = session

    def fetch_tweets(self):
        payload = self.session.get("/2/tweets")
        return [t["text"] for t in payload["results"]]
