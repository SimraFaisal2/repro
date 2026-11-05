import pytest

from src.powerset import powerset

CASES = [[[['a', 'b', 'c']], [[], ['c'], ['b'], ['b', 'c'], ['a'], ['a', 'c'], ['a', 'b'], ['a', 'b', 'c']]], [[['a', 'b']], [[], ['b'], ['a'], ['a', 'b']]], [[['a']], [[], ['a']]], [[[]], [[]]], [[['x', 'df', 'z', 'm']], [[], ['m'], ['z'], ['z', 'm'], ['df'], ['df', 'm'], ['df', 'z'], ['df', 'z', 'm'], ['x'], ['x', 'm'], ['x', 'z'], ['x', 'z', 'm'], ['x', 'df'], ['x', 'df', 'm'], ['x', 'df', 'z'], ['x', 'df', 'z', 'm']]]]


@pytest.mark.parametrize('args,expected', CASES)
def test_powerset(args, expected):
    assert powerset(*args) == expected
