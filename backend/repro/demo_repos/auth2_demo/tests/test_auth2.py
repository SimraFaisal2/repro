from src.auth2 import USERS, authenticate


def test_authenticate_ok():
    assert authenticate(USERS, "alice", "hunter2") is True


def test_authenticate_wrong():
    assert authenticate(USERS, "alice", "wrong") is False
