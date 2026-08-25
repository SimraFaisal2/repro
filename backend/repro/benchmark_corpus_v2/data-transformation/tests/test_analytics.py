from src.analytics import revenue_by_region


def test_revenue_by_region():
    sales = [
        {"region": "eu", "units": 3, "amount": 30},
        {"region": "eu", "units": 1, "amount": 50},
        {"region": "us", "units": 2, "amount": 20},
    ]
    assert revenue_by_region(sales) == {"eu": 80, "us": 20}


def test_revenue_empty():
    assert revenue_by_region([]) == {}
