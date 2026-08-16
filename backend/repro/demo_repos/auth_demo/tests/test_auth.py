from src.auth import USERS, login


def test_login_known_user():
    result = login(USERS, "alice", "secret-alice")
    assert result is not None
    assert result["user"] == "alice"


def test_login_wrong_password():
    assert login(USERS, "alice", "nope") is None


def test_login_unknown_user():
    assert login(USERS, "ghost", "x") is None
