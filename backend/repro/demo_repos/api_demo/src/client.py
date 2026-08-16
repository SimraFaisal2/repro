"""Demo fixture: incorrect API response handling.

`fetch_users()` reads `data["results"]` but the API returns the list
under the key `"data"` — a response-shape mismatch.
"""


class UserFetcher:
    def __init__(self, session):
        self.session = session

    def fetch_users(self):
        resp = self.session.get("/users")
        data = resp.json()
        return [u["name"] for u in data["results"]]
