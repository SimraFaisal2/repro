import threading

from src.counter import Counter

THREADS = 4
PER_THREAD = 2500


def _bump(counter, n):
    for _ in range(n):
        counter.increment()


def test_concurrent_increments():
    counter = Counter()
    threads = [threading.Thread(target=_bump, args=(counter, PER_THREAD))
               for _ in range(THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # every increment must be counted — the unlocked read-modify-write loses
    # updates, so this will be far below THREADS * PER_THREAD
    assert counter.value == THREADS * PER_THREAD


def test_sequential_increments():
    counter = Counter()
    for _ in range(100):
        counter.increment()
    assert counter.value == 100
