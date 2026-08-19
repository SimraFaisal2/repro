from src.session import Session, User, current_email


def test_email_for_signed_in_user():
    s = Session(User("ada@example.com"))
    assert current_email(s) == "ada@example.com"


def test_email_for_anonymous_session():
    # regression: anonymous sessions must not crash — returns None
    assert current_email(Session()) is None
