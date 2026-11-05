"""Adjacent-pair sums."""


def pair_sums(values):
    return [values[i] + values[i + 1] for i in range(len(values))]
