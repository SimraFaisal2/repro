# Phase 2 — component ablations

**Frozen corpus:** `heldout-v1` · **rules:** `rules-v1` (`24f9047`) · **mode:** rules only,
no LLM provider · **cases:** 40.

Each switch is installed in the evaluation harness (`backend/evaluation/run_ablations.py`);
no analyzer, patcher, validation, agent, or corpus file was changed. The baseline control
was rerun through the same harness and reproduced Phase 1: **3/40, 4 reported fixed,
1 false accept**.

## Configuration results

| configuration | correct | reported fixed | false accepts | patch generated | total time |
|---|---:|---:|---:|---:|---:|
| baseline | 3/40 | 4 | 1 | 4/40 (10%) | 81.49 s |
| no runtime tracing | 3/40 | 4 | 1 | 4/40 (10%) | 63.55 s |
| no root-cause diagnosis | 0/40 | 0 | 0 | 0/40 | 79.28 s |
| no regression testing | 3/40 | 4 | 1 | 4/40 (10%) | 78.45 s |
| no static checks | 3/40 | 4 | 1 | 4/40 (10%) | 82.41 s |

### What the switches mean

- **No tracing:** `trace.run_traced` returns no runtime events. Stack frames and the failing
  test's source are still available; only observed calls, arguments, returns, branches,
  and failure-time locals are removed.
- **No diagnosis:** `analyzer.analyze_failure` returns a generic hypothesis with no causal
  claim and no `patch_hint`. Reproduction and localization data are still collected.
- **No regression testing:** the initial baseline suite is real, but the post-patch full
  suite is replaced by a green summary. Target verification still runs independently.
- **No static checks:** all seven pre-apply checks (`minimal`, `only-expected-files`,
  `syntax`, `no-test-changes`, `assertions-intact`, `error-handling-intact`,
  `no-suspicious-ops`) are skipped.

## Per-check removal

The four baseline candidates are the only patches the rules produced. **All four passed
all ten checks** — including `average-nonnull`, the wrong patch. A removal can only change
acceptance if that check failed on a candidate, so the exact gate outcome is a replay over
those four diffs, not ten misleading full reruns. The all-static-checks-off control was run
end-to-end and matches the replay (3/40, one false accept).

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

The full gate also accepts **4/4**, including the one wrong patch, and catches **0** wrong
patches. The table has no non-zero row because this corpus never exercises the checks: the
rule engine emitted only four candidate diffs, all small, in-scope, syntactically valid,
test-preserving, and regression-free.

## Why the false accept survives every ablation

`average-nonnull` changes only:

```python
def average(values):
    if not values:
        return 0.0
    return sum(values) / len(values)
```

The target test (`test_empty`) passes. A second baseline failure, `test_ignores_null`,
still fails because `None` values are not ignored. The dynamic checks are target-shaped:

- `failure-fixed` only asks whether the selected target test is gone.
- `previously-passing-tests` and `no-new-failures` are duplicate checks for *new* failures.
- The regression analyzer does not require every original failure to be gone.

Therefore no removal can catch this patch, and no check catches it today. The independent
hidden oracle does, which is why Phase 1 scored it as a false accept.

## What this changes

1. **Root-cause diagnosis is load-bearing for the rule engine.** Removing it removes every
   patch. The three correct fixes are not produced by tracing or validation alone.
2. **Runtime tracing is not load-bearing for these four rules.** The rules that fired use
   the exception signature, stack location, source, and the test's declared contract; the
   event stream was not needed. This does not show that tracing is useless for other bugs.
3. **Validation is not the current bottleneck.** The static gate and regression suite never
   changed an outcome on this corpus. More checks would not have raised 3/40; better
   candidate generation or an LLM is the next lever.
4. **The gate is insufficient, not merely unused.** Its one real test — the wrong patch —
   passed every check. The missing condition is “all baseline failures resolved”, not
   “selected target fixed.”

This is a low-power ablation: only four candidates, one wrong. The zero rows mean “not
exercised or insufficient on this corpus”, not “the check has no value in general”.

## Reproduce

From `backend/`:

```bash
.venv/bin/python -m evaluation.run_ablations --config baseline
.venv/bin/python -m evaluation.run_ablations --config no-tracing
.venv/bin/python -m evaluation.run_ablations --config no-diagnosis
.venv/bin/python -m evaluation.run_ablations --config no-regression
.venv/bin/python -m evaluation.run_ablations --config no-static-checks
```

Each command writes a JSON and Markdown result under `evaluation/results/ablations/`.
`check_replay.json` is written by the baseline command; it uses the frozen candidate checks,
not a new agent run.

## Limitations

- Rules-only; no LLM or hybrid configuration was run (no provider is configured).
- One deterministic run per configuration; no variance estimate.
- Per-check removals are a replay over four generated candidates, not ten independent
  agent runs. The all-checks-off control is a full run and agrees.
- `no-regression-testing` skips the post-patch suite but still verifies the selected target;
  it is not a claim that the agent never runs any tests.
- The corpus is same-author and synthetic; see the Phase 1 report.
