"""Split a sequence into fixed-size chunks."""


def chunks(values, size):
    if size <= 0:
        raise ValueError("size must be positive")
    return [values[i:i + size - 1] for i in range(0, len(values), size)]
