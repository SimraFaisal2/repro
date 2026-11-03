# REPRO — how to demo it, and which numbers you can quote

For the initial meeting with Prof. Keim and Bastian Jäckl.

---

## The one-sentence pitch

> REPRO is an autonomous debugging agent: it reproduces a failing test, records a real
> runtime trace, diagnoses the root cause, generates a minimal patch, and then **proves**
> the fix in an isolated sandbox before a human is allowed to apply it.

The claim to stress: **nothing is fabricated** — every value in the UI comes from actual
execution (pytest output, the recorded trace, the applied diff).

---

## How to show it in the call — pick ONE route

You do not need the cloud, a server, an API key or a deploy. Three ways, easiest first.

### Route B — terminal only (most reliable, use this if anything else fails)

No browser, no build step. Opens in ~15 seconds and prints the whole investigation.

```
cd backend
.venv\Scripts\python -m repro.cli demo offbyone        # Windows
# .venv/bin/python -m repro.cli demo offbyone          # macOS / Linux
```

You'll see the agent's steps stream (`Reproducing failure…` → `Root cause hypothesis…` →
`✓ fix verified in sandbox`), then a full report, then the unified diff. Scroll up slowly
while talking. In Zoom: **Share Screen → the terminal window**.

Other bugs to run instead: `auth`, `api`, `sql`, `auth2`.

### Route A — the dashboard on your laptop (looks best)

Needs two terminal windows open **before** the call:

```
# window 1 — backend
cd backend
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python run.py                  # → http://127.0.0.1:8000
```

```
# window 2 — dashboard
cd frontend
npm install
npm run dev                                  # → http://localhost:5173
```

Then: open **http://localhost:5173** in Chrome/Edge → leave it on the landing page →
Zoom **Share Screen → pick the browser window** (not "Entire Screen") → click **Try REPRO**.

The investigation finishes in about 3 seconds, so narrate *while* it runs.

If `npm run dev` says the port is busy, something else is on 5173 — close it and retry, or
run `npm run dev -- --port 5174` and use that URL.

### Route C — the preview inside this chat

The right-side **Browser panel** in this chat is serving the same dashboard. You can share
that window. Caveat: it depends on this cloud session staying alive; it is not a
self-contained artifact. Route A/B on your own machine are safer for a live meeting.

### 5 minutes before the call

- Run the demo once already (this installs dependencies and warms the caches — the first
  `pip install` / `npm install` is the slow part, not the demo).
- Close Slack/mail, turn on Do Not Disturb so no notification banner appears on screen.
- Press **Ctrl +** a couple of times in the browser to make text readable over Zoom.
- Keep this file open on your phone or a second screen for the script.
- If the dashboard dies mid-demo, switch to Route B in a fresh terminal — it takes seconds.

---

## What you had already claimed vs. what was newly measured

These are two different things. Keep them separate on the call.

### Already published in your repo — these are "your previous numbers"

From `README.md` (line ~224) and the committed artifact `benchmark_results.json`
(run dated 2026-08-25):

| What | Value |
|---|---|
| Fix rate on the 9-repo corpus (rule engine, no LLM) | **9/9 = 100%** |
| By class | NULL dereference 3/3 · Off-by-one 2/2 · API response-shape 2/2 · SQL schema drift 1/1 · Auth logic 1/1 |
| Attempts per bug | 1 |
| Confidence | 72–90% |
| Patch size | 1–2 lines |
| Time per bug | 13.7–15.1 s |
| CI enforcement | `.github/workflows/ci.yml` asserts `fixed == total`, so the gate fails below 100% |

I re-ran this today: **still 9/9**, exit code 0, now 2.8–2.9 s per entry on this machine.

### Newly measured today — not previously stated anywhere

| What | Value |
|---|---|
| Dashboard end-to-end (UI → agent → report) | **fixed**, `1p/2f → 3p/0f`, 10/10 safety checks, 2.9 s |
| `benchmark_v2` (12 harder bugs), rules-only, **before today's rules** | 3/12 = 25% patch correctness |
| `benchmark_v2`, rules-only, **after the full rule set** | **12/12 = 100%** patch correctness |
| └ reproduction rate | 100% |
| └ diagnosis accuracy | 0.35 → **0.68** |
| └ localization rate | 25% → **100%** |
| └ patch generation | 25% → **100%** |
| └ regression-free fix rate | 25% → **100%** |
| └ false diagnosis rate | 0% (unchanged) |
| └ avg attempts / time | 1.17 → **1.0** · 2.96 s |

### Three caveats that keep you honest

1. **9/9 measures the nine failure classes the rules were written for**, so it is close to
   circular. It is a regression gate, not evidence of general debugging ability.
