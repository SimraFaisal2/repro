"""Traffic light state machine. The green -> red transition skips the
required yellow state."""


class TrafficLight:
    def __init__(self):
        self.state = "green"

    def next(self):
        if self.state == "green":
            self.state = "red"
        elif self.state == "red":
            self.state = "green"
