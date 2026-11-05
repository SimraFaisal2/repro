import pytest

from src.is_valid_parenthesization import is_valid_parenthesization

CASES = [[['((()()))()'], True], [[')()('], False], [['(('], False]]


@pytest.mark.parametrize('args,expected', CASES)
def test_is_valid_parenthesization(args, expected):
    assert is_valid_parenthesization(*args) == expected
