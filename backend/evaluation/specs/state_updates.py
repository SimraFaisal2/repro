"""Held-out wrong-state-update cases (5)."""

CASES = [
    {
        "id": "bank-double-withdraw",
        "name": "Withdrawal subtracts the amount twice",
        "category": "wrong-state",
        "difficulty": "easy",
        "root_cause_file": "src/account.py",
        "root_cause_line": 9,
        "hidden_bug": "Account.withdraw() subtracts the amount twice, so a 30 withdrawal from "
                       "100 leaves 40 instead of 70.",
        "expected_behavior": "One withdrawal reduces the balance by exactly the requested amount.",
        "ground_truth_summary": "Remove the duplicated balance update.",
        "files": {
            "src/account.py": '''"""Bank account state."""


class Account:
    def __init__(self, balance=0):
        self.balance = balance

    def withdraw(self, amount):
        if amount > self.balance:
            raise ValueError("insufficient funds")
        self.balance -= amount
        self.balance -= amount
        return self.balance
''',
            "tests/test_account.py": '''import pytest

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
''',
        },
        "fixed": {
            "src/account.py": '''"""Bank account state."""


class Account:
    def __init__(self, balance=0):
        self.balance = balance

    def withdraw(self, amount):
        if amount > self.balance:
            raise ValueError("insufficient funds")
        self.balance -= amount
        return self.balance
''',
        },
        "oracle": '''import pytest

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
''',
    },
    {
        "id": "switch-not-toggled",
        "name": "Switch press sets on instead of toggling",
        "category": "wrong-state",
        "difficulty": "easy",
        "root_cause_file": "src/switch.py",
        "root_cause_line": 7,
        "hidden_bug": "Switch.press() assigns True instead of negating the current state, so a "
                       "second press leaves the switch on.",
        "expected_behavior": "Each press flips the state; two presses return to off.",
        "ground_truth_summary": "Assign `not self.on`.",
        "files": {
            "src/switch.py": '''"""A simple switch."""


class Switch:
    def __init__(self):
        self.on = False

    def press(self):
        self.on = True
        return self.on
''',
            "tests/test_switch.py": '''from src.switch import Switch


def test_first_press_turns_on():
    assert Switch().press() is True


def test_second_press_turns_off():
    switch = Switch()
    switch.press()
    assert switch.press() is False


def test_initial_state():
    assert Switch().on is False
''',
        },
        "fixed": {
            "src/switch.py": '''"""A simple switch."""


class Switch:
    def __init__(self):
        self.on = False

    def press(self):
        self.on = not self.on
        return self.on
''',
        },
        "oracle": '''from src.switch import Switch


def test_three_presses():
    switch = Switch()
    switch.press()
    switch.press()
    assert switch.press() is True


def test_state_matches_return():
    switch = Switch()
    result = switch.press()
    assert switch.on is result


def test_two_switches_are_independent():
    first, second = Switch(), Switch()
    first.press()
    assert second.on is False


def test_press_returns_bool():
    assert isinstance(Switch().press(), bool)
''',
    },
    {
        "id": "inventory-release",
        "name": "Releasing a reservation consumes stock",
        "category": "wrong-state",
        "difficulty": "medium",
        "root_cause_file": "src/inventory.py",
        "root_cause_line": 18,
        "hidden_bug": "release() subtracts from available instead of adding back, so returning "
                       "reserved stock decreases the sellable quantity.",
        "expected_behavior": "Releasing n units increases available by n and decreases reserved by n.",
        "ground_truth_summary": "Add released units back to available.",
        "files": {
            "src/inventory.py": '''"""Inventory reservations."""


class Inventory:
    def __init__(self, available):
        self.available = available
        self.reserved = 0

    def reserve(self, amount):
        if amount > self.available:
            raise ValueError("not enough stock")
        self.available -= amount
        self.reserved += amount
        return self.reserved

    def release(self, amount):
        if amount > self.reserved:
            raise ValueError("not enough reserved stock")
        self.reserved -= amount
        self.available -= amount
        return self.available
''',
            "tests/test_inventory.py": '''import pytest

from src.inventory import Inventory


def test_reserve():
    inventory = Inventory(10)
    assert inventory.reserve(3) == 3
    assert inventory.available == 7


def test_release():
    inventory = Inventory(10)
    inventory.reserve(3)
    assert inventory.release(2) == 9


def test_over_release():
    inventory = Inventory(10)
    inventory.reserve(3)
    with pytest.raises(ValueError):
        inventory.release(4)
    assert inventory.reserved == 3
''',
        },
        "fixed": {
            "src/inventory.py": '''"""Inventory reservations."""


class Inventory:
    def __init__(self, available):
        self.available = available
        self.reserved = 0

    def reserve(self, amount):
        if amount > self.available:
            raise ValueError("not enough stock")
        self.available -= amount
        self.reserved += amount
        return self.reserved

    def release(self, amount):
        if amount > self.reserved:
            raise ValueError("not enough reserved stock")
        self.reserved -= amount
        self.available += amount
        return self.available
''',
        },
        "oracle": '''import pytest

from src.inventory import Inventory


def test_release_all():
    inventory = Inventory(5)
    inventory.reserve(5)
    assert inventory.release(5) == 5
    assert inventory.available == 5
    assert inventory.reserved == 0


def test_release_zero():
    inventory = Inventory(5)
    inventory.reserve(2)
    assert inventory.release(0) == 3
    assert inventory.reserved == 2


def test_reserve_then_release_twice():
    inventory = Inventory(4)
    inventory.reserve(4)
    inventory.release(1)
    assert inventory.release(1) == 2
    assert inventory.reserved == 2


def test_over_release_does_not_change_state():
    inventory = Inventory(3)
    inventory.reserve(2)
    with pytest.raises(ValueError):
        inventory.release(3)
    assert inventory.available == 1
    assert inventory.reserved == 2
''',
    },
    {
        "id": "retry-double-count",
        "name": "Successful retry increments the attempt counter twice",
        "category": "wrong-state",
        "difficulty": "medium",
        "root_cause_file": "src/retry.py",
        "root_cause_line": 8,
        "hidden_bug": "Retrier.attempt() increments attempts before the success branch and again "
                       "inside it, so a success is counted as two attempts.",
        "expected_behavior": "Each call counts as exactly one attempt, regardless of outcome.",
        "ground_truth_summary": "Remove the second increment.",
        "files": {
            "src/retry.py": '''"""Retry accounting."""


class Retrier:
    def __init__(self):
        self.attempts = 0

    def attempt(self, succeed):
        self.attempts += 1
        if succeed:
            self.attempts += 1
            return True
        return False
''',
            "tests/test_retry.py": '''from src.retry import Retrier


def test_success_counts_once():
    retrier = Retrier()
    retrier.attempt(True)
    assert retrier.attempts == 1


def test_failure_counts_once():
    retrier = Retrier()
    retrier.attempt(False)
    assert retrier.attempts == 1


def test_two_failures_then_success():
    retrier = Retrier()
    retrier.attempt(False)
    retrier.attempt(False)
    retrier.attempt(True)
    assert retrier.attempts == 3
''',
        },
        "fixed": {
            "src/retry.py": '''"""Retry accounting."""


class Retrier:
    def __init__(self):
        self.attempts = 0

    def attempt(self, succeed):
        self.attempts += 1
        if succeed:
            return True
        return False
''',
        },
        "oracle": '''from src.retry import Retrier


def test_initial_zero():
    assert Retrier().attempts == 0


def test_return_value_success():
    assert Retrier().attempt(True) is True


def test_return_value_failure():
    assert Retrier().attempt(False) is False


def test_many_failures():
    retrier = Retrier()
    for _ in range(5):
        retrier.attempt(False)
    assert retrier.attempts == 5
''',
    },
    {
        "id": "cart-quantity",
        "name": "Adding an existing SKU overwrites its quantity",
        "category": "wrong-state",
        "difficulty": "easy",
        "root_cause_file": "src/cart.py",
        "root_cause_line": 7,
        "hidden_bug": "Cart.add() assigns the new quantity instead of adding it to the existing "
                       "quantity for the same SKU.",
        "expected_behavior": "Adding 3 then 2 of a SKU leaves a quantity of 5.",
        "ground_truth_summary": "Accumulate with self.items.get(sku, 0) + qty.",
        "files": {
            "src/cart.py": '''"""Shopping cart."""


class Cart:
    def __init__(self):
        self.items = {}

    def add(self, sku, qty):
        self.items[sku] = qty
''',
            "tests/test_cart.py": '''from src.cart import Cart


def test_add_existing_sku():
    cart = Cart()
    cart.add("apple", 3)
    cart.add("apple", 2)
    assert cart.items["apple"] == 5


def test_add_new_sku():
    cart = Cart()
    cart.add("pear", 4)
    assert cart.items == {"pear": 4}


def test_empty_cart():
    assert Cart().items == {}
''',
        },
        "fixed": {
            "src/cart.py": '''"""Shopping cart."""


class Cart:
    def __init__(self):
        self.items = {}

    def add(self, sku, qty):
        self.items[sku] = self.items.get(sku, 0) + qty
''',
        },
        "oracle": '''from src.cart import Cart


def test_multiple_skus_are_independent():
    cart = Cart()
    cart.add("a", 1)
    cart.add("b", 2)
    cart.add("a", 3)
    assert cart.items == {"a": 4, "b": 2}


def test_zero_quantity():
    cart = Cart()
    cart.add("a", 0)
    assert cart.items["a"] == 0


def test_add_zero_to_existing():
    cart = Cart()
    cart.add("a", 2)
    cart.add("a", 0)
    assert cart.items["a"] == 2


def test_negative_quantity_is_recorded():
    cart = Cart()
    cart.add("a", 2)
    cart.add("a", -1)
    assert cart.items["a"] == 1
''',
    },
]
