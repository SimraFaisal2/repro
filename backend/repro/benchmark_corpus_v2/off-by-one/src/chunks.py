"""Adjacent-pair sums. The comprehension walks every index of `values` and
reads `values[i + 1]`, so the final iteration is out of range."""


def adjacent_sum(values):
    return [values[i] + values[i + 1] for i in range(len(values))]
