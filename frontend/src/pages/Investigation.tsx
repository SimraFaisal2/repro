import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  AlertTriangle,
  ArrowLeft,
  Beaker,
  Check,
  ChevronDown,
  CircleSlash,
  Copy,
  Download,
  FlaskConical,
  GitBranch,
  Loader2,
  Microscope,
  Search,
  Settings2,
  ShieldCheck,
  Split,
  TestTube2,
  Wand2,
  X,
} from "lucide-react";
import { api } from "../api";
import type { DebugStateMachine, EventPayload, Investigation as Inv, PatchReport, TraceData, TraceFrame } from "../types";
import { STATUS_COLOR, STATUS_LABEL } from "../types";
import { Panel, Spinner } from "../components/Panel";
import TraceView from "../components/TraceView";
import DiffView from "../components/DiffView";
import GraphView from "../components/GraphView";
import ActivityLog from "../components/ActivityLog";
import CodeView from "../components/CodeView";

const PHASES = [
  { key: "analyze", label: "Analyze", icon: Search },
  { key: "deps", label: "Dependencies", icon: Settings2 },
  { key: "tests", label: "Tests", icon: TestTube2 },
  { key: "reproduce", label: "Reproduce", icon: Beaker },
  { key: "investigate", label: "Investigate", icon: Microscope },
  { key: "diagnose", label: "Diagnose", icon: AlertTriangle },
  { key: "patch", label: "Patch", icon: Wand2 },
  { key: "verify", label: "Verify", icon: ShieldCheck },
];

const PHASE_KEYWORDS: Record<string, string[]> = {
  analyze: ["Analyzing repository", "Project:"],
  deps: ["dependencies installed", "no dependency files", "pip install", "venv"],
  tests: ["tests discovered", "Running test suite (baseline)", "Baseline:"],
  reproduce: ["Failure reproduced"],
  investigate: ["Runtime trace captured"],
  diagnose: ["Root cause hypothesis"],
  patch: ["Patch generated", "LLM patch verified"],
  verify: ["fix verified in sandbox", "Full suite green", "Reached 3 autonomous"],
};

function phaseState(msg: string): string | null {
  for (const [phase, kws] of Object.entries(PHASE_KEYWORDS)) {
    for (const kw of kws) if (msg.includes(kw)) return phase;
  }
  return null;
}

