import pytest

from src.account import Account


def test_exact_balance():
    account = Account(50)
    assert account.withdraw(50) == 0
    assert account.balance == 0


def test_two_withdrawals():
    account = Account(100)
    account.withdraw(25)
    assert account.withdraw(15) == 60


def test_overdraft_leaves_balance():
    account = Account(5)
    with pytest.raises(ValueError):
        account.withdraw(6)
    assert account.balance == 5


def test_default_balance():
    assert Account().balance == 0
