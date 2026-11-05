from src.scores import sorted_scores


def test_mixed_types():
    assert sorted_scores([90, "85", 70]) == [70, "85", 90]


def test_all_ints():
    assert sorted_scores([3, 1, 2]) == [1, 2, 3]


def test_empty():
    assert sorted_scores([]) == []