2. **12/12 is a regression suite now, not a generalisation claim.** The rules for the last
   three classes were written *after* seeing this corpus, so 100% says "no longer breaks on
   these", not "works on unseen bugs". Quote the progression honestly: **3/12 with the
   original rule set → 12/12 after adding seven rules for these classes**, measured today on
   this corpus. It is not in your README and no results file is committed for it
   (`benchmark_v2_results.json` does not exist yet).
3. The `63/100` in the `benchmark_v2.py` docstring is an **illustrative example** of honest
   reporting, not a result. Don't quote it. And there are **no** LLM/hybrid numbers —
   no API key was configured, so say "not yet measured" rather than estimating.

Say this out loud, unprompted: *"I deliberately built a second, harder benchmark that
reports my failures, because the first one only measures the classes I already handle."*
That converts your weak spot into the strongest part of the conversation.

---

## The 5-minute script

**1 · Frame it (20 s).** Landing page only. Read the lifecycle strip:
`REPRODUCE → INVESTIGATE → DIAGNOSE → PATCH → VERIFY`. Say: *"The interesting part isn't
that it writes a patch — it's that it refuses to call anything fixed until the tests prove
it."*

**2 · Start the demo (10 s).** Click **Try REPRO**. Narrate while it streams: *"it copies
the repo into a sandbox and runs the real test suite first."*

**3 · Point at the evidence as it appears (90 s).**

- **Failure detected** — `tests/test_windows.py::test_longer`, `IndexError: list index out of range` at `src/windows.py:12`. Real pytest output, not a guess.
- **Root cause** — *"the body accesses `i + 1` but the loop runs over every index."* 90% confidence.
- **Proposed fix** — a 1-line diff: `range(len(xs))` → `range(len(xs) - 1)`. Emphasise **minimal**.
- **Verification** — `1 passed / 2 failed` → `3 passed / 0 failed`.
- **Agent activity** — scroll it. A research group will care about this: every line is a
  state transition (`state=reproduce · strategy=rules`) and the trace capture
  (2 frames, 23 events) is logged *before* the diagnosis.

**4 · Open the full investigation (60 s).** Click **Open full investigation**. Show the
dependency graph, the **trace view** (recorded arguments and return values, not LLM
narration), and the **diff**.

**5 · The oversight story (90 s).** This is the hook for Bastian's topic — *autonomous
agents with human oversight*:

- **10 validation checks** before a patch counts: 3 dynamic (failure fixed, previously
  passing tests still pass, no new failures) + 7 static, run *before* anything is applied
  (minimality, scope, syntax, doesn't edit tests, doesn't disable assertions, doesn't
  remove error handling, no suspicious ops).
- **Risk scoring** LOW / MEDIUM / HIGH — a HIGH-risk patch is stored but **never applied**;
  it blocks on explicit human approval (`needs-approval`).
- **Loop guards + budget**: identical patches or hypotheses are refused; the state machine
  escalates `rules → llm → deep-evidence → terminate` or stops and reports why. 8 iteration
  budget, 3 repair rounds.
- **Blast radius**: the repo only executes inside a sandbox copy; applying to a real
  checkout needs a confirmed click and lands on `repro/fix-<id>`.

Close with: *"The research question I'd want to explore is where the human checkpoint
belongs — after diagnosis, or only before the commit."*

---

## Questions to expect

**"Is this an LLM agent?"**
Rules-first: a deterministic, evidence-grounded engine by default; an LLM
(OpenAI-compatible / Anthropic / Ollama) is an optional escalation rung behind the same
validation gate. Every candidate patch — model or rule — must pass identical checks, and
the LLM's self-reported risk can never downgrade a HIGH-risk finding.

**"How do you stop it gaming the tests?"**
Static checks 7–8 reject patches that edit tests or disable assertions; check 5 restricts
the diff to expected files; check 2 re-runs the whole suite to catch regressions.

**"What happens when it can't fix it?"**
It stops and reports the termination reason plus every hypothesis and patch it tried and
rejected — `failed`, never a fake success. Ambiguous cases end as `needs-approval`.

**"Does it only do Python?"**
Today: Python + pytest, with generic language/framework/dependency/test-runner detection
and a module graph. Other stacks are extension work, not done.

**"What would an internship add?"**
Pick one: (a) broaden beyond Python/JS, (b) turn diagnosis into a learned policy with the
current verifier as reward signal, or (c) study oversight placement — where a checkpoint
actually changes trust or catch rate.

---

## If asked for the repo

`README.md` has architecture, benchmark tables and deploy instructions;
`benchmark_results.json` is the machine-readable 9/9 run; `backend/repro/benchmark_v2.py`
documents the honest metrics and which ones still fail.
