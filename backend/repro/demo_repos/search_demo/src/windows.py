"""Demo fixture: off-by-one bug.

`sliding_pairs()` walks every index of the sequence but reads `i + 1`,
which runs past the end on the final iteration.
"""


def sliding_pairs(xs):
    """Return consecutive pairs, e.g. [1,2,3] -> [(1,2),(2,3)]."""
    pairs = []
    for i in range(len(xs)):
        pairs.append((xs[i], xs[i + 1]))
    return pairs
