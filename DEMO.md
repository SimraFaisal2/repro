# REPRO — 5-minute demonstration for Prof. Keim & Bastian Jäckl

This is the interview runbook: a timed script mapped to the four requested parts, the
numbers you may quote, and short answers to the technical questions. Keep it open on a
second screen or phone during the call.

---

## The one-sentence pitch

> REPRO is an autonomous debugging agent: it reproduces a failing test, records a real
> runtime trace, diagnoses the root cause, generates a minimal patch, and then **proves**
> the fix — target test and full suite — inside an isolated sandbox before a human is
> allowed to apply it.

The claim to stress: **nothing is fabricated**. Every count, runtime value and diff in the
UI comes from actual execution (pytest output, `sys.settrace` events, the applied patch).
The interface is a view over evidence, not the evidence itself.

---

## Before the call (do this 5 minutes early)

1. Start the backend and frontend on **your laptop** (not the cloud preview):

   ```powershell
   # window 1
   cd backend
   .\.venv\Scripts\python -m pip install -r requirements.txt
   .\.venv\Scripts\python run.py                 # http://127.0.0.1:8000

   # window 2
   cd frontend
   npm install
   npm run dev                                   # http://localhost:5173
   ```

2. Run the demo once, so pytest caches and imports are warm. The run itself is ~2–3 s.
3. Open the landing page, press **Ctrl +** twice, close Slack/mail, enable Do Not Disturb.
4. Keep a terminal open in the repository root as the fallback:

   ```powershell
   cd backend
   .\.venv\Scripts\python -m repro.cli demo offbyone
   ```

5. In Zoom: **Share Screen → the browser window** (not "Entire Screen").

Two rules for the demo: narrate *before* clicking, because the investigation finishes in
about two seconds; and never claim an LLM is running when it is not. This run uses the
deterministic rule engine, and that is a feature — say so.

---

## The 5-minute script

### 0:00–0:45 · Part 1 — why verification is the problem

No screen, or stay on the landing page. Say:

> "An LLM can write a patch that looks right and is wrong. It can also fix the one failing
> test and quietly break three others. So the hard problem isn't generating code — it's
> deciding whether a change is actually correct. My design principle is that a fix is a
> hypothesis until the test suite says otherwise. REPRO therefore reproduces the failure
> first, and it never calls anything fixed until the full suite is green in a sandbox."

One sentence on the two failure modes: wrong diagnosis, and a patch that is locally right
but globally regressive. Both are addressed by the same gate.

### 0:45–1:40 · Part 2 — architecture, in one pass

Stay on the landing page and point at the lifecycle strip
`REPRODUCE → INVESTIGATE → DIAGNOSE → PATCH → VERIFY`. Explain, in this order:

1. **Failure identification** — the repo is copied into a sandbox, pytest runs, and the
   output is parsed into a structured record: failing test id, error type, message,
   deepest `file:line`, and stack frames. The failing test is then re-run alone with a long
   traceback, so the record is genuine and reproducible.
2. **Investigation** — that test is re-run under a `sys.settrace` tracer that records a call
   tree with arguments, return values, and the locals at the exception point.
3. **Diagnosis and localization** — the analyzer reasons over the error, stack, trace,
   source window and schema. The hypothesis carries a `patch_hint` (`file`, line, rule) and
   separates **observed evidence** from **inferred reasoning**.
4. **Patch and verification** — a patch is *planned*, never applied immediately. Static
   checks run first; then it is applied to the sandbox copy, the target test is re-run, then
   the full suite. Any new failure reverts it.

Say explicitly: *"The reasoner is swappable — rules today, an LLM optionally behind the
same validation gate. The verifier is the part I care about."*

If they want code rather than the UI, open these tabs now (or mention them):
`backend/repro/tests.py` (`parse_failure`), `trace.py`, `agent.py` (`_attempt`),
`validation.py` (the 10 checks), `benchmark_v2.py` (metrics).

### 1:40–3:40 · Part 3 — show it working

**1:40** Click **Try REPRO** on the landing page. While it runs (~2–3 s), say:

> "It is copying the repo into a sandbox, installing nothing because this project is
> stdlib-only, and running the real pytest suite."

