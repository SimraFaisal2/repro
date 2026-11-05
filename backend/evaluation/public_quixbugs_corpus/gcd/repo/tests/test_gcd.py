import pytest

from src.gcd import gcd

CASES = [[[17, 0], 17], [[13, 13], 13], [[37, 600], 1], [[20, 100], 20], [[624129, 2061517], 18913], [[3, 12], 3]]


@pytest.mark.parametrize('args,expected', CASES)
def test_gcd(args, expected):
    assert gcd(*args) == expected
