from src.pricing import discount


def test_exact_threshold():
    assert discount(100) == 90.0


def test_below_threshold():
    assert discount(50) == 50


def test_above_threshold():
    assert discount(150) == 135.0
