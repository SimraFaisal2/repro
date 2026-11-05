# Public benchmark — QuixBugs slice (rules only)

Source: https://github.com/jkoppel/QuixBugs at `4257f44b0ff1181dedaedee6a447e133219fcebf`. Scope: **function-level public benchmark; not repository-level**.

**Correct: 0/8 (0%)** — reported fixed 0, false accepts 0, localized file 0/8, median 6.14s.

| id | status | local | reported | correct | baseline failures | after failures | regressions |
|----|--------|-------|----------|---------|-------------------|----------------|-------------|
| find_in_sorted | failed | — | — | — | 2 | — | 0 |
| gcd | failed | — | — | — | 5 | — | 0 |
| get_factors | timeout | — | — | — | 10 | — | 0 |
| is_valid_parenthesization | failed | — | — | — | 1 | — | 0 |
| kth | failed | — | — | — | 4 | — | 0 |
| max_sublist_sum | failed | — | — | — | 4 | — | 0 |
| powerset | failed | — | — | — | 4 | — | 0 |
| to_base | failed | — | — | — | 7 | — | 0 |

These are function-level QuixBugs cases, not repository-level bugs. All public testcases are visible; there is no hidden oracle here.
