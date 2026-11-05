from src.quantity import quantity


def test_with_units():
    assert quantity("3 items") == 3


def test_bare_number():
    assert quantity("7") == 7


def test_surrounding_spaces():
    assert quantity(" 12 ") == 12
