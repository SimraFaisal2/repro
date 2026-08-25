"""Eligibility rules. The boundary age must be included, but the check uses
a strict greater-than, rejecting users exactly at the boundary."""


def is_adult(age):
    return age > 18
