# Phase 1 — clean held-out evaluation

**Status:** complete. Rules were frozen before any held-out case was authored.
No rule, corpus, or threshold was changed after the first scored run.

- Rules freeze: `rules-v1` at `24f9047`
- Corpus freeze: `heldout-v1` (this corpus commit)
- Protocol: [`../EVAL_PROTOCOL.md`](../EVAL_PROTOCOL.md)
- Raw results: [`heldout_rules.json`](heldout_rules.json) · [`heldout_rules.md`](heldout_rules.md)
- Public slice: [`public_quixbugs_rules.json`](public_quixbugs_rules.json)

## What was built

A 40-case held-out corpus, five cases in each of: off-by-one, wrong
operator/comparison, `None` handling, mutation/aliasing, type errors, wrong
state updates, multi-file bugs, and exception/error handling.

Every case has:

- a buggy repository with a genuinely failing visible pytest suite;
- hidden oracle tests stored **outside** the repository REPRO sees;
- a ground-truth patch that the builder verified makes the visible suite and
  oracle pass;
- metadata with the root-cause file/line and expected behaviour.

The builder rejects any case whose visible suite does not fail, whose ground
truth does not pass, or whose patch does not apply. All 40 passed that gate.
The old v1/v2 corpora and demos were used only to debug the harness.

## Held-out result (rules only, no LLM)

**3/40 correct (7.5%).** The agent reported `fixed` for 4 cases, so there is
**1 false accept**. There were **0 false rejects** and **0 test modifications**.

| metric | result |
|---|---|
| Reproduction | 40/40 (100%) |
| Patch generated | 4/40 (10%) |
| Patch correct (visible + oracle) | 3/40 (7.5%) |
| Reported fixed | 4/40 |
| False accepts | 1 |
| False rejects | 0 |
| Regression-free correct | 3/40 |
| Localization by file | 6/40 (15%) |
| Localization exact line | 1/40 |
| Localization within ±3 lines | 6/40 |
| Median runtime | 1.69 s |
| Total runtime | 82.69 s |

By category:

| category | correct |
|---|---|
| off-by-one | 1/5 |
| wrong-operator | 0/5 |
| none-handling | 0/5 |
| mutation-aliasing | 0/5 |
| type-errors | 1/5 |
| wrong-state | 0/5 |
| multi-file | 0/5 |
| exception-handling | 1/5 |

The three correct cases were `adjacent-pairs` (off-by-one),
`label-user-id` (string concatenation), and `fetch-swallow` (broad exception).

### Diagnosis rubric

Labels were assigned under the pre-registered rubric, single author, after the
run:

| label | count |
|---|---|
| correct mechanism + location | 3 |
| location only | 3 |
| mechanism only | 2 |
| wrong | 32 |

Diagnosis accuracy under this strict rubric is **3/40 (7.5%)**. The six
non-wrong labels are not all fixes: `average-nonnull`, `profile-city`, and
`repository-field` found the right file but the wrong mechanism.

### The false accept

`average-nonnull` is the important failure. The visible failing test
`test_ignores_null` requires `None` values to be ignored; a second failing test
`test_empty` requires an empty-list guard. REPRO added only:

```python
if not values:
    return 0.0
```

It fixed `test_empty`, left `test_ignores_null` failing, and reported `fixed`.
The validation gate passed because its `failure-fixed` check looked at the
target test and its regression checks only looked for *new* failures. A
pre-existing baseline failure outside the target was not treated as a reason
to reject the patch. The independent oracle caught it.

This is a concrete Phase 2 ablation target: the gate currently proves “the
target is fixed and nothing new broke”, not “the repository is healthy”.

## Public QuixBugs slice

**0/8 correct (rules only).** Eight pre-registered, self-contained QuixBugs
algorithms were converted to pytest repositories:

`find_in_sorted`, `gcd`, `get_factors`, `is_valid_parenthesization`, `kth`,
`max_sublist_sum`, `powerset`, `to_base`.

Source: <https://github.com/jkoppel/QuixBugs> at
`4257f44b0ff1181dedaedee6a447e133219fcebf`.

REPRO generated no patch on any of the eight. Seven failed quickly; one
(`get_factors`) hit the 60-second per-case harness timeout and is reported as a
timeout, not as a wrong patch. All public testcases are visible, and these are
function-level bugs, so this is a weaker external check than the repository
corpus. It still shows that the frozen deterministic engine does not generalize
to simple algorithm-level bugs outside its rule classes.

## Integrity checks

- Rules tag `rules-v1` points at the pre-corpus commit; no core analyzer,
  patcher, validation, or agent file changed during Phase 1.
- The corpus was tagged only after the builder passed all 40 cases.
- No held-out case was edited after the first scored run.
- Correctness is independent of the agent’s own `fixed` status: every final
  patch is applied to a clean copy, the original visible tests are restored,
  and the hidden oracle is run separately.
- An agent patch that modifies tests is detected (`touched_tests`); none did.
- The held-out rerun after fixing a harness thread-cleanup race produced the
  same 3/40 and 1 false accept.

## Reproduce

From `backend/`:

```bash
.venv/bin/python -m evaluation.build_corpus --check
REPRO_STRATEGY_MODE=rules .venv/bin/python -m evaluation.run_heldout \
  --labels evaluation/results/heldout_labels.json
```

For the public slice, clone QuixBugs at the commit above to `/tmp/quixbugs`,
then:

```bash
.venv/bin/python -m evaluation.build_public_quixbugs --source /tmp/quixbugs
REPRO_STRATEGY_MODE=rules .venv/bin/python -m evaluation.run_public_quixbugs
```

## Limitations

- Same-author corpus and rules: this is rule-frozen, not externally
  independent. The QuixBugs slice is the external check, and it is
  function-level.
- Hidden oracle tests are also author-written; they probe false accepts but are
  not an absolute behavioural oracle.
- Small synthetic repositories, Python/pytest only, patches capped at 30 lines
  and 3 files.
- No LLM was configured in this workspace, so this report says nothing about
  LLM or hybrid performance.
- The 60-second public timeout is a harness limit; it is reported as a tooling
  outcome, not counted as a correct or incorrect patch.
- Forty cases give counts, not a precise generalization estimate.

## What Phase 1 means

The previously reported v2 result (12/12 after adding rules for v2’s failure
classes) is a regression-suite result, not an estimate of general debugging
ability. On 40 new cases the frozen engine fixes 3, reports 4, and is caught
once by the independent oracle. Phase 2 should now measure which components
account for those 3 successes and which checks would catch the remaining wrong
patches.
