from src.profile import USERS, display_name


def test_display_name_known():
    assert display_name(USERS, 1) == "Ada"


def test_display_name_unknown():
    # regression: unknown id must not crash — returns None instead
    assert display_name(USERS, 999) is None
