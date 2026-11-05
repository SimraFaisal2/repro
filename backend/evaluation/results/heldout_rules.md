# REPRO held-out evaluation — rules only

**Corpus:** `heldout-2026-11-v1` · **rules:** `rules-v1` (`24f9047`) · **run:** 2026-11-05 18:49:16

**Patch correctness: 3/40 (8%)** — reported fixed 4, false accepts 1, false rejects 0, regression-free correct 3.

Reproduction 100% · localization (file) 15% · line exact 1/40 · patch generation 10% · median runtime 1.69s · total 82.69s.

Diagnosis (manual rubric, 40 labelled): {'correct': 3, 'location-only': 3, 'mechanism-only': 2, 'wrong': 32} — accuracy 8%.

| id | category | status | reported | localized | patch | visible | oracle | correct | regressions | time |
|----|----------|--------|----------|-----------|-------|---------|--------|---------|-------------|------|
| adjacent-pairs | off-by-one | fixed | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | 0 | 2.17s |
| page-window | off-by-one | failed | — | — | — | — | — | — | 0 | 2.3s |
| last-n | off-by-one | failed | — | — | — | — | — | — | 0 | 2.29s |
| chunk-size | off-by-one | failed | — | — | — | — | — | — | 0 | 2.36s |
| window-max | off-by-one | failed | — | — | — | — | — | — | 0 | 1.65s |
| discount-threshold | wrong-operator | failed | — | — | — | — | — | — | 0 | 1.69s |
| retry-limit | wrong-operator | failed | — | — | — | — | — | — | 0 | 2.33s |
| temperature-range | wrong-operator | failed | — | — | — | — | — | — | 0 | 2.33s |
| password-length | wrong-operator | failed | — | — | — | — | — | — | 0 | 1.58s |
| grade-boundaries | wrong-operator | failed | — | — | — | — | — | — | 0 | 2.32s |
| profile-city | none-handling | failed | — | ✓ | — | — | — | — | 0 | 2.69s |
| average-nonnull | none-handling | fixed | ✓ | ✓ | ✓ | — | — | — | 0 | 2.19s |
| timeout-default | none-handling | failed | — | — | — | — | — | — | 0 | 1.56s |
| customer-name | none-handling | failed | — | — | — | — | — | — | 0 | 2.71s |
| items-field | none-handling | failed | — | — | — | — | — | — | 0 | 2.29s |
| append-tag | mutation-aliasing | failed | — | — | — | — | — | — | 0 | 1.61s |
| sort-in-place | mutation-aliasing | failed | — | — | — | — | — | — | 0 | 1.59s |
| mutable-default | mutation-aliasing | failed | — | — | — | — | — | — | 0 | 1.67s |
| archive-shallow-copy | mutation-aliasing | failed | — | — | — | — | — | — | 0 | 1.56s |
| zero-grid-aliasing | mutation-aliasing | failed | — | — | — | — | — | — | 0 | 1.58s |
| parse-quantity | type-errors | failed | — | — | — | — | — | — | 0 | 1.6s |
| label-user-id | type-errors | fixed | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | 0 | 2.23s |
| sum-prices | type-errors | failed | — | — | — | — | — | — | 0 | 5.02s |
| lookup-string-key | type-errors | failed | — | — | — | — | — | — | 0 | 1.61s |
| sort-mixed-scores | type-errors | failed | — | — | — | — | — | — | 0 | 1.6s |
| bank-double-withdraw | wrong-state | failed | — | — | — | — | — | — | 0 | 1.61s |
| switch-not-toggled | wrong-state | failed | — | — | — | — | — | — | 0 | 1.61s |
| inventory-release | wrong-state | failed | — | — | — | — | — | — | 0 | 1.68s |
| retry-double-count | wrong-state | failed | — | — | — | — | — | — | 0 | 2.3s |
| cart-quantity | wrong-state | failed | — | — | — | — | — | — | 0 | 1.61s |
| user-serializer | multi-file | failed | — | — | — | — | — | — | 0 | 3.32s |
| plugin-registry | multi-file | failed | — | — | — | — | — | — | 0 | 2.35s |
| checkout-tax | multi-file | failed | — | — | — | — | — | — | 0 | 3.19s |
| event-topic | multi-file | failed | — | — | — | — | — | — | 0 | 1.66s |
| repository-field | multi-file | failed | — | ✓ | — | — | — | — | 0 | 2.02s |
| fetch-swallow | exception-handling | fixed | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | 0 | 2.28s |
| parse-int-swallow | exception-handling | failed | — | — | — | — | — | — | 0 | 1.64s |
| ratio-swallow | exception-handling | failed | — | — | — | — | — | — | 0 | 1.64s |
| transaction-partial | exception-handling | failed | — | — | — | — | — | — | 0 | 1.64s |
| parse-users-skip | exception-handling | failed | — | — | — | — | — | — | 0 | 1.61s |

