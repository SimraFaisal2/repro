"""The REPRO agent: Observe → Reproduce → Investigate → Diagnose → Patch → Verify.

Runs in a worker thread, streams events to a queue (SSE), and persists
every step to SQLite. Autonomous repair attempts are capped at
MAX_ATTEMPTS; after that the agent stops and explains why.
"""
from __future__ import annotations

import queue as _queue
import threading
import time

from . import ai as ai_mod
from . import analyzer, db, patcher, report, repo as repo_mod, tests, trace, validation
from .config import cfg, strategy_ladder
from .sandbox import Sandbox
from .state import DebugState, State


class EventBus:
    """thread-safe per-investigation event queues."""

    def __init__(self) -> None:
        self._queues: dict[str, _queue.Queue] = {}

    def for_inv(self, iid: str) -> _queue.Queue:
        if iid not in self._queues:
            self._queues[iid] = _queue.Queue()
        return self._queues[iid]

    def emit(self, iid: str, payload: dict) -> None:
        self.for_inv(iid).put(payload)

    def close(self, iid: str) -> None:
        q = self._queues.get(iid)
        if q:
            q.put(None)  # sentinel


bus = EventBus()


class Agent:
    def __init__(self, iid: str):
        self.iid = iid

    # ------------------------------------------------------------- helpers
    def _step(self, message: str, kind: str = "info") -> None:
        row = db.add_step(self.iid, message, kind)
        bus.emit(self.iid, {"type": "step", "ts": row["ts"], "message": message, "kind": kind})

    def _status(self, status: str) -> None:
        db.update_investigation(self.iid, status=status)
        bus.emit(self.iid, {"type": "status", "status": status})

    def _ctx(self) -> tuple[dict, dict]:
        inv = db.get_investigation(self.iid)
        project = db.get_project(inv["project_id"])
        return inv, project

    # --------------------------------------------------------------- main
    def run(self) -> None:
        started = time.time()
        try:
            self._status("running")
            inv, project = self._ctx()
            self._step(f"Starting investigation of `{project['name']}`", "info")
            self._step(f"Agent ready — provider: {ai_mod.provider_label()}", "info")

            source = project["local_path"]
            sandbox = Sandbox(f"inv-{self.iid}", source)
            self._step("Isolated workspace prepared", "success")

            # 1. analyze repository
            self._step("Analyzing repository structure…", "progress")
            overview = repo_mod.analyze_project(source)
            db.update_project_overview(project["id"], overview)
            self._step(f"Project: {overview['language']} · {overview['framework']} · "
                       f"{overview['test_framework']} · {overview['files']} files", "info")
            self._step(f"Package manager: {overview['package_manager']} · "
                       f"{overview['dependencies_count']} dependencies · "
                       f"{len(overview['graph']['modules'])} modules", "info")

            # 2. dependencies in isolation
            ok, msg = sandbox.install_dependencies(overview)
            self._step(msg, "success" if ok else "error")

            # 3. discover tests
            self._step("Discovering tests…", "progress")
            test_ids = tests.discover(sandbox)
            self._step(f"{len(test_ids)} tests discovered", "info")

            # 4. baseline suite
            self._step("Running test suite (baseline)…", "progress")
            run = tests.run_suite(sandbox)
            db.add_test_run(self.iid, "baseline", run["total"], run["passed"],
                            run["failed"] + run["error"], run["skipped"], run["duration"],
                            run.get("output", ""))
            self._step(f"Baseline: {run['passed']} passed, {run['failed']} failed, "
                       f"{run['skipped']} skipped in {run['duration']:.1f}s",
                       "success" if run["failed"] == 0 else "error")

            if run["failed"] + run["error"] == 0:
                self._step("No failing tests — nothing to repair", "success")
                self._status("no-failure")
                self._merge_summary(project)  # preserves _trace/_hypothesis
                self._finish(started)
                return

            # 5. autonomous debugging state machine
            remaining = set(run["failed_ids"]) or set(test_ids)
            baseline = {"passed": run["passed"], "failed": run["failed"],
                        "total": run["total"], "failed_ids": run.get("failed_ids") or []}
            debug = DebugState(cfg.debug_budget, ladder=strategy_ladder())
            debug.transition(State.REPRODUCE)
            self._step(f"Entering autonomous debugging state machine — budget "
                       f"{debug.budget} iterations · strategy ladder "
                       f"{' → '.join(debug.ladder)} "
                       f"(mode: {cfg.strategy_mode})", "info")

            while debug.can_continue:
                if debug.strategy == "terminate":
                    self._terminate(debug, project, started,
                                    "strategy ladder exhausted")
                    return
                debug.iteration += 1
                if not remaining:
                    remaining = set(run["failed_ids"]) or remaining
                target = sorted(remaining)[0]
                self._step(f"[{debug.iteration}/{debug.budget}] state={debug.state.value} · "
                           f"strategy={debug.strategy} · target `{target}`", "info")
                result = self._attempt(sandbox, overview, [target], baseline, debug)
                status = result.get("status", "unverified")

                if status == "fixed":
                    full = result.get("full") or {}
                    db.update_investigation(self.iid, attempts=debug.iteration,
                                            confidence=self._confidence())
                    debug.transition(State.SUCCESS)
                    if full.get("failed", 0) == 0:
                        self._step(f"✓ Full suite green: {full['passed']}/{full['total']} "
                                   "passed — no regressions", "success")
                    else:
                        self._step(f"✓ Target fixed — {full['passed']}/{full['total']} "
                                   f"pass, {full['failed']} remaining baseline failure(s)",
                                   "success")
                    self._status("fixed")
                    self._merge_summary(project)  # preserves _trace/_hypothesis
                    self._store_debug(debug)
                    self._finish(started)
                    return
                if status == "needs-approval":
                    debug.transition(State.TERMINATED)
                    debug.termination = "high-risk patch stored — explicit human approval required"
                    self._step("HIGH-risk patch requires explicit human confirmation — "
                               "it has been stored for review, nothing was applied", "warn")
                    db.update_investigation(self.iid, attempts=debug.iteration,
                                            confidence=self._confidence())
                    self._status("needs-approval")
                    self._merge_summary(project)
                    self._store_debug(debug)
                    self._finish(started)
                    return
                if status == "regression":
                    new = result.get("new_failures", [])
                    self._step(f"Patch reverted — {len(new)} previously passing test(s) now "
                               f"fail: {', '.join(new[:3])}", "error")
                elif status == "loop":
                    self._step(f"Loop guard: {result.get('loop_type', 'loop')} — "
                               f"{result.get('detail', '')}", "warn")

                # loop detection across the whole history, then strategy change
                loops = debug.detect_loops()
                if loops:
                    detail = "; ".join(f"{l['type']} ({l['detail'][:36]})" for l in loops)
                    self._step(f"Loop detected — escalating strategy: {detail}", "warn")
                    if not debug.escalate() or debug.strategy == "terminate":
                        self._terminate(debug, project, started,
                                        f"loop detected, strategy ladder exhausted: {detail}")
                        return
                    debug.transition(State.REASSESS)
                    remaining.discard(target)   # stop spinning on the stuck target
                    if not remaining:
                        remaining = set(run["failed_ids"]) or remaining
                    continue

                # no loop — the current strategy simply failed on this target;
                # try the next failing test, then escalate once all are exhausted
                debug.transition(State.REASSESS)
                remaining.discard(target)
                if not remaining:
                    if debug.escalate():
                        remaining = set(run["failed_ids"]) or remaining
                        self._step(f"Strategy `{debug.strategy}` failed on all targets — "
                                   f"escalating", "warn")
                        continue
                    self._terminate(debug, project, started,
                                    f"budget {debug.budget} exhausted without a verified fix "
                                    f"({len(debug.hypotheses)} hypotheses, "
                                    f"{len(debug.patches)} patches attempted)")
                    return

        except Exception as e:  # noqa: BLE001
            db.add_step(self.iid, f"Agent error: {e}", "error")
            try:
                self._status("failed")
            except Exception:
                pass
            self._finish(started)

    # ------------------------------------------------------------ attempts
    def _attempt(self, sandbox: Sandbox, overview: dict, failing_ids: list[str],
                 baseline: dict, debug: DebugState) -> dict:
        """One debug cycle for one failing test, run inside the state machine.

        REPRODUCE → INVESTIGATE → HYPOTHESIZE → RANK → PATCH → VERIFY, with
        the failure feedback loop (ANALYZE FAILURE → REASSESS → COLLECT
        EVIDENCE → new patch → VERIFY) handled by the state machine driver.

        Loop guards here prevent the agent from re-applying identical patches
        or re-ranking identical hypotheses. Returns
        {"status": "fixed"|"needs-approval"|"regression"|"rejected"|
        "loop"|"unverified", ...}.
        """
        if not failing_ids:
            return {"status": "unverified"}
        target = failing_ids[0]
        debug.transition(State.REPRODUCE)
        self._step(f"Targeting failing test: `{target}`", "info")

        # ---- REPRODUCE
        self._step("Reproducing failure…", "progress")
        rep = tests.run_single(sandbox, target)
        failure = rep.get("failure")
        if not failure:
            self._step(f"`{target}` no longer fails in isolation — skipping", "warn")
            return {"status": "unverified"}
        db.add_failure(self.iid, "", failure)
        debug.record_failure(failure, debug.strategy)
        bus.emit(self.iid, {"type": "failure", "failure": failure})
        self._step(f"Failure reproduced: {failure['error_type']} — {failure['error_msg'][:120]}",
                   "error")
        # same failure re-attempted under the SAME strategy with no new
        # evidence ⇒ no new information (a strategy change is an escalation,
        # not a loop, and is allowed to proceed)
        if debug.same_failure_no_new_evidence(failure, debug.strategy):
            return {"status": "loop",
                    "loop_type": "failure-repeated-no-new-evidence",
                    "detail": f"{failure.get('test_id')} seen before without new evidence"}

        # ---- INVESTIGATE
        debug.transition(State.INVESTIGATE)
        self._step("Capturing runtime execution trace…", "progress")
        traced = trace.run_traced(sandbox, target)
        events = traced.get("events", [])
        db.add_events(self.iid, events)
        tdisp = trace.build_trace(failure, events, sandbox, truncated=traced.get("truncated", False))
        frames = tdisp["frames"]
        self._store_trace(tdisp)
        bus.emit(self.iid, {"type": "trace", "trace": tdisp})
        slice_ = tdisp["slice"]
        self._step(f"Runtime trace captured: {len(frames)} frames, {len(events)} events "
                   f"· failure slice {slice_['frames']} frames @ depth {slice_['max_depth']}",
                   "info")

        # ---- HYPOTHESIZE
        debug.transition(State.HYPOTHESIZE)
        self._step("Analyzing evidence…", "progress")
        hypothesis = analyzer.analyze_failure(sandbox, failure, events, frames, rep, overview.get("graph"))
        self._store_hypothesis(hypothesis)
        bus.emit(self.iid, {"type": "hypothesis", "hypothesis": hypothesis})
        self._step(f"Root cause hypothesis: {hypothesis['root_cause']} "
                   f"(confidence {hypothesis['confidence']:.0%})", "info")
        debug.record_evidence(hypothesis.get("evidence", []))
        # ---- RANK: never re-rank an identical hypothesis under the SAME
        # strategy (an escalated strategy is a legitimate escalation — the
        # agent is trying harder on the same evidence, e.g. deep-evidence
        # feeds the attempt history back to the model)
        if debug.hypothesis_already_tried(hypothesis, debug.strategy):
            self._step("Identical hypothesis already tried under this strategy — "
                       "refusing to re-rank", "warn")
            return {"status": "loop", "loop_type": "hypothesis-repeated",
                    "detail": hypothesis.get("root_cause", "")[:120]}
        debug.record_hypothesis(hypothesis, "tried", debug.strategy)

        debug.transition(State.RANK)
        provider = ai_mod.get_provider()
        strategy = debug.strategy

        # 1) deterministic, evidence-grounded patch first — PLAN only, so the
        #    sandbox stays untouched until every static check has passed
        plan = None
        if strategy == "rules" and hypothesis.get("patch_hint"):
            self._step("Generating minimal patch…", "progress")
            plan = patcher.plan_patch(sandbox, hypothesis, self.iid)
            if plan:
                self._step(f"Candidate patch: {plan['files_changed']} file(s), "
                           f"+{plan['lines_added']} / -{plan['lines_removed']}", "info")
        elif strategy != "rules":
            self._step(f"Strategy `{strategy}` — going straight to LLM repair", "info")

        # 2) static validation of the candidate (checks 4-10), BEFORE apply
        debug.transition(State.PATCH)
        checks: list[dict] = []
        static_failed: list[str] = []
        if plan:
            # loop guard: never re-apply an essentially identical patch
            if debug.patch_already_tried(plan):
                self._step("Identical patch already attempted — refusing to re-apply", "warn")
                return {"status": "loop", "loop_type": "patch-repeated",
                        "detail": plan.get("rule", "")}
            expected = self._expected_files(failure, hypothesis)
            checks = validation.validate_static(plan["diff"], plan, expected)
            checks += validation.validate_syntax_edits(sandbox, plan["edits"])
            if validation.all_pass(checks):
                self._step("Static validation passed (minimality, scope, syntax, "
                           "tests/assertions/error-handling intact, no suspicious ops)", "success")
                if not patcher.apply_plan(sandbox, plan):
                    return {"status": "rejected", "failed_checks": ["apply"]}
                plan["applied"] = True
            else:
                static_failed = [c["id"] for c in checks if c["status"] == "fail"]
                self._step(f"Rule-based candidate rejected by static validation "
                           f"({', '.join(static_failed)}) — consulting LLM if available", "warn")
                debug.record_patch(plan, "rejected-static")
                plan = None

        # 3) LLM escape hatch when rules cannot produce a valid patch
        verified = None
        if plan:
            verified = self._verify_target(sandbox, target, baseline)
        if (verified is None or not verified["ok"]) and provider:
            debug.transition(State.ANALYZE_FAILURE)
            if plan:
                self._step("Rule-based patch did not verify — consulting LLM", "warn")
                patcher.revert_patch(sandbox, self.iid)
                debug.record_patch(plan, "unverified")
                plan = None
            self._step(f"Consulting {provider.name}…", "progress")
            try:
                ctx: dict = {
                    "failure": failure,
                    "source_context": self._source_context(sandbox, failure),
                    "evidence": hypothesis.get("evidence", []),
                    "trace": frames,
                }
                if strategy == "deep-evidence":
                    # feed the agent's own history back so the model sees what
                    # has already been tried and rejected
                    ctx["history"] = {
                        "hypotheses": [{"root_cause": h["root_cause"], "rule": h["rule"],
                                         "result": h["result"]} for h in debug.hypotheses],
                        "patches": [{"rule": p["rule"], "result": p["result"]}
                                     for p in debug.patches],
                    }
                fix = provider.analyze_and_fix(ctx)
                llm_patch = None
                if fix and fix.get("fix"):
                    raw_diff = (fix["fix"] or {}).get("diff") or ""
                    if not raw_diff:
                        self._step("LLM returned no diff", "warn")
                    else:
                        # static validation on the RAW diff BEFORE applying
                        expected = self._expected_files(failure, hypothesis)
                        lchecks = validation.validate_static(
                            raw_diff, validation.stats_from_diff(raw_diff), expected)
                        if not validation.all_pass(lchecks):
                            failed = [c["id"] for c in lchecks if c["status"] == "fail"]
                            self._step(f"LLM patch rejected by static validation "
                                       f"({', '.join(failed)})", "warn")
                        else:
                            llm_patch = patcher.llm_diff_to_patch(sandbox, fix["fix"], fix, self.iid)
                            if not llm_patch:
                                self._step("LLM diff could not be applied in the sandbox", "warn")
                if llm_patch:
                    expected = self._expected_files(failure, hypothesis)
                    lchecks = validation.validate_static(llm_patch["diff"], llm_patch, expected)
                    lchecks += validation.validate_syntax(sandbox, llm_patch["diff"])
                    if validation.all_pass(lchecks):
                        llm_ver = self._verify_target(sandbox, target, baseline)
                        if llm_ver and llm_ver["ok"]:
                            plan = llm_patch
                            verified = llm_ver
                            checks = lchecks
                            self._step(f"LLM patch verified ({plan['files_changed']} file(s))",
                                       "success")
                        else:
                            patcher.revert_patch(sandbox, self.iid)
                            debug.record_patch(llm_patch, "unverified")
                            self._step("LLM patch did not verify either", "warn")
                    else:
                        patcher.revert_patch(sandbox, self.iid)
                        failed = [c["id"] for c in lchecks if c["status"] == "fail"]
                        debug.record_patch(llm_patch, "rejected-static")
                        self._step(f"LLM patch rejected by validation ({', '.join(failed)})",
                                   "warn")
            except Exception as e:  # noqa: BLE001
                self._step(f"LLM provider failed ({e}) — keeping rule-based result", "warn")

        if not plan or verified is None or not verified["ok"]:
            if not plan:
                if static_failed:
                    self._step("No patch passed validation — nothing was applied", "error")
                    return {"status": "rejected", "failed_checks": static_failed}
                self._step("No confident patch could be generated from the evidence", "error")
            return {"status": "unverified"}

        # 4) full suite → checks 1-3 + regression analysis
        debug.transition(State.VERIFY)
        self._step("Running full test suite for regression analysis…", "progress")
        full = tests.run_suite(sandbox)
        db.add_test_run(self.iid, "full", full["total"], full["passed"],
                        full["failed"], full["skipped"], full["duration"])
        regression = validation.analyze_regression(baseline, full)
        checks += [
            validation.check("failure-fixed", "Original failure is fixed",
                             target not in set(full.get("failed_ids") or []),
                             f"`{target}` passes in full suite"),
            validation.check("previously-passing-tests",
                             "All previously passing tests still pass",
                             not regression["new_failures"],
                             f"new: {', '.join(regression['new_failures'][:3]) or 'none'}"),
            validation.check("no-new-failures", "No new test failures appear",
                             not regression["new_failures"],
                             f"new: {', '.join(regression['new_failures'][:3]) or 'none'}"),
        ]

        # 5) risk score + patch report. Base risk ALWAYS comes from the
        #    analyzer's hypothesis — an LLM-provided fix dict must never be
        #    allowed to downgrade a HIGH-risk failure to MEDIUM.
        risk = validation.score_risk(hypothesis.get("risk", "MEDIUM"), checks,
                                     regression, plan)
        tests_affected = [target] + (hypothesis.get("related_tests") or [])
        # score the risk BEFORE building the report so report.risk reflects
        # the final (possibly escalated) risk, not the base hypothesis risk
        scored = {**plan, "risk": risk}
        patch = {**scored, "checks": checks,
                 "report": validation.build_report(scored, hypothesis, checks, regression,
                                                    tests_affected)}
        patch.pop("edits", None)
        stored = db.add_patch(self.iid, patch)
        patch["id"] = stored["id"]
        # full-suite verification record (dashboard Verification panel)
        db.add_verification(self.iid, regression["before"], regression["after"], full,
                            full["failed"] == 0)
        self._step(f"Regression analysis: {regression['status']} — "
                   f"{len(regression['fixed_now'])} fixed, "
                   f"{len(regression['new_failures'])} new failures", "info")
        self._step(f"Patch risk: {risk} · confidence "
                   f"{(patch.get('confidence') or 0) * 100:.0f}%", "info")

        if regression["status"] == "new-failures":
            # checks 1-3 not all satisfied → patch must not be considered a fix
            patcher.revert_patch(sandbox, self.iid)
            patch["status"] = "rejected"
            debug.record_patch(patch, "rejected")
            db.update_patch(patch["id"], status="rejected")
            bus.emit(self.iid, {"type": "patch", "patch": patch})
            return {"status": "regression", "new_failures": regression["new_failures"],
                    "patch": patch}
        if risk == "HIGH":
            # high-risk patch: verify done, but require explicit human approval
            patch["status"] = "needs-approval"
            debug.record_patch(patch, "needs-approval")
            db.update_patch(patch["id"], status="needs-approval")
            bus.emit(self.iid, {"type": "patch", "patch": patch})
            return {"status": "needs-approval", "patch": patch}
        patch["status"] = "fixed"
        debug.record_patch(patch, "fixed")
        bus.emit(self.iid, {"type": "patch", "patch": patch})
        return {"status": "fixed", "patch": patch, "full": full}

    def _expected_files(self, failure: dict, hypothesis: dict) -> set[str]:
        """Files the patch is *allowed* to touch: failing file, its frames,
        and the patch-hint target."""
        expected = {failure.get("file", "").replace("\\", "/")}
        for fr in failure.get("frames") or []:
            if fr.get("file"):
                expected.add(fr["file"].replace("\\", "/"))
        hint = hypothesis.get("patch_hint") or {}
        if hint.get("file"):
            expected.add(hint["file"].replace("\\", "/"))
        return {f for f in expected if f}

    def _verify_target(self, sandbox: Sandbox, target: str, before: dict,
                       announce: bool = True) -> dict | None:
        """Re-run the failing test after a patch; record the verification."""
        if announce:
            self._step("Verifying fix — rerunning the failing test…", "progress")
        ver = tests.run_single(sandbox, target)
        after = {"passed": 1 if ver["ok"] else 0, "failed": 0 if ver["ok"] else 1,
                 "total": 1}
        db.add_test_run(self.iid, "verify", 1, 1 if ver["ok"] else 0,
                        0 if ver["ok"] else 1, 0, ver["duration"])
        if ver["ok"]:
            if announce:
                self._step(f"✓ `{target}` now passes — fix verified in sandbox", "success")
            db.add_verification(self.iid, before, after, None, True)
            bus.emit(self.iid, {"type": "verification",
                                "verification": {"before": before, "after": after, "passed": True}})
        else:
            if announce:
                self._step(f"`{target}` still fails after patch — {ver['failure']['error_type']}: "
                           f"{ver['failure']['error_msg'][:120]}", "error")
            db.add_verification(self.iid, before, after, None, False)
            bus.emit(self.iid, {"type": "verification",
                                "verification": {"before": before, "after": after, "passed": False}})
        return ver

    def _source_context(self, sandbox: Sandbox, failure: dict) -> str:
        file = failure.get("file")
        line = failure.get("line")
        if not file:
            return ""
        p = sandbox.root / file
        if not p.exists():
            return ""
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            return ""
        lo, hi = max(0, line - 10), min(len(lines), line + 6)
        return "\n".join(f"{i + 1}: {lines[i]}" for i in range(lo, hi))

    def _confidence(self) -> float:
        patches = db.get_investigation(self.iid).get("patches") or []
        confs = [p.get("confidence") for p in patches if p.get("confidence") is not None]
        return round(sum(confs) / len(confs), 3) if confs else 0.0

    def _merge_summary(self, project: dict) -> None:
        """Merge the report summary INTO the existing summary so the stored
        _trace/_hypothesis blobs survive the final write (a plain overwrite
        would clobber them before _finish)."""
        inv = db.get_investigation(self.iid)
        summary = dict(inv.get("summary") or {})
        summary.update(report.build_summary(inv, project))
        db.update_investigation(self.iid, summary_json=summary)

    def _store_trace(self, tdisp: dict) -> None:
        inv = db.get_investigation(self.iid)
        summary = dict(inv.get("summary") or {})
        summary["_trace"] = tdisp
        db.update_investigation(self.iid, summary_json=summary)

    def _store_hypothesis(self, hypothesis: dict) -> None:
        inv = db.get_investigation(self.iid)
        summary = dict(inv.get("summary") or {})
        summary["_hypothesis"] = hypothesis
        db.update_investigation(self.iid, summary_json=summary)

    def _store_debug(self, debug: DebugState) -> None:
        """Persist the state machine's full history (state, iterations,
        hypotheses/patches/failures attempted, loops, termination reason)
        into the investigation summary so the dashboard can render it."""
        inv = db.get_investigation(self.iid)
        summary = dict(inv.get("summary") or {})
        summary["_debug"] = debug.to_dict()
        db.update_investigation(self.iid, summary_json=summary)

    def _terminate(self, debug: DebugState, project: dict, started: float,
                   reason: str) -> None:
        """Terminate the debug session with a detailed failure report: the
        reason, plus everything that was attempted and rejected."""
        debug.transition(State.TERMINATED)
        debug.termination = reason
        self._step(f"Debug session terminated — {reason}", "error")
        db.update_investigation(self.iid, attempts=debug.iteration,
                                confidence=self._confidence())
        self._status("failed")
        self._merge_summary(project)
        self._store_debug(debug)
        self._finish(started)

    def _finish(self, started: float) -> None:
        dur = time.time() - started
        self._step(f"Investigation finished in {dur:.1f}s", "success")
        inv = db.get_investigation(self.iid)
        summary = dict(inv.get("summary") or {})
        summary.update(report.build_summary(inv, db.get_project(inv["project_id"])))
        db.update_investigation(self.iid, summary_json=summary)
        bus.emit(self.iid, {"type": "done", "status": inv.get("status")})
        bus.close(self.iid)


def start_agent(iid: str) -> threading.Thread:
    t = threading.Thread(target=Agent(iid).run, daemon=True)
    t.start()
    return t
