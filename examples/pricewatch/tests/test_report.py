from pricewatch.report import summarise


def test_summarise_without_data():
    assert summarise("BTC", []) == "BTC: no data"


def test_summarise_single_observation():
    assert summarise("BTC", [100.0]) == "BTC: 100.00 (flat, drawdown 0.00%)"


def test_summarise_direction_and_drawdown():
    assert summarise("BTC", [100.0, 110.0]) == "BTC: 110.00 (up, drawdown 0.00%)"