## Per category

| category | correct | rate | localized file | false accepts | false rejects |
|---|---|---|---|---|---|
| exception-handling | 1/5 | 20% | 1/5 | 0 | 0 |
| multi-file | 0/5 | 0% | 1/5 | 0 | 0 |
| mutation-aliasing | 0/5 | 0% | 0/5 | 0 | 0 |
| none-handling | 0/5 | 0% | 2/5 | 1 | 0 |
| off-by-one | 1/5 | 20% | 1/5 | 0 | 0 |
| type-errors | 1/5 | 20% | 1/5 | 0 | 0 |
| wrong-operator | 0/5 | 0% | 0/5 | 0 | 0 |
| wrong-state | 0/5 | 0% | 0/5 | 0 | 0 |

## Failures and near misses

### `page-window` — Page window returns one extra item

- status **failed**, reported fixed **False**, visible **False**, oracle **False**, final patch **none**
- localization: hint `—` vs expected `src/paging.py`
- hypothesis: Failure in tests/test_paging.py:5 (rule `fallback`, confidence 0.4)
- observed error: `assert [1, 2, 3] == [1, 2]`

### `last-n` — last_n returns n+1 items

- status **failed**, reported fixed **False**, visible **False**, oracle **False**, final patch **none**
- localization: hint `—` vs expected `src/tail.py`
- hypothesis: Failure in tests/test_tail.py:13 (rule `fallback`, confidence 0.4)
- observed error: `assert [3, 4, 5] == [4, 5]`

### `chunk-size` — Chunker uses size-1 as the chunk width

- status **failed**, reported fixed **False**, visible **False**, oracle **False**, final patch **none**
- localization: hint `—` vs expected `src/chunks.py`
- hypothesis: Failure in tests/test_chunks.py:11 (rule `fallback`, confidence 0.4)
- observed error: `assert [[1], [3], [5]] == [[1, 2], [3, 4], [5]]`

### `window-max` — Sliding-window maximum omits the final window

- status **failed**, reported fixed **False**, visible **False**, oracle **False**, final patch **none**
- localization: hint `—` vs expected `src/windows.py`
- hypothesis: Failure in tests/test_windows.py:7 (rule `fallback`, confidence 0.4)
- observed error: `assert [3, 3] == [3, 3, 5]`

### `discount-threshold` — Discount excludes exactly 100

- status **failed**, reported fixed **False**, visible **False**, oracle **False**, final patch **none**
- localization: hint `—` vs expected `src/pricing.py`
- hypothesis: Failure in tests/test_pricing.py:5 (rule `fallback`, confidence 0.4)
- observed error: `assert 100 == 90.0`

### `retry-limit` — Retry predicate compares in the wrong direction

- status **failed**, reported fixed **False**, visible **False**, oracle **False**, final patch **none**
- localization: hint `—` vs expected `src/retries.py`
- hypothesis: Failure in tests/test_retries.py:13 (rule `fallback`, confidence 0.4)
- observed error: `assert False is True`

### `temperature-range` — Temperature check uses an impossible chained comparison

- status **failed**, reported fixed **False**, visible **False**, oracle **False**, final patch **none**
- localization: hint `—` vs expected `src/climate.py`
- hypothesis: Failure in tests/test_climate.py:9 (rule `fallback`, confidence 0.4)
- observed error: `assert False is True`

### `password-length` — Password minimum is off by one

- status **failed**, reported fixed **False**, visible **False**, oracle **False**, final patch **none**
- localization: hint `—` vs expected `src/auth.py`
- hypothesis: Failure in tests/test_auth.py:5 (rule `fallback`, confidence 0.4)
- observed error: `assert False is True`

### `grade-boundaries` — Grade boundaries use strict comparisons

- status **failed**, reported fixed **False**, visible **False**, oracle **False**, final patch **none**
- localization: hint `—` vs expected `src/grades.py`
- hypothesis: Failure in tests/test_grades.py:5 (rule `fallback`, confidence 0.4)
- observed error: `assert 'C' == 'B'`

### `profile-city` — Missing address crashes profile lookup

- status **failed**, reported fixed **False**, visible **False**, oracle **False**, final patch **none**
- localization: hint `src/profile.py` vs expected `src/profile.py`
- hypothesis: user is None when `return user["address"]["city"]` executes (rule `none_subscript`, confidence 0.72)
- observed error: `'address'`

### `average-nonnull` — Average divides by the wrong count when values are null

- status **fixed**, reported fixed **True**, visible **False**, oracle **False**, final patch **proposed**
- localization: hint `src/stats.py` vs expected `src/stats.py`
- hypothesis: `return sum(values) / len(values)` divides by the length of `values` without guarding the empty case (rule `empty_guard_zerodiv`, confidence 0.85)
- observed error: `division by zero`
- **FALSE ACCEPT**: agent reported fixed but independent tests failed

