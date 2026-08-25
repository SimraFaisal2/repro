from src.light import TrafficLight


def test_cycle_includes_yellow():
    light = TrafficLight()
    seen = []
    for _ in range(3):
        seen.append(light.state)
        light.next()
    assert seen == ["green", "yellow", "red"]


def test_starts_green():
    assert TrafficLight().state == "green"
