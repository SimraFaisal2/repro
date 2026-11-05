"""Retry policy."""


def can_retry(attempts, limit):
    return attempts > limit
