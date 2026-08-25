"""Threaded counter. The increment is an unlocked read-modify-write: it
reads the current value, does a little work (which releases the GIL), then
writes the result back. Two threads can both read the same value and both
write it back, losing one increment each time — a classic race."""
import time


class Counter:
    def __init__(self):
        self.value = 0

    def increment(self):
        current = self.value
        time.sleep(0.00005)  # releases the GIL — widens the race window
        self.value = current + 1
