from src.switch import Switch


def test_three_presses():
    switch = Switch()
    switch.press()
    switch.press()
    assert switch.press() is True


def test_state_matches_return():
    switch = Switch()
    result = switch.press()
    assert switch.on is result


def test_two_switches_are_independent():
    first, second = Switch(), Switch()
    first.press()
    assert second.on is False


def test_press_returns_bool():
    assert isinstance(Switch().press(), bool)
