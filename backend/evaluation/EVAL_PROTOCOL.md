# REPRO held-out evaluation protocol (pre-registered)

**Status:** written before the held-out corpus exists. Any change after the first
scored run is a protocol deviation and must be reported, not silently applied.

**Rules freeze:** annotated git tag `rules-v1` at commit `24f9047`
(“Add a standalone example repo with a reproducible failing test suite”).
The deterministic analyzer, patcher, validation gate and agent loop are frozen
for the duration of the held-out study. No rule may be added, removed, or
adjusted in response to held-out results.

**Corpus freeze:** annotated git tag `heldout-v1` after the 40 cases pass the
builder’s baseline/fixed/oracle sanity checks. No case may be edited after the
first scored run. A broken case discovered after the freeze is reported as a
tooling error; it is not repaired and re-scored.

## Research question

How well does the frozen REPRO agent repair bugs it was not designed against,
and what does each stage of the pipeline contribute?

This is an internal held-out evaluation, not an external validity claim. The
same author wrote the cases and the rules; “held out” means only that no rule
was written or changed against these instances. The public-benchmark slice is
the stronger external check.

## Corpus construction

- 40 new, small Python repositories, 5 per category:
  off-by-one, wrong operator/comparison, `None` handling, mutation/aliasing,
  type errors, wrong state updates, multi-file bugs, exception/error handling.
- Each case has:
  - a buggy `repo/` with a visible pytest suite that genuinely fails;
  - hidden `oracle/test_oracle.py` tests that are **never copied into the repo
    REPRO sees**, used to detect patches that only satisfy the visible tests;
  - `ground_truth.patch`, validated to make the visible suite and oracle pass;
  - `meta.json` with category, root-cause file/line, and expected behaviour.
- Cases are authored from category descriptions, not by running REPRO and
  iterating. The old v1/v2 corpora and demo repos may be used only to debug the
  harness, never as scored held-out cases.
- The builder must verify, for every case: visible suite fails on the buggy
  repo; visible suite passes on the fixed repo; visible + oracle pass on the
  fixed repo; the ground-truth patch applies cleanly.

## Metrics

Reported per case and in aggregate, with failures listed individually:

1. **Reproduction** — the agent reproduced a failure rather than reporting
   `no-failure` or crashing.
2. **Localization** — the hypothesis’s claimed file matches the ground-truth
   file; line proximity is reported separately (exact line, ±3 lines, ±10).
3. **Diagnosis** — structured rubric: correct mechanism and location,
   location only, mechanism only, wrong. Adjudicated from the stored hypothesis
   text and metadata; the rubric and labels are committed. Single-author
   adjudication is disclosed; no inter-rater reliability is claimed.
4. **Patch correctness** — the final agent patch applies to a clean copy and
   the visible suite **and** hidden oracle both pass. This is the primary
   outcome. Agent-reported `fixed` is not used as correctness.
5. **Ground-truth overlap** — exact file match, changed-line span IoU, and
   changed-token Jaccard against `ground_truth.patch`. Descriptive only; a
   behaviourally correct alternative patch is still correct.
6. **Regressions** — previously passing visible tests that fail after the
   patch; and oracle tests that pass on the fixed ground truth but fail after
   the agent patch.
7. **Validation checks** — per-check pass/fail for the final patch, plus
   candidate-level records once Phase 2 adds the eval-only candidate log.
8. **False accepts** — agent reports `fixed` but visible + oracle do not both
   pass.
9. **False rejects** — a generated candidate patch is behaviourally correct
   (visible + oracle pass) but the agent does not report it as fixed.
10. **Runtime** — wall-clock seconds per case, plus test-command duration.
11. **Tooling errors** — crashes, timeouts, patch-application failures, and
    invalid cases. Reported separately; never counted as correct.

## Run plan (Phase 1)

- Rules-only mode (`REPRO_STRATEGY_MODE=rules`), one deterministic run over the
  frozen 40-case corpus.
- No LLM calls in Phase 1. LLM comparisons are Phase 3 and will use the same
  frozen corpus, three runs per LLM configuration, with model and version
  recorded.
- Public benchmark: a pre-registered conversion of QuixBugs (all convertible
  cases) and/or a deterministic slice of HumanEvalFix. Conversion rules,
  exclusions and IDs are recorded before running. These are function-level
  benchmarks and are reported separately from the repository-level corpus.
- BugsInPy: one pilot bug in Docker, time-boxed to 30 minutes. If the
  environment cannot be made to run reliably in that budget, it is reported as
  infeasible rather than forced.

## Analysis rules

- Report every case, including failures. No dropping hard cases.
- No tuning of rules, prompts, thresholds or corpus after seeing results.
- No significance claims from 40 cases; report counts, paired differences and
  bootstrap confidence intervals as descriptive uncertainty.
- Phase 2 ablations are defined before running: no tracing, no root-cause
  diagnosis (with an oracle-diagnosis control because rules mode is
  structurally dependent on diagnosis for a patch hint), each validation check
  disabled in turn, and no regression testing. Checks 2 and 3 are identical
  booleans and will be reported as such.
- Phase 3 must separate “LLM only” from “LLM + verification”; the current
  `llm` mode leaks the rule-derived hypothesis into allowed-file scope and
  base risk, so that leak must be removed in eval mode before comparing.

## Known limitations

- Same-author corpus and rules; not externally independent.
- Small synthetic repositories; not representative of large codebases.
- Hidden oracle tests are authored by the same person and may encode
  assumptions; they are a false-accept probe, not an absolute oracle.
- Python/pytest only; patches capped at 30 changed lines and 3 files.
- Process-level sandbox, not a hardened VM.
- Three LLM runs measure run-to-run variability, not population-level
  performance.
- The human-oversight prototype can provide a protocol and pilot tooling, not
  participant evidence.

## Deviations log

| date | change | reason |
|------|--------|--------|
| 2026-11-05 | Fixed a harness thread-cleanup race and reran the held-out corpus | The status event is emitted before the final summary write; the rerun produced identical metrics (3/40, 1 false accept). No rule or corpus change. |
| 2026-11-05 | Assigned the pre-registered diagnosis labels after the run | Single-author adjudication; labels committed in `results/heldout_labels.json`. |
| 2026-11-05 | Converted an 8-algorithm QuixBugs slice | Pre-registered algorithm list; all eight included, one 60s harness timeout reported separately. Function-level, not repository-level. |
