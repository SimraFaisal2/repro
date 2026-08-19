from src.auth import USERS, authenticate


def test_authenticate_correct_password():
    assert authenticate(USERS, "alice", "hunter2") is True


def test_authenticate_wrong_password():
    assert authenticate(USERS, "alice", "wrong") is False
