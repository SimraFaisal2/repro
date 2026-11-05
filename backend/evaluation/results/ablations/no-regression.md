# Phase 2 ablation — no-regression

Corpus `heldout-v1` · timeout 180.0s · run 2026-11-05 23:08:55

**Patch correctness: 3/40** — reported fixed 4, false accepts 1, false rejects 0, patch generation 10%.

## Cases

| id | status | reported | correct | false accept | patch | time |
|---|---|---|---|---|---|---|
| adjacent-pairs | fixed | ✓ | ✓ | — | ✓ | 1.99s |
| page-window | failed | — | — | — | — | 2.42s |
| last-n | failed | — | — | — | — | 2.27s |
| chunk-size | failed | — | — | — | — | 2.26s |
| window-max | failed | — | — | — | — | 1.72s |
| discount-threshold | failed | — | — | — | — | 1.71s |
| retry-limit | failed | — | — | — | — | 2.35s |
| temperature-range | failed | — | — | — | — | 2.35s |
| password-length | failed | — | — | — | — | 1.61s |
| grade-boundaries | failed | — | — | — | — | 2.41s |
| profile-city | failed | — | — | — | — | 2.72s |
| average-nonnull | fixed | ✓ | — | ✓ | ✓ | 1.94s |
| timeout-default | failed | — | — | — | — | 1.63s |
| customer-name | failed | — | — | — | — | 2.7s |
| items-field | failed | — | — | — | — | 2.3s |
| append-tag | failed | — | — | — | — | 1.56s |
| sort-in-place | failed | — | — | — | — | 1.63s |
| mutable-default | failed | — | — | — | — | 1.65s |
| archive-shallow-copy | failed | — | — | — | — | 1.63s |
| zero-grid-aliasing | failed | — | — | — | — | 1.6s |
| parse-quantity | failed | — | — | — | — | 1.61s |
| label-user-id | fixed | ✓ | ✓ | — | ✓ | 1.89s |
| sum-prices | failed | — | — | — | — | 1.63s |
| lookup-string-key | failed | — | — | — | — | 1.56s |
| sort-mixed-scores | failed | — | — | — | — | 1.58s |
| bank-double-withdraw | failed | — | — | — | — | 1.59s |
| switch-not-toggled | failed | — | — | — | — | 1.57s |
| inventory-release | failed | — | — | — | — | 1.57s |
| retry-double-count | failed | — | — | — | — | 2.29s |
| cart-quantity | failed | — | — | — | — | 1.63s |
| user-serializer | failed | — | — | — | — | 3.12s |
| plugin-registry | failed | — | — | — | — | 2.53s |
| checkout-tax | failed | — | — | — | — | 3.04s |
| event-topic | failed | — | — | — | — | 1.61s |
| repository-field | failed | — | — | — | — | 2.03s |
| fetch-swallow | fixed | ✓ | ✓ | — | ✓ | 1.95s |
| parse-int-swallow | failed | — | — | — | — | 1.71s |
| ratio-swallow | failed | — | — | — | — | 1.69s |
| transaction-partial | failed | — | — | — | — | 1.73s |
| parse-users-skip | failed | — | — | — | — | 1.67s |
