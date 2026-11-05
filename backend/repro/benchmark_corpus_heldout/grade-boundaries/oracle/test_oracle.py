from src.grades import grade


def test_perfect():
    assert grade(100) == "A"


def test_just_below_a():
    assert grade(89.9) == "B"


def test_just_below_b():
    assert grade(79.9) == "C"


def test_just_below_c():
    assert grade(69.9) == "F"


def test_zero():
    assert grade(0) == "F"
