"""Order discount calculation."""


def discount(total):
    if total > 100:
        return round(total * 0.9, 2)
    return total
