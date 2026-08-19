from src.repo import RepoService


class FakeClient:
    def get(self, url):
        return {"items": [{"full_name": "user/repo-a"}, {"full_name": "user/repo-b"}]}


def test_list_repos():
    service = RepoService(FakeClient())
    assert service.list_repos() == ["user/repo-a", "user/repo-b"]
