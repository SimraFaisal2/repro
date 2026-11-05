import pytest

from src.to_base import to_base

CASES = [[[8227, 18], '1771'], [[73, 8], '111'], [[16, 19], 'G'], [[31, 16], '1F'], [[41, 2], '101001'], [[44, 5], '134'], [[27, 23], '14'], [[56, 23], '2A'], [[8237, 24], 'E75'], [[8237, 34], '749']]


@pytest.mark.parametrize('args,expected', CASES)
def test_to_base(args, expected):
    assert to_base(*args) == expected
