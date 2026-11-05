from src.auth import valid_password


def test_empty():
    assert valid_password("") is False


def test_unicode_length():
    assert valid_password("pässwörd") is True


def test_no_whitespace_stripping():
    assert valid_password("        ") is True


def test_one_character():
    assert valid_password("x") is False
