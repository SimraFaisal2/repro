# Phase 2 ablation — baseline

Corpus `heldout-v1` · timeout 180.0s · run 2026-11-05 23:12:21

**Patch correctness: 3/40** — reported fixed 4, false accepts 1, false rejects 0, patch generation 10%.

## Per-check replay

Baseline candidates with a patch: 4 (1 wrong).

| check removed | accepted after removal | wrong accepted | wrong caught by check |
|---|---:|---:|---:|
| `minimal` | 4/4 | 1 | 0 |
| `only-expected-files` | 4/4 | 1 | 0 |
| `syntax` | 4/4 | 1 | 0 |
| `no-test-changes` | 4/4 | 1 | 0 |
| `assertions-intact` | 4/4 | 1 | 0 |
| `error-handling-intact` | 4/4 | 1 | 0 |
| `no-suspicious-ops` | 4/4 | 1 | 0 |
| `failure-fixed` | 4/4 | 1 | 0 |
| `previously-passing-tests` | 4/4 | 1 | 0 |
| `no-new-failures` | 4/4 | 1 | 0 |

A removal can only change acceptance when that check failed on a candidate. All four baseline candidates passed all ten checks, so every removal leaves the same one false accept; no check caught it.

## Cases

| id | status | reported | correct | false accept | patch | time |
|---|---|---|---|---|---|---|
| adjacent-pairs | fixed | ✓ | ✓ | — | ✓ | 2.28s |
| page-window | failed | — | — | — | — | 2.34s |
| last-n | failed | — | — | — | — | 2.74s |
| chunk-size | failed | — | — | — | — | 2.42s |
| window-max | failed | — | — | — | — | 1.64s |
| discount-threshold | failed | — | — | — | — | 1.77s |
| retry-limit | failed | — | — | — | — | 2.47s |
| temperature-range | failed | — | — | — | — | 2.4s |
| password-length | failed | — | — | — | — | 1.63s |
| grade-boundaries | failed | — | — | — | — | 2.4s |
| profile-city | failed | — | — | — | — | 2.84s |
| average-nonnull | fixed | ✓ | — | ✓ | ✓ | 2.28s |
| timeout-default | failed | — | — | — | — | 1.69s |
| customer-name | failed | — | — | — | — | 2.79s |
| items-field | failed | — | — | — | — | 2.35s |
| append-tag | failed | — | — | — | — | 1.6s |
| sort-in-place | failed | — | — | — | — | 1.66s |
| mutable-default | failed | — | — | — | — | 1.73s |
| archive-shallow-copy | failed | — | — | — | — | 1.63s |
| zero-grid-aliasing | failed | — | — | — | — | 1.68s |
| parse-quantity | failed | — | — | — | — | 1.63s |
| label-user-id | fixed | ✓ | ✓ | — | ✓ | 2.12s |
| sum-prices | failed | — | — | — | — | 1.67s |
| lookup-string-key | failed | — | — | — | — | 1.64s |
| sort-mixed-scores | failed | — | — | — | — | 1.6s |
| bank-double-withdraw | failed | — | — | — | — | 1.62s |
| switch-not-toggled | failed | — | — | — | — | 1.63s |
| inventory-release | failed | — | — | — | — | 1.67s |
| retry-double-count | failed | — | — | — | — | 2.31s |
| cart-quantity | failed | — | — | — | — | 1.66s |
| user-serializer | failed | — | — | — | — | 3.11s |
| plugin-registry | failed | — | — | — | — | 2.4s |
| checkout-tax | failed | — | — | — | — | 3.17s |
| event-topic | failed | — | — | — | — | 1.64s |
| repository-field | failed | — | — | — | — | 2.02s |
| fetch-swallow | fixed | ✓ | ✓ | — | ✓ | 2.34s |
| parse-int-swallow | failed | — | — | — | — | 1.67s |
| ratio-swallow | failed | — | — | — | — | 1.84s |
| transaction-partial | failed | — | — | — | — | 1.72s |
| parse-users-skip | failed | — | — | — | — | 1.69s |
