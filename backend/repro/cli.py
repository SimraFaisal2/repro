"""REPRO CLI.

    python -m repro.cli analyze <path-or-url>
    python -m repro.cli investigate <path-or-url>
    python -m repro.cli demo [auth|offbyone|api|sql|auth2]
    python -m repro.cli status <investigation-id>
    python -m repro.cli report <investigation-id>
    python -m repro.cli diff <investigation-id>
    python -m repro.cli verify <investigation-id>
    python -m repro.cli benchmark [--only id1,id2] [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import queue
import sys
import time
from pathlib import Path

from . import agent, db, demo, report, tests
from .config import cfg, ensure_dirs
from . import repo as repo_mod
from .sandbox import Sandbox


def _stream(iid: str, timeout: float = 600.0) -> str:
    """Run the agent thread, printing live events. Returns final status."""
    t = agent.start_agent(iid)
    q = agent.bus.for_inv(iid)
    status = "running"
    start = time.time()
    while t.is_alive() and time.time() - start < timeout:
        try:
            item = q.get(timeout=0.5)
        except queue.Empty:
            continue
        if item is None:
            break
        _print_event(item)
        if item.get("type") == "status":
            status = item["status"]
    while True:
        try:
            item = q.get_nowait()
        except queue.Empty:
            break
        if item is None:
            break
        _print_event(item)
        if item.get("type") == "status":
            status = item["status"]
    return status


def _print_event(item: dict) -> None:
    t = item.get("type")
    if t == "step":
        kind = item.get("kind", "info")
        mark = {"success": "✓", "error": "✗", "warn": "!", "progress": "…"}.get(kind, "·")
        print(f"  {mark} {item['message']}", file=sys.stderr, flush=True)
    elif t == "failure":
        f = item.get("failure", {})
        print(f"\n  FAILURE {f.get('test_id')}\n  {f.get('error_type')}: {f.get('error_msg')}\n"
              f"  {f.get('file')}:{f.get('line')}\n", file=sys.stderr, flush=True)
    elif t == "hypothesis":
        h = item.get("hypothesis", {})
        print(f"  ROOT CAUSE: {h.get('root_cause')} (conf {h.get('confidence', 0):.0%})",
              file=sys.stderr, flush=True)
    elif t == "patch":
        p = item.get("patch", {})
        print(f"  PATCH: {p.get('files_changed')} file(s), +{p.get('lines_added')}/-{p.get('lines_removed')}",
              file=sys.stderr, flush=True)
    elif t == "verification":
        v = item.get("verification", {})
        passed = v.get("passed")
        print(f"  VERIFICATION: {'✓ passes' if passed else '✗ still failing'}",
              file=sys.stderr, flush=True)
    elif t == "done":
        print(f"\n  DONE — status: {item.get('status')}", file=sys.stderr, flush=True)


def _create_project_from_arg(arg: str, name: str | None) -> dict:
    if "://" in arg or arg.startswith("git@"):
        dest = cfg.projects_dir / f"repo-{db.new_id()}"
        repo_mod.clone_repo(arg, dest)
        nm = name or dest.name
        return db.create_project(nm, "url", str(dest), source_url=arg)
    p = Path(arg)
    if not p.exists():
        raise SystemExit(f"path not found: {arg}")
    dest = cfg.projects_dir / f"local-{db.new_id()}"
    repo_mod.copy_dir(p, dest)
    return db.create_project(name or p.name, "local", str(dest), source_url="")


def cmd_analyze(args: argparse.Namespace) -> None:
    proj = _create_project_from_arg(args.path, args.name)
    inv = db.create_investigation(proj["id"])
    print(f"REPRO investigation {inv['id']} — {proj['name']}", file=sys.stderr)
    status = _stream(inv["id"])
    full = db.get_investigation(inv["id"])
    summary = full.get("summary") or {}
    print("\n" + report.render_markdown(summary))
    print(f"\ninvestigation id: {inv['id']}   status: {status}")


def cmd_demo(args: argparse.Namespace) -> None:
    proj = demo.create_demo_project(args.bug)
    inv = db.create_investigation(proj["id"])
    print(f"REPRO demo investigation {inv['id']} — {proj['name']}", file=sys.stderr)
    status = _stream(inv["id"])
    full = db.get_investigation(inv["id"])
    summary = full.get("summary") or {}
    print("\n" + report.render_markdown(summary))
    print(f"\ninvestigation id: {inv['id']}   status: {status}")


def cmd_status(args: argparse.Namespace) -> None:
    inv = db.get_investigation(args.id)
    if not inv:
        raise SystemExit(f"no investigation {args.id}")
    print(f"id:          {inv['id']}")
    print(f"status:      {inv['status']}")
    print(f"attempts:    {inv['attempts']}")
    print(f"confidence:  {inv.get('confidence')}")
    runs = inv.get("test_runs") or []
    for r in runs:
        print(f"  [{r['stage']}] {r['passed']} passed / {r['failed']} failed / {r['total']} total "
              f"({r['duration']}s)")
    failures = inv.get("failures") or []
    for f in failures:
        print(f"  FAILED {f['test_id']} — {f['error_type']}: {f['error_msg'][:100]}")


def cmd_report(args: argparse.Namespace) -> None:
    inv = db.get_investigation(args.id)
    if not inv:
        raise SystemExit(f"no investigation {args.id}")
    proj = db.get_project(inv["project_id"])
    summary = inv.get("summary")
    if not summary:
        summary = report.build_summary(inv, proj)
    print(report.render_markdown(summary))


def cmd_diff(args: argparse.Namespace) -> None:
    inv = db.get_investigation(args.id)
    if not inv:
        raise SystemExit(f"no investigation {args.id}")
    patches = inv.get("patches") or []
    if not patches:
        print("(no patch generated)")
        return
    print(patches[-1].get("diff", ""))


def cmd_benchmark(args: argparse.Namespace) -> None:
    from . import benchmark
    # Dedicated fresh db so the benchmark never pollutes dev data.
    benchmark.prepare_db(args.db or benchmark.DEFAULT_DB)
    data = benchmark.run_benchmark(args.only, timeout=args.timeout)
    print(benchmark.render_markdown(data))
    if args.json:
        Path(args.json).write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}", file=sys.stderr)


def cmd_verify(args: argparse.Namespace) -> None:
    inv = db.get_investigation(args.id)
    if not inv:
        raise SystemExit(f"no investigation {args.id}")
    proj = db.get_project(inv["project_id"])
    sb = Sandbox(f"verify-cli-{args.id}", Path(proj["local_path"]))
    run = tests.run_suite(sb)
    sb.cleanup()
    print(f"total={run['total']} passed={run['passed']} failed={run['failed']} "
          f"skipped={run['skipped']} duration={run['duration']:.1f}s")


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ensure_dirs()
    db.init_db()
    p = argparse.ArgumentParser(prog="repro", description="AI software failure & recovery agent")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("analyze", help="analyze a repository (path or git URL)")
    a.add_argument("path")
    a.add_argument("--name")
    a.set_defaults(fn=cmd_analyze)

    i = sub.add_parser("investigate", help="run the full investigation workflow (alias of analyze)")
    i.add_argument("path")
    i.add_argument("--name")
    i.set_defaults(fn=cmd_analyze)

    d = sub.add_parser("demo", help="run a bundled demo investigation")
    d.add_argument("bug", nargs="?", default="auth",
                   choices=list(demo.DEMOS.keys()) + [f"{k} ({v})" for k, v in demo.DEMOS.items()])
    d.set_defaults(fn=cmd_demo)

    s = sub.add_parser("status", help="show investigation status")
    s.add_argument("id")
    s.set_defaults(fn=cmd_status)

    r = sub.add_parser("report", help="print the final report")
    r.add_argument("id")
    r.set_defaults(fn=cmd_report)

    df = sub.add_parser("diff", help="print the generated diff")
    df.add_argument("id")
    df.set_defaults(fn=cmd_diff)

    v = sub.add_parser("verify", help="re-run the test suite to verify")
    v.add_argument("id")
    v.set_defaults(fn=cmd_verify)

    b = sub.add_parser("benchmark",
                       help="run the bug-corpus benchmark and report fix rates")
    b.add_argument("--only", nargs="*", default=None,
                   help="comma-separated corpus ids to run (default: all)")
    b.add_argument("--json", default=None, help="write machine-readable results")
    b.add_argument("--timeout", type=float, default=300.0, help="seconds per entry")
    b.add_argument("--db", default=None, help="dedicated sqlite db path")
    b.set_defaults(fn=cmd_benchmark)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
