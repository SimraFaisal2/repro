"""Maximum value in each sliding window."""


def max_windows(values, width):
    if width <= 0:
        raise ValueError("width must be positive")
    return [max(values[i:i + width]) for i in range(len(values) - width)]
