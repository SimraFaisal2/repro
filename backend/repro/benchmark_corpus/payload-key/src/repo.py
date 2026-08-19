"""Repository listing built against an old JSON field name.

The API response now carries the list under `items`, but the code still
reads `payload["results"]` — a KeyError at runtime.
"""


class RepoService:
    def __init__(self, client):
        self.client = client

    def list_repos(self):
        payload = self.client.get("/repos")
        return [r["full_name"] for r in payload["results"]]
