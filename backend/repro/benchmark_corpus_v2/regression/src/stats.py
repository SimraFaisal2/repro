"""Statistics helpers. A refactor removed the empty-input guard, so
average([]) now divides by zero — a regression of a previously-handled
edge case."""


def average(values):
    return sum(values) / len(values)
