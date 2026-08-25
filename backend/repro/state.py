"""Autonomous debugging state machine.

REPRO's agent is no longer a linear pipeline — it is a state machine that can
reason in loops:

    OBSERVE → REPRODUCE → INVESTIGATE → HYPOTHESIZE → RANK → PATCH → VERIFY
        └────────── ▲                                   │        │
                    │            ANALYZE FAILURE ←──────┘        │ fail
                    │            REASSESS → COLLECT EVIDENCE → new hypothesis
                    └────────────────────────────────────────────┘

The machine tracks explicit state, an iteration counter, a maximum debugging
budget, and four histories (hypotheses, patches, evidence, failures). Loop
detection compares normalized *signatures* so the agent never repeatedly
applies essentially identical patches, never re-ranks an identical hypothesis,
and terminates when an investigation produces no new information.
"""
from __future__ import annotations

import enum
import hashlib
import json
import re


class State(str, enum.Enum):
    OBSERVE = "observe"
    REPRODUCE = "reproduce"
    INVESTIGATE = "investigate"
    HYPOTHESIZE = "hypothesize"
    RANK = "rank"
    PATCH = "patch"
    VERIFY = "verify"
    ANALYZE_FAILURE = "analyze-failure"
    REASSESS = "reassess"
    COLLECT_EVIDENCE = "collect-evidence"
    SUCCESS = "success"
    TERMINATED = "terminated"


# Strategy ladder: when a loop is detected (or a strategy produces nothing new),
# the agent escalates to the next, more powerful strategy before terminating.
# A benchmark mode may substitute a restricted ladder (e.g. rules-only or
# LLM-only) via DebugState(ladder=...).
STRATEGY_LADDER = ["rules", "llm", "deep-evidence", "terminate"]

# How many times the same signature may be seen before it is a loop.
LOOP_LIMIT = 2

_WS = re.compile(r"\s+")


# --------------------------------------------------------------------------
# signatures (normalized identity) for loop detection
# --------------------------------------------------------------------------
def _norm_diff(diff: str) -> str:
    """Whitespace-insensitive diff fingerprint (line numbers ignored)."""
    lines = []
    for l in (diff or "").splitlines():
        if l.startswith(("---", "+++", "@@", "diff", "index")):
            continue
        lines.append(_WS.sub("", l))
    return "\n".join(lines)


def hypothesis_sig(h: dict) -> str:
    """Identity of a hypothesis: rule + root cause + patch hint."""
    hint = h.get("patch_hint") or {}
    key = (h.get("rule", ""), h.get("root_cause", ""),
           json.dumps(hint, sort_keys=True))
    return hashlib.sha1(json.dumps(key).encode()).hexdigest()[:16]


def patch_sig(patch: dict) -> str:
    """Identity of a patch: whitespace-insensitive diff."""
    return hashlib.sha1(_norm_diff(patch.get("diff", "")).encode()).hexdigest()[:16]


def failure_sig(f: dict) -> str:
    """Identity of a failure: test + error + location."""
    key = (f.get("test_id", ""), f.get("error_type", ""),
           (f.get("error_msg") or "")[:120], f.get("file", ""), f.get("line"))
    return hashlib.sha1(json.dumps(key).encode()).hexdigest()[:16]


def evidence_sig(evidence: list[dict]) -> str:
    """Identity of a set of evidence: sorted evidence texts."""
    texts = sorted(e.get("text", "") for e in (evidence or []))
    return hashlib.sha1(json.dumps(texts).encode()).hexdigest()[:16]


