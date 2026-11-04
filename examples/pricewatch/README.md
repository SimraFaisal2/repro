# pricewatch

Price-series analytics for the alerting workers.

`pricewatch` turns a series of daily closing prices into the numbers the
alerting service publishes to the ops channel: day-over-day percentage
changes, the maximum drawdown over the window, and a one-line summary per
symbol.

## Layout

```
pricewatch/
  series.py   # daily_changes(), max_drawdown()
  report.py   # summarise()
tests/
  test_series.py
  test_report.py
```

## Running the tests

```bash
python -m pytest -q
```

The library itself uses only the standard library; the suite needs pytest.

## Conventions

* Percentages are returned as numbers rounded to two decimals (e.g. `2.97`),
  not as fractions.
* `daily_changes([])` and `daily_changes([price])` return `[]` — a single
  observation has no change to report.
* `max_drawdown()` is signed: `0.0` for a series that only rises, negative
  when the price fell from a running peak.

CI runs the same test command on Python 3.11 (`.github/workflows/ci.yml`).
