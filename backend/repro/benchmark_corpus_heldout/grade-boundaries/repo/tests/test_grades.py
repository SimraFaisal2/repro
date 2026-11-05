from src.grades import grade


def test_ninety():
    assert grade(90) == "A"


def test_eighty():
    assert grade(80) == "B"


def test_seventy():
    assert grade(70) == "C"


def test_sixty_nine():
    assert grade(69) == "F"
