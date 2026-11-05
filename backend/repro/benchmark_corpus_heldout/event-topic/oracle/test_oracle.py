from src.events import TOPIC, Bus
from src.handlers import register


def test_two_events():
    bus = Bus()
    received = []
    register(bus)
    bus.publish(TOPIC, received)
    bus.publish(TOPIC, received)
    assert received == ["handled", "handled"]


def test_payload_is_passed_through():
    bus = Bus()
    received = []
    register(bus)
    bus.publish(TOPIC, received)
    assert received[-1] == "handled"


def test_other_subscribers_still_work():
    bus = Bus()
    received = []
    bus.subscribe("other", lambda payload: payload.append("other"))
    register(bus)
    bus.publish("other", received)
    assert received == ["other"]


def test_no_subscribers_is_safe():
    Bus().publish(TOPIC, [])
