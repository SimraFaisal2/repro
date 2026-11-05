from src.retry import Retrier


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
