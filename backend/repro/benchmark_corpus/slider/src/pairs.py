"""Sliding-window helper with an off-by-one bug.

`consecutive_pairs()` iterates over every index of the sequence but
reads `xs[i + 1]` inside the body — an IndexError on the last element.
"""


def consecutive_pairs(xs):
    """Return adjacent pairs, e.g. [1,2,3] -> [(1,2),(2,3)]."""
    pairs = []
    for i in range(len(xs)):
        pairs.append((xs[i], xs[i + 1]))
    return pairs