**1:50 — Failure detected.** Point at the test id, `IndexError: list index out of range`,
and `src/windows.py:12`. Say: *"This is pytest's output, parsed — not generated text."*

**2:10 — Root cause.** It should read:

> Off-by-one: `pairs.append((xs[i], xs[i + 1]))` indexes past the end inside
> `for i in range(len(xs))` — 90% confidence.

Say: *"The evidence is the loop bound, the body indexing `i + 1`, and the runtime values at
the failure. The rule is deterministic; the trace is what makes it grounded."*

**2:30 — Proposed fix.** One line: `range(len(xs))` → `range(len(xs) - 1)`, +1/−1.
Emphasise minimality: *"It is not rewriting the function; it changes the bound that is
provably wrong."*

**2:50 — Verification.** Before `1 passed / 2 failed` → after `3 passed / 0 failed`; full
suite green; risk LOW. Say: *"The number that matters is the second one. One test passing
would not be enough."*

**3:00 — Open full investigation.** Click **Open full investigation**, then show, in this
order and quickly:

- **Runtime trace** — 2 frames, 23 events; expand it to show recorded arguments and return
  values, not prose.
- **Root cause analysis** — the observed-vs-inferred columns. This is the epistemic point:
  facts and reasoning are separated.
- **Proposed fix → 10 safety checks** — expand the details. 10/10 passed; name the
  categories: minimal, expected files only, syntax, no test edits, assertions intact, error
  handling intact, no suspicious operations, failure fixed, no regressions.
- **Debug state machine** — strategy `rules`, iterations `1/8`, no loops. *"It can escalate
  rules → LLM → deep-evidence, or terminate and explain why; it does not spin."*

Close this segment with the blast-radius point:

> "All of this happened in a copy. The repository on disk is untouched. Applying requires a
> separate confirmed action and creates `repro/fix-<id>` — the agent cannot silently commit."

**Fallback:** if the UI fails, switch to the open terminal and run
`python -m repro.cli demo offbyone`. It prints the same investigation as a report and diff
in about 2 seconds. Do not debug the UI live.

### 3:40–4:45 · Part 4 — results and limitations

Quote only these numbers, and say which corpus each belongs to.

| Result | Value |
|---|---|
| Original 9-bug corpus, rules only | **9/9 fixed**, exit 0; CI gate asserts 100% |
| Published per-bug cost | 1 attempt, 72–90% confidence, 1–2 line patches |
| Original run time (published) | 13.7–15.1 s per bug; re-run today: ~2.8 s |
| Second, harder corpus — before new rules | **3/12** patch correctness |
| Second corpus — current rules | **12/12** |
| Diagnosis accuracy on second corpus | 0.35 → **0.675** |
| Root-cause localization | 25% → **100%** |
| False diagnosis rate | **0%** (unchanged) |
| Attempts / time per bug | 1.17 → **1.0** · **2.35 s** average |
| Live demo safety checks | **10/10**, 2.2 s |

Then the caveats, unprompted and in one breath:

- The 9/9 corpus contains exactly the classes the rules were written for — it is a
  regression gate, not evidence of general debugging ability.
- The second corpus started at 3/12; I then added rules for the nine classes it exposed.
  12/12 says "these no longer break", not "works on unseen bugs".
- **No LLM or hybrid numbers.** No API key was configured, so all numbers are rules-only.
  Say "not measured" rather than estimating.
- Python + pytest only; patches are capped at 30 changed lines / 3 files; one failing test
  targeted at a time.
- The sandbox is process-level isolation (copy, stripped environment, timeout); Docker
  isolation is optional. It is not a hardened VM for hostile code.
- Confidence is a rule-derived heuristic, not a calibrated probability.

The honest framing is stronger than the 100%s:

> "I deliberately built a second benchmark that reported my failures, because the first one
> only measured what I already handled. The interesting result is the gap: 3/12, then the
> specific rules I added. That is the methodology I would want to extend."

### 4:45–5:00 · Close

> "The open question I'd want to study here is where the human checkpoint belongs — after
> diagnosis, before the patch is attempted, or only before commit. Right now it is before
> commit, and HIGH-risk patches also require explicit approval before apply. That is the
> oversight question I think is genuinely unresolved."

Then stop talking. Let them ask.

