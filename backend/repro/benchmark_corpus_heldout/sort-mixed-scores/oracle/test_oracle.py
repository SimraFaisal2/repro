from src.scores import sorted_scores


def test_all_strings():
    assert sorted_scores(["10", "2", "1"]) == ["1", "2", "10"]


def test_decimal_strings():
    assert sorted_scores(["2.5", 2, "1.5"]) == ["1.5", 2, "2.5"]


def test_negative_strings():
    assert sorted_scores(["-1", 0, "-2"]) == ["-2", "-1", 0]


def test_stability_for_equal_values():
    assert sorted_scores(["2", 2]) == ["2", 2]
