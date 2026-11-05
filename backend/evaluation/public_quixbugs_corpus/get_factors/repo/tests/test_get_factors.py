import pytest

from src.get_factors import get_factors

CASES = [[[1], []], [[100], [2, 2, 5, 5]], [[101], [101]], [[104], [2, 2, 2, 13]], [[2], [2]], [[3], [3]], [[17], [17]], [[63], [3, 3, 7]], [[74], [2, 37]], [[73], [73]], [[9837], [3, 3, 1093]]]


@pytest.mark.parametrize('args,expected', CASES)
def test_get_factors(args, expected):
    assert get_factors(*args) == expected