### `timeout-default` — Explicit null timeout bypasses the default

- status **failed**, reported fixed **False**, visible **False**, oracle **False**, final patch **none**
- localization: hint `—` vs expected `src/config.py`
- hypothesis: Failure in tests/test_config.py:9 (rule `fallback`, confidence 0.4)
- observed error: `assert None == 30`

### `customer-name` — Guest orders crash on the customer name

- status **failed**, reported fixed **False**, visible **False**, oracle **False**, final patch **none**
- localization: hint `—` vs expected `src/orders.py`
- hypothesis: Failure in tests/test_orders.py:13 (rule `fallback`, confidence 0.4)
- observed error: `'NoneType' object has no attribute 'name'`

### `items-field` — Null items payload is not normalized

- status **failed**, reported fixed **False**, visible **False**, oracle **False**, final patch **none**
- localization: hint `—` vs expected `src/payloads.py`
- hypothesis: Failure in tests/test_payloads.py:13 (rule `fallback`, confidence 0.4)
- observed error: `'items'`

### `append-tag` — Adding a tag mutates the caller's list

- status **failed**, reported fixed **False**, visible **False**, oracle **False**, final patch **none**
- localization: hint `—` vs expected `src/tags.py`
- hypothesis: Failure in tests/test_tags.py:11 (rule `fallback`, confidence 0.4)
- observed error: `assert ['a', 'b'] == ['a']`

### `sort-in-place` — Ordering helper sorts the caller's list in place

- status **failed**, reported fixed **False**, visible **False**, oracle **False**, final patch **none**
- localization: hint `—` vs expected `src/ordering.py`
- hypothesis: Failure in tests/test_ordering.py:11 (rule `fallback`, confidence 0.4)
- observed error: `assert [1, 2, 3] == [3, 1, 2]`

### `mutable-default` — Mutable default argument leaks items across calls

- status **failed**, reported fixed **False**, visible **False**, oracle **False**, final patch **none**
- localization: hint `—` vs expected `src/buckets.py`
- hypothesis: Failure in tests/test_buckets.py:10 (rule `fallback`, confidence 0.4)
- observed error: `assert ['a', 'b'] == ['b']`

### `archive-shallow-copy` — Archive shallow-copies rows and mutates originals

- status **failed**, reported fixed **False**, visible **False**, oracle **False**, final patch **none**
- localization: hint `—` vs expected `src/archive.py`
- hypothesis: Failure in tests/test_archive.py:11 (rule `fallback`, confidence 0.4)
- observed error: `assert [{'id': 1, 'archived': True}] == [{'id': 1}]`

### `zero-grid-aliasing` — Grid rows alias one shared list

- status **failed**, reported fixed **False**, visible **False**, oracle **False**, final patch **none**
- localization: hint `—` vs expected `src/grid.py`
- hypothesis: Failure in tests/test_grid.py:13 (rule `fallback`, confidence 0.4)
- observed error: `assert [[1, 0], [1, 0]] == [[1, 0], [0, 0]]`

### `parse-quantity` — Quantity parser rejects values with units

- status **failed**, reported fixed **False**, visible **False**, oracle **False**, final patch **none**
- localization: hint `—` vs expected `src/quantity.py`
- hypothesis: Failure in src/quantity.py:5 (rule `fallback`, confidence 0.4)
- observed error: `invalid literal for int() with base 10: '3 items'`

### `sum-prices` — Price total assumes numeric strings

- status **failed**, reported fixed **False**, visible **False**, oracle **False**, final patch **none**
- localization: hint `—` vs expected `src/billing.py`
- hypothesis: — (rule `—`, confidence None)
- observed error: `unsupported operand type(s) for +: 'int' and 'str'`

### `lookup-string-key` — Lookup does not normalize string keys

- status **failed**, reported fixed **False**, visible **False**, oracle **False**, final patch **none**
- localization: hint `—` vs expected `src/lookup.py`
- hypothesis: Missing key '1' at `return data[key]` (rule `key_error_generic`, confidence 0.5)
- observed error: `'1'`

### `sort-mixed-scores` — Score sorter cannot compare ints and strings

- status **failed**, reported fixed **False**, visible **False**, oracle **False**, final patch **none**
- localization: hint `—` vs expected `src/scores.py`
- hypothesis: Failure in src/scores.py:5 (rule `fallback`, confidence 0.4)
- observed error: `'<' not supported between instances of 'str' and 'int'`

### `bank-double-withdraw` — Withdrawal subtracts the amount twice

- status **failed**, reported fixed **False**, visible **False**, oracle **False**, final patch **none**
- localization: hint `—` vs expected `src/account.py`
- hypothesis: Failure in tests/test_account.py:8 (rule `fallback`, confidence 0.4)
- observed error: `assert 40 == 70`

