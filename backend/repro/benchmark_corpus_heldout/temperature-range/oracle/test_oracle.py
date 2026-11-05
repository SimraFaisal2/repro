from src.climate import in_range


def test_lower_bound():
    assert in_range(-40) is True


def test_upper_bound():
    assert in_range(125) is True


def test_just_outside():
    assert in_range(-41) is False
    assert in_range(126) is False


def test_zero():
    assert in_range(0) is True