---

## The technical questions — 20–40 second answers

**How does it identify a failure?**
It runs the project's real test suite in a sandbox and parses pytest's output into a
structured failure record: failing test id, error type and message, deepest frame and full
stack. It then re-runs that single test with `--tb=long`; if it does not fail again, the
failure is not considered reproducible. No model is involved in deciding *that* something
failed.

**How does it decide which code to modify?**
Three signals: the deepest failing frame (`file:line`), the runtime trace of the failing
path (arguments, returns, exception locals), and a source window around the failure. The
hypothesis names a `patch_hint` file and line, and the validator restricts the diff to the
failing file, frames on the stack, and that hint. A patch that wanders outside those files
fails check 5 before it is ever applied.

**LLM, rules, or both?**
Both are supported, rules-first. The default engine is deterministic: symptom → rule →
minimal edit. An LLM (OpenAI-compatible, Anthropic, or Ollama) is an optional escalation
rung in the ladder `rules → llm → deep-evidence → terminate`. In this demo no key is set,
so the provider is `None` and the run is pure rules. Every candidate — rule or LLM — passes
the identical validation gate, and an LLM's self-reported risk cannot downgrade a HIGH-risk
finding.

**How do you prevent an incorrect patch from being accepted?**
Ten checks. Seven static checks run **before** applying anything: minimality, only expected
files, syntax, no test edits, assertions intact, error handling intact, no suspicious
operations. Then three dynamic checks after applying in the sandbox: the original failure is
gone, every previously passing test still passes, and no new failure appears. Any regression
reverts the patch. HIGH risk is stored but never auto-applied — it becomes
`needs-approval`. The loop refuses identical hypotheses or patches, and stops after 8
iterations / 3 repair rounds with a termination reason. A patch cannot make tests pass by
editing or weakening them.

**How do you evaluate success?**
Two corpora and per-entry metrics, not one headline number. The original corpus is 9 bugs
with a CI gate at 9/9. The second is 12 harder bugs and reports reproduction rate,
diagnosis accuracy, localization, patch generation, patch correctness, regression-free fix
rate, false diagnosis rate, attempts, time, and token/cost when an LLM is used. Results are
versioned JSON so two REPRO versions can be compared. Current rules-only result on the
second corpus: 12/12, diagnosis 0.675, localization 100%, false diagnosis 0%.

**What happens when the model is unavailable?**
The provider abstraction returns `None`; the agent simply skips the LLM branch and keeps
using the rules. If a provider call throws, the exception is caught, logged as a warning,
and the rule-based result is kept. That is why the demo runs with zero API keys and no
network dependency. The trade-off is coverage: without a model, unsupported failure classes
end in an explicit "no rule matched" fallback rather than a guess.

---

## Follow-ups you may get

**"What if the test itself is wrong?"**
The agent treats tests as the specification and refuses to modify them (static check 7).
If the spec is wrong, the verified patch is wrong in exactly the same way — that is a
fundamental limit of test-based repair, and the reason a human still reviews the diff.

**"Why not just ask an LLM?"**
Because the bottleneck is verification, not generation. An LLM can be plugged in as the
reasoner, but it still has to pass the same executable gate. I have not measured LLM mode,
so I don't claim it is better.

**"What failed in the second benchmark?"**
Initially nine of twelve entries: concurrency, data transformation, exception handling,
external dependencies, incorrect API usage, incorrect conditions, regression, state
transitions, and type errors. They ended in fallback. I added rules for those failure
shapes; that is why the number moved — and why I call it a regression suite, not
generalization.

**"What would an internship add?"**
One of: broaden beyond Python/pytest; turn diagnosis into a learned policy with the current
verifier as reward signal; or study checkpoint placement — where a human checkpoint actually
changes trust or catch rate. The third is closest to Bastian's topic.

---

## If asked for the repo

`README.md` has the architecture, benchmark tables and deploy instructions.
`benchmark_results.json` is the machine-readable 9/9 run.
`backend/repro/benchmark_v2.py` documents the honest metrics and which ones still fail.
`examples/pricewatch/` is a small realistic library whose 4 failures REPRO fixes
(5 passed / 4 failed → 9/9); it is a better "real repo" story than the bundled demos.
