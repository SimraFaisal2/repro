"""Time-series helper with an off-by-one bug.

`adjacent_deltas()` walks `range(len(values))` but reads
`values[i + 1]` inside the body — IndexError on the last element.
"""


def adjacent_deltas(values):
    """Return differences between neighbours, e.g. [10,12,17] -> [2,5]."""
    out = []
    for i in range(len(values)):
        out.append(values[i + 1] - values[i])
    return out
