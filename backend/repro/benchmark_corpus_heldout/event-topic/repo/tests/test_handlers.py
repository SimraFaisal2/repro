from src.events import TOPIC, Bus
from src.handlers import register


def test_handler_receives_event():
    bus = Bus()
    received = []
    register(bus)
    bus.publish(TOPIC, received)
    assert received == ["handled"]


def test_unrelated_topic_is_ignored():
    bus = Bus()
    received = []
    register(bus)
    bus.publish("other", received)
    assert received == []