export default function Investigation() {
  const { id } = useParams<{ id: string }>();
  const [inv, setInv] = useState<Inv | null>(null);
  const [project, setProject] = useState<any>(null);
  const [liveTrace, setLiveTrace] = useState<TraceData | TraceFrame[] | null>(null);
  const [liveHyp, setLiveHyp] = useState<any>(null);
  const [livePatch, setLivePatch] = useState<any>(null);
  const [liveVer, setLiveVer] = useState<any>(null);
  const [toast, setToast] = useState("");
  const [confirming, setConfirming] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  const refresh = useCallback(async () => {
    if (!id) return;
    const data = await api.getInvestigation(id);
    setInv(data);
    const proj = await fetch(`/api/projects/${data.project_id}`).then((r) => r.json());
    setProject(proj);
  }, [id]);

  useEffect(() => {
    if (!id) return;
    refresh();
    const es = new EventSource(api.eventsUrl(id));
    esRef.current = es;
    es.onmessage = (e) => {
      let payload: EventPayload;
      try {
        payload = JSON.parse(e.data);
      } catch {
        return;
      }
      if (payload.type === "__close__") {
        es.close();
        refresh();
        return;
      }
      if (payload.type === "step") {
        setInv((prev) => (prev ? { ...prev, steps: [...prev.steps, { ts: Date.now() / 1000, message: payload.message!, kind: payload.kind! }] } : prev));
      }
      if (payload.type === "status") setInv((prev) => (prev ? { ...prev, status: payload.status! } : prev));
      if (payload.type === "failure") setInv((prev) => (prev && payload.failure ? { ...prev, failures: [...prev.failures.filter((f) => f.test_id !== payload.failure!.test_id), payload.failure] } : prev));
      if (payload.type === "trace") setLiveTrace(payload.trace || null);
      if (payload.type === "hypothesis") setLiveHyp(payload.hypothesis || null);
      if (payload.type === "patch") setLivePatch(payload.patch || null);
      if (payload.type === "verification") setLiveVer(payload.verification || null);
      if (payload.type === "done") {
        es.close();
        refresh();
      }
    };
    es.onerror = () => {
      /* transient; EventSource reconnects */
    };
    return () => es.close();
  }, [id, refresh]);

  const steps = inv?.steps || [];
  const donePhases = useMemo(() => {
    const set = new Set<string>();
    for (const s of steps) {
      const p = phaseState(s.message);
      if (p) set.add(p);
    }
    return set;
  }, [steps]);

  const status = inv?.status || "created";
  const trace = liveTrace || inv?.summary?._trace || null;
  const traceFrames = Array.isArray(trace) ? trace : trace?.frames || [];
  const traceSlice = !Array.isArray(trace) ? trace?.slice : undefined;
  const hyp = liveHyp || inv?.summary?._hypothesis || null;
  const patch = livePatch || inv?.patches?.[inv.patches.length - 1] || null;
  const verification = liveVer || inv?.verifications?.[inv.verifications.length - 1] || null;
  const debug: DebugStateMachine | null = (inv?.summary as any)?._debug || null;
  const failures = inv?.failures || [];
  const running = ["running", "investigating", "created"].includes(status);
  const failingModule = failures[0]?.file ? failures[0].file.replace(/\\/g, "/").replace(/\.py$/, "").replace(/\//g, ".") : null;

  async function applyFix(confirmed = false) {
    if (!id) return;
    if (!confirmed) {
      setConfirming(true);
      return;
    }
    setConfirming(false);
    const needsApproval = status === "needs-approval";
    if (needsApproval && !window.confirm(
      "This is a HIGH-risk patch. It passed verification but carries elevated " +
      "risk (large scope, unexpected files, or a risky failure class).\n\n" +
      "Apply it to your repository on a git branch anyway?"
    )) {
      return;
    }
    try {
      const res = await api.applyPatch(id, true, needsApproval);
      setToast(`Applied on branch ${res.branch}`);
      refresh();
    } catch (e: any) {
      setToast(`apply failed: ${e.message}`);
    }
  }

  async function verify() {
    if (!id) return;
    try {
      const res = await api.verify(id);
      setToast(`verified: ${res.passed}/${res.total} passed`);
      refresh();
    } catch (e: any) {
      setToast(`verify failed: ${e.message}`);
    }
  }

  async function downloadReport() {
    if (!id) return;
    const text = await api.report(id);
    const blob = new Blob([text], { type: "text/markdown" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `repro-report-${id}.md`;
    a.click();
  }

  const evidence = useMemo(() => {
    const all: any[] = hyp?.evidence || [];
    return {
      observed: all.filter((e: any) => e.kind === "observed"),
      inferred: all.filter((e: any) => e.kind === "inferred"),
    };
  }, [hyp]);

  const firstFailure = failures[0];
  const failureSource = firstFailure?.file && traceFrames.length
    ? (traceFrames.find((t: TraceFrame) => t.file === firstFailure.file)?.source ?? null)
    : null;

  return (
    <div className="space-y-5">
      {toast && (
        <div className="fixed bottom-4 right-4 z-50 flex items-center gap-2 rounded-md border border-accent/40 bg-panel px-4 py-2.5 text-sm shadow-xl">
          {toast}
          <button onClick={() => setToast("")}><X size={13} /></button>
        </div>
      )}

      {/* header */}
      <div className="flex flex-wrap items-center gap-3">
        <Link to="/dashboard" className="text-faint hover:text-ink"><ArrowLeft size={16} /></Link>
        <div className="min-w-0">
          <div className="flex items-center gap-2.5">
            <h1 className="text-lg font-semibold truncate">{project?.name || "investigation"}</h1>
            <span className={`inline-flex items-center gap-1.5 text-[11px] font-medium rounded-full border px-2 py-0.5 ${STATUS_COLOR[status] || STATUS_COLOR.created}`}>
              <span className={`size-1.5 rounded-full bg-current ${running ? "pulse-dot" : ""}`} />
              {STATUS_LABEL[status] || status}
            </span>
            <span className="mono text-[11px] text-faint">#{id}</span>
          </div>
          <div className="text-[11px] text-faint mono mt-0.5">
            {inv?.branch && <span className="text-accent"><GitBranch size={11} className="inline mr-1" />{inv.branch}</span>}
            {project?.overview && (
              <span>
                {project.overview.framework} · {project.overview.test_framework} · {project.overview.files} files
                {inv?.confidence != null && <> · confidence {(inv.confidence * 100).toFixed(0)}%</>}
              </span>
            )}
          </div>
        </div>
        <div className="ml-auto flex items-center gap-2">
          {patch && !inv?.branch && !confirming && (
            <button className="btn-good" onClick={() => applyFix()} disabled={running}>
              <GitBranch size={14} /> Apply Fix
            </button>
          )}
          {confirming && (
            <span className="flex items-center gap-2 text-xs">
              <span className="text-muted">Apply to repository on a git branch?</span>
              <button className="btn-good !py-1" onClick={() => applyFix(true)}>
                <GitBranch size={13} /> Confirm
              </button>
              <button className="btn-ghost !py-1" onClick={() => setConfirming(false)}>Cancel</button>
            </span>
          )}
          <button className="btn-ghost" onClick={verify} disabled={running}>
            <FlaskConical size={14} /> Verify
          </button>
          <button className="btn-ghost" onClick={downloadReport}>
            <Download size={14} /> Report
          </button>
        </div>
      </div>

      {/* investigation timeline */}
      <div className="panel px-4 py-3">
        <div className="flex items-center gap-1 overflow-x-auto">
          {PHASES.map((ph, i) => {
            const Icon = ph.icon;
            const done = donePhases.has(ph.key);
            const isLastDone = ph.key === "verify";
            const active = !done && !donePhases.has(PHASES[i - 1]?.key) && !donePhases.has(ph.key) && (i === 0 || donePhases.has(PHASES[i - 1].key));
            const color = done
              ? "text-good border-good/40 bg-good/10"
              : active
              ? "text-accent border-accent/40 bg-accent/10 pulse-dot"
              : "text-faint border-border bg-panel2/40";
            return (
              <div key={ph.key} className="flex items-center gap-1 shrink-0">
                <span className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-[11px] font-mono ${color}`}>
                  <Icon size={12} /> {ph.label}
                  {done && !isLastDone && <Check size={11} />}
                </span>
                {i < PHASES.length - 1 && <span className="text-faint/50">→</span>}
              </div>
            );
          })}
          {running && (
            <span className="ml-2"><Spinner label="agent working" /></span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-5">
        {/* ------- left / main column ------- */}
        <div className="xl:col-span-7 space-y-5 min-w-0">
          {/* failure card */}
          {firstFailure && (
            <Panel title="Failure detected" bodyClass="p-0">
              <div className="p-4 space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="mono text-[13px] text-bad bg-bad/10 border border-bad/30 rounded px-2 py-0.5">
                    {firstFailure.test_id}
                  </span>
                  <span className="text-[11px] mono text-bad">{firstFailure.error_type}</span>
                  <span className="text-[11px] mono text-faint">
                    {firstFailure.file}:{firstFailure.line}
                  </span>
                </div>
                <p className="text-sm text-ink/90 font-mono">{firstFailure.error_msg}</p>
                <div className="flex flex-wrap gap-2 text-[11px]">
                  <span className={`rounded-full border px-2 py-0.5 ${firstFailure.severity === "HIGH" ? "border-bad/40 text-bad bg-bad/10" : "border-warn/40 text-warn bg-warn/10"}`}>
                    {firstFailure.severity}
                  </span>
                  <span className="rounded-full border border-good/40 text-good bg-good/10">
                    reproduced: ✓ yes
                  </span>
                  <span className="rounded-full border border-border text-muted">
                    attempts: {inv?.attempts ?? 0}
                  </span>
                  {patch?.confidence != null && (
                    <span className="rounded-full border border-accent/40 text-accent bg-accent/10">
                      confidence {(patch.confidence * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
                {firstFailure.stack_trace && (
                  <details className="text-[11.5px]">
                    <summary className="cursor-pointer text-faint hover:text-ink flex items-center gap-1">
                      <ChevronDown size={12} /> stack trace
                    </summary>
                    <pre className="mt-2 overflow-x-auto rounded border border-border bg-bg p-3 text-faint mono">{firstFailure.stack_trace}</pre>
                  </details>
                )}
              </div>
            </Panel>
          )}

          {/* runtime trace */}
          <Panel
            title="Runtime trace"
            right={traceFrames.length ? (
              <span className="mono text-[11px] text-faint">
                {traceFrames.length} frame(s)
                {traceSlice?.frames ? ` · slice ${traceSlice.frames}` : ""}
                {traceSlice?.max_depth != null ? ` · depth ${traceSlice.max_depth}` : ""}
              </span>
            ) : undefined}
          >
            {traceFrames.length ? (
              <TraceView trace={trace} />
            ) : running ? (
              <Spinner label="capturing execution trace…" />
            ) : (
              <p className="text-xs text-faint">No failure to trace.</p>
            )}
          </Panel>

          {/* root cause */}
          <Panel title="Root cause analysis" right={hyp ? <span className="mono text-[11px] text-faint">{hyp.rule}</span> : undefined}>
            {hyp ? (
              <div className="space-y-4">
                <div className="rounded-md border border-bad/30 bg-bad/5 px-3 py-2.5">
                  <div className="text-[11px] uppercase tracking-wide text-bad mb-1">root cause</div>
                  <div className="text-sm text-ink">{hyp.root_cause}</div>
                </div>
                <p className="text-[13px] text-ink/80 leading-relaxed">{hyp.explanation}</p>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-md border border-border bg-panel2/40 p-3">
                    <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-good mb-2">
                      <Check size={11} /> observed evidence
                    </div>
                    <ul className="space-y-1.5">
                      {evidence.observed.map((e: any, i: number) => (
                        <li key={i} className="text-[11.5px] text-ink/70 leading-snug">
                          <span className="text-faint">{e.source}: </span>{e.text}
                        </li>
                      ))}
                      {evidence.observed.length === 0 && <li className="text-[11.5px] text-faint">none</li>}
                    </ul>
                  </div>
                  <div className="rounded-md border border-border bg-panel2/40 p-3">
                    <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-vio mb-2">
                      <Microscope size={11} /> inferred reasoning
                    </div>
                    <ul className="space-y-1.5">
                      {evidence.inferred.map((e: any, i: number) => (
                        <li key={i} className="text-[11.5px] text-ink/70 leading-snug">{e.text}</li>
                      ))}
                      {evidence.inferred.length === 0 && <li className="text-[11.5px] text-faint">none</li>}
                    </ul>
                  </div>
                </div>
                {hyp.related_tests && hyp.related_tests.length > 0 && (
                  <div className="text-[11.5px]">
                    <span className="text-faint">related tests: </span>
                    <span className="mono text-ink/70">{(hyp.related_tests as string[]).join(", ")}</span>
                  </div>
                )}
                {failureSource && (
                  <div>
                    <div className="text-[11px] uppercase tracking-wide text-faint mb-1.5">failing source</div>
                    <div className="rounded-md border border-border overflow-hidden">
                      <CodeView source={failureSource.map((s: any) => s.text).join("\n")} startLine={failureSource[0].line} failingLine={firstFailure.line ?? undefined} />
                    </div>
                  </div>
                )}
              </div>
            ) : running ? (
              <Spinner label="analyzing evidence…" />
            ) : (
              <p className="text-xs text-faint">No hypothesis yet.</p>
            )}
          </Panel>

          {/* proposed fix */}
          <Panel
            title="Proposed fix"
            right={patch && (
              <span className="flex items-center gap-3 mono text-[11px] text-faint">
                <span className={RISK_STYLE[patch.risk?.toUpperCase()] || RISK_STYLE.MEDIUM}>
                  risk: {patch.risk?.toLowerCase()}
                </span>
                {patch.confidence != null && <span>conf: {(patch.confidence * 100).toFixed(0)}%</span>}
                <span>+{patch.lines_added}/-{patch.lines_removed}</span>
              </span>
            )}
          >
            {patch ? (
              <div className="space-y-3">
                {patch.reason && <p className="text-[13px] text-ink/80">{patch.reason}</p>}
                <div className="flex items-center gap-2 text-[11px]">
                  <span className="text-faint mono">{patch.files_changed} file(s) changed</span>
                  {patch.branch && (
                    <span className="mono text-accent"><GitBranch size={11} className="inline mr-1" />{patch.branch}</span>
                  )}
                  {inv?.branch && <span className="text-good">· applied to repo</span>}
                  {!inv?.branch && <span className="text-faint">· verified in sandbox</span>}
                </div>
                <PatchReportView report={patch.report || null} checks={patch.checks || []} />
                <DiffView diff={patch.diff} />
                {status === "needs-approval" && !inv?.branch && (
                  <div className="rounded-md border border-warn/40 bg-warn/10 px-3 py-2.5 text-xs text-warn">
                    This HIGH-risk patch passed verification but requires explicit human
                    approval before it can be applied. Review the diff and safety checks above.
                  </div>
                )}
                {!inv?.branch && !confirming && (
                  <div className="flex gap-2">
                    <button className="btn-good" onClick={() => applyFix()} disabled={running}>
                      <GitBranch size={14} /> Apply Fix
                    </button>
                    <button className="btn-ghost" disabled><X size={14} /> Reject</button>
                  </div>
                )}
                {!inv?.branch && confirming && (
                  <div className="flex items-center gap-2 text-xs">
                    {status === "needs-approval" ? (
                      <span className="text-warn">HIGH-risk override — this applies a patch that requires explicit human approval.</span>
                    ) : (
                      <span className="text-muted">This creates branch <span className="mono text-accent">repro/fix-{id}</span> in the project checkout and commits the fix.</span>
                    )}
                    <button className="btn-good" onClick={() => applyFix(true)}>
                      <GitBranch size={13} /> Confirm apply
                    </button>
                    <button className="btn-ghost" onClick={() => setConfirming(false)}>Cancel</button>
                  </div>
                )}
              </div>
            ) : running ? (
              <Spinner label="generating patch…" />
            ) : (
              <p className="text-xs text-faint">No patch generated.</p>
            )}
          </Panel>

          {/* verification */}
          <Panel title="Verification" right={verification ? <span className={`mono text-[11px] ${verification.passed ? "text-good" : "text-bad"}`}>{verification.passed ? "✓ fix verified" : "still failing"}</span> : undefined}>
            {verification ? (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-md border border-border p-3">
                    <div className="text-[11px] uppercase text-faint mb-1">before fix</div>
                    <div className="mono text-lg">{verification.before?.passed ?? 0} <span className="text-good">passed</span></div>
                    <div className="mono text-sm">{verification.before?.failed ?? 0} <span className="text-bad">failed</span></div>
                  </div>
                  <div className="rounded-md border border-border p-3">
                    <div className="text-[11px] uppercase text-faint mb-1">after fix</div>
                    <div className="mono text-lg">{verification.after?.passed ?? 0} <span className="text-good">passed</span></div>
                    <div className="mono text-sm">{verification.after?.failed ?? 0} <span className="text-bad">failed</span></div>
                  </div>
                </div>
                {verification.full && (
                  <div className="rounded-md border border-border bg-panel2/40 px-3 py-2.5 text-[12px]">
                    <span className="text-faint">full suite: </span>
                    <span className="mono text-good">{verification.full.passed}/{verification.full.total} passed</span>
                    {verification.full.duration != null && <span className="text-faint mono ml-2">({verification.full.duration}s)</span>}
                    {verification.full.failed === 0 && <span className="ml-2 text-good">· no regressions</span>}
                  </div>
                )}
              </div>
            ) : running ? (
              <Spinner label="verifying fix…" />
            ) : (
              <p className="text-xs text-faint">No verification yet.</p>
            )}
          </Panel>
        </div>

        {/* ------- right column ------- */}
        <div className="xl:col-span-5 space-y-5 min-w-0">
          {/* project overview */}
          <Panel title="Project overview" right={project?.overview ? <span className="mono text-[11px] text-faint">{project.overview.language} {project.overview.python_version}</span> : undefined}>
            {project?.overview ? (
              <div className="space-y-3">
                <div className="grid grid-cols-3 gap-2 text-center">
                  <Stat label="files" value={project.overview.files} />
                  <Stat label="tests" value={project.overview.tests_files} />
                  <Stat label="deps" value={project.overview.dependencies_count} />
                </div>
                <div className="flex flex-wrap gap-1.5 text-[11px]">
                  <Chip>{project.overview.framework}</Chip>
                  <Chip>{project.overview.package_manager}</Chip>
                  <Chip>{project.overview.test_framework}</Chip>
                  <Chip>python {project.overview.python_version}</Chip>
                </div>
                <details>
                  <summary className="cursor-pointer text-[11px] text-faint hover:text-ink flex items-center gap-1">
                    <ChevronDown size={12} /> structure
                  </summary>
                  <pre className="mt-2 text-[11px] leading-relaxed text-faint mono overflow-x-auto max-h-64 overflow-y-auto">
                    {(project.overview.tree || []).join("\n")}
                  </pre>
                </details>
              </div>
            ) : (
              <Spinner label="analyzing structure…" />
            )}
          </Panel>

          {/* dependency graph */}
          <Panel title="Dependency graph" right={firstFailure ? <span className="text-[11px] text-bad mono">failure path</span> : undefined}>
            {project?.overview?.graph ? (
              <GraphView graph={project.overview.graph} failingModule={failingModule} />
            ) : (
              <Spinner label="building graph…" />
            )}
          </Panel>

          {/* autonomous debugging state machine */}
          <Panel
            title="Debug state machine"
            right={debug ? (
              <span className="mono text-[11px] text-faint">
                {debug.state} · {debug.iteration}/{debug.budget}
              </span>
            ) : undefined}
          >
            {debug ? (
              <div className="space-y-3">
                <div className="flex flex-wrap items-center gap-2 text-[11px]">
                  <span className={`rounded-full border px-2 py-0.5 mono ${STATE_STYLE[debug.state] || "border-border text-muted"}`}>
                    {debug.state}
                  </span>
                  <span className="rounded-full border border-border text-muted mono px-2 py-0.5">
                    strategy: {debug.strategy}
                  </span>
                  <span className="rounded-full border border-border text-muted mono px-2 py-0.5">
                    iterations: {debug.iteration}/{debug.budget}
                  </span>
                  <span className="rounded-full border border-border text-muted mono px-2 py-0.5">
                    evidence sets: {debug.evidence_sets}
                  </span>
                </div>
                {debug.termination && (
                  <div className="rounded-md border border-bad/30 bg-bad/5 px-3 py-2 text-[11.5px] text-bad">
                    ⛔ {debug.termination}
                  </div>
                )}
                {debug.loops.length > 0 && (
                  <details className="text-[11.5px]">
                    <summary className="cursor-pointer text-warn hover:text-ink flex items-center gap-1">
                      <AlertTriangle size={12} /> {debug.loops.length} loop(s) detected
                    </summary>
                    <ul className="mt-2 space-y-1.5">
                      {debug.loops.map((l, i) => (
                        <li key={i} className="flex items-start gap-1.5">
                          <span className="mono text-warn">{l.type}</span>
                          <span className="text-faint">— {l.detail}</span>
                          <span className="mono text-faint ml-auto shrink-0">iter {l.iteration}</span>
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
                {debug.hypotheses.length > 0 && (
                  <details className="text-[11.5px]">
                    <summary className="cursor-pointer text-faint hover:text-ink flex items-center gap-1">
                      <Microscope size={12} /> hypotheses attempted: {debug.hypotheses.length}
                    </summary>
                    <ul className="mt-2 space-y-1.5">
                      {debug.hypotheses.map((h, i) => (
                        <li key={i} className="flex items-start gap-1.5">
                          <span className={`mono shrink-0 ${h.result === "tried" ? "text-accent" : "text-faint"}`}>{h.result}</span>
                          <span className="text-ink/75">{h.rule}: {h.root_cause}</span>
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
                {debug.patches.length > 0 && (
                  <details className="text-[11.5px]">
                    <summary className="cursor-pointer text-faint hover:text-ink flex items-center gap-1">
                      <Wand2 size={12} /> patches attempted: {debug.patches.length}
                    </summary>
                    <ul className="mt-2 space-y-1.5">
                      {debug.patches.map((p, i) => (
                        <li key={i} className="flex items-start gap-1.5">
                          <span className={`mono shrink-0 ${RESULT_STYLE[p.result] || "text-faint"}`}>{p.result}</span>
                          <span className="text-ink/75">{p.rule}</span>
                          <span className="text-faint ml-auto shrink-0 mono">
                            risk {p.risk} · +{p.lines_added}/-{p.lines_removed}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
                {debug.hypotheses.length === 0 && debug.patches.length === 0 && (
                  <p className="text-xs text-faint">No hypotheses or patches recorded yet.</p>
                )}
              </div>
            ) : running ? (
              <Spinner label="running state machine…" />
            ) : (
              <p className="text-xs text-faint">No state machine data for this investigation.</p>
            )}
          </Panel>

          {/* agent activity */}
          <Panel title="Agent activity" right={running ? <Spinner /> : <span className="mono text-[11px] text-faint">{steps.length} steps</span>}>
            <ActivityLog steps={steps} live={running} />
          </Panel>
        </div>
      </div>
    </div>
  );
}

const RISK_STYLE: Record<string, string> = {
  LOW: "text-good",
  MEDIUM: "text-warn",
  HIGH: "text-bad",
};

const STATE_STYLE: Record<string, string> = {
  observe: "border-accent/40 text-accent bg-accent/10",
  reproduce: "border-accent/40 text-accent bg-accent/10",
  investigate: "border-vio/40 text-vio bg-vio/10",
  hypothesize: "border-vio/40 text-vio bg-vio/10",
  rank: "border-vio/40 text-vio bg-vio/10",
  patch: "border-warn/40 text-warn bg-warn/10",
  verify: "border-warn/40 text-warn bg-warn/10",
  "analyze-failure": "border-bad/40 text-bad bg-bad/10",
  reassess: "border-bad/40 text-bad bg-bad/10",
  "collect-evidence": "border-bad/40 text-bad bg-bad/10",
  success: "border-good/40 text-good bg-good/10",
  terminated: "border-bad/40 text-bad bg-bad/10",
};

const RESULT_STYLE: Record<string, string> = {
  tried: "text-accent",
  "rejected-static": "text-bad",
  unverified: "text-warn",
  rejected: "text-bad",
};

function PatchReportView({ report, checks }: { report: PatchReport | null; checks: any[] }) {
  const allChecks = report?.checks?.length ? report.checks : checks;
  const passed = allChecks.filter((c) => c.status === "pass" || c.status === "skip").length;
  const regress = report?.regression_status === "new-failures";
  return (
    <div className="rounded-md border border-border bg-panel2/40 p-3 space-y-2.5">
      <div className="flex flex-wrap items-center gap-2 text-[11px]">
        <span className={`mono ${regress ? "text-bad" : "text-good"}`}>
          regression: {report?.regression_status || "—"}
        </span>
        <span className="mono text-faint">safety checks {passed}/{allChecks.length}</span>
        {report?.tests_affected && report.tests_affected.length > 0 && (
          <span className="text-faint">
            tests affected: {report.tests_affected.length}
          </span>
        )}
      </div>
      {report && (
        <div className="grid grid-cols-2 gap-2 text-[11px]">
          <div>
            <span className="text-faint">before: </span>
            <span className="mono text-good">{report.tests_before?.passed ?? 0}p</span>
            <span className="mono text-bad">/{report.tests_before?.failed ?? 0}f</span>
          </div>
          <div>
            <span className="text-faint">after: </span>
            <span className="mono text-good">{report.tests_after?.passed ?? 0}p</span>
            <span className="mono text-bad">/{report.tests_after?.failed ?? 0}f</span>
          </div>
        </div>
      )}
      <details className="text-[11px]">
        <summary className="cursor-pointer text-faint hover:text-ink flex items-center gap-1">
          <ChevronDown size={12} /> {allChecks.length} safety checks
        </summary>
        <ul className="mt-2 space-y-1">
          {allChecks.map((c, i) => (
            <li key={c.id || i} className="flex items-start gap-1.5">
              {c.status === "pass" ? (
                <Check size={12} className="mt-0.5 shrink-0 text-good" />
              ) : c.status === "fail" ? (
                <X size={12} className="mt-0.5 shrink-0 text-bad" />
              ) : (
                <CircleSlash size={12} className="mt-0.5 shrink-0 text-faint" />
              )}
              <span className="text-ink/75">{c.name}</span>
              <span className="text-faint">— {c.detail}</span>
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-border bg-panel2/40 py-2">
      <div className="mono text-lg">{value}</div>
      <div className="text-[10px] uppercase tracking-wide text-faint">{label}</div>
    </div>
  );
}

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-full border border-border bg-panel2/60 px-2 py-0.5 text-muted mono">{children}</span>
  );
}
