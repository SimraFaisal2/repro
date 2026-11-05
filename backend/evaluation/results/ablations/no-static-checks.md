# Phase 2 ablation — no-static-checks

Corpus `heldout-v1` · timeout 180.0s · run 2026-11-05 23:10:20

**Patch correctness: 3/40** — reported fixed 4, false accepts 1, false rejects 0, patch generation 10%.

## Cases

| id | status | reported | correct | false accept | patch | time |
|---|---|---|---|---|---|---|
| adjacent-pairs | fixed | ✓ | ✓ | — | ✓ | 2.35s |
| page-window | failed | — | — | — | — | 2.51s |
| last-n | failed | — | — | — | — | 2.39s |
| chunk-size | failed | — | — | — | — | 2.38s |
| window-max | failed | — | — | — | — | 1.7s |
| discount-threshold | failed | — | — | — | — | 1.84s |
| retry-limit | failed | — | — | — | — | 2.37s |
| temperature-range | failed | — | — | — | — | 2.39s |
| password-length | failed | — | — | — | — | 1.65s |
| grade-boundaries | failed | — | — | — | — | 2.43s |
| profile-city | failed | — | — | — | — | 2.68s |
| average-nonnull | fixed | ✓ | — | ✓ | ✓ | 2.32s |
| timeout-default | failed | — | — | — | — | 1.59s |
| customer-name | failed | — | — | — | — | 3.63s |
| items-field | failed | — | — | — | — | 2.37s |
| append-tag | failed | — | — | — | — | 1.67s |
| sort-in-place | failed | — | — | — | — | 1.74s |
| mutable-default | failed | — | — | — | — | 1.73s |
| archive-shallow-copy | failed | — | — | — | — | 1.72s |
| zero-grid-aliasing | failed | — | — | — | — | 1.7s |
| parse-quantity | failed | — | — | — | — | 1.63s |
| label-user-id | fixed | ✓ | ✓ | — | ✓ | 2.25s |
| sum-prices | failed | — | — | — | — | 1.65s |
| lookup-string-key | failed | — | — | — | — | 1.64s |
| sort-mixed-scores | failed | — | — | — | — | 1.7s |
| bank-double-withdraw | failed | — | — | — | — | 1.73s |
| switch-not-toggled | failed | — | — | — | — | 1.7s |
| inventory-release | failed | — | — | — | — | 1.7s |
| retry-double-count | failed | — | — | — | — | 2.46s |
| cart-quantity | failed | — | — | — | — | 1.72s |
| user-serializer | failed | — | — | — | — | 3.15s |
| plugin-registry | failed | — | — | — | — | 2.47s |
| checkout-tax | failed | — | — | — | — | 3.09s |
| event-topic | failed | — | — | — | — | 1.62s |
| repository-field | failed | — | — | — | — | 1.99s |
| fetch-swallow | fixed | ✓ | ✓ | — | ✓ | 2.27s |
| parse-int-swallow | failed | — | — | — | — | 1.6s |
| ratio-swallow | failed | — | — | — | — | 1.6s |
| transaction-partial | failed | — | — | — | — | 1.61s |
| parse-users-skip | failed | — | — | — | — | 1.67s |
