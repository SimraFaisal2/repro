import pytest

from src.account import Account


def test_withdraw_once():
    account = Account(100)
    assert account.withdraw(30) == 70


def test_insufficient_funds():
    account = Account(20)
    with pytest.raises(ValueError):
        account.withdraw(21)
    assert account.balance == 20


def test_zero_withdrawal():
    account = Account(10)
    assert account.withdraw(0) == 10
