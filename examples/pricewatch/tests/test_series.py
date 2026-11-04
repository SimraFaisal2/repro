from pricewatch.series import daily_changes, max_drawdown

WEEK = [100.0, 102.0, 101.0, 104.0, 103.0]


def test_daily_changes_empty_series():
    assert daily_changes([]) == []


def test_daily_changes_single_observation():
    assert daily_changes([100.0]) == []


def test_daily_changes_two_observations():
    assert daily_changes([100.0, 110.0]) == [10.0]


def test_daily_changes_week():
    assert daily_changes(WEEK) == [2.0, -0.98, 2.97, -0.96]


def test_max_drawdown_week():
    assert max_drawdown(WEEK) == -0.98


def test_max_drawdown_rising_series():
    assert max_drawdown([90.0, 95.0, 100.0]) == 0.0
