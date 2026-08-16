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
from . import analyzer, db, patcher, report, repo as repo_mod, tests, trace
from .config import cfg
from .sandbox import Sandbox


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
                summary = report.build_summary(db.get_investigation(self.iid), project)
                db.update_investigation(self.iid, summary_json=summary)
                self._finish(started)
                return

            # 5. repair loop
            remaining = set(run["failed_ids"]) or set(test_ids)
            baseline = {"passed": run["passed"], "failed": run["failed"],
                        "total": run["total"]}
            for attempt in range(1, cfg.max_attempts + 1):
                self._step(f"Repair attempt {attempt}/{cfg.max_attempts}", "info")
                fixed = self._attempt(sandbox, overview, sorted(remaining), baseline)
                if fixed:
                    # full suite in the patched sandbox
                    self._step("Running full test suite to check for regressions…", "progress")
                    full = tests.run_suite(sandbox)
                    ver = db.add_verification(
                        self.iid, run, None, full, full["failed"] == 0)
                    db.add_test_run(self.iid, "full", full["total"], full["passed"],
                                    full["failed"], full["skipped"], full["duration"])
                    if full["failed"] == 0:
                        db.update_investigation(self.iid, attempts=attempt, confidence=
                                                self._confidence())
                        self._step(f"✓ Full suite green: {full['passed']}/{full['total']} passed",
                                   "success")
                        self._status("fixed")
                        summary = report.build_summary(db.get_investigation(self.iid), project)
                        db.update_investigation(self.iid, summary_json=summary)
                        self._finish(started)
                        return
                    self._step(f"Target test fixed, but {full['failed']} other test(s) still fail — "
                               "continuing investigation", "warn")
                    remaining = set(full["failed_ids"]) or remaining
                else:
                    self._step(f"Attempt {attempt} could not be verified", "warn")

            # 6. exhausted
            inv_now = db.get_investigation(self.iid)
            self._step(f"Reached {cfg.max_attempts} autonomous repair attempts without full "
                       "verification. The remaining failures likely need a human or an LLM "
                       "provider (set OPENAI_API_KEY / ANTHROPIC_API_KEY / OLLAMA_URL).", "error")
            db.update_investigation(self.iid, attempts=cfg.max_attempts,
                                    confidence=self._confidence())
            self._status("failed")
            summary = report.build_summary(inv_now, project)
            db.update_investigation(self.iid, summary_json=summary)
            self._finish(started)

        except Exception as e:  # noqa: BLE001
            db.add_step(self.iid, f"Agent error: {e}", "error")
            try:
                self._status("failed")
            except Exception:
                pass
            self._finish(started)

    # ------------------------------------------------------------ attempts
    def _attempt(self, sandbox: Sandbox, overview: dict, failing_ids: list[str],
                 baseline: dict) -> bool:
        """Try to fix one failing test. Returns True if the targeted test passes."""
        if not failing_ids:
            return False
        target = failing_ids[0]
        self._step(f"Targeting failing test: `{target}`", "info")

        # reproduce
        self._step("Reproducing failure…", "progress")
        rep = tests.run_single(sandbox, target)
        failure = rep.get("failure")
        if not failure:
            self._step(f"`{target}` no longer fails in isolation — skipping", "warn")
            return False
        db.add_failure(self.iid, "", failure)
        bus.emit(self.iid, {"type": "failure", "failure": failure})
        self._step(f"Failure reproduced: {failure['error_type']} — {failure['error_msg'][:120]}",
                   "error")

        # runtime trace
        self._step("Capturing runtime execution trace…", "progress")
        traced = trace.run_traced(sandbox, target)
        events = traced.get("events", [])
        db.add_events(self.iid, events)
        tdisp = trace.build_trace(failure, events, sandbox)
        self._store_trace(tdisp)
        bus.emit(self.iid, {"type": "trace", "trace": tdisp})
        self._step(f"Runtime trace captured: {len(tdisp)} frames, {len(events)} traced events",
                   "info")

        # analyze
        self._step("Analyzing evidence…", "progress")
        hypothesis = analyzer.analyze_failure(sandbox, failure, events, tdisp, rep, overview.get("graph"))
        self._store_hypothesis(hypothesis)
        bus.emit(self.iid, {"type": "hypothesis", "hypothesis": hypothesis})
        self._step(f"Root cause hypothesis: {hypothesis['root_cause']} "
                   f"(confidence {hypothesis['confidence']:.0%})", "info")

        provider = ai_mod.get_provider()

        # 1) deterministic, evidence-grounded patch first
        patch = None
        if hypothesis.get("patch_hint"):
            self._step("Generating minimal patch…", "progress")
            patch = patcher.generate_patch(sandbox, hypothesis, self.iid)
            if patch:
                self._step(f"Patch generated: {patch['files_changed']} file(s), "
                           f"+{patch['lines_added']} / -{patch['lines_removed']}", "info")

        # 2) LLM escape hatch when rules cannot repair the failure
        verified = None
        if patch:
            verified = self._verify_target(sandbox, target, baseline)
        if (verified is None or not verified["ok"]) and provider:
            if patch:
                self._step("Rule-based patch did not verify — consulting LLM", "warn")
            self._step(f"Consulting {provider.name}…", "progress")
            try:
                fix = provider.analyze_and_fix({
                    "failure": failure,
                    "source_context": self._source_context(sandbox, failure),
                    "evidence": hypothesis.get("evidence", []),
                    "trace": tdisp,
                })
                llm_patch = None
                if fix and fix.get("fix"):
                    llm_patch = patcher.llm_diff_to_patch(sandbox, fix["fix"], fix, self.iid)
                if llm_patch:
                    llm_ver = self._verify_target(sandbox, target, baseline)
                    if llm_ver and llm_ver["ok"]:
                        patch = llm_patch
                        verified = llm_ver
                        self._step(f"LLM patch verified ({patch['files_changed']} file(s))", "success")
                    else:
                        self._step("LLM patch did not verify either", "warn")
            except Exception as e:  # noqa: BLE001
                self._step(f"LLM provider failed ({e}) — keeping rule-based result", "warn")

        if not patch or verified is None or not verified["ok"]:
            if not patch:
                self._step("No confident patch could be generated from the evidence", "error")
            return False
        db.add_patch(self.iid, patch)
        bus.emit(self.iid, {"type": "patch", "patch": patch})
        return True

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

    def _store_trace(self, tdisp: list[dict]) -> None:
        inv = db.get_investigation(self.iid)
        summary = dict(inv.get("summary") or {})
        summary["_trace"] = tdisp
        db.update_investigation(self.iid, summary_json=summary)

    def _store_hypothesis(self, hypothesis: dict) -> None:
        inv = db.get_investigation(self.iid)
        summary = dict(inv.get("summary") or {})
        summary["_hypothesis"] = hypothesis
        db.update_investigation(self.iid, summary_json=summary)

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
