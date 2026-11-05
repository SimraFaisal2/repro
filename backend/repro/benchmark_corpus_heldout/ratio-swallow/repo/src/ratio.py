"""Ratio helper."""


def ratio(numerator, denominator):
    try:
        return numerator / denominator
    except ZeroDivisionError:
        return 0
