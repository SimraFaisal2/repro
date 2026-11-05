from src.quantity import quantity


def test_zero():
    assert quantity("0 boxes") == 0


def test_negative():
    assert quantity("-2 refunds") == -2


def test_tab_separator():
    assert quantity("3\titems") == 3


def test_number_with_plus():
    assert quantity("+4 units") == 4
