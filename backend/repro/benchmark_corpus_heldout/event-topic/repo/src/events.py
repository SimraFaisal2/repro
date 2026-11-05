"""Tiny synchronous event bus."""

TOPIC = "user.created"


class Bus:
    def __init__(self):
        self.subscribers = {}

    def subscribe(self, topic, handler):
        self.subscribers.setdefault(topic, []).append(handler)

    def publish(self, topic, payload):
        for handler in list(self.subscribers.get(topic, [])):
            handler(payload)
