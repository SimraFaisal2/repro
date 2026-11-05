from src.switch import Switch


def test_first_press_turns_on():
    assert Switch().press() is True


def test_second_press_turns_off():
    switch = Switch()
    switch.press()
    assert switch.press() is False


def test_initial_state():
    assert Switch().on is False
