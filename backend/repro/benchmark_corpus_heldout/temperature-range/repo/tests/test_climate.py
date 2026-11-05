from src.climate import in_range


def test_normal():
    assert in_range(20) is True


def test_too_hot():
    assert in_range(150) is False


def test_too_cold():
    assert in_range(-50) is False