# --------------------------------------------------------------------------
# the debug state machine
# --------------------------------------------------------------------------
class DebugState:
    def __init__(self, budget: int, ladder: list[str] | None = None) -> None:
        self.state: State = State.OBSERVE
        self.iteration: int = 0
        self.budget: int = max(1, budget)
        self.ladder: list[str] = list(ladder) if ladder else list(STRATEGY_LADDER)
        self.strategy_index: int = 0
        # histories
        self.hypotheses: list[dict] = []   # {sig, rule, root_cause, confidence, result}
        self.patches: list[dict] = []      # {sig, rule, risk, status, lines_added}
        self.failures: list[dict] = []     # {sig, test_id, error_type, error_msg}
        self.evidence: list[str] = []      # evidence signatures observed
        self.loops: list[dict] = []        # {type, detail, iteration}
        self.termination: str = ""

    # ------------------------------------------------------------- states
    @property
    def strategy(self) -> str:
        return self.ladder[min(self.strategy_index, len(self.ladder) - 1)]

    @property
    def can_continue(self) -> bool:
        return (self.state not in (State.SUCCESS, State.TERMINATED)
                and self.iteration < self.budget)

    def transition(self, state: State) -> None:
        self.state = state

    def escalate(self) -> bool:
        """Move to the next strategy. Returns False when the ladder is
        exhausted (strategy == 'terminate'), meaning the agent should stop."""
        if self.strategy_index < len(self.ladder) - 1:
            self.strategy_index += 1
            return True
        return False

    # ------------------------------------------------------------ records
    def record_hypothesis(self, h: dict, result: str, strategy: str = "") -> None:
        self.hypotheses.append({
            "sig": hypothesis_sig(h),
            "rule": h.get("rule", ""),
            "root_cause": h.get("root_cause", ""),
            "confidence": h.get("confidence"),
            "result": result,
            "strategy": strategy,
        })

    def record_patch(self, patch: dict, result: str) -> None:
        self.patches.append({
            "sig": patch_sig(patch),
            "rule": patch.get("rule", ""),
            "risk": patch.get("risk", ""),
            "status": patch.get("status", result),
            "result": result,
            "lines_added": patch.get("lines_added", 0),
            "lines_removed": patch.get("lines_removed", 0),
        })

    def record_failure(self, f: dict, strategy: str = "") -> None:
        self.failures.append({
            "sig": failure_sig(f),
            "test_id": f.get("test_id", ""),
            "error_type": f.get("error_type", ""),
            "error_msg": (f.get("error_msg") or "")[:120],
            "strategy": strategy,
        })

    def record_evidence(self, evidence: list[dict]) -> None:
        sig = evidence_sig(evidence)
        if sig not in self.evidence:
            self.evidence.append(sig)

    # ----------------------------------------------------- loop detection
    def _sigs(self, kind: str) -> list[str]:
        return [x["sig"] for x in getattr(self, kind)]

    def detect_loops(self) -> list[dict]:
        """Return the loops detected so far (also updates self.loops)."""
        out: list[dict] = []

        # NOTE: hypothesis repetition is NOT looped on here — the RANK guard
        # (hypothesis_already_tried) is the single source of truth. Because
        # record_hypothesis only runs after that guard passes, no
        # (signature, strategy) pair can ever be recorded twice, so a
        # per-hypothesis repeat check would be unreachable. The same
        # hypothesis re-ranked under an ESCALATED strategy is an escalation,
        # not a loop, and must be allowed to run (e.g. deep-evidence feeds
        # the attempt history back to the model).
        patch = self._sigs("patches")
        seen = {s: patch.count(s) for s in set(patch)}
        for s, n in seen.items():
            if n >= LOOP_LIMIT:
                out.append({"type": "patch-repeated", "detail": s,
                            "iteration": self.iteration})
        # failures are looped on (signature, strategy): repeating a failure
        # under a NEW strategy is an escalation, not a loop — it must be
        # allowed to proceed.
        pairs = [(x["sig"], x.get("strategy")) for x in self.failures]
        for p in set(pairs):
            if pairs.count(p) >= LOOP_LIMIT:
                out.append({"type": "failure-repeated",
                            "detail": f"{p[0]} under strategy {p[1] or '—'}",
                            "iteration": self.iteration})
        # no new information: the CURRENT strategy keeps failing with a frozen
        # evidence set — the investigation is spinning on the same evidence
        cur = self.strategy
        n_cur = sum(1 for x in self.failures if x.get("strategy") == cur)
        if n_cur >= LOOP_LIMIT and len(self.evidence) <= 1:
            out.append({"type": "no-new-information",
                        "detail": f"{n_cur} failures under `{cur}`, "
                                  f"{len(self.evidence)} evidence set(s)",
                        "iteration": self.iteration})
        for loop in out:
            if loop not in self.loops:
                self.loops.append(loop)
        return out

    # -------------------------------------------------------- guards used
    # by the agent BEFORE re-doing work
    def hypothesis_already_tried(self, h: dict, strategy: str = "") -> bool:
        """This hypothesis was already tried under THIS strategy. The same
        hypothesis under an escalated strategy is a legitimate escalation
        (the agent is trying harder on the same evidence), not a loop."""
        sig = hypothesis_sig(h)
        return any(x["sig"] == sig and x.get("strategy") == strategy
                   for x in self.hypotheses)

    def patch_already_tried(self, patch: dict) -> bool:
        return patch_sig(patch) in self._sigs("patches")

    def same_failure_no_new_evidence(self, f: dict, strategy: str) -> bool:
        """The same failure was already attempted under THIS strategy AND the
        evidence set has not grown — retrying the same strategy on the same
        evidence would be a loop. A strategy change is an escalation, not a
        loop, and must be allowed to run."""
        sig = failure_sig(f)
        n = sum(1 for x in self.failures
                if x["sig"] == sig and x.get("strategy") == strategy)
        return n > 1 and len(self.evidence) <= 1

    # ------------------------------------------------------------- report
    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "iteration": self.iteration,
            "budget": self.budget,
            "strategy": self.strategy,
            "termination": self.termination,
            "loops": self.loops,
            "hypotheses": [
                {k: v for k, v in h.items() if k not in ("sig", "strategy")}
                for h in self.hypotheses],
            "patches": [
                {k: v for k, v in p.items() if k != "sig"} for p in self.patches],
            "failures": [
                {k: v for k, v in f.items() if k not in ("sig", "strategy")}
                for f in self.failures],
            "evidence_sets": len(self.evidence),
        }
