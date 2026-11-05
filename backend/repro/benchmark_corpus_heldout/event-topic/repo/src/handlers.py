"""Event handlers."""


def register(bus):
    bus.subscribe("user-created", lambda payload: payload.append("handled"))
