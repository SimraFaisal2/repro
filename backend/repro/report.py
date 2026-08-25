"""Final investigation report: structured summary + Markdown export."""
from __future__ import annotations

import time


def build_summary(inv: dict, project: dict) -> dict:
    failures = inv.get("failures") or []
    patches = inv.get("patches") or []
    ver = inv.get("verifications") or []
    first_failure = failures[0] if failures else {}
    last_patch = patches[-1] if patches else {}
    last_ver = ver[-1] if ver else {}
    before = last_ver.get("before") or {}
    after = last_ver.get("after") or {}
    # prefer real suite runs (baseline / full) over single-test verifications
    runs = inv.get("test_runs") or []
    baseline = next((r for r in runs if r["stage"] == "baseline"), None)
    full = next((r for r in reversed(runs) if r["stage"] == "full"), None)
    if baseline:
        before = {"passed": baseline["passed"], "failed": baseline["failed"],
                  "total": baseline["total"]}
    if full:
        after = {"passed": full["passed"], "failed": full["failed"],
                 "total": full["total"]}
    status = inv.get("status")
    if status == "fixed":
        status_label = "✓ VERIFIED"
    elif status == "no-failure":
        status_label = "NO FAILURE DETECTED"
    elif status == "needs-approval":
        status_label = "⚠ HIGH-RISK PATCH — AWAITING HUMAN APPROVAL"
    elif status == "failed":
        status_label = "✗ NOT FIXED"
    else:
        status_label = status.upper()
    patch_report = last_patch.get("report") or {}
    checks = patch_report.get("checks") or last_patch.get("checks") or []
    return {
        "repository": (project or {}).get("name", ""),
        "url": (project or {}).get("source_url", ""),
        "failure": first_failure.get("test_id", ""),
        "error": f"{first_failure.get('error_type')}: {first_failure.get('error_msg')}"
                 if first_failure.get("error_type") else "",
        "root_cause": last_patch.get("reason") or first_failure.get("error_msg", ""),
        "file": first_failure.get("file", ""),
        "line": first_failure.get("line"),
        "tests_before": {"passed": before.get("passed", 0), "failed": before.get("failed", 0),
                         "total": before.get("total", 0)},
        "tests_after": {"passed": after.get("passed", 0), "failed": after.get("failed", 0),
                        "total": after.get("total", 0)},
        "attempts": inv.get("attempts", 0),
        "confidence": inv.get("confidence") or last_patch.get("confidence") or 0.0,
        "status": status_label,
        "risk": patch_report.get("risk") or last_patch.get("risk", ""),
        "regression": patch_report.get("regression_status", ""),
        "regression_new": patch_report.get("regression_new", []),
        "checks_total": len(checks),
        "checks_passed": sum(1 for c in checks if c["status"] in ("pass", "skip")),
        "branch": inv.get("branch") or (last_patch or {}).get("branch", ""),
        "diff": last_patch.get("diff", ""),
        "debug": (inv.get("summary") or {}).get("_debug") or {},
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def render_markdown(summary: dict) -> str:
    s = summary
    lines = [
        "╭─────────────────────────────────────────────────────────────╮",
        "│                       REPRO REPORT                          │",
        "╰─────────────────────────────────────────────────────────────╯",
        "",
        f"**Repository:**  {s['repository']}",
        f"**Failure:**     {s['failure']}",
        f"**Root Cause:**  {s['root_cause']}",
        f"**File:**        {s['file']}:{s['line']}" if s.get("file") else "**File:** —",
        f"**Fix:**         {s['root_cause']}",
        "",
        "**Tests:**",
        f"Before: {s['tests_before']['passed']} passed / {s['tests_before']['failed']} failed",
        f"After:  {s['tests_after']['passed']} passed / {s['tests_after']['failed']} failed",
        "",
        f"**Attempts:**   {s['attempts']}",
        f"**Confidence:** {s['confidence']:.0%}" if isinstance(s['confidence'], float) else f"**Confidence:** {s['confidence']}",
        f"**Risk:**       {s.get('risk') or '—'}"
        + (f" · regression: {s['regression']}" if s.get("regression") else ""),
        f"**Checks:**     {s.get('checks_passed', 0)}/{s.get('checks_total', 0)} safety checks passed",
        f"**Status:**     {s['status']}",
        "",
        "---",
        "",
        "## Failure detail",
        "",
        f"`{s['error']}`" if s.get("error") else "",
        "",
        "## Patch",
        "",
        "```diff",
        s.get("diff") or "(no patch generated)",
        "```",
    ]

    debug = s.get("debug") or {}
    if debug:
        lines += [
            "",
            "---",
            "",
            "## Debug state machine",
            "",
            f"State: `{debug.get('state', '—')}` · iteration "
            f"{debug.get('iteration', 0)}/{debug.get('budget', 0)} · "
            f"strategy `{debug.get('strategy', '—')}`"
            + (f" · evidence sets: {debug.get('evidence_sets', 0)}"
               if debug.get("evidence_sets") is not None else ""),
        ]
        if debug.get("termination"):
            lines.append(f"Termination: {debug['termination']}")
        loops = debug.get("loops") or []
        if loops:
            lines += ["", "**Loops detected:**", ""]
            for l in loops:
                lines.append(f"- `{l['type']}` — {str(l.get('detail', ''))[:80]} "
                             f"(iteration {l.get('iteration')})")
        hypotheses = debug.get("hypotheses") or []
        if hypotheses:
            lines += ["", "**Hypotheses attempted (incl. rejected):**", ""]
            for h in hypotheses:
                lines.append(f"- {h.get('rule', '—')} — "
                             f"{(h.get('root_cause') or '')[:100]} → `{h.get('result')}`")
        patches = debug.get("patches") or []
        if patches:
            lines += ["", "**Patches attempted:**", ""]
            for p in patches:
                lines.append(f"- rule `{p.get('rule', '—')}` · risk {p.get('risk', '—')} · "
                             f"+{p.get('lines_added', 0)}/-{p.get('lines_removed', 0)} "
                             f"→ `{p.get('result')}`")
    lines += ["", f"_Generated by REPRO at {s['generated_at']}_"]
    return "\n".join(lines)
