from src.eligibility import is_adult


def test_boundary_is_adult():
    # boundary age (18) must be included
    assert is_adult(18) is True


def test_clearly_adult():
    assert is_adult(21) is True
    assert is_adult(17) is False
