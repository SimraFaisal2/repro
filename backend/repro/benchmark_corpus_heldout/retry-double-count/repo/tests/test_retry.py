from src.retry import Retrier


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