### `switch-not-toggled` — Switch press sets on instead of toggling

- status **failed**, reported fixed **False**, visible **False**, oracle **False**, final patch **none**
- localization: hint `—` vs expected `src/switch.py`
- hypothesis: Failure in tests/test_switch.py:11 (rule `fallback`, confidence 0.4)
- observed error: `assert True is False`

### `inventory-release` — Releasing a reservation consumes stock

- status **failed**, reported fixed **False**, visible **False**, oracle **False**, final patch **none**
- localization: hint `—` vs expected `src/inventory.py`
- hypothesis: Failure in tests/test_inventory.py:15 (rule `fallback`, confidence 0.4)
- observed error: `assert 5 == 9`

### `retry-double-count` — Successful retry increments the attempt counter twice

- status **failed**, reported fixed **False**, visible **False**, oracle **False**, final patch **none**
- localization: hint `—` vs expected `src/retry.py`
- hypothesis: Failure in tests/test_retry.py:21 (rule `fallback`, confidence 0.4)
- observed error: `assert 2 == 1`

### `cart-quantity` — Adding an existing SKU overwrites its quantity

- status **failed**, reported fixed **False**, visible **False**, oracle **False**, final patch **none**
- localization: hint `—` vs expected `src/cart.py`
- hypothesis: Failure in tests/test_cart.py:8 (rule `fallback`, confidence 0.4)
- observed error: `assert 2 == 5`

### `user-serializer` — Serializer uses a field the model does not have

- status **failed**, reported fixed **False**, visible **False**, oracle **False**, final patch **none**
- localization: hint `—` vs expected `src/serializers.py`
- hypothesis: Failure in src/serializers.py:5 (rule `fallback`, confidence 0.4)
- observed error: `assert 'Ada' == 'Ada Lovelace'`

### `plugin-registry` — Plugin registered under a name the manifest does not use

- status **failed**, reported fixed **False**, visible **False**, oracle **False**, final patch **none**
- localization: hint `—` vs expected `src/registry.py`
- hypothesis: Missing key 'alpha-v1' at `return PLUGINS[name]` (rule `key_error_generic`, confidence 0.5)
- observed error: `'alpha-v1'`

### `checkout-tax` — Checkout applies the tax rate as a flat surcharge

- status **failed**, reported fixed **False**, visible **False**, oracle **False**, final patch **none**
- localization: hint `—` vs expected `src/checkout.py`
- hypothesis: Failure in tests/test_checkout.py:9 (rule `fallback`, confidence 0.4)
- observed error: `assert 20.19 == 21.99`

### `event-topic` — Handler subscribes to a misspelled topic

- status **failed**, reported fixed **False**, visible **False**, oracle **False**, final patch **none**
- localization: hint `—` vs expected `src/handlers.py`
- hypothesis: Failure in tests/test_handlers.py:10 (rule `fallback`, confidence 0.4)
- observed error: `assert [] == ['handled']`

### `repository-field` — Repository reads a renamed model field

- status **failed**, reported fixed **False**, visible **False**, oracle **False**, final patch **none**
- localization: hint `src/repository.py` vs expected `src/repository.py`
- hypothesis: Wrong response key: `return row["email"]` reads 'email' but the value has 'name' (rule `key_fix_traced`, confidence 0.85)
- observed error: `'email'`

### `parse-int-swallow` — Integer parser hides invalid input as zero

- status **failed**, reported fixed **False**, visible **False**, oracle **False**, final patch **none**
- localization: hint `—` vs expected `src/parse.py`
- hypothesis: Failure in tests/test_parse.py:7 (rule `fallback`, confidence 0.4)
- observed error: `DID NOT RAISE ValueError`

### `ratio-swallow` — Ratio helper turns division by zero into zero

- status **failed**, reported fixed **False**, visible **False**, oracle **False**, final patch **none**
- localization: hint `—` vs expected `src/ratio.py`
- hypothesis: Failure in tests/test_ratio.py:7 (rule `fallback`, confidence 0.4)
- observed error: `DID NOT RAISE ZeroDivisionError`

### `transaction-partial` — Failed transaction leaves earlier items committed

- status **failed**, reported fixed **False**, visible **False**, oracle **False**, final patch **none**
- localization: hint `—` vs expected `src/store.py`
- hypothesis: Failure in tests/test_store.py:10 (rule `fallback`, confidence 0.4)
- observed error: `assert [1] == []`

### `parse-users-skip` — User parser silently skips malformed rows

- status **failed**, reported fixed **False**, visible **False**, oracle **False**, final patch **none**
- localization: hint `—` vs expected `src/users.py`
- hypothesis: Failure in tests/test_users.py:7 (rule `fallback`, confidence 0.4)
- observed error: `DID NOT RAISE ValueError`
