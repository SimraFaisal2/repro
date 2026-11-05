# Phase 2 ablation — no-tracing

Corpus `heldout-v1` · timeout 180.0s · run 2026-11-05 23:05:18

**Patch correctness: 3/40** — reported fixed 4, false accepts 1, false rejects 0, patch generation 10%.

## Cases

| id | status | reported | correct | false accept | patch | time |
|---|---|---|---|---|---|---|
| adjacent-pairs | fixed | ✓ | ✓ | — | ✓ | 3.6s |
| page-window | failed | — | — | — | — | 1.74s |
| last-n | failed | — | — | — | — | 1.61s |
| chunk-size | failed | — | — | — | — | 1.64s |
| window-max | failed | — | — | — | — | 1.29s |
| discount-threshold | failed | — | — | — | — | 1.27s |
| retry-limit | failed | — | — | — | — | 1.58s |
| temperature-range | failed | — | — | — | — | 1.64s |
| password-length | failed | — | — | — | — | 1.3s |
| grade-boundaries | failed | — | — | — | — | 1.66s |
| profile-city | failed | — | — | — | — | 2.05s |
| average-nonnull | fixed | ✓ | — | ✓ | ✓ | 1.95s |
| timeout-default | failed | — | — | — | — | 1.24s |
| customer-name | failed | — | — | — | — | 2.37s |
| items-field | failed | — | — | — | — | 1.75s |
| append-tag | failed | — | — | — | — | 1.35s |
| sort-in-place | failed | — | — | — | — | 1.57s |
| mutable-default | failed | — | — | — | — | 1.4s |
| archive-shallow-copy | failed | — | — | — | — | 1.41s |
| zero-grid-aliasing | failed | — | — | — | — | 1.6s |
| parse-quantity | failed | — | — | — | — | 1.35s |
| label-user-id | fixed | ✓ | ✓ | — | ✓ | 1.96s |
| sum-prices | failed | — | — | — | — | 1.26s |
| lookup-string-key | failed | — | — | — | — | 1.26s |
| sort-mixed-scores | failed | — | — | — | — | 1.41s |
| bank-double-withdraw | failed | — | — | — | — | 1.29s |
| switch-not-toggled | failed | — | — | — | — | 1.27s |
| inventory-release | failed | — | — | — | — | 1.31s |
| retry-double-count | failed | — | — | — | — | 1.61s |
| cart-quantity | failed | — | — | — | — | 1.29s |
| user-serializer | failed | — | — | — | — | 2.06s |
| plugin-registry | failed | — | — | — | — | 1.72s |
| checkout-tax | failed | — | — | — | — | 2.27s |
| event-topic | failed | — | — | — | — | 1.3s |
| repository-field | failed | — | — | — | — | 1.25s |
| fetch-swallow | fixed | ✓ | ✓ | — | ✓ | 1.81s |
| parse-int-swallow | failed | — | — | — | — | 1.32s |
| ratio-swallow | failed | — | — | — | — | 1.23s |
| transaction-partial | failed | — | — | — | — | 1.24s |
| parse-users-skip | failed | — | — | — | — | 1.32s |
